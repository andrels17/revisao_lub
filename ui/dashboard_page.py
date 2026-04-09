import math

import pandas as pd
import streamlit as st

from services import dashboard_service
from ui.constants import STATUS_LABEL
from ui.exportacao import botao_exportar_excel


PLOTLY_COLORS = {
    "vencidos": "#ef4444",
    "proximos": "#f59e0b",
    "em_dia":   "#38bdf8",
    "axis":     "rgba(148,163,184,.22)",
    "grid":     "rgba(148,163,184,.08)",
    "font":     "#c8dcf4",
    "muted":    "#8fa4c0",
}


def _inject_styles():
    st.markdown(
        """
        <style>
        /* ── Dashboard ─────────────────────────────────────────────── */
        .dash-hero {
            padding: .75rem .9rem;
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 14px;
            background: #0d1929;
            margin-bottom: .85rem;
        }
        .dash-hero .badge {
            display: inline-block;
            padding: .15rem .5rem;
            border-radius: 999px;
            background: rgba(79,140,255,.10);
            border: 1px solid rgba(79,140,255,.16);
            color: #cde0ff;
            font-size: .68rem; font-weight: 700;
            margin-bottom: .4rem;
        }
        .dash-hero h2 { margin: 0; font-size: 1.05rem; font-weight: 700; }
        .dash-hero p  { margin: .22rem 0 0; color: #8fa4c0; font-size: .83rem; }

        /* KPI grid — 4 colunas no dashboard */
        .dash-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap: .6rem;
            margin-bottom: .75rem;
        }
        .dash-kpi-grid.three { grid-template-columns: repeat(3, minmax(0,1fr)); }

        .dash-kpi {
            position: relative; overflow: hidden;
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem .85rem;
            background: #0d1929;
        }
        .dash-kpi::before {
            content: "";
            position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: var(--kpi-accent, #4f8cff);
        }
        .dash-kpi .lbl  { font-size: .74rem; color: #8fa4c0; font-weight: 600; margin-bottom: .22rem; }
        .dash-kpi .val  { font-size: 1.65rem; font-weight: 800; line-height: 1; color: #e8f1ff; }
        .dash-kpi .hint { font-size: .70rem; color: #6b84a0; margin-top: .22rem; }
        .dash-kpi.d  { --kpi-accent: #ef4444; }
        .dash-kpi.w  { --kpi-accent: #f59e0b; }
        .dash-kpi.s  { --kpi-accent: #22c55e; }

        /* Section wrapper */
        .dash-section {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem .85rem .75rem;
            background: #0d1929;
            margin-bottom: .75rem;
        }
        .dash-section-title {
            font-size: .78rem; font-weight: 700;
            color: #8fa4c0;
            text-transform: uppercase; letter-spacing: .06em;
            margin-bottom: .55rem;
        }

        /* Filtros */
        .dash-filters {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .75rem .85rem .2rem;
            background: #0d1929;
            margin-bottom: .75rem;
        }

        @media (max-width: 900px) {
            .dash-kpi-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
            .dash-kpi-grid.three { grid-template-columns: repeat(2,minmax(0,1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero(total_alertas: int):
    st.markdown(
        f"""
        <div class="dash-hero">
            <div class="badge">Dashboard executivo</div>
            <h2>Pendências de manutenção</h2>
            <p>Alertas consolidados de revisão e lubrificação · <strong>{total_alertas}</strong> item(ns) no total</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value, hint: str = "", cls: str = ""):
    css = f"dash-kpi {cls}".strip()
    st.markdown(
        f"""
        <div class="{css}">
            <div class="lbl">{label}</div>
            <div class="val">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(kpis):
    # Linha 1: 4 KPIs de alertas
    st.markdown('<div class="dash-kpi-grid">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        _kpi("Equipamentos", kpis["total_equipamentos"], "Base monitorada")
    with c2:
        _kpi("Alertas vencidos", kpis["vencidos"], "Maior urgência", "d")
    with c3:
        _kpi("Alertas próximos", kpis["proximos"], "Janela de atenção", "w")
    with c4:
        _kpi("Itens em dia", kpis["em_dia"], "Status saudável", "s")
    st.markdown("</div>", unsafe_allow_html=True)

    # Linha 2: 3 KPIs de equipamentos
    st.markdown('<div class="dash-kpi-grid three">', unsafe_allow_html=True)
    c5, c6, c7 = st.columns(3, gap="small")
    with c5:
        _kpi("Equip. com alerta", kpis["equipamentos_com_alerta"], "Vencidos ou próximos", "d")
    with c6:
        _kpi("Equip. vencidos", kpis["equipamentos_vencidos"], "Ao menos 1 item vencido", "d")
    with c7:
        _kpi("Equip. próximos", kpis["equipamentos_proximos"], "Ao menos 1 item próximo", "w")
    st.markdown("</div>", unsafe_allow_html=True)


def _apply_plotly_theme(fig, height: int):
    fig.update_layout(
        height=height,
        margin=dict(t=8, b=8, l=8, r=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PLOTLY_COLORS["font"], size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.18,
            xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOTLY_COLORS["muted"], size=11),
        ),
    )
    return fig


def _grafico_status(kpis):
    labels = ["Vencidos", "Próximos", "Em dia"]
    values = [kpis["vencidos"], kpis["proximos"], kpis["em_dia"]]
    if sum(values) == 0:
        st.info("Sem distribuição para exibir.")
        return
    try:
        import plotly.graph_objects as go
        fig = go.Figure(data=[
            go.Pie(
                labels=labels, values=values, hole=0.65,
                textinfo="label+percent",
                textfont=dict(color="#cce0ff", size=11),
                hovertemplate="%{label}: %{value}<extra></extra>",
                marker=dict(
                    colors=[PLOTLY_COLORS["vencidos"], PLOTLY_COLORS["proximos"], PLOTLY_COLORS["em_dia"]],
                    line=dict(color="#07111f", width=2),
                ),
            )
        ])
        _apply_plotly_theme(fig, 260)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        st.bar_chart(pd.DataFrame({"Status": labels, "Qtd": values}).set_index("Status"))


def _grafico_setores(ranking):
    if not ranking:
        st.info("Sem setores com pendências relevantes.")
        return
    df = pd.DataFrame(ranking[:10])
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Vencidos", x=df["Vencidos"], y=df["Setor"], orientation="h",
            marker=dict(color=PLOTLY_COLORS["vencidos"]),
            hovertemplate="%{y}: %{x} vencido(s)<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="Próximos", x=df["Próximos"], y=df["Setor"], orientation="h",
            marker=dict(color=PLOTLY_COLORS["proximos"]),
            hovertemplate="%{y}: %{x} próximo(s)<extra></extra>",
        ))
        _apply_plotly_theme(fig, max(260, 38 * len(df)))
        fig.update_layout(
            barmode="stack",
            xaxis_title="Alertas",
            xaxis=dict(showgrid=True, gridcolor=PLOTLY_COLORS["grid"], zeroline=False),
            yaxis=dict(autorange="reversed", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        st.bar_chart(df.set_index("Setor")[["Vencidos", "Próximos"]])


def _formatar_alertas_df(alertas):
    if not alertas:
        return pd.DataFrame()
    return pd.DataFrame(alertas)[[
        "origem", "equipamento_label", "setor", "etapa",
        "tipo", "atual", "ultima_execucao", "vencimento", "falta", "status",
    ]].rename(columns={
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
    }).assign(Status=lambda df: df["Status"].map(lambda x: STATUS_LABEL.get(x, x)))


def _slice_page(df: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    if df.empty:
        return df
    start = max(0, (page - 1) * page_size)
    return df.iloc[start:start + page_size]


def render():
    _inject_styles()

    # ── Cabeçalho ──────────────────────────────────────────────────
    col_h, col_btn = st.columns([5, 1])
    with col_h:
        st.title("📊 Dashboard")
    with col_btn:
        st.write("")
        if st.button("↺ Atualizar", help="Recarrega dados do banco"):
            dashboard_service.carregar_alertas.clear()
            st.rerun()

    with st.spinner("Carregando…"):
        alertas, total_equipamentos = dashboard_service.carregar_alertas()

    kpis = dashboard_service.resumo_kpis(alertas, total_equipamentos)

    _render_cards(kpis)

    if not alertas:
        st.info("Nenhum alerta encontrado. Verifique se os equipamentos possuem template configurado.")
        return

    ranking_setores = dashboard_service.ranking_setores(alertas)
    ranking_eq      = dashboard_service.ranking_equipamentos_criticos(alertas)

    # ── Gráficos ────────────────────────────────────────────────────
    col_g1, col_g2 = st.columns([1, 1.5], gap="medium")
    with col_g1:
        st.markdown('<div class="dash-section"><div class="dash-section-title">Distribuição</div>', unsafe_allow_html=True)
        _grafico_status(kpis)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_g2:
        st.markdown('<div class="dash-section"><div class="dash-section-title">Setores prioritários</div>', unsafe_allow_html=True)
        _grafico_setores(ranking_setores)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Filtros ─────────────────────────────────────────────────────
    st.markdown('<div class="dash-filters">', unsafe_allow_html=True)
    setores = sorted({item.get("setor") or "-" for item in alertas})
    f1, f2, f3, f4 = st.columns([2.5, 1.2, 1.2, 1.1], gap="small")
    with f1:
        busca = st.text_input("Buscar equipamento / etapa", placeholder="Código, nome ou item", label_visibility="collapsed")
    with f2:
        setor_filtro = st.multiselect("Setor", setores, placeholder="Setor")
    with f3:
        origem_filtro = st.selectbox("Origem", ["Todas", "Revisão", "Lubrificação"])
    with f4:
        status_filtro = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA"])
    st.markdown("</div>", unsafe_allow_html=True)

    # Aplicar filtros
    termo = (busca or "").strip().lower()
    filtrados = alertas
    if termo:
        filtrados = [a for a in filtrados if termo in f'{a.get("equipamento_label","")} {a.get("etapa","")} {a.get("setor","")}'.lower()]
    if setor_filtro:
        filtrados = [a for a in filtrados if (a.get("setor") or "-") in setor_filtro]
    if origem_filtro != "Todas":
        filtrados = [a for a in filtrados if a.get("origem") == origem_filtro]
    if status_filtro != "Todos":
        filtrados = [a for a in filtrados if a.get("status") == status_filtro]

    df_alertas = _formatar_alertas_df(filtrados)

    # ── Tabela de alertas ───────────────────────────────────────────
    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    bar1, bar2, bar3 = st.columns([3, 1.3, 1], gap="small")
    with bar1:
        st.markdown(f'<div class="dash-section-title">Pendências · {len(df_alertas)} item(ns)</div>', unsafe_allow_html=True)
    with bar2:
        page_size = st.selectbox("Linhas", [20, 50, 100, 200], index=1, label_visibility="collapsed")
    with bar3:
        botao_exportar_excel(df_alertas, "alertas_filtrados", label="⬇ Excel", key="exp_dash_alertas")

    if df_alertas.empty:
        st.info("Nenhum item para os filtros selecionados.")
    else:
        total_pages = max(1, math.ceil(len(df_alertas) / page_size))
        nav1, nav2 = st.columns([1, 5], gap="small")
        with nav1:
            page = st.number_input("Pág.", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
        with nav2:
            st.caption(f"Página {int(page)} de {total_pages}")
        st.dataframe(_slice_page(df_alertas, int(page), int(page_size)), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Rankings ────────────────────────────────────────────────────
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown('<div class="dash-section"><div class="dash-section-title">Setores com mais alertas</div>', unsafe_allow_html=True)
        if ranking_setores:
            st.dataframe(pd.DataFrame(ranking_setores[:15]), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta de vencimento para exibir.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="dash-section"><div class="dash-section-title">Top equipamentos críticos</div>', unsafe_allow_html=True)
        if ranking_eq:
            st.dataframe(pd.DataFrame(ranking_eq), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento crítico para exibir.")
        st.markdown("</div>", unsafe_allow_html=True)
