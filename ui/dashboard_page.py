import pandas as pd
import streamlit as st

from services import dashboard_service
from ui.exportacao import botao_exportar_excel
from ui.constants  import STATUS_LABEL, STATUS_COR





def _cards(kpis):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipamentos", kpis["total_equipamentos"])
    c2.metric("Alertas vencidos", kpis["vencidos"], delta=None)
    c3.metric("Alertas próximos", kpis["proximos"])
    c4.metric("Itens em dia", kpis["em_dia"])

    c5, c6, c7 = st.columns(3)
    c5.metric("Equipamentos com alerta", kpis["equipamentos_com_alerta"])
    c6.metric("Equipamentos vencidos", kpis["equipamentos_vencidos"])
    c7.metric("Equipamentos próximos", kpis["equipamentos_proximos"])


def _grafico_pizza(kpis):
    """Gráfico de pizza com distribuição de status."""
    labels = ["Vencidos", "Próximos", "Em dia"]
    values = [kpis["vencidos"], kpis["proximos"], kpis["em_dia"]]
    cores = ["#ef4444", "#f59e0b", "#22c55e"]

    if sum(values) == 0:
        return

    try:
        import plotly.graph_objects as go  # type: ignore
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker_colors=cores,
            hole=0.4,
            textinfo="label+percent",
        )])
        fig.update_layout(
            margin=dict(t=30, b=0, l=0, r=0),
            height=250,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        df_pizza = pd.DataFrame({"Status": labels, "Qtd": values})
        st.bar_chart(df_pizza.set_index("Status"))


def _grafico_barras_setores(ranking):
    """Barras horizontais por setor."""
    if not ranking:
        return
    try:
        import plotly.graph_objects as go  # type: ignore
        setores = [r["Setor"] for r in ranking]
        vencidos = [r["Vencidos"] for r in ranking]
        proximos = [r["Próximos"] for r in ranking]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Vencidos", x=vencidos, y=setores, orientation="h", marker_color="#ef4444"))
        fig.add_trace(go.Bar(name="Próximos", x=proximos, y=setores, orientation="h", marker_color="#f59e0b"))
        fig.update_layout(
            barmode="stack",
            margin=dict(t=10, b=0, l=0, r=0),
            height=max(200, 40 * len(setores)),
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        df_bar = pd.DataFrame(ranking).set_index("Setor")[["Vencidos", "Próximos"]]
        st.bar_chart(df_bar)


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
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.title("Dashboard")
        st.caption("Visão executiva de alertas de revisão e lubrificação.")
    with col_btn:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco"):
            dashboard_service.carregar_alertas.clear()
            st.rerun()

    alertas, total_equipamentos = dashboard_service.carregar_alertas()
    kpis = dashboard_service.resumo_kpis(alertas, total_equipamentos)
    _cards(kpis)

    if not alertas:
        st.info("Nenhum alerta encontrado. Verifique se os equipamentos possuem template de revisão ou lubrificação configurado.")
        return

    # ── Gráficos resumo ──────────────────────────────────────────────────────
    ranking_setores = dashboard_service.ranking_setores(alertas)
    col_pizza, col_barras = st.columns([1, 2])
    with col_pizza:
        st.subheader("Distribuição de status")
        _grafico_pizza(kpis)
    with col_barras:
        st.subheader("Alertas por setor")
        _grafico_barras_setores(ranking_setores)

    st.divider()

    # ── Filtros ───────────────────────────────────────────────────────────────
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

    # ── Tabela de pendências ──────────────────────────────────────────────────
    st.subheader(f"Pendências e próximos vencimentos ({len(filtrados)} itens)")
    df_alertas = _formatar_alertas_df(filtrados)
    if not df_alertas.empty:
        col_exp = st.columns([5,1])[1]
        with col_exp:
            botao_exportar_excel(df_alertas, "alertas", label="⬇️ Excel", key="exp_dash_alertas")
        st.dataframe(df_alertas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum item para os filtros selecionados.")

    # ── Rankings ──────────────────────────────────────────────────────────────
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

