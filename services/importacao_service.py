from __future__ import annotations

from io import BytesIO
from typing import Any
import math
import re
import unicodedata

import pandas as pd

from database.connection import get_conn, release_conn
from services import auditoria_service, equipamentos_service

MODO_IGNORAR = "ignorar"
MODO_SOBRESCREVER = "sobrescrever"
MODO_ATUALIZAR = "atualizar"
MODO_BLOQUEAR = "bloquear"
MODO_PREENCHER_VAZIOS = "preencher_vazios"

_MAX_BIGINT = 9223372036854775807
_PROGRESS_STEP = 25

ALIASES = {
    "codigo": ["cod_equipamento", "codigo", "id", "cod", "codigo_equipamento"],
    "nome": ["descricao_equipamento", "nome", "descricao_nome", "descricao_equip"],
    "tipo": ["descricaotipoequipamento", "tipo", "tipo_equipamento", "grupo", "categoria"],
    "setor": ["setor", "departamento", "descricao_setor", "setor_nome"],
    "tipo_horimetro": ["tipo_horimetro", "tipo_medidor", "medidor_tipo"],
    "valor_medidor": ["valor_medidor", "medidor_atual"],
    "km_atual": ["km_atual", "hodometro", "hodometro_atual", "km"],
    "horas_atual": ["horas_atual", "horimetro", "horimetro_atual", "horas"],
    "placa": ["placa"],
    "serie": ["serie", "numero_serie", "n_serie"],
}

CAMPOS_PREVIEW = ["codigo", "nome", "tipo", "setor", "km_atual", "horas_atual", "placa", "serie"]


def get_template_csv() -> bytes:
    df = pd.DataFrame(
        [
            {
                "codigo": "EQ-001",
                "nome": "Equipamento Exemplo",
                "tipo": "Caminhão",
                "setor": "Operação > Caminhões",
                "km_atual": 12500,
                "horas_atual": "",
                "placa": "ABC1D23",
                "serie": "SER-001",
            }
        ]
    )
    return df.to_csv(index=False).encode("utf-8-sig")


def _to_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _normalizar_codigo(value: Any) -> str:
    s = _to_str(value)
    if not s:
        return ""
    try:
        f = float(s.replace(",", "."))
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return s


def _parse_num(value: Any):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".") if "," in s else s
    try:
        return float(s)
    except Exception:
        return None


def _sanitize_meter(value: Any, campo: str) -> int | None:
    n = _parse_num(value)
    if n is None:
        return None
    if isinstance(n, float) and (math.isnan(n) or math.isinf(n)):
        raise ValueError(f"{campo} inválido")
    if n < 0:
        raise ValueError(f"{campo} não pode ser negativo")
    n_int = int(n)
    if n_int > _MAX_BIGINT:
        raise ValueError(f"{campo} excede o limite aceito pelo banco")
    return n_int


def _normalizar_nome(texto: Any) -> str:
    s = _to_str(texto).lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _split_hierarquia_setor(valor: Any) -> list[str]:
    bruto = _to_str(valor)
    if not bruto:
        return []
    partes = re.split(r"\s*(?:>|/|\\|\|)\s*", bruto)
    return [_to_str(p) for p in partes if _to_str(p)]


def normalizar_colunas(df: pd.DataFrame):
    df = df.copy()
    original_cols = list(df.columns)
    df.columns = [str(c).strip().lower() for c in df.columns]

    rename_map = {}
    reconhecidas = {}
    usados = set()
    for campo, possiveis in ALIASES.items():
        for col in df.columns:
            if col in usados:
                continue
            if col == campo or col in possiveis:
                rename_map[col] = campo
                reconhecidas[campo] = original_cols[df.columns.get_loc(col)]
                usados.add(col)
                break

    df = df.rename(columns=rename_map)
    return df, reconhecidas


def validar_colunas(df: pd.DataFrame):
    obrigatorias = ["codigo", "nome"]
    faltantes = [c for c in obrigatorias if c not in df.columns]
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")


def normalizar_tipo(tipo_original: Any) -> str:
    if pd.isna(tipo_original) or str(tipo_original).strip() == "":
        return "Veículos Leves"

    t = str(tipo_original).strip().upper()
    if "CAMINH" in t:
        return "Caminhão"
    if "TRATOR" in t:
        return "Trator"
    if "COLHEIT" in t or "COLHEDOR" in t:
        return "Colheitadeira"
    if "PULVER" in t:
        return "Pulverizador"
    if any(k in t for k in ["IMPLEMENTO", "REBOQUE", "GRADE", "SULCADOR", "SUBSOLADOR", "PIPA", "JULIETA", "TANQUE"]):
        return "Implemento"
    if any(k in t for k in ["CARREGADEIRA", "MAQUINA", "MÁQUINA", "EMPILHADEIRA", "GERADOR", "ELETROBOMBA", "PIVOT", "PIVÔ", "TURBOMAQ"]):
        return "Máquina"
    if any(k in t for k in ["MOTO", "AUTO", "CARRO", "DRONE", "AVIAO", "AVIÃO", "UTILITARIO", "UTILITÁRIO", "CAMIONETE", "PASSEIO"]):
        return "Veículos Leves"
    return str(tipo_original).strip().title()


def separar_medidor(df: pd.DataFrame):
    if "tipo_horimetro" not in df.columns or "valor_medidor" not in df.columns:
        return df
    df = df.copy()
    if "km_atual" not in df.columns:
        df["km_atual"] = None
    if "horas_atual" not in df.columns:
        df["horas_atual"] = None
    for i, row in df.iterrows():
        tipo = str(row.get("tipo_horimetro", "")).strip().upper()
        valor = _parse_num(row.get("valor_medidor"))
        if valor is None:
            continue
        if any(k in tipo for k in ["KM", "QUILOMETRO", "QUILÔMETRO"]):
            if pd.isna(row.get("km_atual")) or _parse_num(row.get("km_atual")) is None:
                df.at[i, "km_atual"] = valor
        elif "HORA" in tipo:
            if pd.isna(row.get("horas_atual")) or _parse_num(row.get("horas_atual")) is None:
                df.at[i, "horas_atual"] = valor
    return df


def consolidar_duplicados(df: pd.DataFrame):
    if "codigo" not in df.columns:
        return df, []
    df = df.copy()
    df["codigo"] = df["codigo"].apply(_normalizar_codigo)
    duplicados = df[df.duplicated(subset=["codigo"], keep=False)]["codigo"].dropna().astype(str).unique().tolist()
    df["_ordem_importacao"] = range(len(df))
    df = df.sort_values("_ordem_importacao").drop_duplicates(subset=["codigo"], keep="last").drop(columns=["_ordem_importacao"])
    return df, duplicados


def _carregar_bytes(file_bytes: bytes, nome_arquivo: str) -> pd.DataFrame:
    if str(nome_arquivo).lower().endswith(".csv"):
        for enc in ("utf-8-sig", "utf-8", "latin1"):
            try:
                return pd.read_csv(BytesIO(file_bytes), encoding=enc)
            except Exception:
                continue
        raise ValueError("Não foi possível ler o CSV enviado.")
    return pd.read_excel(BytesIO(file_bytes))


def _setores_index(cur=None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    own_conn = None
    if cur is None:
        own_conn = get_conn()
        cur = own_conn.cursor()
    try:
        cur.execute("select id, nome, setor_pai_id, tipo_nivel from setores where coalesce(ativo, true) = true")
        rows = cur.fetchall()
        idx = {}
        nomes = []
        for sid, nome, setor_pai_id, tipo_nivel in rows:
            if not nome:
                continue
            nomes.append(_to_str(nome))
            idx[_normalizar_nome(nome)] = {
                "id": sid,
                "nome": _to_str(nome),
                "setor_pai_id": setor_pai_id,
                "tipo_nivel": _to_str(tipo_nivel) or "setor",
            }
        return idx, nomes
    finally:
        if own_conn is not None:
            release_conn(own_conn)


def _equipamentos_existentes(cur=None) -> dict[str, dict[str, Any]]:
    own_conn = None
    if cur is None:
        own_conn = get_conn()
        cur = own_conn.cursor()
    try:
        cur.execute(
            """
            select id, codigo, nome, tipo, setor_id,
                   km_atual, horas_atual, placa, serie
              from equipamentos
            """
        )
        rows = cur.fetchall()
        return {
            _normalizar_codigo(r[1]): {
                "id": r[0],
                "codigo": r[1],
                "nome": r[2],
                "tipo": r[3],
                "setor_id": r[4],
                "km_atual": float(r[5] or 0),
                "horas_atual": float(r[6] or 0),
                "placa": _to_str(r[7]),
                "serie": _to_str(r[8]),
            }
            for r in rows if r and r[1] is not None
        }
    finally:
        if own_conn is not None:
            release_conn(own_conn)


def _resolver_setor_existente(setores_idx: dict[str, dict[str, Any]], setor_nome: str):
    chave = _normalizar_nome(setor_nome)
    if not chave:
        return None
    exato = setores_idx.get(chave)
    if exato:
        return exato
    for nome_norm, item in setores_idx.items():
        if nome_norm == chave or nome_norm in chave or chave in nome_norm:
            return item
    return None


def _criar_setor_no_conn(cur, conn, nome: str, setor_pai_id=None, tipo_nivel: str = "setor"):
    cur.execute(
        """
        insert into setores (nome, tipo_nivel, setor_pai_id, ativo)
        values (%s, %s, %s, %s)
        returning id
        """,
        (nome, tipo_nivel, setor_pai_id, True),
    )
    novo_id = cur.fetchone()[0]
    auditoria_service.registrar_no_conn(
        conn,
        acao="importacao_criar_setor",
        entidade="setores",
        entidade_id=novo_id,
        valor_antigo=None,
        valor_novo={
            "nome": nome,
            "tipo_nivel": tipo_nivel,
            "setor_pai_id": setor_pai_id,
            "origem": "importacao_equipamentos",
        },
    )
    return novo_id


def _obter_ou_criar_setor(cur, conn, setores_idx: dict[str, dict[str, Any]], caminho_setor: str):
    partes = _split_hierarquia_setor(caminho_setor)
    if not partes:
        return None, [], caminho_setor

    setor_pai_id = None
    criados = []
    ultimo_id = None

    for pos, nome in enumerate(partes):
        normalizado = _normalizar_nome(nome)
        item_existente = setores_idx.get(normalizado)

        if item_existente and (not setor_pai_id or item_existente.get("setor_pai_id") == setor_pai_id):
            ultimo_id = item_existente["id"]
            setor_pai_id = ultimo_id
            continue

        resolvido = None
        for _, item in setores_idx.items():
            if item.get("setor_pai_id") == setor_pai_id and _normalizar_nome(item.get("nome")) == normalizado:
                resolvido = item
                break

        if resolvido:
            ultimo_id = resolvido["id"]
            setor_pai_id = ultimo_id
            continue

        tipo_nivel = "departamento" if pos == 0 and len(partes) > 1 else "setor"
        novo_id = _criar_setor_no_conn(cur, conn, nome, setor_pai_id=setor_pai_id, tipo_nivel=tipo_nivel)
        item = {
            "id": novo_id,
            "nome": nome,
            "setor_pai_id": setor_pai_id,
            "tipo_nivel": tipo_nivel,
        }
        setores_idx[normalizado] = item
        criados.append({"id": novo_id, "nome": nome, "caminho_original": caminho_setor})
        ultimo_id = novo_id
        setor_pai_id = novo_id

    return ultimo_id, criados, " > ".join(partes)


def processar_arquivo(file_bytes: bytes, nome_arquivo: str) -> dict[str, Any]:
    try:
        bruto = _carregar_bytes(file_bytes, nome_arquivo)
        df, reconhecidas = normalizar_colunas(bruto)
        validar_colunas(df)

        for col in CAMPOS_PREVIEW:
            if col not in df.columns:
                df[col] = None

        df["codigo"] = df["codigo"].apply(_normalizar_codigo)
        df["nome"] = df["nome"].apply(_to_str)
        df["tipo"] = df["tipo"].apply(normalizar_tipo)
        df = separar_medidor(df)
        df["km_atual"] = df["km_atual"].apply(lambda v: _sanitize_meter(v, "km_atual") if _parse_num(v) is not None else None)
        df["horas_atual"] = df["horas_atual"].apply(lambda v: _sanitize_meter(v, "horas_atual") if _parse_num(v) is not None else None)
        df["setor"] = df["setor"].apply(_to_str)
        df["placa"] = df["placa"].apply(_to_str)
        df["serie"] = df["serie"].apply(_to_str)

        df, duplicados_arquivo = consolidar_duplicados(df)
        df = df.reset_index(drop=True)

        setores_idx, _ = _setores_index()
        existentes = _equipamentos_existentes()

        erros = []
        avisos = []
        linhas_validas = []
        preview_rows = []
        novas = duplicadas_sistema = com_aviso = com_erro = 0
        setores_a_criar = []
        setores_a_criar_set = set()

        if duplicados_arquivo:
            avisos.append(
                "Códigos duplicados no arquivo foram consolidados pela última ocorrência: "
                + ", ".join(sorted(map(str, duplicados_arquivo))[:20])
            )

        for idx, row in df.iterrows():
            codigo = _normalizar_codigo(row.get("codigo"))
            nome = _to_str(row.get("nome"))
            tipo = normalizar_tipo(row.get("tipo"))
            setor_nome = _to_str(row.get("setor"))
            placa = _to_str(row.get("placa"))
            serie = _to_str(row.get("serie"))

            linha_erros = []
            linha_avisos = []
            setor_id = None
            setor_resolvido = ""
            acao_setor = "sem setor"

            try:
                km_atual = _sanitize_meter(row.get("km_atual"), "km_atual")
            except Exception as e:
                km_atual = None
                linha_erros.append(str(e))

            try:
                horas_atual = _sanitize_meter(row.get("horas_atual"), "horas_atual")
            except Exception as e:
                horas_atual = None
                linha_erros.append(str(e))

            if not codigo:
                linha_erros.append("codigo vazio")
            if not nome:
                linha_erros.append("nome vazio")

            if setor_nome:
                existente_setor = _resolver_setor_existente(setores_idx, setor_nome)
                if existente_setor:
                    setor_id = existente_setor["id"]
                    setor_resolvido = existente_setor["nome"]
                    acao_setor = "usar existente"
                else:
                    partes = _split_hierarquia_setor(setor_nome)
                    setor_resolvido = " > ".join(partes) if partes else setor_nome
                    acao_setor = "criar automaticamente"
                    chave_preview = _normalizar_nome(setor_resolvido)
                    if chave_preview and chave_preview not in setores_a_criar_set:
                        setores_a_criar_set.add(chave_preview)
                        setores_a_criar.append({"nome": partes[-1] if partes else setor_nome, "caminho_original": setor_resolvido})
                    linha_avisos.append(f"setor '{setor_nome}' será criado automaticamente")

            existente = existentes.get(codigo)
            acao_prevista = "atualizar" if existente else "novo"
            if existente:
                duplicadas_sistema += 1
            else:
                novas += 1

            if linha_erros:
                com_erro += 1
                erros.append(f"Linha {idx + 2}: {'; '.join(linha_erros)}")
            else:
                linhas_validas.append(
                    {
                        "codigo": codigo,
                        "nome": nome,
                        "tipo": tipo,
                        "setor": setor_nome,
                        "setor_id": setor_id,
                        "setor_resolvido": setor_resolvido,
                        "km_atual": km_atual,
                        "horas_atual": horas_atual,
                        "placa": placa,
                        "serie": serie,
                        "acao_prevista": acao_prevista,
                        "acao_setor": acao_setor,
                    }
                )

            if linha_avisos:
                com_aviso += 1
                avisos.append(f"Linha {idx + 2}: {'; '.join(linha_avisos)}")

            preview_rows.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "tipo": tipo,
                    "setor": setor_nome,
                    "setor_resolvido": setor_resolvido,
                    "ação_setor": acao_setor,
                    "km_atual": km_atual,
                    "horas_atual": horas_atual,
                    "placa": placa,
                    "serie": serie,
                    "ação": acao_prevista,
                    "status": "erro" if linha_erros else ("aviso" if linha_avisos else "ok"),
                }
            )

        df_ok = pd.DataFrame(linhas_validas)
        preview_full = pd.DataFrame(preview_rows)

        return {
            "df": df_ok,
            "preview_full": preview_full,
            "erros": erros,
            "avisos": avisos,
            "linhas_ok": len(df_ok),
            "linhas_erro": com_erro,
            "colunas_reconhecidas": reconhecidas,
            "setores_a_criar": setores_a_criar,
            "resumo": {
                "total_linhas": len(df),
                "novas": novas,
                "duplicadas_sistema": duplicadas_sistema,
                "com_aviso": com_aviso,
                "com_erro": com_erro,
                "setores_novos": len(setores_a_criar),
            },
            "detalhe": ", ".join(sorted({a for vals in ALIASES.values() for a in vals})),
        }
    except Exception as e:
        return {
            "erro": str(e),
            "detalhe": ", ".join(sorted({a for vals in ALIASES.values() for a in vals})),
        }


def _colunas_tabela(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        select column_name
          from information_schema.columns
         where table_schema = 'public'
           and table_name = %s
        """,
        (table_name,),
    )
    return {str(r[0]) for r in cur.fetchall()}


def _atualizar_existente(cur, conn, colunas, existente: dict[str, Any], row: dict[str, Any], modo: str) -> bool:
    updates = []
    params = []

    def add(campo_db: str, valor: Any):
        updates.append(f"{campo_db} = %s")
        params.append(valor)

    setor_id = row.get("setor_id")

    if modo == MODO_ATUALIZAR:
        if row.get("nome") and row.get("nome") != _to_str(existente.get("nome")):
            add("nome", row.get("nome"))
        if "tipo" in colunas and row.get("tipo") and row.get("tipo") != _to_str(existente.get("tipo")):
            add("tipo", row.get("tipo"))
        if setor_id is not None and "setor_id" in colunas and setor_id != existente.get("setor_id"):
            add("setor_id", setor_id)
        if row.get("km_atual") is not None and "km_atual" in colunas and float(row.get("km_atual") or 0) != float(existente.get("km_atual") or 0):
            add("km_atual", row.get("km_atual"))
        if row.get("horas_atual") is not None and "horas_atual" in colunas and float(row.get("horas_atual") or 0) != float(existente.get("horas_atual") or 0):
            add("horas_atual", row.get("horas_atual"))
        if row.get("placa") and "placa" in colunas and row.get("placa") != _to_str(existente.get("placa")):
            add("placa", row.get("placa"))
        if row.get("serie") and "serie" in colunas and row.get("serie") != _to_str(existente.get("serie")):
            add("serie", row.get("serie"))
    elif modo == MODO_PREENCHER_VAZIOS:
        if not _to_str(existente.get("nome")) and row.get("nome"):
            add("nome", row.get("nome"))
        if "tipo" in colunas and not _to_str(existente.get("tipo")) and row.get("tipo"):
            add("tipo", row.get("tipo"))
        if setor_id is not None and "setor_id" in colunas and not existente.get("setor_id"):
            add("setor_id", setor_id)
        if row.get("km_atual") is not None and "km_atual" in colunas:
            novo_km = max(float(existente.get("km_atual") or 0), float(row.get("km_atual") or 0))
            if novo_km != float(existente.get("km_atual") or 0):
                add("km_atual", novo_km)
        if row.get("horas_atual") is not None and "horas_atual" in colunas:
            novo_h = max(float(existente.get("horas_atual") or 0), float(row.get("horas_atual") or 0))
            if novo_h != float(existente.get("horas_atual") or 0):
                add("horas_atual", novo_h)
        if row.get("placa") and "placa" in colunas and not _to_str(existente.get("placa")):
            add("placa", row.get("placa"))
        if row.get("serie") and "serie" in colunas and not _to_str(existente.get("serie")):
            add("serie", row.get("serie"))
    else:
        return False

    if not updates:
        return False

    params.append(existente["id"])
    cur.execute(f"update equipamentos set {', '.join(updates)} where id = %s", tuple(params))
    auditoria_service.registrar_no_conn(
        conn,
        acao="importar_atualizar_equipamento",
        entidade="equipamentos",
        entidade_id=existente["id"],
        valor_antigo=existente,
        valor_novo=row,
    )
    return True


def importar(df: pd.DataFrame, setor_padrao_id=None, modo_duplicados=MODO_IGNORAR, progress_callback=None) -> dict[str, Any]:
    if df is None or df.empty:
        return {"importados": 0, "atualizados": 0, "preenchidos_vazios": 0, "duplicados": 0, "setores_criados": 0, "erros": []}

    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _colunas_tabela(cur, "equipamentos")
        existentes = _equipamentos_existentes(cur)
        setores_idx, _ = _setores_index(cur)

        import_cols = ["codigo", "nome", "tipo", "setor_id", "km_atual", "horas_atual", "ativo"]
        if "placa" in colunas:
            import_cols.append("placa")
        if "serie" in colunas:
            import_cols.append("serie")
        if "km_inicial_plano" in colunas:
            import_cols.append("km_inicial_plano")
        elif "km_base_plano" in colunas:
            import_cols.append("km_base_plano")
        if "horas_inicial_plano" in colunas:
            import_cols.append("horas_inicial_plano")
        elif "horas_base_plano" in colunas:
            import_cols.append("horas_base_plano")

        placeholders = ", ".join(["%s"] * len(import_cols))
        insert_sql = f"insert into equipamentos ({', '.join(import_cols)}) values ({placeholders}) returning id"

        importados = atualizados = preenchidos_vazios = duplicados = setores_criados = 0
        erros = []
        total = len(df)
        rows = df.to_dict(orient="records")

        for i, row in enumerate(rows, start=1):
            codigo = _normalizar_codigo(row.get("codigo"))
            existente = existentes.get(codigo)
            cur.execute("SAVEPOINT importacao_item")
            try:
                row = dict(row)
                row["km_atual"] = _sanitize_meter(row.get("km_atual"), "km_atual")
                row["horas_atual"] = _sanitize_meter(row.get("horas_atual"), "horas_atual")

                setor_nome = _to_str(row.get("setor"))
                if setor_nome:
                    setor_id, criados_agora, setor_resolvido = _obter_ou_criar_setor(cur, conn, setores_idx, setor_nome)
                    row["setor_id"] = setor_id
                    row["setor_resolvido"] = setor_resolvido
                    setores_criados += len(criados_agora)
                else:
                    row["setor_id"] = None
                    row["setor_resolvido"] = ""

                if existente:
                    if modo_duplicados == MODO_IGNORAR:
                        duplicados += 1
                    elif modo_duplicados == MODO_ATUALIZAR:
                        if _atualizar_existente(cur, conn, colunas, existente, row, MODO_ATUALIZAR):
                            atualizados += 1
                            existente.update(
                                {
                                    "nome": row.get("nome") or existente.get("nome"),
                                    "tipo": row.get("tipo") or existente.get("tipo"),
                                    "setor_id": row.get("setor_id") if row.get("setor_id") is not None else existente.get("setor_id"),
                                    "km_atual": float(row.get("km_atual") if row.get("km_atual") is not None else existente.get("km_atual") or 0),
                                    "horas_atual": float(row.get("horas_atual") if row.get("horas_atual") is not None else existente.get("horas_atual") or 0),
                                    "placa": row.get("placa") or existente.get("placa"),
                                    "serie": row.get("serie") or existente.get("serie"),
                                }
                            )
                        else:
                            duplicados += 1
                    elif modo_duplicados == MODO_PREENCHER_VAZIOS:
                        if _atualizar_existente(cur, conn, colunas, existente, row, MODO_PREENCHER_VAZIOS):
                            preenchidos_vazios += 1
                            if row.get("km_atual") is not None:
                                existente["km_atual"] = max(float(existente.get("km_atual") or 0), float(row.get("km_atual") or 0))
                            if row.get("horas_atual") is not None:
                                existente["horas_atual"] = max(float(existente.get("horas_atual") or 0), float(row.get("horas_atual") or 0))
                            if not _to_str(existente.get("placa")) and row.get("placa"):
                                existente["placa"] = row.get("placa")
                            if not _to_str(existente.get("serie")) and row.get("serie"):
                                existente["serie"] = row.get("serie")
                            if not existente.get("setor_id") and row.get("setor_id") is not None:
                                existente["setor_id"] = row.get("setor_id")
                        else:
                            duplicados += 1
                    else:
                        duplicados += 1
                else:
                    insert_data = {
                        "codigo": codigo,
                        "nome": row.get("nome"),
                        "tipo": row.get("tipo") or "Veículos Leves",
                        "setor_id": row.get("setor_id"),
                        "km_atual": row.get("km_atual") or 0,
                        "horas_atual": row.get("horas_atual") or 0,
                        "ativo": True,
                        "placa": row.get("placa") or None,
                        "serie": row.get("serie") or None,
                        "km_inicial_plano": row.get("km_atual") or 0,
                        "km_base_plano": row.get("km_atual") or 0,
                        "horas_inicial_plano": row.get("horas_atual") or 0,
                        "horas_base_plano": row.get("horas_atual") or 0,
                    }
                    cur.execute(insert_sql, tuple(insert_data[c] for c in import_cols))
                    equipamento_id = cur.fetchone()[0]
                    auditoria_service.registrar_no_conn(
                        conn,
                        acao="importar_criar_equipamento",
                        entidade="equipamentos",
                        entidade_id=equipamento_id,
                        valor_antigo=None,
                        valor_novo=row,
                    )
                    importados += 1
                    existentes[codigo] = {
                        "id": equipamento_id,
                        "codigo": codigo,
                        "nome": insert_data["nome"],
                        "tipo": insert_data["tipo"],
                        "setor_id": insert_data["setor_id"],
                        "km_atual": float(insert_data["km_atual"] or 0),
                        "horas_atual": float(insert_data["horas_atual"] or 0),
                        "placa": _to_str(insert_data.get("placa")),
                        "serie": _to_str(insert_data.get("serie")),
                    }
            except Exception as e:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT importacao_item")
                except Exception:
                    conn.rollback()
                erros.append(f"Código {codigo}: {e}")
            else:
                try:
                    cur.execute("RELEASE SAVEPOINT importacao_item")
                except Exception:
                    pass

            if progress_callback and (i == total or i == 1 or i % _PROGRESS_STEP == 0):
                try:
                    progress_callback(i, total, codigo)
                except Exception:
                    pass

        conn.commit()
        try:
            equipamentos_service.limpar_cache()
        except Exception:
            pass
        return {
            "importados": importados,
            "atualizados": atualizados,
            "preenchidos_vazios": preenchidos_vazios,
            "duplicados": duplicados,
            "setores_criados": setores_criados,
            "erros": erros,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


preparar_importacao = processar_arquivo
processar_importacao = processar_arquivo
