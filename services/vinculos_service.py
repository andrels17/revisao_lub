from database.connection import get_conn

try:
    from psycopg2 import errors as pg_errors
except Exception:  # pragma: no cover
    pg_errors = None


# ── helpers ──────────────────────────────────────────────────

def _is_schema_error(exc):
    names = {exc.__class__.__name__}
    if exc.__class__.__module__:
        names.add(f"{exc.__class__.__module__}.{exc.__class__.__name__}")
    text = str(exc).lower()
    return (
        "undefinedtable" in " ".join(n.lower() for n in names)
        or "undefinedcolumn" in " ".join(n.lower() for n in names)
        or "relation" in text and "does not exist" in text
        or "column" in text and "does not exist" in text
    )


def _safe_fetchall(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        return cur.fetchall()
    except Exception as exc:
        if _is_schema_error(exc):
            return []
        raise
    finally:
        conn.close()


def _safe_fetchone(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        return cur.fetchone()
    except Exception as exc:
        if _is_schema_error(exc):
            return None
        raise
    finally:
        conn.close()


# ── Vínculos por Equipamento (operacional) ───────────────────

def listar_por_equipamento(equipamento_id):
    rows = _safe_fetchall(
        """
        select ve.id, ve.responsavel_id, r.nome, r.telefone,
               ve.tipo_vinculo, ve.principal
        from vinculos_equipamento ve
        join responsaveis r on r.id = ve.responsavel_id
        where ve.equipamento_id = %s and coalesce(ve.ativo, true) = true
        order by ve.principal desc, r.nome
        """,
        (equipamento_id,),
    )
    return [
        {
            "id": r[0],
            "responsavel_id": r[1],
            "responsavel_nome": r[2],
            "responsavel_telefone": r[3] or "",
            "tipo_vinculo": r[4],
            "principal": r[5],
        }
        for r in rows
    ]


def criar_vinculo_equipamento(equipamento_id, responsavel_id, tipo_vinculo="lubrificador", principal=False):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into vinculos_equipamento
                (equipamento_id, responsavel_id, tipo_vinculo, principal)
            values (%s, %s, %s, %s)
            on conflict (equipamento_id, responsavel_id, tipo_vinculo)
            do update set principal = excluded.principal, ativo = true
            returning id
            """,
            (equipamento_id, responsavel_id, tipo_vinculo, principal),
        )
        vid = cur.fetchone()[0]
        conn.commit()
        return vid
    finally:
        conn.close()


def remover_vinculo_equipamento(vinculo_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "update vinculos_equipamento set ativo = false where id = %s",
            (vinculo_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── Vínculos por Setor (gestão) ──────────────────────────────

def listar_por_setor(setor_id):
    rows = _safe_fetchall(
        """
        select vs.id, vs.responsavel_id, r.nome, r.telefone,
               vs.tipo_responsabilidade, vs.principal
        from vinculos_setor vs
        join responsaveis r on r.id = vs.responsavel_id
        where vs.setor_id = %s and coalesce(vs.ativo, true) = true
        order by vs.principal desc, r.nome
        """,
        (setor_id,),
    )
    return [
        {
            "id": r[0],
            "responsavel_id": r[1],
            "responsavel_nome": r[2],
            "responsavel_telefone": r[3] or "",
            "tipo_responsabilidade": r[4],
            "principal": r[5],
        }
        for r in rows
    ]


def criar_vinculo_setor(setor_id, responsavel_id, tipo_responsabilidade="gestor", principal=False):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into vinculos_setor
                (setor_id, responsavel_id, tipo_responsabilidade, principal)
            values (%s, %s, %s, %s)
            on conflict (setor_id, responsavel_id, tipo_responsabilidade)
            do update set principal = excluded.principal, ativo = true
            returning id
            """,
            (setor_id, responsavel_id, tipo_responsabilidade, principal),
        )
        vid = cur.fetchone()[0]
        conn.commit()
        return vid
    finally:
        conn.close()


def remover_vinculo_setor(vinculo_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "update vinculos_setor set ativo = false where id = %s",
            (vinculo_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── Consultas para alertas ───────────────────────────────────

def responsavel_gestao_setor(setor_id):
    """Retorna o responsável principal de gestão de um setor."""
    row = _safe_fetchone(
        """
        select r.nome, r.telefone
        from vinculos_setor vs
        join responsaveis r on r.id = vs.responsavel_id
        where vs.setor_id = %s and coalesce(vs.ativo, true) = true
        order by vs.principal desc
        limit 1
        """,
        (setor_id,),
    )
    return {"nome": row[0], "telefone": row[1] or ""} if row else None
