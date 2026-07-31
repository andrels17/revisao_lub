from __future__ import annotations

import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import OperationalError
from psycopg2.pool import ThreadedConnectionPool
import streamlit as st


# ---------------------------------------------------------------------------
# Pool ÚNICO por processo, compartilhado entre TODAS as sessões do Streamlit.
#
# Antes, o pool ficava em st.session_state: cada sessão de usuário abria seu
# próprio SimpleConnectionPool(maxconn=10). Com poucos usuários simultâneos
# isso já esgotava o limite de conexões do Neon (N sessões x 10 = N*10
# conexões possíveis). Agora existe um único pool por processo, guardado via
# st.cache_resource (mecanismo do próprio Streamlit para recursos
# compartilhados entre sessões, thread-safe na criação).
#
# Como o pool passa a ser acessado por várias sessões/threads ao mesmo tempo,
# trocamos SimpleConnectionPool (não é thread-safe) por ThreadedConnectionPool.
# ---------------------------------------------------------------------------

_pool_lock = threading.Lock()
_conn_ids_lock = threading.Lock()
_pool_conn_ids: set[int] = set()


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
    """Rollback condicional: só faz roundtrip se há transação ativa."""
    try:
        if conn and not conn.closed:
            # STATUS_READY (1) = sem transação. Evita roundtrip desnecessário.
            if getattr(conn, 'status', None) != 1:  # 1 = STATUS_READY
                conn.rollback()
    except Exception:
        pass


def _register_pool_conn(conn) -> None:
    try:
        with _conn_ids_lock:
            _pool_conn_ids.add(id(conn))
    except Exception:
        pass


def _is_pool_managed(conn) -> bool:
    try:
        with _conn_ids_lock:
            return id(conn) in _pool_conn_ids
    except Exception:
        return False


def _mark_discarded(conn) -> None:
    try:
        with _conn_ids_lock:
            _pool_conn_ids.discard(id(conn))
    except Exception:
        pass


def _is_connection_usable(conn) -> bool:
    """
    Validação leve sem roundtrip ao banco.
    Verifica apenas se a conexão está aberta e em estado válido.
    """
    try:
        if conn is None or conn.closed:
            return False
        # STATUS_READY=1, STATUS_BEGIN=2, STATUS_IN_TRANSACTION=2, STATUS_INTRANS_INERROR=3
        # STATUS_INTRANS_INERROR (3) indica erro não tratado — conexão inutilizável
        status = getattr(conn, 'status', None)
        if status == 3:  # STATUS_INTRANS_INERROR
            return False
        return True
    except Exception:
        return False


def _create_pool() -> ThreadedConnectionPool:
    return ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=_get_dsn(),
        connect_timeout=10,
        sslmode="require",
    )


@st.cache_resource(show_spinner=False)
def _cached_pool() -> ThreadedConnectionPool:
    """Recurso compartilhado por todo o processo (todas as sessões).

    st.cache_resource garante que a criação seja feita uma única vez e que
    o mesmo objeto seja reaproveitado por todas as sessões do app.
    """
    return _create_pool()


def _get_pool() -> ThreadedConnectionPool:
    with _pool_lock:
        return _cached_pool()


def _recreate_pool() -> ThreadedConnectionPool:
    """Descarta o pool atual (e todas as conexões) e cria um novo, do zero."""
    with _pool_lock:
        old_pool = None
        try:
            # .clear() sem argumentos limpa todas as entradas desta função cacheada
            old_pool = _cached_pool()
        except Exception:
            old_pool = None

        _cached_pool.clear()

        if old_pool is not None:
            try:
                old_pool.closeall()
            except Exception:
                pass

        with _conn_ids_lock:
            _pool_conn_ids.clear()

        return _cached_pool()


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

    pool = _recreate_pool()
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

    try:
        pool = _cached_pool()
    except Exception:
        pool = None
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
    """Fecha o pool compartilhado (afeta TODAS as sessões, use com cuidado)."""
    with _pool_lock:
        try:
            pool = _cached_pool()
        except Exception:
            pool = None

        _cached_pool.clear()

        if pool is not None:
            try:
                pool.closeall()
            except Exception:
                pass

        with _conn_ids_lock:
            _pool_conn_ids.clear()


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
