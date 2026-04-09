from __future__ import annotations

import streamlit as st
from database.connection import get_conn, release_conn
from services import auth_service


_CACHE_KEY = "_escopo_cache"


def _usuario():
    return auth_service.usuario_logado() or {}


def _cache_get():
    user = _usuario()
    if not user:
        return None
    current = st.session_state.get(_CACHE_KEY)
    if current and current.get("user_id") == user.get("id"):
        return current
    return None


def _cache_set(payload: dict):
    st.session_state[_CACHE_KEY] = payload
    return payload


def carregar_escopo() -> dict:
    cache = _cache_get()
    if cache is not None:
        return cache

    user = _usuario()
    role = user.get("role")
    responsavel_id = user.get("responsavel_id")
    base = {
        "user_id": user.get("id"),
        "role": role,
        "responsavel_id": responsavel_id,
        "setor_ids": set(),
        "equipamento_ids": set(),
        "restrito": False,
        "descricao": "Acesso completo.",
    }
    if not user or role in {None, "admin", "visualizador"}:
        return _cache_set(base)

    if not responsavel_id:
        base["descricao"] = "Sem responsável vinculado; exibindo visão ampla."
        return _cache_set(base)

    with get_conn() as conn:
        cur = conn.cursor()
        try:
            if role == "gestor":
                cur.execute(
                    """
                    select distinct setor_id::text
                    from vinculos_setor
                    where responsavel_id = %s::uuid and ativo = true
                    """,
                    (responsavel_id,),
                )
                setores = {row[0] for row in cur.fetchall() if row and row[0]}
                if setores:
                    base["setor_ids"] = setores
                    base["restrito"] = True
                    base["descricao"] = f"Escopo restrito a {len(setores)} setor(es) vinculado(s)."
            elif role == "operador":
                cur.execute(
                    """
                    select distinct equipamento_id::text
                    from vinculos_equipamento
                    where responsavel_id = %s::uuid and ativo = true
                    """,
                    (responsavel_id,),
                )
                equipamentos = {row[0] for row in cur.fetchall() if row and row[0]}
                if equipamentos:
                    base["equipamento_ids"] = equipamentos
                    base["restrito"] = True
                    base["descricao"] = f"Escopo restrito a {len(equipamentos)} equipamento(s) vinculado(s)."
        except Exception:
            conn.rollback()
    return _cache_set(base)



def limpar_cache():
    st.session_state.pop(_CACHE_KEY, None)



def resumo_escopo() -> str:
    return carregar_escopo().get("descricao") or "Acesso completo."



def filtrar_setores(setores: list[dict]) -> list[dict]:
    escopo = carregar_escopo()
    permitidos = escopo.get("setor_ids") or set()
    if not escopo.get("restrito") or not permitidos:
        return setores
    return [s for s in setores if str(s.get("id")) in permitidos]



def filtrar_equipamentos(equipamentos: list[dict]) -> list[dict]:
    escopo = carregar_escopo()
    if not escopo.get("restrito"):
        return equipamentos
    equipamento_ids = escopo.get("equipamento_ids") or set()
    setor_ids = escopo.get("setor_ids") or set()
    filtrados = []
    for e in equipamentos:
        eid = str(e.get("id")) if e.get("id") is not None else None
        sid = str(e.get("setor_id")) if e.get("setor_id") is not None else None
        if equipamento_ids and eid in equipamento_ids:
            filtrados.append(e)
        elif setor_ids and sid in setor_ids:
            filtrados.append(e)
    return filtrados



def pode_gerenciar_cadastros() -> bool:
    return auth_service.role_atual() in {"admin", "gestor"}



def pode_importar() -> bool:
    return auth_service.role_atual() == "admin"



def pode_ver_equipamento(equipamento: dict | None) -> bool:
    if not equipamento:
        return False
    return bool(filtrar_equipamentos([equipamento]))
