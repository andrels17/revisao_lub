"""
Relatório de Manutenção por Período
Exporta revisões e lubrificações realizadas em um intervalo de datas.
"""
import datetime

import pandas as pd
import streamlit as st

from database.connection import get_conn
from ui.exportacao import botao_exportar_excel

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


@st.cache_data(ttl=120, show_spinner=False)
def _carregar_revisoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        filtros = ["em.tipo = 'revisao'", "em.data_execucao >= %s", "em.data_execucao <= %s"]
        params  = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s"); params.append(setor_id)
        if equipamento_id:
            filtros.append("em.equipamento_id = %s"); params.append(equipamento_id)

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
            where {" and ".join(filtros)}
            order by em.data_execucao desc, e.codigo
            """,
            params,
        )
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=[
            "ID", "Data", "Código", "Equipamento", "Setor",
            "KM", "Horas", "Responsável", "Status", "Observações"
        ])
    finally:
        conn.close()


@st.cache_data(ttl=120, show_spinner=False)
def _carregar_lubrificacoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        filtros = ["el.data_execucao >= %s", "el.data_execucao <= %s"]
        params  = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s"); params.append(setor_id)
        if equipamento_id:
            filtros.append("el.equipamento_id = %s"); params.append(equipamento_id)

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
                where {" and ".join(filtros)}
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

        return pd.DataFrame(rows, columns=[
            "ID", "Data", "Código", "Equipamento", "Setor",
            "Item", "Produto", "KM", "Horas", "Responsável", "Observações"
        ])
    finally:
        conn.close()


def _carregar_setores():
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("select id, nome from setores where ativo = true order by nome")
        return cur.fetchall()
    finally:
        conn.close()


def _carregar_equipamentos(setor_id=None):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        if setor_id:
            cur.execute("select id, codigo, nome from equipamentos where ativo = true and setor_id = %s order by codigo", (setor_id,))
        else:
            cur.execute("select id, codigo, nome from equipamentos where ativo = true order by codigo")
        return cur.fetchall()
    finally:
        conn.close()


def render():
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.title("Relatório de Manutenção")
        st.caption("Consulte e exporte o histórico de revisões e lubrificações realizadas em qualquer período.")
    with col_btn:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco"):
            _carregar_revisoes.clear()
            _carregar_lubrificacoes.clear()
            st.rerun()

    # ── Filtros ───────────────────────────────────────────────────────────────
    hoje     = datetime.date.today()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        data_ini = st.date_input("Data inicial", value=hoje.replace(day=1), key="rel_ini")
    with col2:
        data_fim = st.date_input("Data final",   value=hoje,                 key="rel_fim")
    with col3:
        setores     = _carregar_setores()
        setor_opts  = [None] + list(setores)
        setor_sel   = st.selectbox("Setor", setor_opts,
                                   format_func=lambda s: "Todos" if s is None else s[1],
                                   key="rel_setor")
        setor_id    = setor_sel[0] if setor_sel else None
    with col4:
        equipamentos = _carregar_equipamentos(setor_id)
        eqp_opts     = [None] + list(equipamentos)
        eqp_sel      = st.selectbox("Equipamento", eqp_opts,
                                    format_func=lambda e: "Todos" if e is None else f"{e[1]} — {e[2]}",
                                    key="rel_eqp")
        eqp_id       = eqp_sel[0] if eqp_sel else None

    if data_ini > data_fim:
        st.error("A data inicial deve ser anterior à data final.")
        return

    # ── Abas ──────────────────────────────────────────────────────────────────
    tab_rev, tab_lub = st.tabs(["Revisões", "Lubrificações"])

    with tab_rev:
        df_rev = _carregar_revisoes(data_ini, data_fim, setor_id, eqp_id)
        st.subheader(f"Revisões realizadas — {len(df_rev)} registro(s)")
        if df_rev.empty:
            st.info("Nenhuma revisão encontrada para o período e filtros selecionados.")
        else:
            col_exp = st.columns([5, 1])[1]
            with col_exp:
                botao_exportar_excel(df_rev, "relatorio_revisoes", label="⬇️ Excel", key="exp_rel_rev")
            st.dataframe(df_rev.drop(columns=["ID"]), use_container_width=True, hide_index=True)

            # Sumário por responsável
            with st.expander("Resumo por responsável"):
                resumo = (
                    df_rev.groupby("Responsável")
                    .agg(Qtd=("ID", "count"))
                    .reset_index()
                    .sort_values("Qtd", ascending=False)
                )
                st.dataframe(resumo, use_container_width=True, hide_index=True)

    with tab_lub:
        df_lub = _carregar_lubrificacoes(data_ini, data_fim, setor_id, eqp_id)
        st.subheader(f"Lubrificações realizadas — {len(df_lub)} registro(s)")
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
