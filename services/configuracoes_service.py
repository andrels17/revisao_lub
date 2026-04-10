from __future__ import annotations

import streamlit as st
import psycopg2
from psycopg2 import OperationalError, InterfaceError

from database.connection import get_conn, release_conn
from services import cache_service
from ui import constants as ui_constants

CONFIG_DEFAULTS = {
    "tolerancia_proximo_km": 500,
    "tolerancia_proximo_horas": 50,
    "ttl_cache": 60,
    "dias_sem_leitura": 7,
    "alerta_cooldown_horas": 24,
    "fila_alertas_limite": 200,
}

SESSION_PREFIX = "cfg_"


# =========================
# SAFE DB HELPERS (NOVO)
# =========================
def _safe_rollback(conn):
    try:
        if conn and not conn.closed:
            conn.rollback()
    except Exception:
        pass


def _safe_close(conn) -> None:
    release_conn(conn)


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(int(value), max_value))


def _apply_defaults_to_session() -> dict:
    cfg = {k: int(v) for k, v in CONFIG_DEFAULTS.items()}
    for chave, valor in cfg.items():
        st.session_state[f"{SESSION_PREFIX}{chave}"] = valor
    ui_constants.TOLERANCIA_PROXIMO_KM = int(cfg["tolerancia_proximo_km"])
    ui_constants.TOLERANCIA_PROXIMO_HORAS = int(cfg["tolerancia_proximo_horas"])
    ui_constants.TOLERANCIA_PADRAO = int(cfg["tolerancia_proximo_km"])
    return cfg


def _is_missing_table_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in [
        "does not exist",
        "relation",
        "undefinedtable",
    ])


# =========================
# GARANTIR TABELA (CORRIGIDO)
# =========================
def garantir_tabela() -> bool:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            create table if not exists configuracoes_sistema (
                chave varchar(100) primary key,
                valor varchar(500) not null,
                descricao text,
                atualizado_em timestamptz default now()
            )
            """
        )

        conn.commit()
        return True

    except (OperationalError, InterfaceError):
        _safe_rollback(conn)
        return False
    except psycopg2.Error:
        _safe_rollback(conn)
        return False
    finally:
        _safe_close(conn)


# =========================
# CARREGAR CONFIG (CORRIGIDO)
# =========================
@st.cache_data(ttl=300, show_spinner=False)
def carregar_todas() -> dict:
    tabela_ok = garantir_tabela()
    if not tabela_ok:
        return dict(CONFIG_DEFAULTS)

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("select chave, valor from configuracoes_sistema")
        rows = cur.fetchall()

    except (OperationalError, InterfaceError):
        _safe_rollback(conn)
        return dict(CONFIG_DEFAULTS)
    except psycopg2.Error:
        _safe_rollback(conn)
        return dict(CONFIG_DEFAULTS)
    finally:
        _safe_close(conn)

    data = {k: v for k, v in rows}
    merged = {**CONFIG_DEFAULTS, **data}

    tolerancia_km = merged.get("tolerancia_proximo_km", merged.get("tolerancia_padrao", CONFIG_DEFAULTS["tolerancia_proximo_km"]))
    tolerancia_horas = merged.get("tolerancia_proximo_horas", CONFIG_DEFAULTS["tolerancia_proximo_horas"])

    return {
        "tolerancia_proximo_km": _clamp_int(_parse_int(tolerancia_km, CONFIG_DEFAULTS["tolerancia_proximo_km"]), 1, 5000),
        "tolerancia_proximo_horas": _clamp_int(_parse_int(tolerancia_horas, CONFIG_DEFAULTS["tolerancia_proximo_horas"]), 1, 500),
        "ttl_cache": _clamp_int(_parse_int(merged.get("ttl_cache"), CONFIG_DEFAULTS["ttl_cache"]), 10, 600),
        "dias_sem_leitura": _clamp_int(_parse_int(merged.get("dias_sem_leitura"), CONFIG_DEFAULTS["dias_sem_leitura"]), 1, 180),
        "alerta_cooldown_horas": _clamp_int(_parse_int(merged.get("alerta_cooldown_horas"), CONFIG_DEFAULTS["alerta_cooldown_horas"]), 1, 168),
        "fila_alertas_limite": _clamp_int(_parse_int(merged.get("fila_alertas_limite"), CONFIG_DEFAULTS["fila_alertas_limite"]), 20, 1000),
    }


def aplicar_no_session_state():
    cfg = carregar_todas()
    for chave, valor in cfg.items():
        st.session_state[f"{SESSION_PREFIX}{chave}"] = valor
    ui_constants.TOLERANCIA_PROXIMO_KM = int(cfg["tolerancia_proximo_km"])
    ui_constants.TOLERANCIA_PROXIMO_HORAS = int(cfg["tolerancia_proximo_horas"])
    ui_constants.TOLERANCIA_PADRAO = int(cfg["tolerancia_proximo_km"])
    return cfg


# =========================
# SALVAR (CORRIGIDO)
# =========================
def salvar(configs: dict):
    tabela_ok = garantir_tabela()
    if not tabela_ok:
        _apply_defaults_to_session()
        st.warning("Não foi possível salvar configurações no banco. Usando valores padrão nesta sessão.")
        return

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        for chave, valor in configs.items():
            cur.execute(
                """
                insert into configuracoes_sistema (chave, valor, atualizado_em)
                values (%s, %s, now())
                on conflict (chave)
                do update set valor = excluded.valor, atualizado_em = now()
                """,
                (chave, str(valor)),
            )

        conn.commit()

    except (OperationalError, InterfaceError):
        _safe_rollback(conn)
        st.warning("Erro de conexão ao salvar configurações.")
    except psycopg2.Error:
        _safe_rollback(conn)
        st.warning("Não foi possível salvar configurações no banco.")
    finally:
        _safe_close(conn)

    cache_service.invalidate_configuracoes()
    aplicar_no_session_state()


# =========================
# RESETAR (CORRIGIDO)
# =========================
def resetar():
    tabela_ok = garantir_tabela()
    if not tabela_ok:
        _apply_defaults_to_session()
        return

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("delete from configuracoes_sistema")
        conn.commit()

    except (OperationalError, InterfaceError):
        _safe_rollback(conn)
    except psycopg2.Error:
        _safe_rollback(conn)
    finally:
        _safe_close(conn)

    cache_service.invalidate_configuracoes()
    aplicar_no_session_state()


# =========================
# GETTERS
# =========================
def get_tolerancia_proximo_km() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}tolerancia_proximo_km", ui_constants.TOLERANCIA_PROXIMO_KM))


def get_tolerancia_proximo_horas() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}tolerancia_proximo_horas", ui_constants.TOLERANCIA_PROXIMO_HORAS))


def get_tolerancia_padrao() -> int:
    return get_tolerancia_proximo_km()


def get_ttl_cache() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}ttl_cache", CONFIG_DEFAULTS["ttl_cache"]))


def get_dias_sem_leitura() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}dias_sem_leitura", CONFIG_DEFAULTS["dias_sem_leitura"]))


def get_alerta_cooldown_horas() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}alerta_cooldown_horas", CONFIG_DEFAULTS["alerta_cooldown_horas"]))


def get_fila_alertas_limite() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}fila_alertas_limite", CONFIG_DEFAULTS["fila_alertas_limite"]))
