import pandas as pd
import streamlit as st

from services import (
    equipamentos_service,
    execucoes_service,
    responsaveis_service,
    revisoes_service,
)


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}



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



def _render_registro_execucao(equipamentos, responsaveis):
    st.subheader("Registrar execução")

    if not equipamentos:
        st.info("Cadastre equipamentos antes de registrar execuções.")
        return

    if not responsaveis:
        st.info("Cadastre responsáveis antes de registrar execuções.")
        return

    equipamentos_map = {f'{e["codigo"]} - {e["nome"]}': e for e in equipamentos}
    responsaveis_map = {r["nome"]: r for r in responsaveis}

    with st.form("form_execucao", clear_on_submit=True):
        equipamento_label = st.selectbox("Equipamento", list(equipamentos_map.keys()))
        col1, col2 = st.columns(2)
        with col1:
            responsavel_label = st.selectbox("Responsável", list(responsaveis_map.keys()))
            tipo = st.selectbox("Tipo", ["revisao", "lubrificacao"])
            data_execucao = st.date_input("Data da execução")
        with col2:
            km_execucao = st.number_input("KM atual", min_value=0.0, value=0.0, step=1.0)
            horas_execucao = st.number_input("Horas atuais", min_value=0.0, value=0.0, step=1.0)
            status = st.selectbox("Status", ["concluida", "pendente"])

        observacoes = st.text_area("Observações")
        salvar = st.form_submit_button("Salvar execução", use_container_width=True)

        if salvar:
            equipamento = equipamentos_map[equipamento_label]
            responsavel = responsaveis_map[responsavel_label]

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
        st.dataframe(pd.DataFrame(historico), use_container_width=True)
    else:
        st.info("Nenhuma execução registrada ainda.")

    with st.expander("Histórico por equipamento"):
        equipamentos_map = {f'{e["codigo"]} - {e["nome"]}': e for e in equipamentos}
        equipamento_label = st.selectbox(
            "Selecionar equipamento",
            list(equipamentos_map.keys()),
            key="historico_equipamento",
        )
        equipamento = equipamentos_map[equipamento_label]
        dados = execucoes_service.listar_por_equipamento(equipamento["id"])
        if dados:
            st.dataframe(pd.DataFrame(dados), use_container_width=True)
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
        st.subheader("Próximas revisões")
        if not pendencias_df.empty:
            st.dataframe(pendencias_df, use_container_width=True)
        else:
            st.info("Nenhum dado encontrado.")

    with tab2:
        _render_registro_execucao(equipamentos, responsaveis)

    with tab3:
        _render_historico(equipamentos)
