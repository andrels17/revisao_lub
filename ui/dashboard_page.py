import math

import pandas as pd
import streamlit as st

from services import dashboard_service
from ui.constants import STATUS_LABEL
from ui.exportacao import botao_exportar_excel


PLOTLY_COLORS = {
    "vencidos": "#ef4444",
    "proximos": "#f59e0b",
    "em_dia": "#38bdf8",
    "axis": "rgba(157,176,199,.34)",
    "grid": "rgba(157,176,199,.12)",
    "font": "#dbe9ff",
    "muted": "#9db0c7",
}


def _inject_styles():
    st.markdown(
        """
        <style>
        .modern-hero{
            padding: 1.15rem 1.2rem;
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(12,24,42,.98), rgba(18,35,58,.96));
            color: #f8fbff;
            box-shadow: 0 18px 50px rgba(0,0,0,.24);
            margin-bottom: 1.1rem;
        }
        .modern-hero h2{margin:0;font-size:1.35rem;font-weight:700;}
        .modern-hero p{margin:.35rem 0 0 0;color:#c0d0e6;font-size:.92rem;}
        .mini-card{
            position:relative;
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 18px;
            padding: 1.02rem 1rem 1rem 1rem;
            background: linear-gradient(180deg, rgba(15,27,45,.98), rgba(19,35,58,.98));
            box-shadow: 0 14px 30px rgba(0,0,0,.20);
            min-height: 126px;
            margin-bottom: 1.1rem;
            overflow:hidden;
        }
        .mini-card::before{
            content:"";
            position:absolute;
            left:0;top:0;right:0;height:3px;
            background: linear-gradient(90deg, rgba(79,140,255,.92), rgba(56,189,248,.82));
        }
        .mini-card .label{font-size:.80rem;color:#9bb2cc;margin-bottom:.45rem;}
        .mini-card .value{font-size:1.85rem;font-weight:800;color:#edf4ff;line-height:1.1;}
        .mini-card .hint{font-size:.78rem;color:#7389a4;margin-top:.5rem;}
        .section-card{
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 20px;
            padding: 1.05rem 1rem .95rem 1rem;
            background: linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow: 0 14px 30px rgba(0,0,0,.18);
            margin-top: .22rem;
        }
        .section-card h3{margin-top:.08rem;margin-bottom:.75rem;}
        .pill{
            display:inline-block;
            padding:.18rem .55rem;
            border-radius:999px;
            font-size:.72rem;
            font-weight:700;
            background:rgba(79,140,255,.12);
            border:1px solid rgba(79,140,255,.18);
            color:#dcebff;
            margin-right:.35rem;
        }
        .dashboard-block-gap{height:.22rem;}
        .table-note{color:#7f93ad;font-size:.78rem;margin-top:.15rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero(total_alertas: int):
    st.markdown(
        f"""
        <div class="modern-hero">
            <div class="pill">Dashboard executivo</div>
            <h2>Visão rápida das pendências de manutenção</h2>
            <p>Alertas consolidados de revisão e lubrificação. Total atual: <strong>{total_alertas}</strong> item(ns).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value, hint: str = ""):
    st.markdown(
        f"""
        <div class="mini-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(kpis):
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        _metric_card("Total de equipamentos", kpis["total_equipamentos"], "Base monitorada")
    with c2:
        _metric_card("Alertas vencidos", kpis["vencidos"], "Maior urgência")
    with c3:
        _metric_card("Alertas próximos", kpis["proximos"], "Janela de atenção")
    with c4:
        _metric_card("Itens em dia", kpis["em_dia"], "Status saudável")

    st.markdown('<div class="dashboard-block-gap"></div>', unsafe_allow_html=True)
    c5, c6, c7 = st.columns(3, gap="medium")
    with c5:
        _metric_card("Equipamentos com alerta", kpis["equipamentos_com_alerta"], "Vencidos ou próximos")
    with c6:
        _metric_card("Equipamentos vencidos", kpis["equipamentos_vencidos"], "Ao menos 1 item vencido")
    with c7:
        _metric_card("Equipamentos próximos", kpis["equipamentos_proximos"], "Ao menos 1 item próximo")


def _apply_plotly_theme(fig, height: int):
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PLOTLY_COLORS["font"], size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOTLY_COLORS["muted"]),
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

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.62,
                    textinfo="label+percent",
                    textfont=dict(color="#eaf2ff", size=12),
                    hovertemplate="%{label}: %{value}<extra></extra>",
                    marker=dict(
                        colors=[
                            PLOTLY_COLORS["vencidos"],
                            PLOTLY_COLORS["proximos"],
                            PLOTLY_COLORS["em_dia"],
                        ],
                        line=dict(color="rgba(7,17,31,.95)", width=3),
                    ),
                )
            ]
        )
        _apply_plotly_theme(fig, 300)
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
        fig.add_trace(
            go.Bar(
                name="Vencidos",
                x=df["Vencidos"],
                y=df["Setor"],
                orientation="h",
                marker=dict(color=PLOTLY_COLORS["vencidos"]),
                hovertemplate="%{y}: %{x} vencido(s)<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Próximos",
                x=df["Próximos"],
                y=df["Setor"],
                orientation="h",
                marker=dict(color=PLOTLY_COLORS["proximos"]),
                hovertemplate="%{y}: %{x} próximo(s)<extra></extra>",
            )
        )
        _apply_plotly_theme(fig, max(300, 42 * len(df)))
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

    df = pd.DataFrame(alertas)[[
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


def _slice_page(df: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    if df.empty:
        return df
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return df.iloc[start:end]


def render():
    _inject_styles()

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.title("📊 Dashboard")
    with top_right:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega dados do banco"):
            dashboard_service.carregar_alertas.clear()
            st.rerun()

    with st.spinner("Carregando dados…"):
        alertas, total_equipamentos = dashboard_service.carregar_alertas()

    kpis = dashboard_service.resumo_kpis(alertas, total_equipamentos)
    _hero(kpis["total_alertas"])
    _render_cards(kpis)

    if not alertas:
        st.info("Nenhum alerta encontrado. Verifique se os equipamentos possuem template configurado.")
        return

    ranking_setores = dashboard_service.ranking_setores(alertas)
    ranking_eq = dashboard_service.ranking_equipamentos_criticos(alertas)

    col_g1, col_g2 = st.columns([1, 1.4], gap="medium")
    with col_g1:
        with st.container(border=False):
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Distribuição")
            _grafico_status(kpis)
            st.markdown("</div>", unsafe_allow_html=True)
    with col_g2:
        with st.container(border=False):
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Setores prioritários")
            _grafico_setores(ranking_setores)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="dashboard-block-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Filtros rápidos")
    f1, f2, f3, f4 = st.columns([2.2, 1.1, 1.1, 1], gap="medium")
    setores = sorted({item.get("setor") or "-" for item in alertas})

    with f1:
        busca = st.text_input("Buscar equipamento / etapa", placeholder="Código, nome ou item")
    with f2:
        setor_filtro = st.multiselect("Setor", setores)
    with f3:
        origem_filtro = st.selectbox("Origem", ["Todas", "Revisão", "Lubrificação"])
    with f4:
        status_filtro = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA"])

    termo = (busca or "").strip().lower()
    filtrados = alertas
    if termo:
        filtrados = [
            a for a in filtrados
            if termo in f'{a.get("equipamento_label","")} {a.get("etapa","")} {a.get("setor","")}'.lower()
        ]
    if setor_filtro:
        filtrados = [a for a in filtrados if (a.get("setor") or "-") in setor_filtro]
    if origem_filtro != "Todas":
        filtrados = [a for a in filtrados if a.get("origem") == origem_filtro]
    if status_filtro != "Todos":
        filtrados = [a for a in filtrados if a.get("status") == status_filtro]
    st.markdown("</div>", unsafe_allow_html=True)

    df_alertas = _formatar_alertas_df(filtrados)

    st.write("")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    bar1, bar2, bar3 = st.columns([3, 1.2, 1], gap="medium")
    with bar1:
        st.subheader(f"Pendências e próximos vencimentos ({len(df_alertas)})")
        st.markdown('<div class="table-note">Tabela em tema escuro para reduzir o brilho e melhorar a leitura.</div>', unsafe_allow_html=True)
    with bar2:
        page_size = st.selectbox("Linhas por página", [20, 50, 100, 200], index=1)
    with bar3:
        botao_exportar_excel(df_alertas, "alertas_filtrados", label="⬇️ Excel", key="exp_dash_alertas")

    if df_alertas.empty:
        st.info("Nenhum item para os filtros selecionados.")
    else:
        total_pages = max(1, math.ceil(len(df_alertas) / page_size))
        nav1, nav2, nav3 = st.columns([1, 1, 4], gap="medium")
        with nav1:
            page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
        with nav2:
            st.caption(f"de {total_pages}")
        with nav3:
            st.caption("Paginação aplicada para deixar a tela mais leve com bases grandes.")

        st.dataframe(_slice_page(df_alertas, int(page), int(page_size)), use_container_width=True, hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="dashboard-block-gap"></div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Setores com mais alertas")
        if ranking_setores:
            st.dataframe(pd.DataFrame(ranking_setores[:15]), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta de vencimento ou proximidade para exibir.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top equipamentos críticos")
        if ranking_eq:
            st.dataframe(pd.DataFrame(ranking_eq), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento crítico para os filtros selecionados.")
        st.markdown("</div>", unsafe_allow_html=True)
