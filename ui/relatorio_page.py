"""
Relatório de Manutenção por Período
Exporta revisões e lubrificações realizadas em um intervalo de datas.
"""
import datetime

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


def _carregar_setores():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome from setores where ativo = true order by nome")
        return cur.fetchall()
    finally:
        release_conn(conn)


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


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">📈 Ferramentas</div>
            <h2>Relatório de manutenção</h2>
            <p>Consolide revisões e lubrificações por período, enxergue a distribuição operacional e exporte o resultado com menos ruído visual.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    total = len(df_rev) + len(df_lub)
    equipamentos = len(set(df_rev.get("Código", pd.Series(dtype=str)).tolist() + df_lub.get("Código", pd.Series(dtype=str)).tolist()))
    cards = [
        ("status-info", "📦 Total de registros", total, "Execuções no período"),
        ("status-danger", "🔧 Revisões", len(df_rev), "Itens concluídos"),
        ("status-success", "🛢️ Lubrificações", len(df_lub), "Itens concluídos"),
        ("status-warning", "🚜 Equipamentos impactados", equipamentos, "Base com execução"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{label}</div><div class='value'>{int(value)}</div><div class='sub'>{sub}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def _apply_plotly_theme(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(t=22, b=10, l=10, r=10),
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
    resumo = df.groupby(["Setor", "Tipo"]).size().reset_index(name="Qtd")

    try:
        import plotly.express as px

        fig = px.bar(
            resumo,
            x="Setor",
            y="Qtd",
            color="Tipo",
            barmode="group",
            color_discrete_map={"Revisões": PLOTLY_COLORS["rev"], "Lubrificações": PLOTLY_COLORS["lub"]},
        )
        _apply_plotly_theme(fig, 360)
        fig.update_traces(marker_line_width=0, opacity=0.95, hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pivot = resumo.pivot(index="Setor", columns="Tipo", values="Qtd").fillna(0)
        st.bar_chart(pivot, use_container_width=True)


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
        .sort_values("Qtd", ascending=False)
    )
    st.dataframe(resumo, use_container_width=True, hide_index=True)


def render():
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco", use_container_width=True):
            _carregar_revisoes.clear()
            _carregar_lubrificacoes.clear()
            st.rerun()

    st.markdown(
        "<div class='section-caption'>Filtre por período, setor e equipamento para montar uma visão executiva do que foi realizado e exportar o resultado em segundos.</div>",
        unsafe_allow_html=True,
    )

    hoje = datetime.date.today()
    st.markdown("<div class='filters-shell'><div class='filters-title'>Recorte do relatório</div>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        data_ini = st.date_input("Data inicial", value=hoje.replace(day=1), key="rel_ini")
    with col2:
        data_fim = st.date_input("Data final", value=hoje, key="rel_fim")
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
    st.markdown("</div>", unsafe_allow_html=True)

    if data_ini > data_fim:
        st.error("A data inicial deve ser anterior à data final.")
        return

    df_rev = _carregar_revisoes(data_ini, data_fim, setor_id, eqp_id)
    df_lub = _carregar_lubrificacoes(data_ini, data_fim, setor_id, eqp_id)
    _render_kpi_cards(df_rev, df_lub)

    tab_exec, tab_rev, tab_lub = st.tabs(["Visão executiva", "Revisões", "Lubrificações"])

    with tab_exec:
        col_chart, col_table = st.columns([1.2, 1], vertical_alignment="top")
        with col_chart:
            st.markdown("<div class='section-card'><h3>Distribuição por setor</h3><p>Comparativo entre revisões e lubrificações realizadas dentro do período filtrado.</p></div>", unsafe_allow_html=True)
            _render_distribution_chart(df_rev, df_lub)
        with col_table:
            st.markdown("<div class='section-card'><h3>Resumo por responsável</h3><p>Volume executado por pessoa considerando os dois tipos de manutenção.</p></div>", unsafe_allow_html=True)
            _render_responsaveis_summary(df_rev, df_lub)

    with tab_rev:
        st.markdown("<div class='section-card'><h3>Revisões realizadas</h3><p>Consulte o histórico detalhado e exporte quando precisar compartilhar ou auditar.</p></div>", unsafe_allow_html=True)
        if df_rev.empty:
            st.info("Nenhuma revisão encontrada para o período e filtros selecionados.")
        else:
            col_exp = st.columns([5, 1])[1]
            with col_exp:
                botao_exportar_excel(df_rev, "relatorio_revisoes", label="⬇️ Excel", key="exp_rel_rev")
            st.dataframe(df_rev.drop(columns=["ID"]), use_container_width=True, hide_index=True)
            with st.expander("Resumo por responsável"):
                resumo = (
                    df_rev.groupby("Responsável")
                    .agg(Qtd=("ID", "count"))
                    .reset_index()
                    .sort_values("Qtd", ascending=False)
                )
                st.dataframe(resumo, use_container_width=True, hide_index=True)

    with tab_lub:
        st.markdown("<div class='section-card'><h3>Lubrificações realizadas</h3><p>Visualize o consolidado por item lubrificado e faça a exportação com o mesmo padrão do sistema.</p></div>", unsafe_allow_html=True)
        if df_lub.empty:
            st.info("Nenhuma lubrificação encontrada para o período e filtros selecionados.")
        else:
            col_exp = st.columns([5, 1])[1]
            with col_exp:
                botao_exportar_excel(df_lub, "relatorio_lubrificacoes", label="⬇️ Excel", key="exp_rel_lub")
            st.dataframe(df_lub.drop(columns=["ID"]), use_container_width=True, hide_index=True)
            with st.expander("Resumo por item lubrificado"):
                resumo = (
                    df_lub.groupby("Item")
                    .agg(Qtd=("ID", "count"))
                    .reset_index()
                    .sort_values("Qtd", ascending=False)
                )
                st.dataframe(resumo, use_container_width=True, hide_index=True)
