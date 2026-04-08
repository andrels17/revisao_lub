import os
from contextlib import contextmanager
from urllib.parse import urlparse, parse_qsl, urlunparse

import psycopg2
import psycopg2.pool
import streamlit as st


def _get_secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)


def _normalize_database_url(raw_url: str) -> str:
    url = (raw_url or "").strip().strip('"').strip("'")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não foi configurada no Streamlit Cloud > Secrets."
        )

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError(
            "DATABASE_URL inválida. Use o formato postgresql://USUARIO:SENHA@HOST/DB?sslmode=require"
        )

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    query.setdefault("connect_timeout", "10")

    normalized_query = "&".join(f"{k}={v}" for k, v in query.items())
    return urlunparse(
        (
            "postgresql",
            parsed.netloc,
            parsed.path,
            parsed.params,
            normalized_query,
            parsed.fragment,
        )
    )


def _build_url_from_parts() -> str | None:
    host = _get_secret("DB_HOST")
    dbname = _get_secret("DB_NAME")
    user = _get_secret("DB_USER")
    password = _get_secret("DB_PASS")
    port = _get_secret("DB_PORT", "5432")

    if not all([host, dbname, user, password]):
        return None

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require&connect_timeout=10"


@st.cache_resource
def _get_pool():
    """Cria um pool de conexões reutilizável (criado uma vez por sessão do Streamlit)."""
    database_url = _get_secret("DATABASE_URL") or _build_url_from_parts()
    dsn = _normalize_database_url(database_url)
    try:
        return psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=dsn)
    except psycopg2.OperationalError as exc:
        raise RuntimeError(
            "Não foi possível conectar ao banco Neon. Verifique se a DATABASE_URL está correta, "
            "se o banco está ativo e se a URL contém sslmode=require."
        ) from exc


@contextmanager
def get_conn_ctx():
    """Context manager que devolve a conexão ao pool automaticamente."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


class _PooledConn:
    """
    Wrapper fino em torno de uma conexão do pool.
    Expõe a mesma interface que psycopg2.connection; close() devolve ao pool
    em vez de encerrar a conexão, sem precisar fazer monkey-patch no objeto C.
    """
    __slots__ = ("_conn", "_pool")

    def __init__(self, conn, pool):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_pool", pool)

    # ── delegação transparente ────────────────────────────────────────────────
    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_conn"), name, value)

    # ── substituição de close() ───────────────────────────────────────────────
    def close(self):
        pool = object.__getattribute__(self, "_pool")
        conn = object.__getattribute__(self, "_conn")
        pool.putconn(conn)

    # ── suporte a context manager (with get_conn() as conn:) ──────────────────
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = object.__getattribute__(self, "_conn")
        if exc_type:
            conn.rollback()
        self.close()
        return False


def get_conn() -> _PooledConn:
    """
    Retorna uma conexão do pool compartilhado encapsulada em _PooledConn.
    Todo o código legado (conn = get_conn() … conn.close()) se beneficia
    automaticamente do pool sem precisar ser alterado.
    """
    pool = _get_pool()
    return _PooledConn(pool.getconn(), pool)
