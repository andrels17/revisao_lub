import pandas as pd
import streamlit as st

from services import (
    equipamentos_service,
    execucoes_service,
    responsaveis_service,
    revisoes_service,
)


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}
STATUS_LABEL = {
    "VENCIDO": "🔴 Vencido",
    "PROXIMO": "🟡 Próximo",
    "EM DIA": "🟢 Em dia",
}


def _carregar_pendencias(equipamentos):
    dados = []
    for eqp in equipamentos:
        revisoes = revisoes_service.calcular_proximas_revisoes(eqp["id"])
        if not revisoes:
            continue

        for rev in revisoes:
            dados.append(
                {
                    "equipamento_id": eqp["id"],
                    "setor": eqp.get("setor_nome") or "-",
                    "Equipamento": f'{eqp["codigo"]} - {eqp["nome"]}',
                    "Etapa": rev["etapa"],
                    "Controle": rev.get("tipo_controle", eqp["tipo"] or "-"),
                    "Atual": rev["atual"],
                    "Última execução": rev.get("ultima_execucao", 0),
                    "Vencimento": rev["vencimento"],
                    "Status": rev["status"],
                    "Falta": rev["diferenca"],
                    "_ordem": STATUS_ORDEM.get(rev["status"], 99),
                }
            )

    if not dados:
        return pd.DataFrame()

    df = pd.DataFrame(dados)
    return df.sort_values(by=["_ordem", "Falta", "Equipamento"]).drop(columns=["_ordem"])


def _formatar_equipamento(equipamento):
    return f'{equipamento["codigo"]} - {equipamento["nome"]}'


def _formatar_responsavel(responsavel):
    return responsavel["nome"]


def _render_pendencias(pendencias_df, equipamentos):
    st.subheader("Próximas revisões")

    if pendencias_df.empty:
        st.info("Nenhum dado encontrado.")
        return

    setores = sorted({eqp.get("setor_nome") or "-" for eqp in equipamentos})
    col1, col2 = st.columns([2, 1])
    with col1:
        setores_selecionados = st.multiselect("Filtrar por setor", setores, key="pendencias_setor")
    with col2:
        status_filtro = st.selectbox("Filtrar por status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA"], key="pendencias_status")

    df = pendencias_df.copy()
    if setores_selecionados:
        df = df[df["setor"].isin(setores_selecionados)]
    if status_filtro != "Todos":
        df = df[df["Status"] == status_filtro]

    if df.empty:
        st.info("Nenhuma pendência para os filtros selecionados.")
        return

    df = df.rename(columns={"setor": "Setor"})
    df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_registro_execucao(equipamentos, responsaveis):
    st.subheader("Registrar execução")

    if not equipamentos:
        st.info("Cadastre equipamentos antes de registrar execuções.")
        return

    if not responsaveis:
        st.info("Cadastre responsáveis antes de registrar execuções.")
        return

    with st.form("form_execucao", clear_on_submit=True):
        equipamento = st.selectbox(
            "Equipamento",
            options=equipamentos,
            format_func=_formatar_equipamento,
            key="execucao_equipamento",
        )
        col1, col2 = st.columns(2)
        with col1:
            responsavel = st.selectbox(
                "Responsável",
                options=responsaveis,
                format_func=_formatar_responsavel,
                key="execucao_responsavel",
            )
            tipo = st.selectbox("Tipo", ["revisao", "lubrificacao"])
            data_execucao = st.date_input("Data da execução")
        with col2:
            km_execucao = st.number_input(
                "KM atual",
                min_value=0.0,
                value=float(equipamento.get("km_atual") or 0),
                step=1.0,
            )
            horas_execucao = st.number_input(
                "Horas atuais",
                min_value=0.0,
                value=float(equipamento.get("horas_atual") or 0),
                step=1.0,
            )
            status = st.selectbox("Status", ["concluida", "pendente"])

        observacoes = st.text_area("Observações")
        salvar = st.form_submit_button("Salvar execução", use_container_width=True)

        if salvar:
            execucoes_service.criar_execucao(
                {
                    "equipamento_id": equipamento["id"],
                    "responsavel_id": responsavel["id"],
                    "tipo": tipo,
                    "data_execucao": data_execucao,
                    "km_execucao": km_execucao,
                    "horas_execucao": horas_execucao,
                    "observacoes": observacoes,
                    "status": status,
                }
            )
            st.success("Execução registrada com sucesso.")
            st.rerun()


def _render_historico(equipamentos):
    st.subheader("Histórico de execuções")

    historico = execucoes_service.listar()
    if historico:
        st.dataframe(pd.DataFrame(historico), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma execução registrada ainda.")

    with st.expander("Histórico por equipamento"):
        if not equipamentos:
            st.info("Nenhum equipamento cadastrado.")
            return

        equipamento = st.selectbox(
            "Selecionar equipamento",
            options=equipamentos,
            format_func=_formatar_equipamento,
            key="historico_equipamento",
        )
        if not equipamento:
            st.info("Selecione um equipamento.")
            return

        dados = execucoes_service.listar_por_equipamento(equipamento["id"])
        if dados:
            st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum histórico para este equipamento.")


def render():
    st.title("Controle de Revisões")

    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()

    pendencias_df = _carregar_pendencias(equipamentos)

    tab1, tab2, tab3 = st.tabs([
        "Pendências",
        "Registrar execução",
        "Histórico",
    ])

    with tab1:
        _render_pendencias(pendencias_df, equipamentos)

    with tab2:
        _render_registro_execucao(equipamentos, responsaveis)

    with tab3:
        _render_historico(equipamentos)
