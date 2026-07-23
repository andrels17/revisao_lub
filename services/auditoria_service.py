from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from database.connection import get_conn, release_conn
from services import auth_service


ACTIONS_CREATE = {"insert", "create", "criar", "import"}


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _sanitize(payload):
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=_json_default)
    except Exception:
        return json.dumps({"valor": str(payload)}, ensure_ascii=False)


def _usuario_atual_id():
    usuario = auth_service.usuario_logado() or {}
    return usuario.get("id")


def registrar(acao: str, entidade: str, entidade_id=None, valor_antigo=None, valor_novo=None):
    usuario_id = _usuario_atual_id()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into log_auditoria (
                usuario_id,
                acao,
                entidade,
                entidade_id,
                valor_antigo,
                valor_novo
            )
            values (%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                usuario_id,
                acao,
                entidade,
                str(entidade_id) if entidade_id is not None else None,
                _sanitize(valor_antigo),
                _sanitize(valor_novo),
            ),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        release_conn(conn)


def registrar_no_conn(conn, acao: str, entidade: str, entidade_id=None, valor_antigo=None, valor_novo=None):
    usuario_id = _usuario_atual_id()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into log_auditoria (
                usuario_id,
                acao,
                entidade,
                entidade_id,
                valor_antigo,
                valor_novo
            )
            values (%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                usuario_id,
                acao,
                entidade,
                str(entidade_id) if entidade_id is not None else None,
                _sanitize(valor_antigo),
                _sanitize(valor_novo),
            ),
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def listar_logs(
    limite: int = 500,
    usuario_id: str | None = None,
    entidade: str | None = None,
    acao: str | None = None,
    data_inicio=None,
    data_fim=None,
) -> list[dict]:
    """Lista logs de auditoria com filtros opcionais."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = []
        params: list = []
        if usuario_id:
            filtros.append("l.usuario_id = %s::uuid")
            params.append(usuario_id)
        if entidade:
            filtros.append("l.entidade = %s")
            params.append(entidade)
        if acao:
            filtros.append("l.acao = %s")
            params.append(acao)
        if data_inicio:
            filtros.append("l.criado_em::date >= %s")
            params.append(data_inicio)
        if data_fim:
            filtros.append("l.criado_em::date <= %s")
            params.append(data_fim)
        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
        params.append(limite)
        cur.execute(
            f"""
            SELECT l.id, l.criado_em, l.acao, l.entidade, l.entidade_id,
                   u.nome AS usuario_nome, u.email AS usuario_email,
                   l.valor_antigo, l.valor_novo
            FROM public.log_auditoria l
            LEFT JOIN public.usuarios u ON u.id = l.usuario_id
            {where}
            ORDER BY l.criado_em DESC
            LIMIT %s
            """,
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        release_conn(conn)


def listar_entidades() -> list[str]:
    """Retorna entidades distintas registradas no log de auditoria."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT entidade FROM public.log_auditoria ORDER BY entidade")
        return [r[0] for r in cur.fetchall() if r[0]]
    except Exception:
        return []
    finally:
        release_conn(conn)


def listar_acoes() -> list[str]:
    """Retorna ações distintas registradas no log de auditoria."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT acao FROM public.log_auditoria ORDER BY acao")
        return [r[0] for r in cur.fetchall() if r[0]]
    except Exception:
        return []
    finally:
        release_conn(conn)
