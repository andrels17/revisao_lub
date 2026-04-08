import pandas as pd
import streamlit as st

from services import dashboard_service
from ui.exportacao import botao_exportar_excel
from ui.constants  import STATUS_LABEL, STATUS_COR


# ── card colorido ─────────────────────────────────────────────────────────────

def _metric_card(label: str, value, bg: str, icon: str = ""):
    st.markdown(
        f"""
        <div style="
            background:{bg};border-radius:10px;padding:16px 20px;
            text-align:center;margin-bottom:4px;
        ">
            <div style="font-size:1.6rem;line-height:1">{icon}</div>
            <div style="font-size:2rem;font-weight:700;color:#fff;line-height:1.2">{value}</div>
            <div style="font-size:0.78rem;color:#fff;opacity:0.88;margin-top:4px">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _cards(kpis):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("Total de equipamentos", kpis["total_equipamentos"], "#1e40af", "🚜")
    with c2:
        _metric_card("Alertas vencidos",  kpis["vencidos"],
                     "#dc2626" if kpis["vencidos"]  else "#16a34a", "🔴")
    with c3:
        _metric_card("Alertas próximos",  kpis["proximos"],
                     "#d97706" if kpis["proximos"]  else "#16a34a", "🟡")
    with c4:
        _metric_card("Itens em dia", kpis["em_dia"], "#16a34a", "🟢")

    st.write("")
    c5, c6, c7, _ = st.columns(4)
    with c5:
        _metric_card("Equipamentos c/ alerta", kpis["equipamentos_com_alerta"],
                     "#7c3aed" if kpis["equipamentos_com_alerta"] else "#16a34a", "⚠️")
    with c6:
        _metric_card("Equipamentos vencidos", kpis["equipamentos_vencidos"],
                     "#dc2626" if kpis["equipamentos_vencidos"] else "#16a34a", "🔴")
    with c7:
        _metric_card("Equipamentos próximos", kpis["equipamentos_proximos"],
                     "#d97706" if kpis["equipamentos_proximos"] else "#16a34a", "🟡")


# ── gráficos ──────────────────────────────────────────────────────────────────

def _grafico_pizza(kpis):
    labels = ["Vencidos", "Próximos", "Em dia"]
    values = [kpis["vencidos"], kpis["proximos"], kpis["em_dia"]]
    cores  = ["#ef4444", "#f59e0b", "#22c55e"]
    if sum(values) == 0:
        st.info("Sem alertas para exibir.")
        return
    try:
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, marker_colors=cores,
            hole=0.45, textinfo="label+percent",
            hovertemplate="%{label}: %{value}<extra></extra>",
        )])
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=240, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(pd.DataFrame({"Status": labels, "Qtd": values}).set_index("Status"))


def _grafico_barras_setores(ranking):
    if not ranking:
        st.info("Nenhum alerta por setor.")
        return
    try:
        import plotly.graph_objects as go
        setores  = [r["Setor"]    for r in ranking]
        vencidos = [r["Vencidos"] for r in ranking]
        proximos = [r["Próximos"] for r in ranking]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Vencidos", x=vencidos, y=setores, orientation="h",
                             marker_color="#ef4444",
                             hovertemplate="%{y}: %{x} vencido(s)<extra></extra>"))
        fig.add_trace(go.Bar(name="Próximos", x=proximos, y=setores, orientation="h",
                             marker_color="#f59e0b",
                             hovertemplate="%{y}: %{x} próximo(s)<extra></extra>"))
        fig.update_layout(
            barmode="stack", margin=dict(t=10, b=0, l=0, r=0),
            height=max(180, 38 * len(setores)),
            legend=dict(orientation="h", y=-0.18), xaxis_title="Alertas",
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(pd.DataFrame(ranking).set_index("Setor")[["Vencidos", "Próximos"]])


def _formatar_alertas_df(alertas):
    if not alertas:
        return pd.DataFrame()
    df = pd.DataFrame(alertas)[[
        "origem", "equipamento_label", "setor", "etapa",
        "tipo", "atual", "ultima_execucao", "vencimento", "falta", "status",
    ]].rename(columns={
        "origem": "Origem", "equipamento_label": "Equipamento", "setor": "Setor",
        "etapa": "Etapa / Item", "tipo": "Controle", "atual": "Atual",
        "ultima_execucao": "Última execução", "vencimento": "Vencimento",
        "falta": "Falta", "status": "Status",
    })
    df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    return df


# ── página ────────────────────────────────────────────────────────────────────

def render():
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.title("📊 Dashboard")
        st.caption("Visão executiva de alertas de revisão e lubrificação.")
    with col_btn:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco"):
            dashboard_service.carregar_alertas.clear()
            st.rerun()

    with st.spinner("Carregando dados…"):
        alertas, total_equipamentos = dashboard_service.carregar_alertas()

    kpis = dashboard_service.resumo_kpis(alertas, total_equipamentos)
    _cards(kpis)

    if not alertas:
        st.divider()
        st.info("Nenhum alerta encontrado. Verifique se os equipamentos possuem template de revisão ou lubrificação configurado.")
        return

    st.divider()

    # ── Gráficos ──────────────────────────────────────────────────────────────
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
    setores        = sorted({item["setor"] for item in alertas if item["setor"]})
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        setor_filtro  = st.multiselect("Filtrar por setor", setores)
    with col2:
        origem_filtro = st.selectbox("Origem", ["Todas", "Revisão", "Lubrificação"])
    with col3:
        status_filtro = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA"])

    filtrados = alertas
    if setor_filtro:
        filtrados = [a for a in filtrados if a["setor"] in setor_filtro]
    if origem_filtro != "Todas":
        filtrados = [a for a in filtrados if a["origem"] == origem_filtro]
    if status_filtro != "Todos":
        filtrados = [a for a in filtrados if a["status"] == status_filtro]

    # ── Tabela ────────────────────────────────────────────────────────────────
    st.subheader(f"Pendências e próximos vencimentos ({len(filtrados)} itens)")
    df_alertas = _formatar_alertas_df(filtrados)
    if not df_alertas.empty:
        col_exp = st.columns([5, 1])[1]
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
            st.info("Nenhum alerta de vencimento ou proximidade para exibir.")
    with col_b:
        st.subheader("Top equipamentos críticos")
        ranking_eq = dashboard_service.ranking_equipamentos_criticos(filtrados)
        if ranking_eq:
            st.dataframe(pd.DataFrame(ranking_eq), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento crítico para os filtros selecionados.")
