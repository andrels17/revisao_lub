import io
from collections import defaultdict

import pandas as pd

from database.connection import get_conn, release_conn
from services import (
    auditoria_service,
    equipamentos_service,
    responsaveis_service,
    setores_service,
    vinculos_service,
)

COLUNAS_OBRIGATORIAS = ["codigo", "nome"]
COLUNAS_OPCIONAIS = [
    "tipo",
    "empresa",
    "unidade",
    "departamento",
    "setor",
    "subsetor",
    "km_atual",
    "horas_atual",
    "placa",
    "serie",
    "responsavel",
    "responsavel_nome",
    "gestor",
    "tipo_horimetro",
]

TIPOS_REFERENCIA = {
    "caminhão", "trator", "colheitadeira", "pulverizador", "implemento", "máquina", "outro"
}

MODO_IGNORAR = "ignorar"
MODO_ATUALIZAR = "atualizar"
MODO_PREENCHER_VAZIOS = "preencher_vazios"

HIERARQUIA_SETORES = [
    ("empresa", "empresa"),
    ("unidade", "unidade"),
    ("departamento", "departamento"),
    ("setor", "setor"),
    ("subsetor", "subsetor"),
]


def get_template_csv() -> bytes:
    df = pd.DataFrame(
        columns=[
            "codigo",
            "nome",
            "tipo",
            "empresa",
            "unidade",
            "departamento",
            "setor",
            "subsetor",
            "km_atual",
            "horas_atual",
            "responsavel",
            "gestor",
            "placa",
            "serie",
        ]
    )
    df.loc[0] = {
        "codigo": "EQ001",
        "nome": "Trator John Deere",
        "tipo": "Trator",
        "empresa": "Matriz",
        "unidade": "Usina Norte",
        "departamento": "Agrícola",
        "setor": "Plantio",
        "subsetor": "Frente A",
        "km_atual": 0,
        "horas_atual": 1200,
        "responsavel": "João Silva",
        "gestor": "Maria Souza",
        "placa": "ABC-1234",
        "serie": "JD-2024-001",
    }
    return df.to_csv(index=False).encode("utf-8")


def _normalizar_coluna(nome: str) -> str:
    return str(nome or "").strip().lower().replace(" ", "_")


def _normalizar_texto(valor) -> str:
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _normalizar_chave(valor) -> str:
    return _normalizar_texto(valor).strip().lower()


def _parse_numerico(valor, campo: str, linha: int, erros: list) -> float:
    try:
        if pd.isna(valor) or valor in (None, ""):
            return 0.0
        if isinstance(valor, str):
            valor = valor.strip().replace(".", "").replace(",", ".") if valor.count(",") == 1 else valor.strip().replace(",", ".")
        return float(valor or 0)
    except (ValueError, TypeError):
        erros.append(f"Linha {linha}: valor inválido em '{campo}' — '{valor}' não é numérico")
        return 0.0


def _carregar_existentes_map() -> dict:
    itens = equipamentos_service.listar()
    return {str(item.get("codigo", "")).strip().upper(): item for item in itens if item.get("codigo")}


def _carregar_setores_map() -> dict:
    itens = setores_service.listar()
    return {
        (_normalizar_chave(item.get("nome")), _normalizar_chave(item.get("tipo_nivel")), str(item.get("setor_pai_id") or "")): item["id"]
        for item in itens
        if item.get("nome")
    }


def _carregar_responsaveis_map() -> dict:
    itens = responsaveis_service.listar()
    return {_normalizar_chave(item.get("nome")): item["id"] for item in itens if item.get("nome")}


def _consolidar_duplicados_arquivo(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if "codigo" not in df.columns:
        return df, []

    df = df.copy()
    df["_linha_origem"] = range(2, len(df) + 2)
    df["_codigo_norm"] = df["codigo"].apply(lambda v: _normalizar_texto(v).upper())

    avisos = []
    duplicados = df[df["_codigo_norm"].ne("")].duplicated(subset=["_codigo_norm"], keep=False)
    if duplicados.any():
        for codigo, grupo in df.loc[duplicados].groupby("_codigo_norm", sort=False):
            linhas = grupo["_linha_origem"].tolist()
            manter = linhas[-1]
            ignoradas = ", ".join(str(x) for x in linhas[:-1])
            avisos.append(
                f"Código {codigo}: {len(linhas)} ocorrência(s) no arquivo; mantida a linha {manter} e consolidadas as linhas {ignoradas}"
            )
        df = df.drop_duplicates(subset=["_codigo_norm"], keep="last")

    return df.drop(columns=["_codigo_norm"]), avisos


def _resolver_medidores(row, linha: int, erros: list) -> tuple[float, float]:
    km = _parse_numerico(row.get("km_atual", 0), "km_atual", linha, erros)
    horas = _parse_numerico(row.get("horas_atual", 0), "horas_atual", linha, erros)

    if "tipo_horimetro" not in row.index:
        return km, horas

    tipo_h = _normalizar_chave(row.get("tipo_horimetro"))
    if not tipo_h:
        return km, horas

    valor_unico = _parse_numerico(row.get("km_atual", 0), "km/hr_atual", linha, erros)
    if any(chave in tipo_h for chave in ["hora", "horimet", "hr"]):
        return 0.0, valor_unico
    if any(chave in tipo_h for chave in ["km", "quil", "hod"]):
        return valor_unico, 0.0
    if "não possui" in tipo_h or "nao possui" in tipo_h:
        return 0.0, 0.0
    return km, horas


def _get_or_create_setor_hierarquia(setores_map: dict, row: pd.Series, contadores: defaultdict) -> int | None:
    pai_id = None
    ultimo_id = None
    for coluna, tipo_nivel in HIERARQUIA_SETORES:
        nome = _normalizar_texto(row.get(coluna))
        if not nome:
            continue
        chave = (_normalizar_chave(nome), tipo_nivel, str(pai_id or ""))
        setor_id = setores_map.get(chave)
        if not setor_id:
            setor_id = setores_service.criar(nome, tipo_nivel=tipo_nivel, setor_pai_id=pai_id, ativo=True)
            setores_map[chave] = setor_id
            contadores[tipo_nivel] += 1
        pai_id = setor_id
        ultimo_id = setor_id
    return ultimo_id


def _get_or_create_responsavel_id(responsaveis_map: dict, nome: str, contadores: defaultdict) -> int | None:
    chave = _normalizar_chave(nome)
    if not chave:
        return None
    responsavel_id = responsaveis_map.get(chave)
    if responsavel_id:
        return responsavel_id
    responsavel_id = responsaveis_service.criar(nome, ativo=True)
    responsaveis_map[chave] = responsavel_id
    contadores["responsaveis"] += 1
    return responsavel_id


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

    df.columns = [_normalizar_coluna(c) for c in df.columns]
    df, avisos_duplicados = _consolidar_duplicados_arquivo(df)

    ausentes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if ausentes:
        return {"erro": f"Colunas obrigatórias ausentes: {', '.join(ausentes)}"}

    erros: list[str] = []
    avisos: list[str] = list(avisos_duplicados)
    existentes_map = _carregar_existentes_map()
    setores_map = _carregar_setores_map()
    responsaveis_map = _carregar_responsaveis_map()

    duplicados_sistema = 0
    novos_niveis = defaultdict(set)
    novos_responsaveis = set()
    preview_rows = []

    for idx, row in df.iterrows():
        linha = int(row.get("_linha_origem", idx + 2))
        codigo = _normalizar_texto(row.get("codigo"))
        nome = _normalizar_texto(row.get("nome"))
        tipo_original = _normalizar_texto(row.get("tipo"))
        status_linha = "nova"
        acao_sugerida = "importar"

        if not codigo:
            erros.append(f"Linha {linha}: código vazio")
            status_linha = "erro"
        elif not nome:
            erros.append(f"Linha {linha}: nome vazio")
            status_linha = "erro"

        codigo_upper = codigo.upper()
        if codigo_upper in existentes_map:
            duplicados_sistema += 1
            avisos.append(f"Linha {linha}: código {codigo} já existe no sistema")
            status_linha = "duplicado"
            acao_sugerida = "revisar duplicado"

        tipo_ref = _normalizar_chave(tipo_original)
        if tipo_ref and tipo_ref not in TIPOS_REFERENCIA and status_linha != "erro":
            status_linha = "aviso"
            acao_sugerida = "importar tipo livre"

        for coluna, tipo_nivel in HIERARQUIA_SETORES:
            valor = _normalizar_texto(row.get(coluna))
            if valor:
                chave = (_normalizar_chave(valor), tipo_nivel)
                existe = any(k[0] == chave[0] and k[1] == chave[1] for k in setores_map.keys())
                if not existe:
                    novos_niveis[tipo_nivel].add(valor)
                    if status_linha == "nova":
                        status_linha = "aviso"
                        acao_sugerida = "criar estrutura automaticamente"

        responsavel_nome = _normalizar_texto(row.get("responsavel") or row.get("responsavel_nome"))
        gestor_nome = _normalizar_texto(row.get("gestor"))
        if responsavel_nome and _normalizar_chave(responsavel_nome) not in responsaveis_map:
            novos_responsaveis.add(responsavel_nome)
            if status_linha == "nova":
                status_linha = "aviso"
                acao_sugerida = "criar responsável automaticamente"
        if gestor_nome and _normalizar_chave(gestor_nome) not in responsaveis_map:
            novos_responsaveis.add(gestor_nome)
            if status_linha == "nova":
                status_linha = "aviso"
                acao_sugerida = "criar gestor automaticamente"

        km_preview, horas_preview = _resolver_medidores(row, linha, erros)
        preview_rows.append(
            {
                "linha": linha,
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo_original,
                "empresa": _normalizar_texto(row.get("empresa")),
                "unidade": _normalizar_texto(row.get("unidade")),
                "departamento": _normalizar_texto(row.get("departamento")),
                "setor": _normalizar_texto(row.get("setor")),
                "subsetor": _normalizar_texto(row.get("subsetor")),
                "responsavel": responsavel_nome,
                "gestor": gestor_nome,
                "km_atual": km_preview,
                "horas_atual": horas_preview,
                "status_importacao": status_linha,
                "acao_sugerida": acao_sugerida,
                "ja_existe": codigo_upper in existentes_map if codigo_upper else False,
            }
        )

    resumo = {
        "total_linhas": int(len(df)),
        "novas": int(sum(1 for item in preview_rows if item["status_importacao"] == "nova")),
        "duplicadas_sistema": int(duplicados_sistema),
        "com_erro": int(sum(1 for item in preview_rows if item["status_importacao"] == "erro")),
        "com_aviso": int(sum(1 for item in preview_rows if item["status_importacao"] == "aviso")),
        "novos_setores": len(novos_niveis["setor"]),
        "novos_departamentos": len(novos_niveis["departamento"]),
        "novas_empresas": len(novos_niveis["empresa"]),
        "novas_unidades": len(novos_niveis["unidade"]),
        "novos_subsetores": len(novos_niveis["subsetor"]),
        "novos_responsaveis": len(novos_responsaveis),
    }

    for tipo_nivel in ["empresa", "unidade", "departamento", "setor", "subsetor"]:
        nomes = sorted(novos_niveis[tipo_nivel], key=str.lower)
        if nomes:
            avisos.insert(
                0,
                f"{len(nomes)} {tipo_nivel}(s) serão criado(s) automaticamente: {', '.join(nomes[:10])}" + (" ..." if len(nomes) > 10 else ""),
            )
    if novos_responsaveis:
        nomes = sorted(novos_responsaveis, key=str.lower)
        avisos.insert(
            0,
            f"{len(nomes)} responsável(is) serão criado(s) automaticamente: {', '.join(nomes[:10])}" + (" ..." if len(nomes) > 10 else ""),
        )

    preview = pd.DataFrame(preview_rows)
    linhas_erro = len([r for r in preview_rows if r["status_importacao"] == "erro"])
    return {
        "df": df.drop(columns=[c for c in ["_linha_origem"] if c in df.columns]),
        "erros": erros,
        "avisos": avisos,
        "linhas_ok": max(0, len(df) - linhas_erro),
        "linhas_erro": linhas_erro,
        "preview": preview.head(15),
        "preview_full": preview,
        "resumo": resumo,
    }


def importar(df: pd.DataFrame, setor_padrao_id=None, modo_duplicados: str = MODO_IGNORAR, progress_callback=None) -> dict:
    setores_map = _carregar_setores_map()
    responsaveis_map = _carregar_responsaveis_map()
    importados = 0
    atualizados = 0
    duplicados = 0
    preenchidos_vazios = 0
    erros = []
    total = len(df)
    criados = defaultdict(int)

    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = _normalizar_texto(row.get("codigo"))
        nome = _normalizar_texto(row.get("nome"))
        if not codigo or not nome:
            if progress_callback:
                progress_callback(idx + 1, total, codigo or "—")
            continue

        tipo = _normalizar_texto(row.get("tipo")) or "Outro"
        setor_id = _get_or_create_setor_hierarquia(setores_map, row, criados)
        if not setor_id:
            setor_id = setor_padrao_id

        km, horas = _resolver_medidores(row, linha, erros)
        responsavel_id = _get_or_create_responsavel_id(
            responsaveis_map,
            _normalizar_texto(row.get("responsavel") or row.get("responsavel_nome")),
            criados,
        )
        gestor_id = _get_or_create_responsavel_id(
            responsaveis_map,
            _normalizar_texto(row.get("gestor")),
            criados,
        )

        try:
            equipamento_id = equipamentos_service.criar(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                setor_id=setor_id,
                km_atual=km,
                horas_atual=horas,
            )
            _vincular_responsaveis(equipamento_id, setor_id, responsavel_id, gestor_id, erros, linha, codigo)
            importados += 1
        except Exception as e:
            msg = str(e)
            if "unique" in msg.lower() or "duplicate" in msg.lower() or "já existe" in msg.lower():
                if modo_duplicados == MODO_ATUALIZAR:
                    try:
                        equipamento_id = _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, preencher_vazios=False)
                        _vincular_responsaveis(equipamento_id, setor_id, responsavel_id, gestor_id, erros, linha, codigo)
                        atualizados += 1
                    except Exception as e2:
                        erros.append(f"Linha {linha} ({codigo}): erro ao atualizar — {e2}")
                elif modo_duplicados == MODO_PREENCHER_VAZIOS:
                    try:
                        equipamento_id, alterou = _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas, preencher_vazios=True)
                        _vincular_responsaveis(equipamento_id, setor_id, responsavel_id, gestor_id, erros, linha, codigo)
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
        "empresas_criadas": criados["empresa"],
        "unidades_criadas": criados["unidade"],
        "departamentos_criados": criados["departamento"],
        "setores_criados": criados["setor"],
        "subsetores_criados": criados["subsetor"],
        "responsaveis_criados": criados["responsaveis"],
        "erros": erros,
    }


def _vincular_responsaveis(equipamento_id, setor_id, responsavel_id, gestor_id, erros, linha, codigo):
    if responsavel_id:
        try:
            vinculos_service.criar_vinculo_equipamento(
                equipamento_id=equipamento_id,
                responsavel_id=responsavel_id,
                tipo_vinculo="operacional",
                principal=True,
            )
        except Exception as exc:
            erros.append(f"Linha {linha} ({codigo}): não foi possível vincular responsável operacional — {exc}")
    if gestor_id and setor_id:
        try:
            vinculos_service.criar_vinculo_setor(
                setor_id=setor_id,
                responsavel_id=gestor_id,
                tipo_responsabilidade="gestor",
                principal=True,
            )
        except Exception as exc:
            erros.append(f"Linha {linha} ({codigo}): não foi possível vincular gestor ao setor — {exc}")



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
        alterou = any(
            [
                anterior[1] != atual[1],
                anterior[2] != atual[2],
                str(anterior[3] or "") != str(atual[3] or ""),
                float(anterior[4] or 0) != float(atual[4] or 0),
                float(anterior[5] or 0) != float(atual[5] or 0),
            ]
        )
        return atual[0], alterou
    finally:
        release_conn(conn)
