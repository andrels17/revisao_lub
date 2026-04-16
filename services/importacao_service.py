from __future__ import annotations

from io import BytesIO
from typing import Any
import math
import re
import unicodedata
from uuid import uuid4

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
    "codigo": ["cod_equipamento", "codigo", "id", "cod", "codigo_equipamento", "equipamento"],
    "nome": ["descricao_equipamento", "nome", "descricao_nome", "descricao_equip"],
    "grupo": ["descricaotipoequipamento", "grupo"],
    "tipo": ["descricaotipoequipamento", "tipo", "tipo_equipamento", "categoria"],
    "setor": ["descricao", "setor", "departamento", "descricao_setor", "setor_nome"],
    "tipo_horimetro": ["tipo_horimetro", "horimetro", "tipo_medidor", "medidor_tipo"],
    "valor_medidor": ["km_atual", "valor_medidor", "medidor_atual", "hodometro", "hodometro_atual", "km"],
    "km_atual": ["km_atual_destino"],
    "horas_atual": ["horas_atual", "horimetro_atual", "horas"],
    "ativo": ["ativo", "status"],
    "placa": ["placa"],
    "serie": ["serie", "numero_serie", "n_serie"],
}

CAMPOS_PREVIEW = ["codigo", "nome", "grupo", "tipo", "tipo_horimetro", "setor", "km_atual", "horas_atual", "ativo", "placa", "serie"]


def get_template_csv() -> bytes:
    df = pd.DataFrame(
        [
            {
                "COD_EQUIPAMENTO": "EQ-001",
                "DESCRICAO_EQUIPAMENTO": "Equipamento Exemplo",
                "DESCRICAOTIPOEQUIPAMENTO": "Caminhão",
                "TIPO_HORIMETRO": "KM",
                "KM_ATUAL": 12500,
                "DESCRICAO": "Operação > Caminhões",
                "ATIVO": "S",
                "PLACA": "ABC1D23",
                "SERIE": "SER-001",
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

def _parse_bool_ativo(value: Any) -> bool:
    s = _normalizar_nome(value)
    if not s:
        return True
    if s in {"1", "true", "t", "sim", "s", "ativo", "at", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "nao", "não", "n", "inativo", "inativo(a)", "off", "no"}:
        return False
    return True


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
    return _classificacao_tipo_padrao(tipo_original)




def normalizar_tipo_controle(valor: Any) -> str | None:
    tipo = _normalizar_nome(valor)
    if not tipo:
        return None
    if tipo in {"km", "k", "quilometro", "quilometros", "quilômetro", "quilômetros", "hodometro", "hodômetro", "odometro", "odômetro"}:
        return "km"
    if tipo in {"h", "hr", "hrs", "hora", "horas", "horimetro", "horímetro"}:
        return "horas"
    if "hora" in tipo or "hori" in tipo:
        return "horas"
    if "km" in tipo or "quilo" in tipo or "odo" in tipo or "hodo" in tipo:
        return "km"
    return None


def _normalizar_texto_regra(valor: Any) -> str:
    s = _to_str(valor).upper()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _regra_confere(texto: str, padrao: str, regra: str) -> bool:
    if not texto or not padrao:
        return False
    regra_norm = _normalizar_nome(regra) or "contains"
    if regra_norm == "exact":
        return texto == padrao
    if regra_norm == "startswith":
        return texto.startswith(padrao)
    return padrao in texto


def _ensure_tipos_equipamento_map(cur) -> None:
    if not _tabela_existe(cur, "tipos_equipamento_map"):
        cur.execute(
            """
            create table if not exists tipos_equipamento_map (
                id bigserial primary key,
                ativo boolean not null default true,
                prioridade integer not null default 100,
                campo_origem text not null default 'grupo',
                origem_valor text not null,
                regra text not null default 'contains',
                tipo_destino text not null,
                observacao text,
                created_at timestamptz not null default now()
            )
            """
        )
    else:
        cur.execute("alter table tipos_equipamento_map add column if not exists ativo boolean not null default true")
        cur.execute("alter table tipos_equipamento_map add column if not exists prioridade integer not null default 100")
        cur.execute("alter table tipos_equipamento_map add column if not exists campo_origem text not null default 'grupo'")
        cur.execute("alter table tipos_equipamento_map add column if not exists origem_valor text")
        cur.execute("alter table tipos_equipamento_map add column if not exists regra text not null default 'contains'")
        cur.execute("alter table tipos_equipamento_map add column if not exists tipo_destino text")
        cur.execute("alter table tipos_equipamento_map add column if not exists observacao text")
        cur.execute("alter table tipos_equipamento_map add column if not exists created_at timestamptz not null default now()")

    cur.execute("create index if not exists idx_tipos_equipamento_map_prio on tipos_equipamento_map(ativo, prioridade)")

    cur.execute("select count(1) from tipos_equipamento_map")
    total = int(cur.fetchone()[0] or 0)
    if total == 0:
        cur.execute(
            """
            insert into tipos_equipamento_map
                (ativo, prioridade, campo_origem, origem_valor, regra, tipo_destino, observacao)
            values
                (true, 1,  'grupo', 'CAMINH',             'contains', 'Caminhões',             'Classificação macro por grupo'),
                (true, 2,  'grupo', 'CACAMBA',            'contains', 'Caminhões',             'Classificação macro por grupo'),
                (true, 10, 'grupo', 'TRATOR',             'contains', 'Tratores',              'Classificação macro por grupo'),
                (true, 20, 'grupo', 'CARREGADEIRA',       'contains', 'Carregadeiras',         'Classificação macro por grupo'),
                (true, 30, 'grupo', 'COLHEITADEIRA',      'contains', 'Colheitadeiras',        'Classificação macro por grupo'),
                (true, 40, 'grupo', 'EMPILHADEIRA',       'contains', 'Empilhadeiras',         'Classificação macro por grupo'),
                (true, 50, 'grupo', 'AUTOMOVEIS',         'contains', 'Veículos Leves',        'Classificação macro por grupo'),
                (true, 51, 'grupo', 'MOTOCICLETA',        'contains', 'Veículos Leves',        'Classificação macro por grupo'),
                (true, 60, 'grupo', 'GERADOR',            'contains', 'Equipamentos de Apoio', 'Classificação macro por grupo'),
                (true, 61, 'grupo', 'MOTOR ESTACIONARIO', 'contains', 'Equipamentos de Apoio', 'Classificação macro por grupo'),
                (true, 62, 'grupo', 'ELETRO BOMBA',       'contains', 'Equipamentos de Apoio', 'Classificação macro por grupo'),
                (true, 70, 'grupo', 'MAQUINA PESADA',     'contains', 'Máquinas Pesadas',      'Classificação macro por grupo')
            """
        )


def _carregar_regras_tipo(cur) -> list[dict[str, Any]]:
    try:
        _ensure_tipos_equipamento_map(cur)
        cur.execute(
            """
            select ativo, prioridade, campo_origem, origem_valor, regra, tipo_destino
              from tipos_equipamento_map
             where coalesce(ativo, true) = true
             order by prioridade asc, id asc
            """
        )
        rows = cur.fetchall()
    except Exception:
        return []

    regras = []
    for ativo, prioridade, campo_origem, origem_valor, regra, tipo_destino in rows:
        regras.append({
            "ativo": bool(ativo) if ativo is not None else True,
            "prioridade": int(prioridade or 100),
            "campo_origem": _to_str(campo_origem) or "grupo",
            "origem_valor": _to_str(origem_valor),
            "regra": _to_str(regra) or "contains",
            "tipo_destino": _to_str(tipo_destino),
        })
    return regras


def _classificar_tipo_por_regras(row: dict[str, Any], regras: list[dict[str, Any]] | None = None) -> str:
    grupo = _normalizar_texto_regra(row.get("grupo"))
    nome = _normalizar_texto_regra(row.get("nome"))
    tipo = _normalizar_texto_regra(row.get("tipo"))
    ambos = " ".join([x for x in [grupo, nome, tipo] if x]).strip()

    for regra_item in (regras or []):
        if not regra_item.get("ativo", True):
            continue
        padrao = _normalizar_texto_regra(regra_item.get("origem_valor"))
        campo = _normalizar_nome(regra_item.get("campo_origem")) or "grupo"
        tipo_destino = _to_str(regra_item.get("tipo_destino"))
        if not padrao or not tipo_destino:
            continue

        textos = []
        if campo == "grupo":
            textos = [grupo]
        elif campo == "nome":
            textos = [nome]
        elif campo == "tipo":
            textos = [tipo]
        else:
            textos = [ambos, grupo, nome, tipo]

        if any(_regra_confere(texto, padrao, regra_item.get("regra", "contains")) for texto in textos if texto):
            return tipo_destino

    return _classificacao_tipo_padrao(row.get("grupo") or row.get("tipo") or row.get("nome"))


def _classificacao_tipo_padrao(tipo_original: Any) -> str:
    t = _normalizar_texto_regra(tipo_original)
    if not t:
        return "Outros"
    if "CAMINH" in t or "CACAMBA" in t:
        return "Caminhões"
    if "TRATOR" in t:
        return "Tratores"
    if "CARREGADEIRA" in t:
        return "Carregadeiras"
    if "COLHEITADEIRA" in t or "COLHEDOR" in t:
        return "Colheitadeiras"
    if "EMPILHADEIRA" in t:
        return "Empilhadeiras"
    if any(k in t for k in ["AUTOMOVEIS", "AUTOMOVEL", "MOTOCICLETA", "MOTO", "CARRO", "PASSEIO", "UTILITARIO", "CAMIONETE"]):
        return "Veículos Leves"
    if any(k in t for k in ["GERADOR", "MOTOR ESTACIONARIO", "ELETRO BOMBA", "ELETROBOMBA"]):
        return "Equipamentos de Apoio"
    if "MAQUINA PESADA" in t:
        return "Máquinas Pesadas"
    return "Outros"


def separar_medidor(df: pd.DataFrame):
    df = df.copy()
    if "km_atual" not in df.columns:
        df["km_atual"] = None
    if "horas_atual" not in df.columns:
        df["horas_atual"] = None

    for i, row in df.iterrows():
        tipo = _normalizar_nome(row.get("tipo_horimetro"))
        valor_bruto = row.get("valor_medidor")
        if valor_bruto is None or (isinstance(valor_bruto, float) and pd.isna(valor_bruto)):
            valor_bruto = row.get("km_atual")
        valor = _parse_num(valor_bruto)
        if valor is None:
            continue

        if "hora" in tipo:
            df.at[i, "horas_atual"] = valor
            if _parse_num(row.get("km_atual")) == valor:
                df.at[i, "km_atual"] = None
        else:
            df.at[i, "km_atual"] = valor
            if _parse_num(row.get("horas_atual")) == valor:
                df.at[i, "horas_atual"] = None

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
        colunas = _colunas_tabela(cur, "equipamentos")
        possui_grupo_texto = "grupo" in colunas
        possui_grupo_id = "grupo_id" in colunas
        possui_tabela_grupos = _tabela_existe(cur, "grupos")
        grupo_select = "coalesce(e.grupo, e.tipo)" if possui_grupo_texto else "coalesce(g.nome, e.tipo)"
        grupo_id_select = "e.grupo_id" if possui_grupo_id else "null::uuid"
        join_grupos = "left join grupos g on g.id = e.grupo_id" if possui_tabela_grupos and possui_grupo_id else ""
        cur.execute(
            f"""
            select e.id, e.codigo, e.nome, e.tipo,
                   {grupo_select} as grupo,
                   e.setor_id, {grupo_id_select} as grupo_id,
                   e.km_atual, e.horas_atual, e.ativo, e.placa, e.serie,
                   coalesce(e.tipo_controle, '') as tipo_controle
              from equipamentos e
              {join_grupos}
            """
        )
        rows = cur.fetchall()
        return {
            _normalizar_codigo(r[1]): {
                "id": r[0],
                "codigo": r[1],
                "nome": r[2],
                "tipo": r[3],
                "grupo": _to_str(r[4]),
                "setor_id": r[5],
                "grupo_id": r[6],
                "km_atual": float(r[7] or 0),
                "horas_atual": float(r[8] or 0),
                "ativo": bool(r[9]) if r[9] is not None else True,
                "placa": _to_str(r[10]),
                "serie": _to_str(r[11]),
                "tipo_controle": _to_str(r[12]),
            }
            for r in rows if r and r[1] is not None
        }
    finally:
        if own_conn is not None:
            release_conn(own_conn)



def _tabela_existe(cur, table_name: str) -> bool:
    cur.execute(
        """
        select exists(
            select 1
              from information_schema.tables
             where table_schema = 'public'
               and table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])


def _ensure_grupos_schema(cur) -> None:
    if not _tabela_existe(cur, "grupos"):
        cur.execute(
            """
            create table if not exists grupos (
                id uuid primary key,
                nome text not null,
                setor_id uuid null,
                ativo boolean not null default true,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
        cur.execute("create index if not exists idx_grupos_setor on grupos(setor_id)")
        cur.execute("create index if not exists idx_grupos_ativo on grupos(ativo)")
    colunas = _colunas_tabela(cur, "equipamentos")
    if "grupo_id" not in colunas:
        cur.execute("alter table equipamentos add column if not exists grupo_id uuid")
        cur.execute("create index if not exists idx_equipamentos_grupo_id on equipamentos(grupo_id)")


def _grupos_index(cur=None) -> dict[tuple[str, str | None], dict[str, Any]]:
    own_conn = None
    if cur is None:
        own_conn = get_conn()
        cur = own_conn.cursor()
    try:
        _ensure_grupos_schema(cur)
        cur.execute("select id, nome, setor_id, ativo from grupos where coalesce(ativo, true) = true")
        rows = cur.fetchall()
        idx = {}
        for gid, nome, setor_id, ativo in rows:
            idx[(_normalizar_nome(nome), str(setor_id) if setor_id else None)] = {
                "id": gid,
                "nome": _to_str(nome),
                "setor_id": str(setor_id) if setor_id else None,
                "ativo": bool(ativo) if ativo is not None else True,
            }
        return idx
    finally:
        if own_conn is not None:
            release_conn(own_conn)


def _resolver_grupo_existente(grupos_idx: dict[tuple[str, str | None], dict[str, Any]], grupo_nome: str, setor_id=None):
    nome_norm = _normalizar_nome(grupo_nome)
    setor_key = str(setor_id) if setor_id else None
    if not nome_norm:
        return None
    exato = grupos_idx.get((nome_norm, setor_key))
    if exato:
        return exato
    if setor_key is not None:
        exato_sem_setor = grupos_idx.get((nome_norm, None))
        if exato_sem_setor:
            return exato_sem_setor
    for (nome_idx, setor_idx), item in grupos_idx.items():
        if setor_key is not None and setor_idx not in {setor_key, None}:
            continue
        if nome_idx == nome_norm or nome_idx in nome_norm or nome_norm in nome_idx:
            return item
    return None


def _criar_grupo_no_conn(cur, conn, nome: str, setor_id=None):
    _ensure_grupos_schema(cur)
    novo_id = str(uuid4())
    cur.execute(
        """
        insert into grupos (id, nome, setor_id, ativo)
        values (%s::uuid, %s, %s, %s)
        returning id::text
        """,
        (novo_id, nome, str(setor_id) if setor_id else None, True),
    )
    novo_id = cur.fetchone()[0]
    auditoria_service.registrar_no_conn(
        conn,
        acao="importacao_criar_grupo",
        entidade="grupos",
        entidade_id=novo_id,
        valor_antigo=None,
        valor_novo={"nome": nome, "setor_id": str(setor_id) if setor_id else None, "origem": "importacao_equipamentos"},
    )
    return novo_id


def _obter_ou_criar_grupo(cur, conn, grupos_idx: dict[tuple[str, str | None], dict[str, Any]], grupo_nome: str, setor_id=None):
    nome = _to_str(grupo_nome)
    if not nome:
        return None, False, ""
    existente = _resolver_grupo_existente(grupos_idx, nome, setor_id=setor_id)
    if existente:
        return existente["id"], False, existente["nome"]
    gid = _criar_grupo_no_conn(cur, conn, nome, setor_id=setor_id)
    grupos_idx[(_normalizar_nome(nome), str(setor_id) if setor_id else None)] = {"id": gid, "nome": nome, "setor_id": str(setor_id) if setor_id else None, "ativo": True}
    return gid, True, nome

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
        if "grupo" not in df.columns:
            df["grupo"] = df.get("tipo")
        df["grupo"] = df["grupo"].apply(_to_str)
        df["tipo"] = df["tipo"].apply(normalizar_tipo)
        df = separar_medidor(df)
        df["km_atual"] = df["km_atual"].apply(lambda v: _sanitize_meter(v, "km_atual") if _parse_num(v) is not None else None)
        df["horas_atual"] = df["horas_atual"].apply(lambda v: _sanitize_meter(v, "horas_atual") if _parse_num(v) is not None else None)
        df["setor"] = df["setor"].apply(_to_str)
        if "ativo" not in df.columns:
            df["ativo"] = True
        df["ativo"] = df["ativo"].apply(_parse_bool_ativo)
        df["placa"] = df["placa"].apply(_to_str)
        df["serie"] = df["serie"].apply(_to_str)

        df, duplicados_arquivo = consolidar_duplicados(df)
        df = df.reset_index(drop=True)

        conn = get_conn()
        try:
            cur = conn.cursor()
            regras_tipo = _carregar_regras_tipo(cur)
        finally:
            release_conn(conn)

        setores_idx, _ = _setores_index()
        grupos_idx = _grupos_index()
        existentes = _equipamentos_existentes()

        erros = []
        avisos = []
        linhas_validas = []
        preview_rows = []
        novas = duplicadas_sistema = com_aviso = com_erro = 0
        setores_a_criar = []
        setores_a_criar_set = set()
        grupos_a_criar = []
        grupos_a_criar_set = set()

        if duplicados_arquivo:
            avisos.append(
                "Códigos duplicados no arquivo foram consolidados pela última ocorrência: "
                + ", ".join(sorted(map(str, duplicados_arquivo))[:20])
            )

        for idx, row in df.iterrows():
            codigo = _normalizar_codigo(row.get("codigo"))
            nome = _to_str(row.get("nome"))
            grupo = _to_str(row.get("grupo") or row.get("tipo"))
            tipo = _classificar_tipo_por_regras({"grupo": grupo, "nome": nome, "tipo": row.get("tipo")}, regras_tipo)
            setor_nome = _to_str(row.get("setor"))
            ativo = _parse_bool_ativo(row.get("ativo"))
            placa = _to_str(row.get("placa"))
            serie = _to_str(row.get("serie"))

            linha_erros = []
            linha_avisos = []
            setor_id = None
            setor_resolvido = ""
            acao_setor = "sem setor"
            grupo_id = None
            grupo_resolvido = ""
            acao_grupo = "sem grupo"

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

            if grupo:
                existente_grupo = _resolver_grupo_existente(grupos_idx, grupo, setor_id=setor_id)
                if existente_grupo:
                    grupo_id = existente_grupo["id"]
                    grupo_resolvido = existente_grupo["nome"]
                    acao_grupo = "usar existente"
                else:
                    grupo_resolvido = grupo
                    acao_grupo = "criar automaticamente"
                    chave_grupo = (_normalizar_nome(grupo), str(setor_id) if setor_id else _normalizar_nome(setor_resolvido) or None)
                    if chave_grupo not in grupos_a_criar_set:
                        grupos_a_criar_set.add(chave_grupo)
                        grupos_a_criar.append({"nome": grupo, "setor": setor_resolvido or setor_nome})
                    linha_avisos.append(f"grupo '{grupo}' será criado automaticamente")

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
                        "grupo": grupo,
                        "grupo_id": grupo_id,
                        "grupo_resolvido": grupo_resolvido,
                        "acao_grupo": acao_grupo,
                        "tipo": tipo,
                        "setor": setor_nome,
                        "setor_id": setor_id,
                        "setor_resolvido": setor_resolvido,
                        "km_atual": km_atual,
                        "horas_atual": horas_atual,
                        "ativo": ativo,
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
                    "grupo": grupo,
                    "grupo_resolvido": grupo_resolvido,
                    "ação_grupo": acao_grupo,
                    "tipo": tipo,
                    "setor": setor_nome,
                    "setor_resolvido": setor_resolvido,
                    "ação_setor": acao_setor,
                    "km_atual": km_atual,
                    "horas_atual": horas_atual,
                    "ativo": ativo,
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
            "grupos_a_criar": grupos_a_criar,
            "resumo": {
                "total_linhas": len(df),
                "novas": novas,
                "duplicadas_sistema": duplicadas_sistema,
                "com_aviso": com_aviso,
                "com_erro": com_erro,
                "setores_novos": len(setores_a_criar),
                "grupos_novos": len(grupos_a_criar),
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
        if "grupo" in colunas and row.get("grupo") and row.get("grupo") != _to_str(existente.get("grupo")):
            add("grupo", row.get("grupo"))
        if "grupo_id" in colunas and row.get("grupo_id") and row.get("grupo_id") != existente.get("grupo_id"):
            add("grupo_id", row.get("grupo_id"))
        if "tipo" in colunas and row.get("tipo") and row.get("tipo") != _to_str(existente.get("tipo")):
            add("tipo", row.get("tipo"))
        if setor_id is not None and "setor_id" in colunas and setor_id != existente.get("setor_id"):
            add("setor_id", setor_id)
        if row.get("km_atual") is not None and "km_atual" in colunas and float(row.get("km_atual") or 0) != float(existente.get("km_atual") or 0):
            add("km_atual", row.get("km_atual"))
        if row.get("horas_atual") is not None and "horas_atual" in colunas and float(row.get("horas_atual") or 0) != float(existente.get("horas_atual") or 0):
            add("horas_atual", row.get("horas_atual"))
        if "ativo" in colunas and bool(row.get("ativo", True)) != bool(existente.get("ativo", True)):
            add("ativo", bool(row.get("ativo", True)))
        if row.get("placa") and "placa" in colunas and row.get("placa") != _to_str(existente.get("placa")):
            add("placa", row.get("placa"))
        if row.get("serie") and "serie" in colunas and row.get("serie") != _to_str(existente.get("serie")):
            add("serie", row.get("serie"))
        if "tipo_controle" in colunas and row.get("tipo_controle") and row.get("tipo_controle") != _to_str(existente.get("tipo_controle")):
            add("tipo_controle", row.get("tipo_controle"))
    elif modo == MODO_PREENCHER_VAZIOS:
        if not _to_str(existente.get("nome")) and row.get("nome"):
            add("nome", row.get("nome"))
        if "grupo" in colunas and not _to_str(existente.get("grupo")) and row.get("grupo"):
            add("grupo", row.get("grupo"))
        if "grupo_id" in colunas and not existente.get("grupo_id") and row.get("grupo_id"):
            add("grupo_id", row.get("grupo_id"))
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
        if "tipo_controle" in colunas and row.get("tipo_controle") and not _to_str(existente.get("tipo_controle")):
            add("tipo_controle", row.get("tipo_controle"))
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
        _ensure_grupos_schema(cur)
        regras_tipo = _carregar_regras_tipo(cur)
        colunas = _colunas_tabela(cur, "equipamentos")
        existentes = _equipamentos_existentes(cur)
        setores_idx, _ = _setores_index(cur)
        grupos_idx = _grupos_index(cur)

        import_cols = ["codigo", "nome", "tipo", "setor_id", "km_atual", "horas_atual", "ativo"]
        if "tipo_controle" in colunas:
            import_cols.insert(3, "tipo_controle")
        if "grupo" in colunas:
            import_cols.insert(3, "grupo")
        if "grupo_id" in colunas:
            insert_pos = import_cols.index("setor_id")
            import_cols.insert(insert_pos + 1, "grupo_id")
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

        importados = atualizados = preenchidos_vazios = duplicados = setores_criados = grupos_criados = 0
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
                row["tipo_controle"] = normalizar_tipo_controle(row.get("tipo_horimetro")) or normalizar_tipo_controle(existente.get("tipo_controle") if existente else None) or "km"

                setor_nome = _to_str(row.get("setor"))
                if setor_nome:
                    setor_id, criados_agora, setor_resolvido = _obter_ou_criar_setor(cur, conn, setores_idx, setor_nome)
                    row["setor_id"] = setor_id
                    row["setor_resolvido"] = setor_resolvido
                    setores_criados += len(criados_agora)
                else:
                    row["setor_id"] = None
                    row["setor_resolvido"] = ""

                row["tipo"] = _classificar_tipo_por_regras(row, regras_tipo)
                grupo_nome = _to_str(row.get("grupo") or row.get("tipo"))
                if grupo_nome:
                    grupo_id, grupo_criado, grupo_resolvido = _obter_ou_criar_grupo(cur, conn, grupos_idx, grupo_nome, setor_id=row.get("setor_id"))
                    row["grupo_id"] = grupo_id
                    row["grupo_resolvido"] = grupo_resolvido
                    grupos_criados += 1 if grupo_criado else 0
                else:
                    row["grupo_id"] = None
                    row["grupo_resolvido"] = ""

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
                                    "grupo": row.get("grupo") or existente.get("grupo"),
                                    "grupo_id": row.get("grupo_id") or existente.get("grupo_id"),
                                    "setor_id": row.get("setor_id") if row.get("setor_id") is not None else existente.get("setor_id"),
                                    "ativo": bool(row.get("ativo", True)),
                                    "km_atual": float(row.get("km_atual") if row.get("km_atual") is not None else existente.get("km_atual") or 0),
                                    "horas_atual": float(row.get("horas_atual") if row.get("horas_atual") is not None else existente.get("horas_atual") or 0),
                                    "placa": row.get("placa") or existente.get("placa"),
                                    "serie": row.get("serie") or existente.get("serie"),
                                    "tipo_controle": row.get("tipo_controle") or existente.get("tipo_controle"),
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
                            if not existente.get("grupo_id") and row.get("grupo_id") is not None:
                                existente["grupo_id"] = row.get("grupo_id")
                            if not _to_str(existente.get("tipo_controle")) and row.get("tipo_controle"):
                                existente["tipo_controle"] = row.get("tipo_controle")
                        else:
                            duplicados += 1
                    else:
                        duplicados += 1
                else:
                    insert_data = {
                        "codigo": codigo,
                        "nome": row.get("nome"),
                        "tipo": row.get("tipo") or "Outros",
                        "tipo_controle": row.get("tipo_controle") or "km",
                        "grupo": row.get("grupo") or row.get("tipo") or "Outros",
                        "setor_id": row.get("setor_id"),
                        "grupo_id": row.get("grupo_id"),
                        "km_atual": row.get("km_atual") or 0,
                        "horas_atual": row.get("horas_atual") or 0,
                        "ativo": bool(row.get("ativo", True)),
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
                        "grupo": _to_str(insert_data.get("grupo")),
                        "setor_id": insert_data["setor_id"],
                        "grupo_id": insert_data.get("grupo_id"),
                        "ativo": bool(insert_data.get("ativo", True)),
                        "km_atual": float(insert_data["km_atual"] or 0),
                        "horas_atual": float(insert_data["horas_atual"] or 0),
                        "placa": _to_str(insert_data.get("placa")),
                        "serie": _to_str(insert_data.get("serie")),
                        "tipo_controle": _to_str(insert_data.get("tipo_controle")),
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
            "grupos_criados": grupos_criados,
            "erros": erros,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


preparar_importacao = processar_arquivo
processar_importacao = processar_arquivo
