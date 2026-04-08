from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from database.connection import get_conn
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
        conn.close()


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
