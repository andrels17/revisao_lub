import pandas as pd
import streamlit as st

from services import equipamentos_service, execucoes_service, responsaveis_service, revisoes_service

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
        "controle": pendencia["Controle"],
        "leitura_atual": float(pendencia["Atual"] or 0),
        "observacoes": f'Baixa rápida da pendência: {pendencia["Etapa"]}',
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


def _salvar_execucao(equipamento, responsavel, data_execucao, tipo, leitura_execucao, observacoes):
    prefill = st.session_state.get("execucao_prefill") or {}
    tipo_controle = prefill.get("controle")

    km_execucao = None
    horas_execucao = None

    if tipo == "revisao":
        if tipo_controle == "horas":
            leitura_atual = float(equipamento.get("horas_atual") or 0)
            if leitura_execucao < leitura_atual:
                st.error(f"A leitura informada não pode ser menor que a leitura atual ({leitura_atual:.0f} h).")
                return False
            horas_execucao = leitura_execucao
        else:
            leitura_atual = float(equipamento.get("km_atual") or 0)
            if leitura_execucao < leitura_atual:
                st.error(f"A leitura informada não pode ser menor que a leitura atual ({leitura_atual:.0f} km).")
                return False
            km_execucao = leitura_execucao
    else:
        km_execucao = float(equipamento.get("km_atual") or 0)
        horas_execucao = float(equipamento.get("horas_atual") or 0)

    execucoes_service.criar_execucao(
        {
            "equipamento_id": equipamento["id"],
            "responsavel_id": responsavel["id"],
            "tipo": tipo,
            "data_execucao": data_execucao,
            "km_execucao": km_execucao,
            "horas_execucao": horas_execucao,
            "observacoes": observacoes,
            "status": "concluida",
        }
    )
    st.session_state.pop("execucao_prefill", None)
    st.success("Execução registrada com sucesso.")
    st.rerun()
    return True


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

    tipo_padrao = prefill.get("tipo", "revisao")
    controle = prefill.get("controle")
    origem = prefill.get("origem")
    leitura_padrao = float(prefill.get("leitura_atual") or 0)

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
                    index=0 if tipo_padrao == "revisao" else 1,
                    key=f"{form_key}_tipo",
                )
            with col2:
                data_execucao = st.date_input("Data da execução", key=f"{form_key}_data")
                leitura_execucao = st.number_input(
                    "Leitura executada",
                    min_value=0.0,
                    value=leitura_padrao,
                    step=1.0,
                    key=f"{form_key}_leitura",
                )
            with col3:
                st.text_input(
                    "Controle",
                    value=controle or equipamento.get("tipo") or "-",
                    disabled=True,
                    key=f"{form_key}_controle",
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
                    index=0 if tipo_padrao == "revisao" else 1,
                    key=f"{form_key}_tipo",
                )
                data_execucao = st.date_input("Data da execução", key=f"{form_key}_data")
            with col2:
                leitura_execucao = st.number_input(
                    "Leitura executada",
                    min_value=0.0,
                    value=leitura_padrao,
                    step=1.0,
                    key=f"{form_key}_leitura",
                )
                st.text_input(
                    "Controle",
                    value=controle or equipamento.get("tipo") or "-",
                    disabled=True,
                    key=f"{form_key}_controle",
                )

        observacoes = st.text_area(
            "Observações",
            value=prefill.get("observacoes", ""),
            key=f"{form_key}_observacoes",
        )
        salvar = st.form_submit_button("Salvar execução", use_container_width=True)

        if salvar:
            _salvar_execucao(
                equipamento=equipamento,
                responsavel=responsavel,
                data_execucao=data_execucao,
                tipo=tipo,
                leitura_execucao=leitura_execucao,
                observacoes=observacoes,
            )


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
            f"**{item['Equipamento']}**  \n{item['Etapa']} · {item['Controle']}"
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
        equipamentos = [item for item in equipamentos_service.listar() if item["id"] == equipamento_id]
        if equipamentos:
            with st.container(border=True):
                st.markdown("**Executar pendência selecionada**")
                _render_form_execucao(equipamentos, responsaveis, "form_execucao_rapida", compacta=True)


def _render_pendencias(pendencias_df, responsaveis):
    st.subheader("Próximas revisões")

    if pendencias_df.empty:
        st.info("Nenhum dado encontrado.")
        return

    df = pendencias_df.copy()
    setores = sorted(df["setor"].dropna().unique().tolist())

    col1, col2 = st.columns([2, 1])
    with col1:
        setores_selecionados = st.multiselect("Filtrar por setor", setores, key="pendencias_setor")
    with col2:
        status_filtro = st.selectbox(
            "Filtrar por status",
            ["Todos", "VENCIDO", "PROXIMO", "EM DIA"],
            key="pendencias_status",
        )

    if setores_selecionados:
        df = df[df["setor"].isin(setores_selecionados)]
    if status_filtro != "Todos":
        df = df[df["Status"] == status_filtro]

    if df.empty:
        st.info("Nenhuma pendência para os filtros selecionados.")
        return

    df_tabela = df.rename(columns={"setor": "Setor"}).copy()
    if "equipamento_id" in df_tabela.columns:
        df_tabela = df_tabela.drop(columns=["equipamento_id"])
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

        dados = execucoes_service.listar_por_equipamento(equipamento["id"])
        if dados:
            st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum histórico para este equipamento.")


def render():
    st.title("Controle de Revisões")

    equipamentos = equipamentos_service.listar()
    responsaveis = [item for item in responsaveis_service.listar() if item.get("ativo", True)]

    pendencias_df = _carregar_pendencias()

    tab1, tab2, tab3 = st.tabs(["Pendências", "Registrar execução", "Histórico"])

    with tab1:
        _render_pendencias(pendencias_df, responsaveis)

    with tab2:
        _render_registro_execucao(equipamentos, responsaveis)

    with tab3:
        _render_historico(equipamentos)
