from __future__ import annotations

import streamlit as st

from database.connection import get_conn
from ui import constants as ui_constants

CONFIG_DEFAULTS = {
    "tolerancia_padrao": 10,
    "ttl_cache": 60,
    "dias_sem_leitura": 7,
}

SESSION_PREFIX = "cfg_"


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def garantir_tabela():
    conn = get_conn()
    cur = conn.cursor()
    try:
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
    finally:
        conn.close()


def carregar_todas() -> dict:
    garantir_tabela()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select chave, valor from configuracoes_sistema")
        rows = cur.fetchall()
    finally:
        conn.close()

    data = {k: v for k, v in rows}
    merged = {**CONFIG_DEFAULTS, **data}
    return {
        "tolerancia_padrao": _parse_int(merged.get("tolerancia_padrao"), CONFIG_DEFAULTS["tolerancia_padrao"]),
        "ttl_cache": _parse_int(merged.get("ttl_cache"), CONFIG_DEFAULTS["ttl_cache"]),
        "dias_sem_leitura": _parse_int(merged.get("dias_sem_leitura"), CONFIG_DEFAULTS["dias_sem_leitura"]),
    }


def aplicar_no_session_state():
    cfg = carregar_todas()
    for chave, valor in cfg.items():
        st.session_state[f"{SESSION_PREFIX}{chave}"] = valor
    ui_constants.TOLERANCIA_PADRAO = int(cfg["tolerancia_padrao"])
    return cfg


def salvar(configs: dict):
    garantir_tabela()
    conn = get_conn()
    cur = conn.cursor()
    try:
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
    finally:
        conn.close()
    aplicar_no_session_state()


def resetar():
    garantir_tabela()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("delete from configuracoes_sistema")
        conn.commit()
    finally:
        conn.close()
    aplicar_no_session_state()


def get_tolerancia_padrao() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}tolerancia_padrao", ui_constants.TOLERANCIA_PADRAO))


def get_ttl_cache() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}ttl_cache", CONFIG_DEFAULTS["ttl_cache"]))


def get_dias_sem_leitura() -> int:
    return int(st.session_state.get(f"{SESSION_PREFIX}dias_sem_leitura", CONFIG_DEFAULTS["dias_sem_leitura"]))
