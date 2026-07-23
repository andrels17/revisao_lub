"""Página de Log de Auditoria — visível apenas para administradores."""
from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from services import auth_service, auditoria_service
from ui.exportacao import botao_exportar_excel
from ui.theme import render_page_intro


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .audit-shell { margin-top: .15rem; }
        .audit-filters {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 14px;
            padding: .85rem .95rem .4rem;
            background: rgba(9,18,33,.52);
            margin-bottom: .85rem;
        }
        .audit-stat {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 14px;
            padding: .75rem .85rem;
            background: rgba(9,18,33,.52);
            text-align: center;
        }
        .audit-stat .k { font-size: .72rem; color: #8fa4c0; text-transform: uppercase;
            font-weight: 700; letter-spacing: .06em; }
        .audit-stat .v { font-size: 1.45rem; font-weight: 900; color: #f8fbff; margin-top: .2rem; }
        .audit-note {
            border-left: 3px solid rgba(79,140,255,.5);
            padding: .55rem .75rem;
            border-radius: 10px;
            background: rgba(79,140,255,.08);
            color: #dcebff;
            font-size: .84rem;
            margin-bottom: .75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fmt_dt(valor) -> str:
    if not valor:
        return "—"
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(valor)


def render() -> None:
    auth_service.requer_role("admin")
    _inject_styles()

    render_page_intro(
        "Log de Auditoria",
        "Rastreio completo de todas as ações realizadas no sistema por usuários.",
        "Governança",
    )

    st.markdown('<div class="audit-note">'
                '🔍 Todos os registros de criação, edição e exclusão realizados no sistema são armazenados automaticamente neste log.'
                '</div>', unsafe_allow_html=True)

    # ── Filtros ──────────────────────────────────────────────────────
    st.markdown('<div class="audit-filters">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.2, 1.2])
    with col1:
        busca = st.text_input("Buscar usuário / entidade / ação", placeholder="Pesquisar…", label_visibility="collapsed")
    with col2:
        entidades = [""] + auditoria_service.listar_entidades()
        entidade_filtro = st.selectbox("Entidade", entidades, format_func=lambda x: "Todas as entidades" if x == "" else x)
    with col3:
        acoes = [""] + auditoria_service.listar_acoes()
        acao_filtro = st.selectbox("Ação", acoes, format_func=lambda x: "Todas as ações" if x == "" else x)
    with col4:
        data_inicio = st.date_input("De", value=None, label_visibility="collapsed")
    with col5:
        data_fim = st.date_input("Até", value=None, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Carregar logs ────────────────────────────────────────────────
    with st.spinner("Carregando logs…"):
        logs = auditoria_service.listar_logs(
            limite=1000,
            entidade=entidade_filtro or None,
            acao=acao_filtro or None,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    # Filtro de busca textual
    termo = (busca or "").strip().lower()
    if termo:
        logs = [
            l for l in logs
            if termo in str(l.get("usuario_nome") or "").lower()
            or termo in str(l.get("usuario_email") or "").lower()
            or termo in str(l.get("entidade") or "").lower()
            or termo in str(l.get("acao") or "").lower()
            or termo in str(l.get("entidade_id") or "").lower()
        ]

    # ── KPIs ─────────────────────────────────────────────────────────
    total = len(logs)
    usuarios_unicos = len({l.get("usuario_email") for l in logs if l.get("usuario_email")})
    entidades_unicas = len({l.get("entidade") for l in logs if l.get("entidade")})
    acoes_unicas = len({l.get("acao") for l in logs if l.get("acao")})

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value in [
        (k1, "Registros", total),
        (k2, "Usuários ativos", usuarios_unicos),
        (k3, "Entidades", entidades_unicas),
        (k4, "Tipos de ação", acoes_unicas),
    ]:
        with col:
            st.markdown(
                f'<div class="audit-stat"><div class="k">{label}</div><div class="v">{value}</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")

    if not logs:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    # ── Tabela ───────────────────────────────────────────────────────
    df = pd.DataFrame(logs)
    df["criado_em"] = df["criado_em"].apply(_fmt_dt)
    df = df.rename(columns={
        "id": "ID",
        "criado_em": "Data/Hora",
        "acao": "Ação",
        "entidade": "Entidade",
        "entidade_id": "ID Entidade",
        "usuario_nome": "Usuário",
        "usuario_email": "E-mail",
    })

    cols_exibir = [c for c in ["Data/Hora", "Usuário", "E-mail", "Ação", "Entidade", "ID Entidade"] if c in df.columns]

    col_exp, col_btn = st.columns([4, 1])
    with col_exp:
        st.caption(f"{total} registro(s) encontrado(s)")
    with col_btn:
        botao_exportar_excel(df[cols_exibir], "log_auditoria", label="⬇ Excel", key="exp_auditoria")

    st.dataframe(df[cols_exibir], use_container_width=True, hide_index=True)

    # ── Detalhes de valor_antigo / valor_novo ────────────────────────
    with st.expander("Ver detalhes completos (com valores anteriores/novos)"):
        cols_full = [c for c in ["Data/Hora", "Usuário", "Ação", "Entidade", "ID Entidade", "valor_antigo", "valor_novo"] if c in df.columns]
        st.dataframe(df[cols_full] if cols_full else df, use_container_width=True, hide_index=True)
