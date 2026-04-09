"""
Relatório de Manutenção por Período
Exporta revisões e lubrificações realizadas em um intervalo de datas.
"""
from __future__ import annotations

import datetime
from typing import Iterable

import pandas as pd
import streamlit as st

from database.connection import get_conn, release_conn
from ui.exportacao import botao_exportar_excel

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


PLOTLY_COLORS = {
    "rev": "#4f8cff",
    "lub": "#22c55e",
    "axis": "rgba(157,176,199,.36)",
    "grid": "rgba(157,176,199,.12)",
    "font": "#dbe9ff",
    "muted": "#9db0c7",
}


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_revisoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = ["em.tipo = 'revisao'", "em.data_execucao >= %s", "em.data_execucao <= %s"]
        params = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s")
            params.append(setor_id)
        if equipamento_id:
            filtros.append("em.equipamento_id = %s")
            params.append(equipamento_id)

        cur.execute(
            f"""
            select em.id,
                   em.data_execucao,
                   e.codigo,
                   e.nome                               as equipamento,
                   coalesce(s.nome, '-')               as setor,
                   em.km_execucao,
                   em.horas_execucao,
                   coalesce(r.nome, '-')               as responsavel,
                   coalesce(em.status, 'concluida')    as status,
                   em.observacoes
            from execucoes_manutencao em
            join equipamentos e on e.id = em.equipamento_id
            left join setores s     on s.id = e.setor_id
            left join responsaveis r on r.id = em.responsavel_id
            where {' and '.join(filtros)}
            order by em.data_execucao desc, e.codigo
            """,
            params,
        )
        rows = cur.fetchall()
        return pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Data",
                "Código",
                "Equipamento",
                "Setor",
                "KM",
                "Horas",
                "Responsável",
                "Status",
                "Observações",
            ],
        )
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_lubrificacoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = ["el.data_execucao >= %s", "el.data_execucao <= %s"]
        params = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s")
            params.append(setor_id)
        if equipamento_id:
            filtros.append("el.equipamento_id = %s")
            params.append(equipamento_id)

        try:
            cur.execute(
                f"""
                select el.id,
                       el.data_execucao,
                       e.codigo,
                       e.nome                         as equipamento,
                       coalesce(s.nome, '-')          as setor,
                       el.nome_item,
                       coalesce(el.tipo_produto, '-') as tipo_produto,
                       el.km_execucao,
                       el.horas_execucao,
                       coalesce(r.nome, '-')          as responsavel,
                       el.observacoes
                from execucoes_lubrificacao el
                join equipamentos e on e.id = el.equipamento_id
                left join setores s     on s.id = e.setor_id
                left join responsaveis r on r.id = el.responsavel_id
                where {' and '.join(filtros)}
                order by el.data_execucao desc, e.codigo
                """,
                params,
            )
            rows = cur.fetchall()
        except Exception as exc:
            if not psycopg2 or not isinstance(
                exc,
                (
                    psycopg2.errors.UndefinedTable,
                    psycopg2.errors.UndefinedColumn,
                    psycopg2.errors.UndefinedObject,
                ),
            ):
                raise
            conn.rollback()
            rows = []

        return pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Data",
                "Código",
                "Equipamento",
                "Setor",
                "Item",
                "Produto",
                "KM",
                "Horas",
                "Responsável",
                "Observações",
            ],
        )
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_setores():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome from setores where ativo = true order by nome")
        return cur.fetchall()
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_equipamentos(setor_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if setor_id:
            cur.execute(
                "select id, codigo, nome from equipamentos where ativo = true and setor_id = %s order by codigo",
                (setor_id,),
            )
        else:
            cur.execute("select id, codigo, nome from equipamentos where ativo = true order by codigo")
        return cur.fetchall()
    finally:
        release_conn(conn)


def _normalizar_base(df: pd.DataFrame, tipo_label: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Data", "Código", "Equipamento", "Setor", "Responsável", "Tipo"])
    base = df.copy()
    base["Data"] = pd.to_datetime(base["Data"], errors="coerce")
    base["Tipo"] = tipo_label
    return base


def _formatar_int(valor: float | int) -> str:
    try:
        return f"{int(valor):,}".replace(",", ".")
    except Exception:
        return "0"


def _texto_intervalo(data_ini: datetime.date, data_fim: datetime.date) -> str:
    dias = (data_fim - data_ini).days + 1
    return f"{data_ini.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')} · {dias} dia(s)"


def _render_page_header(data_ini: datetime.date, data_fim: datetime.date) -> None:
    st.markdown(
        f"""
        <div class="page-header-card report-hero-card">
            <div class="hero-topline">
                <span class="hero-chip">Relatórios</span>
                <span class="hero-chip soft">Padrão SaaS</span>
            </div>
            <div class="hero-grid">
                <div>
                    <div class="eyebrow">Operação · Manutenção</div>
                    <h2>Relatório de manutenção</h2>
                    <p>Visual executivo com filtros rápidos, KPIs consolidados e tabelas prontas para exportação.</p>
                </div>
                <div class="hero-highlight">
                    <div class="label">Período analisado</div>
                    <div class="value">{_texto_intervalo(data_ini, data_fim)}</div>
                    <div class="sub">Use os filtros abaixo para refinar setor, equipamento e busca textual.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    base_rev = _normalizar_base(df_rev, "Revisão")
    base_lub = _normalizar_base(df_lub, "Lubrificação")
    base = pd.concat([base_rev, base_lub], ignore_index=True)

    total = len(base)
    equipamentos = base["Código"].fillna("-").astype(str).nunique() if not base.empty else 0
    setores = base["Setor"].fillna("-").astype(str).nunique() if not base.empty else 0
    responsaveis = (
        base["Responsável"]
        .fillna("-")
        .astype(str)
        .replace("", "-")
        .nunique()
        if not base.empty
        else 0
    )

    cards = [
        ("status-info", "Execuções no período", total, "Total consolidado de revisões e lubrificações"),
        ("status-danger", "Revisões realizadas", len(df_rev), "Apontamentos de revisão concluídos"),
        ("status-success", "Lubrificações realizadas", len(df_lub), "Apontamentos de lubrificação concluídos"),
        ("status-warning", "Equipamentos atendidos", equipamentos, f"{_formatar_int(setores)} setor(es) com execução"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{label}</div><div class='value'>{_formatar_int(value)}</div><div class='sub'>{sub}</div></div>"
        )

    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='report-meta-strip'><span><strong>{_formatar_int(responsaveis)}</strong> responsável(is) com registro</span><span><strong>{_formatar_int(setores)}</strong> setor(es) ativos no período</span></div>",
        unsafe_allow_html=True,
    )


def _apply_plotly_theme(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(t=24, b=8, l=8, r=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PLOTLY_COLORS["font"], size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOTLY_COLORS["muted"]),
        ),
        xaxis=dict(
            showgrid=False,
            linecolor=PLOTLY_COLORS["axis"],
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=PLOTLY_COLORS["grid"],
            zeroline=False,
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        hoverlabel=dict(bgcolor="#0f1b2d", font_color="#eef5ff", bordercolor="#1f3350"),
    )
    return fig


def _render_distribution_chart(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    base = []
    if not df_rev.empty:
        rev = df_rev.copy()
        rev["Tipo"] = "Revisões"
        base.append(rev[["Setor", "Tipo"]])
    if not df_lub.empty:
        lub = df_lub.copy()
        lub["Tipo"] = "Lubrificações"
        base.append(lub[["Setor", "Tipo"]])

    if not base:
        st.info("Sem dados suficientes para gerar a visão executiva.")
        return

    df = pd.concat(base, ignore_index=True)
    resumo = (
        df.groupby(["Setor", "Tipo"])
        .size()
        .reset_index(name="Qtd")
        .sort_values(["Qtd", "Setor"], ascending=[False, True])
    )

    try:
        import plotly.express as px

        fig = px.bar(
            resumo,
            x="Setor",
            y="Qtd",
            color="Tipo",
            barmode="group",
            text="Qtd",
            color_discrete_map={"Revisões": PLOTLY_COLORS["rev"], "Lubrificações": PLOTLY_COLORS["lub"]},
        )
        _apply_plotly_theme(fig, 365)
        fig.update_traces(
            marker_line_width=0,
            opacity=0.95,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>",
        )
        fig.update_yaxes(title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pivot = resumo.pivot(index="Setor", columns="Tipo", values="Qtd").fillna(0)
        st.bar_chart(pivot, use_container_width=True)


def _render_timeline_chart(base: pd.DataFrame) -> None:
    if base.empty:
        st.info("Sem dados suficientes para gerar a evolução diária.")
        return

    resumo = (
        base.assign(Dia=base["Data"].dt.date)
        .groupby(["Dia", "Tipo"])
        .size()
        .reset_index(name="Qtd")
        .sort_values("Dia")
    )

    try:
        import plotly.express as px

        fig = px.line(
            resumo,
            x="Dia",
            y="Qtd",
            color="Tipo",
            markers=True,
            color_discrete_map={"Revisão": PLOTLY_COLORS["rev"], "Lubrificação": PLOTLY_COLORS["lub"]},
        )
        _apply_plotly_theme(fig, 320)
        fig.update_traces(line_width=3, marker_size=8, hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>")
        fig.update_yaxes(title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pivot = resumo.pivot(index="Dia", columns="Tipo", values="Qtd").fillna(0)
        st.line_chart(pivot, use_container_width=True)


def _render_top_setores(base: pd.DataFrame) -> None:
    if base.empty:
        st.info("Nenhum setor com execução no período.")
        return

    resumo = (
        base.groupby("Setor")
        .size()
        .reset_index(name="Qtd")
        .sort_values(["Qtd", "Setor"], ascending=[False, True])
        .head(6)
    )
    itens = []
    max_qtd = max(int(resumo["Qtd"].max()), 1)
    for idx, row in resumo.iterrows():
        pct = (int(row["Qtd"]) / max_qtd) * 100
        itens.append(
            f"""
            <div class="rank-item">
                <div class="rank-main">
                    <span class="rank-index">{list(resumo.index).index(idx) + 1:02d}</span>
                    <div>
                        <strong>{row['Setor']}</strong>
                        <small>{_formatar_int(row['Qtd'])} execução(ões)</small>
                    </div>
                </div>
                <div class="rank-bar"><span style="width:{pct:.1f}%"></span></div>
            </div>
            """
        )
    st.markdown("<div class='rank-list'>" + "".join(itens) + "</div>", unsafe_allow_html=True)


def _render_responsaveis_summary(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    frames = []
    if not df_rev.empty:
        r = df_rev[["Responsável"]].copy()
        r["Tipo"] = "Revisão"
        frames.append(r)
    if not df_lub.empty:
        l = df_lub[["Responsável"]].copy()
        l["Tipo"] = "Lubrificação"
        frames.append(l)

    if not frames:
        st.info("Nenhum responsável registrado no período selecionado.")
        return

    df = pd.concat(frames, ignore_index=True)
    resumo = (
        df.groupby(["Responsável", "Tipo"])
        .size()
        .reset_index(name="Qtd")
        .sort_values(["Qtd", "Responsável"], ascending=[False, True])
    )
    st.dataframe(resumo, use_container_width=True, hide_index=True)


def _render_highlights(base: pd.DataFrame) -> None:
    if base.empty:
        st.info("Sem dados para gerar destaques do período.")
        return

    setor_top = base.groupby("Setor").size().sort_values(ascending=False)
    resp_top = base.groupby("Responsável").size().sort_values(ascending=False)
    equip_top = base.groupby(["Código", "Equipamento"]).size().sort_values(ascending=False)

    highlight_cards = [
        ("Setor com maior volume", setor_top.index[0], _formatar_int(setor_top.iloc[0])),
        ("Responsável mais ativo", resp_top.index[0], _formatar_int(resp_top.iloc[0])),
        (
            "Equipamento com mais registros",
            f"{equip_top.index[0][0]} · {equip_top.index[0][1]}",
            _formatar_int(equip_top.iloc[0]),
        ),
    ]
    html = []
    for titulo, valor, qtd in highlight_cards:
        html.append(
            f"<div class='highlight-card'><div class='k'>{titulo}</div><div class='v'>{valor}</div><div class='s'>{qtd} registro(s)</div></div>"
        )
    st.markdown("<div class='highlight-grid'>" + "".join(html) + "</div>", unsafe_allow_html=True)


def _filtrar_por_busca(df: pd.DataFrame, colunas: Iterable[str], texto: str) -> pd.DataFrame:
    if df.empty or not texto:
        return df
    texto = texto.strip().lower()
    if not texto:
        return df

    mascara = pd.Series(False, index=df.index)
    for coluna in colunas:
        if coluna in df.columns:
            mascara = mascara | df[coluna].fillna("").astype(str).str.lower().str.contains(texto, na=False)
    return df[mascara].copy()


def _render_filtros_rapidos() -> tuple[datetime.date, datetime.date]:
    hoje = datetime.date.today()
    presets = {
        "Hoje": (hoje, hoje),
        "7 dias": (hoje - datetime.timedelta(days=6), hoje),
        "30 dias": (hoje - datetime.timedelta(days=29), hoje),
        "Mês atual": (hoje.replace(day=1), hoje),
        "90 dias": (hoje - datetime.timedelta(days=89), hoje),
    }
    if "relatorio_periodo_rapido" not in st.session_state:
        st.session_state.relatorio_periodo_rapido = "Mês atual"
        st.session_state.rel_ini = presets["Mês atual"][0]
        st.session_state.rel_fim = presets["Mês atual"][1]

    escolhido = st.radio(
        "Período rápido",
        options=list(presets.keys()),
        horizontal=True,
        key="relatorio_periodo_rapido",
        label_visibility="collapsed",
    )
    data_ini, data_fim = presets[escolhido]
    st.session_state.rel_ini = data_ini
    st.session_state.rel_fim = data_fim
    return data_ini, data_fim


def _render_secao_tabela(titulo: str, descricao: str, df: pd.DataFrame, nome_arquivo: str, resumo_titulo: str, resumo_df: pd.DataFrame) -> None:
    st.markdown(
        f"<div class='section-card'><h3>{titulo}</h3><p>{descricao}</p></div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info(f"Nenhum dado encontrado em {titulo.lower()} para o filtro atual.")
        return

    col_table_actions = st.columns([5, 1])[1]
    with col_table_actions:
        botao_exportar_excel(df, nome_arquivo, label="⬇️ Excel", key=f"exp_{nome_arquivo}")
    st.dataframe(df.drop(columns=["ID"], errors="ignore"), use_container_width=True, hide_index=True)
    with st.expander(resumo_titulo):
        st.dataframe(resumo_df, use_container_width=True, hide_index=True)


def _inject_local_styles() -> None:
    st.markdown(
        """
        <style>
        .report-hero-card {
            margin-bottom: .9rem;
            border-radius: 18px;
            padding: 1rem 1rem 1.05rem;
            background: linear-gradient(180deg, rgba(17,31,50,.98), rgba(13,25,41,.98));
            border: 1px solid rgba(148,163,184,.16);
            box-shadow: 0 10px 30px rgba(0,0,0,.18);
        }
        .hero-topline { display:flex; gap:.45rem; margin-bottom:.7rem; flex-wrap:wrap; }
        .hero-chip {
            display:inline-flex; align-items:center; gap:.35rem;
            padding:.24rem .62rem; border-radius:999px; font-size:.72rem; font-weight:700;
            color:#d6e6ff; background:rgba(79,140,255,.14); border:1px solid rgba(79,140,255,.22);
        }
        .hero-chip.soft { background:rgba(255,255,255,.05); border-color:rgba(148,163,184,.14); color:#9db0c7; }
        .hero-grid {
            display:grid; grid-template-columns: minmax(0, 1.8fr) minmax(280px, .9fr); gap:.9rem; align-items:stretch;
        }
        .hero-highlight {
            border:1px solid rgba(148,163,184,.12); border-radius:16px; padding:.9rem 1rem;
            background:rgba(255,255,255,.03);
        }
        .hero-highlight .label { color:#8fa4c0; font-size:.73rem; text-transform:uppercase; letter-spacing:.06em; font-weight:700; }
        .hero-highlight .value { color:#e8f1ff; font-size:1rem; font-weight:800; margin:.35rem 0 .3rem; }
        .hero-highlight .sub { color:#8fa4c0; font-size:.8rem; line-height:1.45; }
        .report-meta-strip {
            display:flex; flex-wrap:wrap; gap:.55rem; margin:-.15rem 0 .95rem;
        }
        .report-meta-strip span {
            border:1px solid rgba(148,163,184,.12); background:rgba(255,255,255,.03); color:#9db0c7;
            border-radius:999px; padding:.35rem .75rem; font-size:.78rem;
        }
        .report-meta-strip strong { color:#e8f1ff; }
        .report-shell {
            border:1px solid rgba(148,163,184,.12); border-radius:16px; background:rgba(13,25,41,.92);
            padding:.95rem 1rem 1rem; margin-bottom:.95rem;
        }
        .filters-title-inline {
            margin:0 0 .75rem; display:flex; align-items:center; justify-content:space-between; gap:.8rem; flex-wrap:wrap;
        }
        .filters-title-inline h3 { margin:0; font-size:1rem; }
        .filters-title-inline p { margin:.2rem 0 0; color:#8fa4c0; font-size:.82rem; }
        .report-card {
            border:1px solid rgba(148,163,184,.12); border-radius:16px; background:rgba(13,25,41,.92);
            padding:.9rem; height:100%;
        }
        .report-card h3 { margin:.05rem 0 .3rem; font-size:.95rem; }
        .report-card p { margin:0 0 .8rem; color:#8fa4c0; font-size:.81rem; }
        .rank-list { display:flex; flex-direction:column; gap:.55rem; }
        .rank-item {
            border:1px solid rgba(148,163,184,.10); border-radius:14px; background:rgba(255,255,255,.02); padding:.7rem .8rem;
        }
        .rank-main { display:flex; align-items:center; gap:.7rem; margin-bottom:.55rem; }
        .rank-index {
            min-width:2rem; height:2rem; display:flex; align-items:center; justify-content:center;
            border-radius:10px; background:rgba(79,140,255,.14); color:#cfe1ff; font-weight:800; font-size:.8rem;
        }
        .rank-main strong { display:block; }
        .rank-main small { color:#8fa4c0; }
        .rank-bar { height:8px; border-radius:999px; background:rgba(255,255,255,.05); overflow:hidden; }
        .rank-bar span { display:block; height:100%; border-radius:999px; background:linear-gradient(90deg, #4f8cff, #7ab0ff); }
        .highlight-grid {
            display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:.65rem; margin:.1rem 0 .95rem;
        }
        .highlight-card {
            border:1px solid rgba(148,163,184,.12); border-radius:14px; padding:.8rem .9rem;
            background:rgba(255,255,255,.025);
        }
        .highlight-card .k { color:#8fa4c0; font-size:.74rem; font-weight:700; margin-bottom:.4rem; }
        .highlight-card .v { color:#e8f1ff; font-size:.95rem; font-weight:800; line-height:1.35; }
        .highlight-card .s { color:#6b84a0; font-size:.74rem; margin-top:.25rem; }
        .stTabs [data-baseweb="tab-list"] { gap:.35rem; }
        .stTabs [data-baseweb="tab"] {
            border-radius:12px 12px 0 0; background:rgba(255,255,255,.02); border:1px solid rgba(148,163,184,.10);
            border-bottom:none; padding:.55rem .9rem;
        }
        @media (max-width: 980px) {
            .hero-grid, .highlight-grid { grid-template-columns:1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render():
    _inject_local_styles()

    top_l, top_r = st.columns([6, 1], vertical_alignment="center")
    with top_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco", use_container_width=True):
            _carregar_revisoes.clear()
            _carregar_lubrificacoes.clear()
            _carregar_setores.clear()
            _carregar_equipamentos.clear()
            st.rerun()

    with top_l:
        data_ini, data_fim = _render_filtros_rapidos()

    _render_page_header(data_ini, data_fim)

    st.markdown("<div class='report-shell'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='filters-title-inline'>
            <div>
                <h3>Filtros do relatório</h3>
                <p>Combine período, setor, equipamento e busca textual para montar uma visão mais precisa.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1.1, 1.4, 1.2])
    with col1:
        data_ini = st.date_input("Data inicial", value=st.session_state.get("rel_ini", data_ini), key="rel_ini")
    with col2:
        data_fim = st.date_input("Data final", value=st.session_state.get("rel_fim", data_fim), key="rel_fim")
    with col3:
        setores = _carregar_setores()
        setor_opts = [None] + list(setores)
        setor_sel = st.selectbox(
            "Setor",
            setor_opts,
            format_func=lambda s: "Todos" if s is None else s[1],
            key="rel_setor",
        )
        setor_id = setor_sel[0] if setor_sel else None
    with col4:
        equipamentos = _carregar_equipamentos(setor_id)
        eqp_opts = [None] + list(equipamentos)
        eqp_sel = st.selectbox(
            "Equipamento",
            eqp_opts,
            format_func=lambda e: "Todos" if e is None else f"{e[1]} — {e[2]}",
            key="rel_eqp",
        )
        eqp_id = eqp_sel[0] if eqp_sel else None
    with col5:
        busca = st.text_input(
            "Busca rápida",
            key="rel_busca_rapida",
            placeholder="Código, equipamento, setor, responsável...",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if data_ini > data_fim:
        st.error("A data inicial deve ser anterior à data final.")
        return

    with st.spinner("Carregando relatório de manutenção..."):
        df_rev = _carregar_revisoes(data_ini, data_fim, setor_id, eqp_id)
        df_lub = _carregar_lubrificacoes(data_ini, data_fim, setor_id, eqp_id)

    df_rev = _filtrar_por_busca(df_rev, ["Código", "Equipamento", "Setor", "Responsável", "Observações", "Status"], busca)
    df_lub = _filtrar_por_busca(df_lub, ["Código", "Equipamento", "Setor", "Responsável", "Observações", "Item", "Produto"], busca)

    base = pd.concat(
        [
            _normalizar_base(df_rev, "Revisão"),
            _normalizar_base(df_lub, "Lubrificação"),
        ],
        ignore_index=True,
    )

    _render_kpi_cards(df_rev, df_lub)
    _render_highlights(base)

    tab_exec, tab_rev, tab_lub = st.tabs(["Visão executiva", "Revisões", "Lubrificações"])

    with tab_exec:
        c1, c2 = st.columns([1.45, 1], vertical_alignment="top")
        with c1:
            st.markdown(
                "<div class='report-card'><h3>Distribuição por setor</h3><p>Comparativo entre revisões e lubrificações dentro do período filtrado.</p></div>",
                unsafe_allow_html=True,
            )
            _render_distribution_chart(df_rev, df_lub)
        with c2:
            st.markdown(
                "<div class='report-card'><h3>Top setores</h3><p>Setores com maior volume de execução no recorte atual.</p></div>",
                unsafe_allow_html=True,
            )
            _render_top_setores(base)

        c3, c4 = st.columns([1.2, 1], vertical_alignment="top")
        with c3:
            st.markdown(
                "<div class='report-card'><h3>Evolução diária</h3><p>Comportamento do volume executado ao longo dos dias.</p></div>",
                unsafe_allow_html=True,
            )
            _render_timeline_chart(base)
        with c4:
            st.markdown(
                "<div class='report-card'><h3>Resumo por responsável</h3><p>Volume executado por pessoa considerando os dois tipos de manutenção.</p></div>",
                unsafe_allow_html=True,
            )
            _render_responsaveis_summary(df_rev, df_lub)

    with tab_rev:
        resumo_rev = (
            df_rev.groupby(["Responsável", "Status"])
            .agg(Qtd=("ID", "count"))
            .reset_index()
            .sort_values(["Qtd", "Responsável"], ascending=[False, True])
            if not df_rev.empty
            else pd.DataFrame(columns=["Responsável", "Status", "Qtd"])
        )
        _render_secao_tabela(
            "Revisões realizadas",
            "Histórico detalhado de revisões com padrão visual mais limpo e exportação direta.",
            df_rev,
            "relatorio_revisoes",
            "Resumo por responsável e status",
            resumo_rev,
        )

    with tab_lub:
        resumo_lub = (
            df_lub.groupby(["Item", "Produto"])
            .agg(Qtd=("ID", "count"))
            .reset_index()
            .sort_values(["Qtd", "Item"], ascending=[False, True])
            if not df_lub.empty
            else pd.DataFrame(columns=["Item", "Produto", "Qtd"])
        )
        _render_secao_tabela(
            "Lubrificações realizadas",
            "Consolidado por item lubrificado com a mesma experiência de exportação do restante do sistema.",
            df_lub,
            "relatorio_lubrificacoes",
            "Resumo por item lubrificado",
            resumo_lub,
        )
