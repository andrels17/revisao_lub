import io
import unicodedata

import pandas as pd

from database.connection import get_conn, release_conn
from services import auditoria_service, equipamentos_service, setores_service

COLUNAS_OBRIGATORIAS = ["codigo", "nome"]
COLUNAS_OPCIONAIS = ["tipo", "setor", "tipo_horimetro", "km_atual", "horas_atual", "placa", "serie", "ativo"]
COLUNAS_SISTEMA = COLUNAS_OBRIGATORIAS + COLUNAS_OPCIONAIS

TIPOS_VALIDOS = {
    "caminhão", "trator", "colheitadeira", "pulverizador",
    "implemento", "máquina", "outro",
}

MODO_IGNORAR = "ignorar"
MODO_ATUALIZAR = "atualizar"
MODO_PREENCHER_VAZIOS = "preencher_vazios"

SEM_MAPEAMENTO = "__IGNORAR__"

ALIASES_COLUNAS = {
    "codigo": [
        "codigo", "cod_equipamento", "cod equipamento", "equipamento", "id_equipamento",
    ],
    "nome": [
        "nome", "descricao_equipamento", "descrição_equipamento", "equipamento_nome", "descricao",
    ],
    "tipo": [
        "tipo", "descricao_tipoequipamento", "descricaotipoequipamento", "tipo_equipamento", "grupo",
    ],
    "setor": [
        "setor", "departamento", "descricao", "setor_nome", "departamento_nome",
    ],
    "tipo_horimetro": [
        "tipo_horimetro", "tipo_horímetro", "tipo de horimetro", "tipo de horímetro",
        "horimetro_tipo", "horímetro_tipo",
    ],
    "km_atual": [
        "km_atual", "km atual", "hodometro", "hodômetro", "quilometragem", "km_total",
    ],
    "horas_atual": [
        "horas_atual", "horas atual", "horimetro", "horímetro", "horimetro_atual", "horimetro atual",
    ],
    "placa": ["placa"],
    "serie": ["serie", "série", "chassis", "serial"],
    "ativo": ["ativo", "status", "situacao", "situação", "ativo_1"],
}


MAPEAMENTO_TIPO_MEDIDOR = {
    "km": "km",
    "kms": "km",
    "quilometro": "km",
    "quilometros": "km",
    "quilômetro": "km",
    "quilômetros": "km",
    "kilometro": "km",
    "kilometros": "km",
    "hodometro": "km",
    "hodômetro": "km",
    "odometro": "km",
    "odômetro": "km",
    "hora": "horas",
    "horas": "horas",
    "hr": "horas",
    "hrs": "horas",
    "horimetro": "horas",
    "horímetro": "horas",
}


def get_template_csv() -> bytes:
    df = pd.DataFrame(columns=["codigo", "nome", "tipo", "setor", "tipo_horimetro", "km_atual", "horas_atual", "placa", "serie", "ativo"])
    df.loc[0] = {
        "codigo": "EQ001",
        "nome": "Trator John Deere",
        "tipo": "Trator",
        "setor": "Setor Agrícola",
        "tipo_horimetro": "HORAS",
        "km_atual": 0,
        "horas_atual": 1200,
        "placa": "ABC-1234",
        "serie": "JD-2024-001",
        "ativo": "Ativo",
    }
    return df.to_csv(index=False).encode("utf-8")


def _normalizar_nome_coluna(valor: str) -> str:
    texto = str(valor or "").strip().lower().replace("-", "_").replace(" ", "_")
    texto = "".join(
        ch for ch in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(ch)
    )
    while "__" in texto:
        texto = texto.replace("__", "_")
    return texto.strip("_")


def _parse_numerico(valor, campo: str, linha: int, erros: list) -> float:
    try:
        if pd.isna(valor):
            return 0.0
        if isinstance(valor, str):
            valor = valor.strip().replace(".", "").replace(",", ".") if "," in valor else valor.strip()
        return float(valor or 0)
    except (ValueError, TypeError):
        erros.append(f"Linha {linha}: valor inválido em '{campo}' — '{valor}' não é numérico")
        return 0.0


def _normalizar_texto(valor) -> str:
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _normalizar_ativo(valor) -> bool:
    texto = _normalizar_nome_coluna(valor)
    if texto in {"", "1", "s", "sim", "ativo", "true", "t", "yes", "y"}:
        return True
    if texto in {"0", "n", "nao", "não", "inativo", "false", "f", "no"}:
        return False
    return True


def _classificar_tipo_medidor(valor) -> str:
    texto = _normalizar_nome_coluna(valor)
    texto = texto.replace("_", "")
    for chave, destino in MAPEAMENTO_TIPO_MEDIDOR.items():
        chave_norm = _normalizar_nome_coluna(chave).replace("_", "")
        if texto == chave_norm or chave_norm in texto:
            return destino
    return ""


def _aplicar_medicao_compartilhada(df: pd.DataFrame) -> pd.DataFrame:
    if "tipo_horimetro" not in df.columns:
        return df

    tipo_series = df["tipo_horimetro"].apply(_classificar_tipo_medidor)
    tem_km = "km_atual" in df.columns and df["km_atual"].notna().any()
    tem_horas = "horas_atual" in df.columns and df["horas_atual"].notna().any()

    if tem_km and not tem_horas:
        valor_compartilhado = df["km_atual"]
        df.loc[tipo_series == "horas", "horas_atual"] = valor_compartilhado[tipo_series == "horas"]
        df.loc[tipo_series == "horas", "km_atual"] = 0
    elif tem_horas and not tem_km:
        valor_compartilhado = df["horas_atual"]
        df.loc[tipo_series == "km", "km_atual"] = valor_compartilhado[tipo_series == "km"]
        df.loc[tipo_series == "km", "horas_atual"] = 0
    elif tem_km and tem_horas:
        km_vazio = df["km_atual"].isna() | (df["km_atual"].astype(str).str.strip() == "")
        horas_vazio = df["horas_atual"].isna() | (df["horas_atual"].astype(str).str.strip() == "")
        df.loc[(tipo_series == "km") & km_vazio, "km_atual"] = df.loc[(tipo_series == "km") & km_vazio, "horas_atual"]
        df.loc[(tipo_series == "horas") & horas_vazio, "horas_atual"] = df.loc[(tipo_series == "horas") & horas_vazio, "km_atual"]

    return df


def _carregar_existentes_map() -> dict:
    itens = equipamentos_service.listar()
    return {str(item.get("codigo", "")).strip().upper(): item for item in itens if item.get("codigo")}


def ler_arquivo(file_bytes: bytes, filename: str) -> dict:
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return {"erro": "Formato não suportado. Use CSV ou XLSX."}
    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {e}"}

    colunas_originais = [str(c).strip() for c in df.columns]
    return {
        "df_raw": df.copy(),
        "columns": colunas_originais,
        "preview_raw": df.head(20),
    }


def sugerir_mapeamento(columns: list[str]) -> dict:
    norm_to_original = {_normalizar_nome_coluna(col): col for col in columns}
    sugestao = {}
    for campo, aliases in ALIASES_COLUNAS.items():
        escolhido = None
        for alias in aliases:
            alias_norm = _normalizar_nome_coluna(alias)
            if alias_norm in norm_to_original:
                escolhido = norm_to_original[alias_norm]
                break
        sugestao[campo] = escolhido or SEM_MAPEAMENTO
    return sugestao


def aplicar_mapeamento(df_raw: pd.DataFrame, column_mapping: dict | None = None) -> pd.DataFrame:
    mapping = column_mapping or sugerir_mapeamento([str(c) for c in df_raw.columns])
    df = pd.DataFrame()

    for campo in COLUNAS_SISTEMA:
        origem = mapping.get(campo)
        if origem and origem != SEM_MAPEAMENTO and origem in df_raw.columns:
            df[campo] = df_raw[origem]
        else:
            df[campo] = None

    return _aplicar_medicao_compartilhada(df)


def processar_arquivo(file_bytes: bytes, filename: str, column_mapping: dict | None = None) -> dict:
    leitura = ler_arquivo(file_bytes, filename)
    if "erro" in leitura:
        return leitura

    df_raw = leitura["df_raw"]
    df = aplicar_mapeamento(df_raw, column_mapping)

    ausentes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns or df[col].isna().all()]
    if ausentes:
        return {"erro": f"Colunas obrigatórias ausentes ou não mapeadas: {', '.join(ausentes)}"}

    erros = []
    avisos = []
    codigos_arquivo = {}
    existentes_map = _carregar_existentes_map()
    setores_map = {s["nome"].strip().lower(): s["id"] for s in setores_service.listar() if s.get("nome")}

    duplicados_sistema = 0
    setores_nao_encontrados = 0
    preview_rows = []

    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = _normalizar_texto(row.get("codigo"))
        nome = _normalizar_texto(row.get("nome"))
        tipo_original = _normalizar_texto(row.get("tipo"))
        setor_txt = _normalizar_texto(row.get("setor"))
        tipo_medidor = _normalizar_texto(row.get("tipo_horimetro"))

        status_linha = "nova"
        acao_sugerida = "importar"

        if not codigo:
            erros.append(f"Linha {linha}: código vazio")
            status_linha = "erro"
        elif not nome:
            erros.append(f"Linha {linha}: nome vazio")
            status_linha = "erro"

        codigo_upper = codigo.upper()
        if codigo_upper:
            if codigo_upper in codigos_arquivo:
                erros.append(f"Linha {linha}: código duplicado no arquivo ({codigo}) — já apareceu na linha {codigos_arquivo[codigo_upper]}")
                status_linha = "erro"
            else:
                codigos_arquivo[codigo_upper] = linha
            if codigo_upper in existentes_map:
                duplicados_sistema += 1
                avisos.append(f"Linha {linha}: código {codigo} já existe no sistema")
                status_linha = "duplicado"
                acao_sugerida = "revisar duplicado"

        if setor_txt and setor_txt.lower() not in setores_map:
            setores_nao_encontrados += 1
            avisos.append(f"Linha {linha}: setor '{setor_txt}' não encontrado; será usado setor padrão se informado")
            if status_linha == "nova":
                status_linha = "aviso"
                acao_sugerida = "usar setor padrão"

        if tipo_medidor:
            tipo_classificado = _classificar_tipo_medidor(tipo_medidor)
            if not tipo_classificado:
                avisos.append(
                    f"Linha {linha}: TIPO_HORIMETRO '{tipo_medidor}' não foi reconhecido automaticamente. Revise a associação dessa linha."
                )
                if status_linha == "nova":
                    status_linha = "aviso"
            else:
                acao_sugerida = f"popular {tipo_classificado} a partir do medidor"

        horas_raw = row.get("horas_atual")
        if _normalizar_texto(horas_raw) and not pd.api.types.is_number(horas_raw):
            horas_txt = _normalizar_texto(horas_raw).lower()
            if any(token in horas_txt for token in ["km", "quil", "hora", "hori"]):
                avisos.append(
                    f"Linha {linha}: coluna mapeada para horas_atual parece textual ('{horas_raw}'). O sistema importará 0 nesse campo."
                )
                if status_linha == "nova":
                    status_linha = "aviso"

        preview_rows.append(
            {
                "linha": linha,
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo_original,
                "setor": setor_txt,
                "tipo_horimetro": tipo_medidor,
                "km_atual": row.get("km_atual", 0),
                "horas_atual": row.get("horas_atual", 0),
                "placa": row.get("placa", ""),
                "serie": row.get("serie", ""),
                "ativo": row.get("ativo", True),
                "status_importacao": status_linha,
                "acao_sugerida": acao_sugerida,
                "ja_existe": codigo_upper in existentes_map if codigo_upper else False,
            }
        )

    preview = pd.DataFrame(preview_rows)
    resumo = {
        "total_linhas": int(len(df)),
        "novas": int(sum(1 for item in preview_rows if item["status_importacao"] == "nova")),
        "duplicadas_sistema": int(duplicados_sistema),
        "com_erro": int(sum(1 for item in preview_rows if item["status_importacao"] == "erro")),
        "com_aviso": int(sum(1 for item in preview_rows if item["status_importacao"] == "aviso")),
        "setores_nao_encontrados": int(setores_nao_encontrados),
    }

    return {
        "df": df,
        "df_raw": df_raw,
        "mapping": column_mapping or sugerir_mapeamento([str(c) for c in df_raw.columns]),
        "suggested_mapping": sugerir_mapeamento([str(c) for c in df_raw.columns]),
        "available_columns": [str(c) for c in df_raw.columns],
        "erros": erros,
        "avisos": avisos,
        "linhas_ok": max(0, len(df) - len([r for r in preview_rows if r["status_importacao"] == "erro"])),
        "linhas_erro": len([r for r in preview_rows if r["status_importacao"] == "erro"]),
        "preview": preview.head(15),
        "preview_full": preview,
        "preview_raw": df_raw.head(15),
        "resumo": resumo,
    }



def importar(
    df: pd.DataFrame,
    setor_padrao_id=None,
    modo_duplicados: str = MODO_IGNORAR,
    progress_callback=None,
) -> dict:
    setores_map = {s["nome"].lower(): s["id"] for s in setores_service.listar() if s.get("nome")}
    importados = 0
    atualizados = 0
    duplicados = 0
    preenchidos_vazios = 0
    erros = []
    total = len(df)

    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = _normalizar_texto(row.get("codigo"))
        nome = _normalizar_texto(row.get("nome"))
        if not codigo or not nome:
            if progress_callback:
                progress_callback(idx + 1, total, codigo or "—")
            continue

        tipo = _normalizar_texto(row.get("tipo")) or "Outro"
        setor_nome = _normalizar_texto(row.get("setor")).lower()
        setor_id = setores_map.get(setor_nome) or setor_padrao_id

        km = _parse_numerico(row.get("km_atual", 0), "km_atual", linha, erros)
        horas = _parse_numerico(row.get("horas_atual", 0), "horas_atual", linha, erros)
        ativo = _normalizar_ativo(row.get("ativo"))

        try:
            equipamentos_service.criar(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                setor_id=setor_id,
                km_atual=km,
                horas_atual=horas,
                ativo=ativo,
            )
            importados += 1
        except Exception as e:
            msg = str(e)
            if "unique" in msg.lower() or "duplicate" in msg.lower():
                if modo_duplicados == MODO_ATUALIZAR:
                    try:
                        _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, ativo, preencher_vazios=False)
                        atualizados += 1
                    except Exception as e2:
                        erros.append(f"Linha {linha} ({codigo}): erro ao atualizar — {e2}")
                elif modo_duplicados == MODO_PREENCHER_VAZIOS:
                    try:
                        alterou = _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, ativo, preencher_vazios=True)
                        preenchidos_vazios += int(bool(alterou))
                    except Exception as e2:
                        erros.append(f"Linha {linha} ({codigo}): erro ao preencher vazios — {e2}")
                else:
                    duplicados += 1
            else:
                erros.append(f"Linha {linha} ({codigo}): {msg}")

        if progress_callback:
            progress_callback(idx + 1, total, codigo)

    return {
        "importados": importados,
        "atualizados": atualizados,
        "duplicados": duplicados,
        "preenchidos_vazios": preenchidos_vazios,
        "erros": erros,
    }



def _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, ativo, preencher_vazios=False):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select id::text, nome, tipo, setor_id::text, coalesce(km_atual, 0), coalesce(horas_atual, 0), coalesce(ativo, true)
            from equipamentos
            where codigo = %s
            """,
            (codigo,),
        )
        anterior = cur.fetchone()
        if not anterior:
            raise ValueError("equipamento não encontrado para atualização")

        nome_final = nome
        tipo_final = tipo
        setor_final = setor_id
        ativo_final = ativo
        if preencher_vazios:
            nome_final = anterior[1] or nome
            tipo_final = anterior[2] or tipo
            setor_final = anterior[3] or setor_id
            ativo_final = anterior[6] if anterior[6] is not None else ativo

        cur.execute(
            """
            update equipamentos
               set nome = %s,
                   tipo = %s,
                   setor_id = %s,
                   km_atual = greatest(coalesce(km_atual, 0), %s),
                   horas_atual = greatest(coalesce(horas_atual, 0), %s),
                   ativo = %s
             where codigo = %s
            returning id::text, nome, tipo, setor_id::text, coalesce(km_atual, 0), coalesce(horas_atual, 0), coalesce(ativo, true)
            """,
            (nome_final, tipo_final, setor_final, km, horas, ativo_final, codigo),
        )
        atual = cur.fetchone()
        auditoria_service.registrar_no_conn(
            conn,
            acao="importacao_preencher_vazios" if preencher_vazios else "importacao_atualizar_equipamento",
            entidade="equipamentos",
            entidade_id=atual[0],
            valor_antigo={
                "nome": anterior[1],
                "tipo": anterior[2],
                "setor_id": anterior[3],
                "km_atual": float(anterior[4] or 0),
                "horas_atual": float(anterior[5] or 0),
                "ativo": bool(anterior[6]),
            },
            valor_novo={
                "codigo": codigo,
                "nome": atual[1],
                "tipo": atual[2],
                "setor_id": atual[3],
                "km_atual": float(atual[4] or 0),
                "horas_atual": float(atual[5] or 0),
                "ativo": bool(atual[6]),
            },
        )
        conn.commit()
        return any(
            [
                anterior[1] != atual[1],
                anterior[2] != atual[2],
                str(anterior[3] or "") != str(atual[3] or ""),
                float(anterior[4] or 0) != float(atual[4] or 0),
                float(anterior[5] or 0) != float(atual[5] or 0),
                bool(anterior[6]) != bool(atual[6]),
            ]
        )
    finally:
        release_conn(conn)
