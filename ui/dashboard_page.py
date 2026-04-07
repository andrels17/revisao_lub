import pandas as pd
import streamlit as st

from services import dashboard_service


STATUS_LABEL = {
    "VENCIDO": "🔴 Vencido",
    "PROXIMO": "🟡 Próximo",
    "EM DIA": "🟢 Em dia",
}



def _cards(kpis):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipamentos", kpis["total_equipamentos"])
    c2.metric("Alertas vencidos", kpis["vencidos"])
    c3.metric("Alertas próximos", kpis["proximos"])
    c4.metric("Itens em dia", kpis["em_dia"])

    c5, c6, c7 = st.columns(3)
    c5.metric("Equipamentos com alerta", kpis["equipamentos_com_alerta"])
    c6.metric("Equipamentos vencidos", kpis["equipamentos_vencidos"])
    c7.metric("Equipamentos próximos", kpis["equipamentos_proximos"])



def _formatar_alertas_df(alertas):
    if not alertas:
        return pd.DataFrame()

    df = pd.DataFrame(alertas)
    df = df[[
        "origem",
        "equipamento_label",
        "setor",
        "etapa",
        "tipo",
        "atual",
        "ultima_execucao",
        "vencimento",
        "falta",
        "status",
    ]].rename(
        columns={
            "origem": "Origem",
            "equipamento_label": "Equipamento",
            "setor": "Setor",
            "etapa": "Etapa / Item",
            "tipo": "Controle",
            "atual": "Atual",
            "ultima_execucao": "Última execução",
            "vencimento": "Vencimento",
            "falta": "Falta",
            "status": "Status",
        }
    )
    df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    return df



def render():
    st.title("Dashboard")
    st.caption("Visão executiva de alertas de revisão e lubrificação.")

    alertas = dashboard_service.carregar_alertas()
    kpis = dashboard_service.resumo_kpis(alertas)
    _cards(kpis)

    if not alertas:
        st.info("Nenhum alerta encontrado. Verifique se os equipamentos possuem template de revisão ou lubrificação configurado.")
        return

    setores = sorted({item["setor"] for item in alertas if item["setor"]})
    origens = ["Todas", "Revisão", "Lubrificação"]
    status_options = ["Todos", "VENCIDO", "PROXIMO", "EM DIA"]
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
    if origem_filtro != "Todas":
        filtrados = [item for item in filtrados if item["origem"] == origem_filtro]
    if status_filtro != "Todos":
        filtrados = [item for item in filtrados if item["status"] == status_filtro]

    st.subheader("Pendências e próximos vencimentos")
    df_alertas = _formatar_alertas_df(filtrados)
    if not df_alertas.empty:
        st.dataframe(df_alertas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum item para os filtros selecionados.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Setores com mais alertas")
        ranking = dashboard_service.ranking_setores(filtrados)
        if ranking:
            st.dataframe(pd.DataFrame(ranking), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta de vencimento ou proximidade para exibir por setor.")

    with col_b:
        st.subheader("Top equipamentos críticos")
        ranking_eq = dashboard_service.ranking_equipamentos_criticos(filtrados)
        if ranking_eq:
            st.dataframe(pd.DataFrame(ranking_eq), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento crítico para os filtros selecionados.")
