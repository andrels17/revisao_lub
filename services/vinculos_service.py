from psycopg2 import errors
import streamlit as st

from database.connection import get_conn, release_conn
from services import cache_service


# ── Vínculos por Equipamento (operacional) ───────────────────

@st.cache_data(ttl=180, show_spinner=False)
def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select ve.id, ve.responsavel_id, r.nome, r.telefone,
                   ve.tipo_vinculo, ve.principal
            from vinculos_equipamento ve
            join responsaveis r on r.id = ve.responsavel_id
            where ve.equipamento_id = %s and ve.ativo = true
            order by ve.principal desc, r.nome
            """,
            (equipamento_id,),
        )
        rows = cur.fetchall()
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
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)


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
        cache_service.invalidate_vinculos()
        return vid
    finally:
        release_conn(conn)


def remover_vinculo_equipamento(vinculo_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "update vinculos_equipamento set ativo = false where id = %s",
            (vinculo_id,),
        )
        conn.commit()
        cache_service.invalidate_vinculos()
    finally:
        release_conn(conn)


# ── Vínculos por Setor (gestão) ──────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def listar_por_setor(setor_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select vs.id, vs.responsavel_id, r.nome, r.telefone,
                   vs.tipo_responsabilidade, vs.principal
            from vinculos_setor vs
            join responsaveis r on r.id = vs.responsavel_id
            where vs.setor_id = %s and vs.ativo = true
            order by vs.principal desc, r.nome
            """,
            (setor_id,),
        )
        rows = cur.fetchall()
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
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)


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
        cache_service.invalidate_vinculos()
        return vid
    finally:
        release_conn(conn)


def remover_vinculo_setor(vinculo_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "update vinculos_setor set ativo = false where id = %s",
            (vinculo_id,),
        )
        conn.commit()
        cache_service.invalidate_vinculos()
    finally:
        release_conn(conn)


# ── Consultas para alertas ───────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def responsavel_gestao_setor(setor_id):
    """Retorna o responsável principal de gestão de um setor."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select r.nome, r.telefone
            from vinculos_setor vs
            join responsaveis r on r.id = vs.responsavel_id
            where vs.setor_id = %s and vs.ativo = true
            order by vs.principal desc
            limit 1
            """,
            (setor_id,),
        )
        row = cur.fetchone()
        return {"nome": row[0], "telefone": row[1] or ""} if row else None
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return None
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def mapa_responsaveis_operacionais():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select ve.equipamento_id, ve.id, ve.responsavel_id, r.nome, r.telefone,
                   ve.tipo_vinculo, ve.principal
            from vinculos_equipamento ve
            join responsaveis r on r.id = ve.responsavel_id
            where ve.ativo = true
            order by ve.equipamento_id, ve.principal desc, r.nome
            """
        )
        rows = cur.fetchall()
        out = {}
        for r in rows:
            out.setdefault(r[0], []).append({
                "id": r[1],
                "responsavel_id": r[2],
                "responsavel_nome": r[3],
                "responsavel_telefone": r[4] or "",
                "tipo_vinculo": r[5],
                "principal": r[6],
            })
        return out
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return {}
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def mapa_responsaveis_gestao():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select vs.setor_id, r.nome, r.telefone
            from (
                select distinct on (setor_id) setor_id, responsavel_id, principal
                from vinculos_setor
                where ativo = true
                order by setor_id, principal desc, responsavel_id
            ) vs
            join responsaveis r on r.id = vs.responsavel_id
            """
        )
        rows = cur.fetchall()
        return {r[0]: {"nome": r[1], "telefone": r[2] or ""} for r in rows}
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return {}
    finally:
        release_conn(conn)
