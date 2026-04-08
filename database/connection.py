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


def get_conn():
    """Compatibilidade com código legado — retorna uma conexão direta."""
    database_url = _get_secret("DATABASE_URL") or _build_url_from_parts()
    dsn = _normalize_database_url(database_url)
    try:
        return psycopg2.connect(dsn)
    except psycopg2.OperationalError as exc:
        raise RuntimeError(
            "Não foi possível conectar ao banco Neon. Verifique se a DATABASE_URL está correta, "
            "se o banco está ativo e se a URL contém sslmode=require."
        ) from exc
