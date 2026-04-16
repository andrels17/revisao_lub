import math

import pandas as pd
import streamlit as st

from services import dashboard_service, prioridades_service
from ui.constants import STATUS_LABEL
from ui.exportacao import botao_exportar_excel


PLOTLY_COLORS = {
    "vencidos": "#ef4444",
    "proximos": "#f59e0b",
    "em_dia":   "#22c55e",
    "axis":     "rgba(148,163,184,.22)",
    "grid":     "rgba(148,163,184,.08)",
    "font":     "#c8dcf4",
    "muted":    "#8fa4c0",
    "paper":    "#0d1929",
    "outline":  "rgba(148,163,184,.12)",
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
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 16px;
            padding: .9rem .95rem .85rem;
            background:
                radial-gradient(circle at top right, rgba(255,255,255,.045), transparent 36%),
                linear-gradient(180deg, rgba(16,31,52,.96), rgba(11,24,40,.98));
            min-height: 120px;
            transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
        }
        .dash-kpi:hover {
            transform: translateY(-2px);
            border-color: rgba(96,165,250,.22);
            box-shadow: 0 10px 22px rgba(2,8,23,.22);
        }
        .dash-kpi::before {
            content: "";
            position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: var(--kpi-accent, #4f8cff);
        }
        .dash-kpi::after {
            content: "";
            position: absolute;
            inset: auto -24px -24px auto;
            width: 86px;
            height: 86px;
            border-radius: 999px;
            background: radial-gradient(circle, var(--kpi-glow, rgba(79,140,255,.18)) 0%, rgba(79,140,255,0) 72%);
            pointer-events: none;
        }
        .dash-kpi-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: .75rem;
        }
        .dash-kpi-main {
            min-width: 0;
            flex: 1;
        }
        .dash-kpi .lbl  {
            font-size: .74rem;
            color: #8fa4c0;
            font-weight: 700;
            letter-spacing: .02em;
            margin-bottom: .30rem;
        }
        .dash-kpi .val  {
            font-size: 2rem;
            font-weight: 800;
            line-height: .95;
            color: #f8fbff;
            margin-bottom: .28rem;
        }
        .dash-kpi .hint {
            font-size: .73rem;
            color: #88a2bf;
            margin-top: .26rem;
            line-height: 1.3;
        }
        .dash-kpi .meta {
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            padding: .18rem .52rem;
            border-radius: 999px;
            font-size: .68rem;
            font-weight: 700;
            background: rgba(255,255,255,.04);
            border: 1px solid rgba(255,255,255,.05);
            color: #cfe0f7;
            white-space: nowrap;
        }
        .dash-kpi .icon {
            flex: 0 0 auto;
            width: 40px;
            height: 40px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            background: rgba(255,255,255,.05);
            border: 1px solid rgba(255,255,255,.06);
            box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
        }
        .dash-kpi .icon .orb {
            width: 14px;
            height: 14px;
            border-radius: 999px;
            background: var(--kpi-accent, #4f8cff);
            box-shadow: 0 0 0 4px color-mix(in srgb, var(--kpi-accent, #4f8cff) 18%, transparent);
        }
        .dash-kpi.n  {
            --kpi-accent: #4f8cff;
            --kpi-glow: rgba(79,140,255,.22);
        }
        .dash-kpi.d  {
            --kpi-accent: #ef4444;
            --kpi-glow: rgba(239,68,68,.22);
        }
        .dash-kpi.w  {
            --kpi-accent: #f59e0b;
            --kpi-glow: rgba(245,158,11,.22);
        }
        .dash-kpi.s  {
            --kpi-accent: #22c55e;
            --kpi-glow: rgba(34,197,94,.22);
        }

        /* Section wrapper */
        .dash-section {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem .85rem .75rem;
            background: #0d1929;
            margin-bottom: .75rem;
            animation: dashFadeUp .32s ease-out;
            will-change: transform, opacity;
            transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
        }
        .dash-section:hover {
            transform: translateY(-1px);
            border-color: rgba(96,165,250,.18);
            box-shadow: 0 10px 24px rgba(3,8,20,.18);
        }
        @keyframes dashFadeUp {
            from { opacity: 0; transform: translateY(6px); }
            to   { opacity: 1; transform: translateY(0); }
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


        .dash-prio-grid {
            display:grid;
            grid-template-columns: 1.15fr .85fr;
            gap: .7rem;
            margin-bottom: .75rem;
        }
        .dash-prio-box {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 14px;
            background: #0d1929;
            padding: .85rem .95rem;
        }
        .dash-prio-head {
            display:flex; align-items:flex-start; justify-content:space-between; gap:.75rem; margin-bottom:.65rem;
        }
        .dash-prio-head h3 { margin:0; font-size:.98rem; font-weight:800; color:#f8fbff; }
        .dash-prio-head p { margin:.18rem 0 0; color:#8fa4c0; font-size:.76rem; }
        .dash-prio-link {
            display:inline-flex; align-items:center; justify-content:center;
            min-height:36px; padding:0 .8rem; border-radius:10px;
            border:1px solid rgba(79,140,255,.16); background:rgba(79,140,255,.08);
            color:#dbeafe; font-weight:700; font-size:.74rem; white-space:nowrap;
        }
        .dash-prio-mini-grid {
            display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.5rem;
        }
        .dash-prio-mini {
            border:1px solid rgba(148,163,184,.10); border-radius:12px; padding:.7rem .75rem; background:rgba(15,23,42,.58);
        }
        .dash-prio-mini .lbl { font-size:.68rem; color:#8fa4c0; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
        .dash-prio-mini .val { font-size:1.35rem; font-weight:800; color:#f8fbff; margin:.18rem 0 .15rem; }
        .dash-prio-mini .sub { font-size:.72rem; color:#89a2bd; }
        .dash-prio-mini.danger .val { color:#fca5a5; }
        .dash-prio-mini.warn .val { color:#fcd34d; }
        .dash-prio-mini.info .val { color:#93c5fd; }
        .dash-prio-mini.ok .val { color:#86efac; }
        .dash-prio-list { display:flex; flex-direction:column; gap:.5rem; }
        .dash-prio-item {
            border:1px solid rgba(148,163,184,.10); border-radius:12px; padding:.72rem .8rem; background:rgba(15,23,42,.58);
        }
        .dash-prio-item-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.65rem; }
        .dash-prio-item-title { font-size:.84rem; font-weight:800; color:#eff6ff; }
        .dash-prio-item-desc { font-size:.74rem; color:#8fa4c0; margin-top:.14rem; }
        .dash-prio-pill { display:inline-flex; align-items:center; padding:.13rem .48rem; border-radius:999px; font-size:.66rem; font-weight:700; }
        .dash-prio-pill.danger { background:rgba(239,68,68,.10); color:#fecaca; }
        .dash-prio-pill.warn { background:rgba(245,158,11,.10); color:#fde68a; }
        .dash-prio-pill.info { background:rgba(96,165,250,.10); color:#bfdbfe; }
        .dash-prio-meta { display:flex; flex-wrap:wrap; gap:.3rem; margin-top:.42rem; }
        .dash-prio-chip { display:inline-flex; align-items:center; padding:.13rem .42rem; border-radius:999px; font-size:.66rem; font-weight:700; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.05); color:#dbeafe; }
        @media (max-width: 900px) {
            .dash-prio-grid { grid-template-columns:1fr; }
            .dash-prio-mini-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
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
            <div class="badge">Painel operacional</div>
            <h2>Pendências de manutenção</h2>
            <p>Alertas consolidados de revisão e lubrificação · <strong>{total_alertas}</strong> item(ns) no total</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value, hint: str = "", cls: str = "", meta: str = ""):
    css = f"dash-kpi {cls}".strip()
    meta_html = f'<div class="meta">{meta}</div>' if meta else ""
    st.markdown(
        f"""
        <div class="{css}">
            <div class="dash-kpi-top">
                <div class="dash-kpi-main">
                    <div class="lbl">{label}</div>
                    <div class="val">{value}</div>
                    {meta_html}
                    <div class="hint">{hint}</div>
                </div>
                <div class="icon"><span class="orb"></span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(kpis):
    total_alertas = int(kpis["vencidos"] + kpis["proximos"])
    total_equip = max(int(kpis["total_equipamentos"]), 1)
    pct_alerta = round((int(kpis["equipamentos_com_alerta"]) / total_equip) * 100)
    pct_vencidos = round((int(kpis["vencidos"]) / max(total_alertas or 1, 1)) * 100) if total_alertas else 0
    pct_proximos = round((int(kpis["proximos"]) / max(total_alertas or 1, 1)) * 100) if total_alertas else 0
    pct_em_dia = round((int(kpis["em_dia"]) / max(int(kpis["em_dia"]) + total_alertas, 1)) * 100)

    st.markdown('<div class="dash-kpi-grid">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        _kpi("Equipamentos", kpis["total_equipamentos"], "Base monitorada no dashboard", "n", "Visão geral")
    with c2:
        _kpi("Alertas vencidos", kpis["vencidos"], "Itens que já passaram do ponto de execução", "d", f"{pct_vencidos}% dos alertas")
    with c3:
        _kpi("Alertas próximos", kpis["proximos"], "Itens entrando na janela de atenção", "w", f"{pct_proximos}% dos alertas")
    with c4:
        _kpi("Itens em dia", kpis["em_dia"], "Pendências saudáveis no ciclo atual", "s", f"{pct_em_dia}% do total")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="dash-kpi-grid three">', unsafe_allow_html=True)
    c5, c6, c7 = st.columns(3, gap="small")
    with c5:
        _kpi("Equip. com alerta", kpis["equipamentos_com_alerta"], "Ao menos um item vencido ou próximo", "d", f"{pct_alerta}% da frota")
    with c6:
        _kpi("Equip. vencidos", kpis["equipamentos_vencidos"], "Equipamentos com criticidade imediata", "d", "Ação prioritária")
    with c7:
        _kpi("Equip. próximos", kpis["equipamentos_proximos"], "Equipamentos que merecem acompanhamento", "w", "Prevenção operacional")
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
            traceorder="normal",
        ),
        transition=dict(duration=260, easing="cubic-in-out"),
        hoverlabel=dict(
            bgcolor="#0b1525",
            bordercolor=PLOTLY_COLORS["outline"],
            font=dict(color="#e8f1ff", size=12),
        ),
    )
    return fig


def _grafico_status(kpis):
    labels = ["Vencidos", "Próximos", "Em dia"]
    values = [kpis["vencidos"], kpis["proximos"], kpis["em_dia"]]
    total = sum(values)
    if total == 0:
        st.info("Sem distribuição para exibir.")
        return
    try:
        import plotly.graph_objects as go
        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.72,
                sort=False,
                direction="clockwise",
                texttemplate="%{value} · %{percent}",
                textposition="outside",
                textfont=dict(color="#d9e8ff", size=12),
                hovertemplate="%{label}: %{value} item(ns) · %{percent}<extra></extra>",
                marker=dict(
                    colors=[PLOTLY_COLORS["vencidos"], PLOTLY_COLORS["proximos"], PLOTLY_COLORS["em_dia"]],
                    line=dict(color="#07111f", width=3),
                ),
                pull=[0.02, 0.0, 0.0],
                automargin=True,
            )
        ])
        _apply_plotly_theme(fig, 290)
        fig.update_layout(
            showlegend=True,
            legend=dict(y=-0.14),
            margin=dict(t=8, b=42, l=8, r=8),
            uniformtext_minsize=11,
            uniformtext_mode="hide",
            annotations=[
                dict(
                    text=f"<b>{total}</b><br><span style='font-size:12px;color:{PLOTLY_COLORS['muted']}'>alertas</span>",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(color="#f8fbff", size=24),
                    align="center",
                )
            ],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        st.bar_chart(pd.DataFrame({"Status": labels, "Qtd": values}).set_index("Status"))

def _grafico_setores(ranking):
    if not ranking:
        st.info("Sem setores com pendências relevantes.")
        return
    df = pd.DataFrame(ranking[:10]).copy()
    df["Total"] = df[["Vencidos", "Próximos"]].sum(axis=1)
    df = df.sort_values(["Total", "Vencidos", "Próximos"], ascending=[True, True, True])
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Próximos",
            x=df["Próximos"],
            y=df["Setor"],
            orientation="h",
            marker=dict(color=PLOTLY_COLORS["proximos"]),
            cliponaxis=False,
            hovertemplate="%{y}: %{x} próximo(s)<extra></extra>",
            offsetgroup="alertas",
        ))
        fig.add_trace(go.Bar(
            name="Vencidos",
            x=df["Vencidos"],
            y=df["Setor"],
            orientation="h",
            marker=dict(color=PLOTLY_COLORS["vencidos"]),
            cliponaxis=False,
            hovertemplate="%{y}: %{x} vencido(s)<extra></extra>",
            offsetgroup="alertas",
        ))
        fig.add_trace(go.Scatter(
            x=df["Total"],
            y=df["Setor"],
            mode="text",
            text=df["Total"].map(lambda v: f"{int(v)}"),
            textposition="middle right",
            textfont=dict(color="#e8f1ff", size=13),
            hoverinfo="skip",
            showlegend=False,
            cliponaxis=False,
        ))
        _apply_plotly_theme(fig, max(290, 46 * len(df)))
        fig.update_layout(
            barmode="stack",
            bargap=0.38,
            margin=dict(t=8, b=36, l=8, r=28),
            xaxis_title=None,
            yaxis_title=None,
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showline=False,
                ticks="",
                showticklabels=False,
                fixedrange=True,
                rangemode="tozero",
            ),
            yaxis=dict(
                autorange="reversed",
                showgrid=False,
                zeroline=False,
                showline=False,
                ticks="",
                tickfont=dict(color="#e8f1ff", size=12),
                fixedrange=True,
            ),
            legend=dict(y=-0.16),
        )
        max_total = max(df["Total"].max(), 1)
        fig.update_xaxes(range=[0, max_total * 1.22])
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False, "staticPlot": False},
        )
        st.caption("Rótulo ao fim da barra = total de alertas por setor.")
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




def _prio_css(status: str) -> str:
    return {"VENCIDO": "danger", "PROXIMO": "warn", "SEM_LEITURA": "info"}.get((status or "").upper(), "ok")


def _prio_label(status: str) -> str:
    return {"VENCIDO": "Vencido", "PROXIMO": "Próximo", "SEM_LEITURA": "Sem leitura"}.get((status or "").upper(), status or "Em dia")


def _abrir_prioridades() -> None:
    st.session_state["pagina_atual"] = "🔥 Prioridades do Dia"
    st.rerun()


def _render_bloco_prioridades_dashboard() -> None:
    try:
        payload = prioridades_service.carregar_prioridades()
    except Exception:
        return

    resumo = payload.get("resumo") or {}
    itens = payload.get("itens") or []
    destaques = itens[:3]

    st.markdown('<div class="dash-prio-grid">', unsafe_allow_html=True)
    left, right = st.columns([1.2, .8], gap="small")
    with left:
        st.markdown('<div class="dash-prio-box">', unsafe_allow_html=True)
        head_l, head_r = st.columns([4.2, 1.1], vertical_alignment="center")
        with head_l:
            st.markdown(
                "<div class='dash-prio-head'><div><h3>Prioridades do dia</h3><p>Resumo operacional com foco no que precisa de ação imediata.</p></div></div>",
                unsafe_allow_html=True,
            )
        with head_r:
            if st.button("Abrir painel", key="dash_open_prio", use_container_width=True):
                _abrir_prioridades()
        st.markdown('<div class="dash-prio-mini-grid">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4, gap="small")
        mini = [
            ("Pendências", int(resumo.get("total_pendencias", 0)), "Tudo que pede ação hoje", "danger"),
            ("Críticos", int(resumo.get("equipamentos_criticos", 0)), "Equipamentos em risco", "warn"),
            ("Vencidos", int(resumo.get("vencidos", 0)), "Ação imediata", "danger"),
            ("Sem leitura", int(resumo.get("sem_leitura", 0)), "Janela acima de 7 dias", "info"),
        ]
        for col, (label, value, sub, css) in zip([c1,c2,c3,c4], mini):
            with col:
                st.markdown(f"<div class='dash-prio-mini {css}'><div class='lbl'>{label}</div><div class='val'>{value}</div><div class='sub'>{sub}</div></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="dash-prio-box"><div class="dash-section-title">Ações imediatas</div><div class="dash-prio-list">', unsafe_allow_html=True)
        if not destaques:
            st.success("Nenhuma prioridade aberta no momento.")
        else:
            for idx, item in enumerate(destaques):
                css = _prio_css(str(item.get("status") or ""))
                atraso = float(item.get("atraso", 0) or 0)
                falta = float(item.get("falta", 0) or 0)
                unidade = item.get("unidade") or ""
                extra = f"Atraso {atraso:.0f} {unidade}" if css == "danger" else (f"Falta {max(falta,0):.0f} {unidade}" if css == "warn" else f"{int(float(item.get('dias_sem_leitura', 0) or 0))} dia(s)")
                st.markdown(
                    f"<div class='dash-prio-item'><div class='dash-prio-item-top'><div><div class='dash-prio-item-title'>{item.get('titulo') or '-'}</div><div class='dash-prio-item-desc'>{item.get('descricao') or '-'}</div></div><span class='dash-prio-pill {css}'>{_prio_label(str(item.get('status') or ''))}</span></div><div class='dash-prio-meta'><span class='dash-prio-chip'>{item.get('origem') or '-'}</span><span class='dash-prio-chip'>{item.get('setor_nome') or '-'}</span><span class='dash-prio-chip'>{extra}</span></div></div>",
                    unsafe_allow_html=True,
                )
        st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)



def _fmt_data_curta(valor):
    if valor is None or valor == "":
        return "Sem registro"
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _render_bloco_movimentacao() -> None:
    dados = dashboard_service.carregar_movimentacao()
    kpis = dados.get("kpis") or {}
    ranking = pd.DataFrame(dados.get("ranking_rodados") or [])
    parados = pd.DataFrame(dados.get("alertas_parados") or [])
    anom = dados.get("anomalias") or {}

    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    st.markdown('<div class="dash-section-title">Movimentação e inteligência de leituras</div>', unsafe_allow_html=True)
    st.caption(
        f"Janela móvel de {int(kpis.get('janela_dias', 30) or 30)} dias · alerta de parado a partir de {int(kpis.get('threshold_parado', 0) or 0)} dia(s) sem leitura."
    )

    g1, g2, g3, g4 = st.columns(4, gap="small")
    g1.metric("Com leitura", int(kpis.get("equipamentos_com_leitura", 0) or 0))
    g2.metric("Sem leitura", int(kpis.get("equipamentos_sem_leitura", 0) or 0))
    g3.metric("Parados", int(kpis.get("equipamentos_parados", 0) or 0))
    g4.metric("Leituras na janela", int(kpis.get("leituras_na_janela", 0) or 0))

    a1, a2, a3 = st.columns(3, gap="medium")
    with a1:
        st.markdown("**Top mais rodados**")
        if ranking.empty:
            st.info("Ainda não há leituras suficientes para montar o ranking.")
        else:
            ranking = ranking.copy()
            ranking["Última leitura"] = ranking["Última leitura"].apply(_fmt_data_curta)
            st.dataframe(ranking, use_container_width=True, hide_index=True)
    with a2:
        st.markdown("**Top equipamentos parados**")
        if parados.empty:
            st.success("Nenhum equipamento parado acima da janela configurada.")
        else:
            parados = parados.copy()
            parados["Última leitura"] = parados["Última leitura"].apply(_fmt_data_curta)
            st.dataframe(parados, use_container_width=True, hide_index=True)
    with a3:
        st.markdown("**Inteligência automática**")
        resumo = pd.DataFrame([
            {"Detecção": "Leitura travada", "Qtd": len(anom.get("travadas", []))},
            {"Detecção": "Salto anormal", "Qtd": len(anom.get("saltos", []))},
            {"Detecção": "Inconsistência KM/H", "Qtd": len(anom.get("inconsistencias", []))},
        ])
        st.dataframe(resumo, use_container_width=True, hide_index=True)
        with st.expander("Ver detalhes da inteligência", expanded=False):
            tabs = st.tabs(["Travadas", "Saltos", "KM x Horas"])
            with tabs[0]:
                df = pd.DataFrame(anom.get("travadas") or [])
                if df.empty:
                    st.success("Nenhum travamento detectado.")
                else:
                    if "Última leitura" in df.columns:
                        df["Última leitura"] = df["Última leitura"].apply(_fmt_data_curta)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            with tabs[1]:
                df = pd.DataFrame(anom.get("saltos") or [])
                if df.empty:
                    st.success("Nenhum salto anormal detectado.")
                else:
                    if "Última leitura" in df.columns:
                        df["Última leitura"] = df["Última leitura"].apply(_fmt_data_curta)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            with tabs[2]:
                df = pd.DataFrame(anom.get("inconsistencias") or [])
                if df.empty:
                    st.success("Nenhuma inconsistência entre KM e horas detectada.")
                else:
                    if "Última leitura" in df.columns:
                        df["Última leitura"] = df["Última leitura"].apply(_fmt_data_curta)
                    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)


def render():
    _inject_styles()

    # ── Cabeçalho ──────────────────────────────────────────────────
    col_h, col_btn = st.columns([5, 1])
    with col_h:
        st.title("Painel Operacional")
    with col_btn:
        st.write("")
        if st.button("Atualizar", help="Recarrega dados do banco"):

            dashboard_service.carregar_alertas.clear()
            try:
                dashboard_service.carregar_movimentacao.clear()
            except Exception:
                pass
            try:
                prioridades_service.limpar_cache()
            except Exception:
                pass
            st.rerun()

    with st.spinner("Carregando…"):
        alertas, total_equipamentos = dashboard_service.carregar_alertas()

    kpis = dashboard_service.resumo_kpis(alertas, total_equipamentos)

    _render_cards(kpis)
    _render_bloco_prioridades_dashboard()
    _render_bloco_movimentacao()

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
