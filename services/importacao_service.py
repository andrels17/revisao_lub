import io
import re

import pandas as pd

from database.connection import get_conn, release_conn
from services import auditoria_service, equipamentos_service, setores_service

COLUNAS_OBRIGATORIAS = ["codigo", "nome"]
COLUNAS_OPCIONAIS = ["tipo", "setor", "km_atual", "horas_atual", "placa", "serie"]

COLUNAS_EQUIVALENTES = {
    "codigo": ["codigo", "cod_equipamento", "codequipamento", "id_equipamento", "equipamento_codigo"],
    "nome": ["nome", "nome_equipamento", "descricao_equipamento", "descricaoequipamento", "equipamento"],
    "tipo": ["tipo", "grupo", "descricao_tipo_equipamento", "descricaotipoequipamento", "tipo_equipamento"],
    "setor": ["setor", "departamento", "descricao_setor", "setor_nome", "descricao"],
    "km_atual": ["km_atual", "hodometro", "hodometro_atual", "odometro", "quilometragem", "kmhr_atual"],
    "horas_atual": ["horas_atual", "horimetro", "horimetro_atual", "horimetroatual"],
    "placa": ["placa"],
    "serie": ["serie", "serial", "chassi", "chassis"],
}


def _slug_coluna(nome: str) -> str:
    nome = str(nome or "").strip().lower()
    nome = re.sub(r"[^a-z0-9]+", "_", nome)
    return nome.strip("_")


def _aplicar_mapeamento_automatico(df: pd.DataFrame):
    colunas_originais = list(df.columns)
    slug_to_original = {_slug_coluna(c): c for c in colunas_originais}
    rename_map = {}
    mapeadas = {}

    for campo, aliases in COLUNAS_EQUIVALENTES.items():
        for alias in aliases:
            original = slug_to_original.get(alias)
            if original:
                rename_map[original] = campo
                mapeadas[campo] = original
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    df.columns = [_slug_coluna(c) for c in df.columns]
    return df, mapeadas


TIPOS_VALIDOS = {
    "caminhão", "trator", "colheitadeira", "pulverizador",
    "implemento", "máquina", "outro",
}

MODO_IGNORAR = "ignorar"
MODO_ATUALIZAR = "atualizar"
MODO_PREENCHER_VAZIOS = "preencher_vazios"


def get_template_csv() -> bytes:
    df = pd.DataFrame(columns=["codigo", "nome", "tipo", "setor", "km_atual", "horas_atual", "placa", "serie"])
    df.loc[0] = {
        "codigo": "EQ001",
        "nome": "Trator John Deere",
        "tipo": "Trator",
        "setor": "Setor Agrícola",
        "km_atual": 0,
        "horas_atual": 1200,
        "placa": "ABC-1234",
        "serie": "JD-2024-001",
    }
    return df.to_csv(index=False).encode("utf-8")


def _parse_numerico(valor, campo: str, linha: int, erros: list) -> float:
    try:
        if pd.isna(valor):
            return 0.0
        return float(valor or 0)
    except (ValueError, TypeError):
        erros.append(f"Linha {linha}: valor inválido em '{campo}' — '{valor}' não é numérico")
        return 0.0


def _normalizar_texto(valor) -> str:
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _carregar_existentes_map() -> dict:
    itens = equipamentos_service.listar()
    return {str(item.get("codigo", "")).strip().upper(): item for item in itens if item.get("codigo")}


def processar_arquivo(file_bytes: bytes, filename: str) -> dict:
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return {"erro": "Formato não suportado. Use CSV ou XLSX."}
    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {e}"}

    df, colunas_mapeadas = _aplicar_mapeamento_automatico(df)

    ausentes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if ausentes:
        detalhe = ""
        if colunas_mapeadas:
            detalhe = " | colunas reconhecidas: " + ", ".join(f"{k}←{v}" for k, v in colunas_mapeadas.items())
        return {"erro": f"Colunas obrigatórias ausentes: {', '.join(ausentes)}{detalhe}"}

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
        tipo = tipo_original.lower()
        setor_txt = _normalizar_texto(row.get("setor"))

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

        if tipo and tipo not in TIPOS_VALIDOS:
            erros.append(
                f"Linha {linha}: tipo '{row.get('tipo')}' desconhecido — use: {', '.join(t.title() for t in sorted(TIPOS_VALIDOS))}"
            )
            status_linha = "erro"

        if setor_txt and setor_txt.lower() not in setores_map:
            setores_nao_encontrados += 1
            avisos.append(f"Linha {linha}: setor '{setor_txt}' não encontrado; será usado setor padrão se informado")
            if status_linha == "nova":
                status_linha = "aviso"
                acao_sugerida = "usar setor padrão"

        preview_rows.append(
            {
                "linha": linha,
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo_original,
                "setor": setor_txt,
                "km_atual": row.get("km_atual", 0),
                "horas_atual": row.get("horas_atual", 0),
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
        "erros": erros,
        "avisos": avisos,
        "linhas_ok": max(0, len(df) - len([r for r in preview_rows if r["status_importacao"] == "erro"])),
        "linhas_erro": len([r for r in preview_rows if r["status_importacao"] == "erro"]),
        "preview": preview.head(15),
        "preview_full": preview,
        "resumo": resumo,
        "colunas_mapeadas": colunas_mapeadas,
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

        try:
            equipamentos_service.criar(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                setor_id=setor_id,
                km_atual=km,
                horas_atual=horas,
            )
            importados += 1
        except Exception as e:
            msg = str(e)
            if "unique" in msg.lower() or "duplicate" in msg.lower():
                if modo_duplicados == MODO_ATUALIZAR:
                    try:
                        _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, preencher_vazios=False)
                        atualizados += 1
                    except Exception as e2:
                        erros.append(f"Linha {linha} ({codigo}): erro ao atualizar — {e2}")
                elif modo_duplicados == MODO_PREENCHER_VAZIOS:
                    try:
                        alterou = _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, preencher_vazios=True)
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



def _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, preencher_vazios=False):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select id::text, nome, tipo, setor_id::text, coalesce(km_atual, 0), coalesce(horas_atual, 0)
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
        if preencher_vazios:
            nome_final = anterior[1] or nome
            tipo_final = anterior[2] or tipo
            setor_final = anterior[3] or setor_id

        cur.execute(
            """
            update equipamentos
               set nome = %s,
                   tipo = %s,
                   setor_id = %s,
                   km_atual = greatest(coalesce(km_atual, 0), %s),
                   horas_atual = greatest(coalesce(horas_atual, 0), %s)
             where codigo = %s
            returning id::text, nome, tipo, setor_id::text, coalesce(km_atual, 0), coalesce(horas_atual, 0)
            """,
            (nome_final, tipo_final, setor_final, km, horas, codigo),
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
            },
            valor_novo={
                "codigo": codigo,
                "nome": atual[1],
                "tipo": atual[2],
                "setor_id": atual[3],
                "km_atual": float(atual[4] or 0),
                "horas_atual": float(atual[5] or 0),
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
            ]
        )
    finally:
        release_conn(conn)
