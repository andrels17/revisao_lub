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


def _carregar_pendencias():
    dados = revisoes_service.listar_controle_revisoes()
    if not dados:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "equipamento_id": item["equipamento_id"],
                "setor": item["setor_nome"] or "-",
                "Equipamento": f'{item["codigo"]} - {item["equipamento_nome"]}',
                "Etapa": item["etapa"],
                "Controle": item["tipo_controle"] or "-",
                "Atual": float(item["leitura_atual"] or 0),
                "Última execução": float(item["ultima_execucao"] or 0),
                "Vencimento": float(item["vencimento"] or 0),
                "Status": item["status"],
                "Falta": float(item["falta"] or 0),
                "observacoes_sugeridas": f'Baixa rápida da pendência: {item["etapa"]}',
                "_ordem": STATUS_ORDEM.get(item["status"], 99),
            }
            for item in dados
        ]
    )

    return df.sort_values(by=["_ordem", "Falta", "Equipamento"]).drop(columns=["_ordem"])


def _formatar_equipamento(equipamento):
    return f'{equipamento["codigo"]} - {equipamento["nome"]}'


def _formatar_responsavel(responsavel):
    return responsavel["nome"]


def _set_prefill(pendencia):
    st.session_state["execucao_prefill"] = {
        "equipamento_id": pendencia["equipamento_id"],
        "tipo": "revisao",
        "observacoes": pendencia.get("observacoes_sugeridas") or f'Baixa rápida da pendência: {pendencia["Etapa"]}',
        "origem": f'{pendencia["Equipamento"]} | {pendencia["Etapa"]}',
    }


def _obter_prefill_equipamento(equipamentos):
    prefill = st.session_state.get("execucao_prefill") or {}
    equipamento_id = prefill.get("equipamento_id")
    if not equipamento_id:
        return equipamentos[0] if equipamentos else None

    for equipamento in equipamentos:
        if equipamento["id"] == equipamento_id:
            return equipamento

    return equipamentos[0] if equipamentos else None


def _render_form_execucao(equipamentos, responsaveis, form_key, compacta=False):
    if not equipamentos:
        st.info("Cadastre equipamentos antes de registrar execuções.")
        return

    if not responsaveis:
        st.info("Cadastre responsáveis antes de registrar execuções.")
        return

    prefill = st.session_state.get("execucao_prefill") or {}
    equipamento_padrao = _obter_prefill_equipamento(equipamentos)
    if equipamento_padrao is None:
        st.info("Nenhum equipamento cadastrado.")
        return

    equipamento_index = next(
        (i for i, item in enumerate(equipamentos) if item["id"] == equipamento_padrao["id"]),
        0,
    )

    origem = prefill.get("origem")
    if origem:
        st.caption(f"Pendência selecionada: {origem}")

    with st.form(form_key, clear_on_submit=False):
        equipamento = st.selectbox(
            "Equipamento",
            options=equipamentos,
            index=equipamento_index,
            format_func=_formatar_equipamento,
            key=f"{form_key}_equipamento",
        )

        if compacta:
            col1, col2, col3 = st.columns(3)
            with col1:
                responsavel = st.selectbox(
                    "Responsável",
                    options=responsaveis,
                    format_func=_formatar_responsavel,
                    key=f"{form_key}_responsavel",
                )
                tipo = st.selectbox(
                    "Tipo",
                    ["revisao", "lubrificacao"],
                    index=0 if prefill.get("tipo", "revisao") == "revisao" else 1,
                    key=f"{form_key}_tipo",
                )
            with col2:
                data_execucao = st.date_input("Data da execução", key=f"{form_key}_data")
                km_execucao = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(equipamento.get("km_atual") or 0),
                    step=1.0,
                    key=f"{form_key}_km",
                )
            with col3:
                horas_execucao = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(equipamento.get("horas_atual") or 0),
                    step=1.0,
                    key=f"{form_key}_horas",
                )
                status = st.selectbox(
                    "Status",
                    ["concluida", "pendente"],
                    key=f"{form_key}_status",
                )
        else:
            col1, col2 = st.columns(2)
            with col1:
                responsavel = st.selectbox(
                    "Responsável",
                    options=responsaveis,
                    format_func=_formatar_responsavel,
                    key=f"{form_key}_responsavel",
                )
                tipo = st.selectbox(
                    "Tipo",
                    ["revisao", "lubrificacao"],
                    index=0 if prefill.get("tipo", "revisao") == "revisao" else 1,
                    key=f"{form_key}_tipo",
                )
                data_execucao = st.date_input("Data da execução", key=f"{form_key}_data")
            with col2:
                km_execucao = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(equipamento.get("km_atual") or 0),
                    step=1.0,
                    key=f"{form_key}_km",
                )
                horas_execucao = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(equipamento.get("horas_atual") or 0),
                    step=1.0,
                    key=f"{form_key}_horas",
                )
                status = st.selectbox(
                    "Status",
                    ["concluida", "pendente"],
                    key=f"{form_key}_status",
                )

        observacoes = st.text_area(
            "Observações",
            value=prefill.get("observacoes", ""),
            key=f"{form_key}_observacoes",
        )
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
            st.session_state.pop("execucao_prefill", None)
            st.success("Execução registrada com sucesso.")
            st.rerun()


def _render_baixa_rapida(df, responsaveis):
    st.subheader("Baixa operacional rápida")
    st.caption("Selecione uma pendência e já registre a execução sem sair da tela.")

    registros = df.to_dict("records")[:30]
    if not registros:
        st.info("Nenhuma pendência disponível para execução rápida.")
        return

    for idx, item in enumerate(registros):
        col1, col2, col3, col4, col5 = st.columns([3.3, 1.2, 1.1, 1.1, 1.2])
        col1.markdown(
            f"**{item['Equipamento']}**  \n"
            f"{item['Etapa']} · {item['Controle']}"
        )
        col2.markdown(f"**Setor**  \n{item['setor']}")
        col3.markdown(f"**Atual**  \n{item['Atual']:.0f}")
        col4.markdown(f"**Venc.**  \n{item['Vencimento']:.0f}")
        col5.button(
            "Executar",
            key=f"executar_pendencia_{idx}",
            use_container_width=True,
            on_click=_set_prefill,
            args=(item,),
        )

    prefill = st.session_state.get("execucao_prefill")
    if prefill:
        equipamento_id = prefill.get("equipamento_id")
        equipamentos = [
            item for item in equipamentos_service.listar() if item["id"] == equipamento_id
        ]
        if equipamentos:
            with st.container(border=True):
                st.markdown("**Executar pendência selecionada**")
                _render_form_execucao(equipamentos, responsaveis, "form_execucao_rapida", compacta=True)


def _render_pendencias(pendencias_df, equipamentos, responsaveis):
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

    df_tabela = df.rename(columns={"setor": "Setor"}).copy()
    df_tabela["Status"] = df_tabela["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)

    st.divider()
    _render_baixa_rapida(df, responsaveis)


def _render_registro_execucao(equipamentos, responsaveis):
    st.subheader("Registrar execução")
    _render_form_execucao(equipamentos, responsaveis, "form_execucao_principal")


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
        _render_pendencias(pendencias_df, equipamentos, responsaveis)

    with tab2:
        _render_registro_execucao(equipamentos, responsaveis)

    with tab3:
        _render_historico(equipamentos)
