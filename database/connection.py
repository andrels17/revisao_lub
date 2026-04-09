from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import OperationalError
from psycopg2.pool import SimpleConnectionPool
import streamlit as st


_POOL_KEY = "_db_pool"
_POOL_CONN_IDS_KEY = "_db_pool_conn_ids"


def _get_dsn() -> str:
    candidates = [
        os.getenv("DATABASE_URL"),
        os.getenv("DB_URL"),
        os.getenv("NEON_DATABASE_URL"),
        st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None,
        st.secrets.get("DB_URL") if hasattr(st, "secrets") else None,
        st.secrets.get("NEON_DATABASE_URL") if hasattr(st, "secrets") else None,
    ]
    dsn = next((v for v in candidates if v), None)
    if not dsn:
        raise RuntimeError(
            "String de conexão não encontrada. Defina DATABASE_URL, DB_URL ou NEON_DATABASE_URL."
        )
    return dsn


def _safe_close_raw(conn) -> None:
    try:
        if conn and not conn.closed:
            conn.close()
    except Exception:
        pass


def _safe_rollback(conn) -> None:
    try:
        if conn and not conn.closed:
            conn.rollback()
    except Exception:
        pass


def _register_pool_conn(conn) -> None:
    try:
        ids = st.session_state.setdefault(_POOL_CONN_IDS_KEY, set())
        ids.add(id(conn))
    except Exception:
        pass


def _is_pool_managed(conn) -> bool:
    try:
        return id(conn) in st.session_state.get(_POOL_CONN_IDS_KEY, set())
    except Exception:
        return False


def _mark_discarded(conn) -> None:
    try:
        st.session_state.get(_POOL_CONN_IDS_KEY, set()).discard(id(conn))
    except Exception:
        pass


def _is_connection_usable(conn) -> bool:
    """
    Validação leve, sem roundtrip obrigatório de SELECT 1 a cada checkout/release.
    Em conexões pooladas, isso evita uma ida extra ao Neon por uso.
    """
    try:
        if conn is None or conn.closed:
            return False
        conn.rollback()
        return not conn.closed
    except Exception:
        return False


def _create_pool() -> SimpleConnectionPool:
    return SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=_get_dsn(),
        connect_timeout=10,
        sslmode="require",
    )


def _get_pool() -> SimpleConnectionPool:
    pool = st.session_state.get(_POOL_KEY)
    if pool is None:
        pool = _create_pool()
        st.session_state[_POOL_KEY] = pool
        st.session_state.setdefault(_POOL_CONN_IDS_KEY, set())
    return pool


def get_conn():
    """
    Retorna uma conexão válida.
    Evita roundtrip extra de saúde em todo checkout; recria o pool quando necessário.
    """
    pool = _get_pool()
    conn = None

    try:
        conn = pool.getconn()
        _register_pool_conn(conn)
    except Exception:
        conn = None

    if _is_connection_usable(conn):
        return conn

    if conn is not None:
        try:
            _mark_discarded(conn)
            pool.putconn(conn, close=True)
        except Exception:
            _safe_close_raw(conn)

    try:
        old_pool = st.session_state.pop(_POOL_KEY, None)
        st.session_state.pop(_POOL_CONN_IDS_KEY, None)
        if old_pool is not None:
            try:
                old_pool.closeall()
            except Exception:
                pass
    except Exception:
        pass

    pool = _create_pool()
    st.session_state[_POOL_KEY] = pool
    st.session_state[_POOL_CONN_IDS_KEY] = set()
    conn = pool.getconn()
    _register_pool_conn(conn)

    if not _is_connection_usable(conn):
        try:
            _mark_discarded(conn)
            pool.putconn(conn, close=True)
        except Exception:
            _safe_close_raw(conn)
        raise OperationalError("Não foi possível obter uma conexão válida com o banco.")

    return conn


def release_conn(conn) -> None:
    """
    Devolve a conexão ao pool com segurança.
    Para conexões do pool, evita SELECT 1 no release.
    """
    if conn is None:
        return

    pool = st.session_state.get(_POOL_KEY)
    pool_managed = _is_pool_managed(conn)

    try:
        _safe_rollback(conn)

        if pool is None or not pool_managed:
            _mark_discarded(conn)
            _safe_close_raw(conn)
            return

        if conn.closed:
            try:
                _mark_discarded(conn)
                pool.putconn(conn, close=True)
            except Exception:
                _safe_close_raw(conn)
            return

        pool.putconn(conn)
    except Exception:
        try:
            _mark_discarded(conn)
            if pool is not None and pool_managed:
                pool.putconn(conn, close=True)
            else:
                _safe_close_raw(conn)
        except Exception:
            _safe_close_raw(conn)


def close_all_connections() -> None:
    pool = st.session_state.pop(_POOL_KEY, None)
    st.session_state.pop(_POOL_CONN_IDS_KEY, None)
    if pool is not None:
        try:
            pool.closeall()
        except Exception:
            pass


@contextmanager
def get_conn_ctx():
    conn = None
    try:
        conn = get_conn()
        yield conn
    finally:
        release_conn(conn)


# compatibilidade com códigos que usam get_connection()
def get_connection():
    return get_conn()
