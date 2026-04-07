from __future__ import annotations

import pandas as pd
import streamlit as st

from services import dashboard_service


STATUS_LABEL = {
    "VENCIDO": "🔴 Vencido",
    "PROXIMO": "🟡 Próximo",
    "EM DIA": "🟢 Em dia",
    "REALIZADO": "✅ Realizado no ciclo",
}


def _cards(kpis):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipamentos", kpis["total_equipamentos"])
    c2.metric("Itens vencidos", kpis["vencidos"])
    c3.metric("Itens próximos", kpis["proximos"])
    c4.metric("Realizados no ciclo", kpis["realizados"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Itens em dia", kpis["em_dia"])
    c6.metric("Equipamentos com alerta", kpis["equipamentos_com_alerta"])
    c7.metric("Equipamentos vencidos", kpis["equipamentos_vencidos"])
    c8.metric("Equipamentos com realizado", kpis["equipamentos_realizados"])


def _formatar_alertas_df(alertas):
    if not alertas:
        return pd.DataFrame()

    df = pd.DataFrame(alertas)
    df = df[[
        "origem",
        "equipamento_label",
        "setor",
        "item",
        "controle",
        "referencia_ciclo",
        "atual",
        "executado_em",
        "proximo_vencimento",
        "falta",
        "status",
    ]].rename(
        columns={
            "origem": "Origem",
            "equipamento_label": "Equipamento",
            "setor": "Setor",
            "item": "Item",
            "controle": "Controle",
            "referencia_ciclo": "Referência do ciclo",
            "atual": "Atual",
            "executado_em": "Executado em",
            "proximo_vencimento": "Próximo vencimento",
            "falta": "Falta",
            "status": "Status",
        }
    )
    df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    return df


def _grafico_status(alertas):
    if not alertas:
        return
    df = pd.DataFrame(alertas)
    base = df.groupby(["origem", "status"]).size().reset_index(name="Total")
    base["Status"] = base["status"].map(lambda x: STATUS_LABEL.get(x, x))
    chart = base.pivot(index="Status", columns="origem", values="Total").fillna(0)
    st.bar_chart(chart)


def _grafico_setores(alertas):
    if not alertas:
        return
    df = pd.DataFrame(alertas)
    base = df[df["status"].isin(["VENCIDO", "PROXIMO"])].groupby(["setor", "origem"]).size().reset_index(name="Total")
    if base.empty:
        st.info("Nenhum alerta vencido ou próximo para exibir no gráfico por setor.")
        return
    chart = base.pivot(index="setor", columns="origem", values="Total").fillna(0).sort_values(by=list(base["origem"].unique()), ascending=False)
    st.bar_chart(chart)


def render():
    st.title("Dashboard")
    st.caption("Visão executiva consolidada de revisão e lubrificação.")

    alertas = dashboard_service.carregar_alertas()
    kpis = dashboard_service.resumo_kpis(alertas)
    _cards(kpis)

    if not alertas:
        st.info("Nenhum item encontrado. Verifique se os equipamentos possuem templates configurados.")
        return

    setores = sorted({item["setor"] for item in alertas if item["setor"]})
    origens = ["Todos", "Revisão", "Lubrificação"]
    status_options = ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"]

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        setor_filtro = st.multiselect("Filtrar por setor", setores)
    with col2:
        origem_filtro = st.selectbox("Origem", origens)
    with col3:
        status_filtro = st.selectbox("Status", status_options)

    filtrados = alertas
    if setor_filtro:
        filtrados = [item for item in filtrados if item["setor"] in setor_filtro]
    if origem_filtro != "Todos":
        filtrados = [item for item in filtrados if item["origem"] == origem_filtro]
    if status_filtro != "Todos":
        filtrados = [item for item in filtrados if item["status"] == status_filtro]

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Distribuição por status")
        _grafico_status(filtrados)
    with g2:
        st.subheader("Alertas por setor")
        _grafico_setores(filtrados)

    st.subheader("Pendências e próximos vencimentos")
    df_alertas = _formatar_alertas_df(filtrados)
    if not df_alertas.empty:
        st.dataframe(df_alertas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum item para os filtros selecionados.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Setores com mais alertas")
        ranking = dashboard_service.ranking_setores(filtrados)
        if ranking:
            st.dataframe(pd.DataFrame(ranking), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta relevante para exibir por setor.")

    with c2:
        st.subheader("Top equipamentos críticos")
        top_criticos = dashboard_service.top_equipamentos_criticos(filtrados)
        if top_criticos:
            st.dataframe(pd.DataFrame(top_criticos), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento crítico para os filtros selecionados.")
