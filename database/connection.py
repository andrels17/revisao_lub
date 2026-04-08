from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import InterfaceError, OperationalError
from psycopg2.pool import SimpleConnectionPool
import streamlit as st


_POOL_KEY = "_db_pool"


def _get_dsn() -> str:
    """
    Lê a string de conexão do ambiente/segredos.
    Ajuste a ordem abaixo se no seu projeto você usa outra chave.
    """
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


def _is_connection_usable(conn) -> bool:
    try:
        if conn is None or conn.closed:
            return False
        with conn.cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def _new_raw_connection():
    conn = psycopg2.connect(_get_dsn(), connect_timeout=10, sslmode="require")
    conn.autocommit = False
    return conn


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
    return pool


def get_conn():
    """
    Retorna uma conexão válida.
    Se o pool devolver conexão fechada/inválida, descarta e cria outra.
    """
    pool = _get_pool()
    conn = None

    try:
        conn = pool.getconn()
    except Exception:
        conn = None

    if _is_connection_usable(conn):
        return conn

    if conn is not None:
        try:
            pool.putconn(conn, close=True)
        except Exception:
            _safe_close_raw(conn)

    try:
        fresh = _new_raw_connection()
        if _is_connection_usable(fresh):
            return fresh
    except Exception:
        pass

    # última tentativa: recria o pool inteiro
    try:
        old_pool = st.session_state.pop(_POOL_KEY, None)
        if old_pool is not None:
            try:
                old_pool.closeall()
            except Exception:
                pass
    except Exception:
        pass

    pool = _create_pool()
    st.session_state[_POOL_KEY] = pool
    conn = pool.getconn()

    if not _is_connection_usable(conn):
        try:
            pool.putconn(conn, close=True)
        except Exception:
            _safe_close_raw(conn)
        raise OperationalError("Não foi possível obter uma conexão válida com o banco.")

    return conn


def release_conn(conn) -> None:
    """
    Devolve a conexão ao pool com segurança.
    Se estiver inválida, descarta.
    """
    if conn is None:
        return

    pool = st.session_state.get(_POOL_KEY)

    try:
        _safe_rollback(conn)

        if pool is None:
            _safe_close_raw(conn)
            return

        if conn.closed or not _is_connection_usable(conn):
            try:
                pool.putconn(conn, close=True)
            except Exception:
                _safe_close_raw(conn)
            return

        pool.putconn(conn)
    except Exception:
        try:
            if pool is not None:
                pool.putconn(conn, close=True)
            else:
                _safe_close_raw(conn)
        except Exception:
            _safe_close_raw(conn)


def close_all_connections() -> None:
    pool = st.session_state.pop(_POOL_KEY, None)
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
