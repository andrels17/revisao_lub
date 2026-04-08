from ui.constants  import STATUS_LABEL, STATUS_ORDEM
from ui.exportacao import botao_exportar_excel
import pandas as pd
import streamlit as st
from services import equipamentos_service, responsaveis_service, lubrificacoes_service, vinculos_service



def _fmt_eqp(e):
    return f"{e['codigo']} - {e['nome']}"


def _carregar_pendencias(equipamentos):
    dados = []
    for eqp in equipamentos:
        for item in lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"]):
            dados.append({
                "equipamento_id": eqp["id"],
                "setor": eqp.get("setor_nome") or "-",
                "Equipamento": _fmt_eqp(eqp),
                "Item": item["item"],
                "Produto": item["tipo_produto"],
                "Controle": item["tipo_controle"],
                "Atual": item["atual"],
                "Última troca": item["ultima_execucao"],
                "Próxima troca": item["vencimento"],
                "Falta": item["diferenca"],
                "Status": item["status"],
                "_item_id": item["item_id"],
                "_ordem": STATUS_ORDEM.get(item["status"], 99),
            })
    if not dados:
        return pd.DataFrame()
    df = pd.DataFrame(dados)
    return df.sort_values(["_ordem", "Falta", "Equipamento"]).drop(columns=["_ordem"])


def _render_pendencias(pendencias_df, equipamentos):
    st.subheader("Pendências de Lubrificação")
    if pendencias_df.empty:
        st.info("Nenhuma lubrificação configurada. Vincule um template de lubrificação aos equipamentos.")
        return

    setores = sorted({eqp.get("setor_nome") or "-" for eqp in equipamentos})
    c1, c2 = st.columns([2, 1])
    with c1:
        setores_sel = st.multiselect("Filtrar por setor", setores, key="lub_setor")
    with c2:
        status_filtro = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA"], key="lub_status")

    df = pendencias_df.copy()
    if setores_sel:
        df = df[df["setor"].isin(setores_sel)]
    if status_filtro != "Todos":
        df = df[df["Status"] == status_filtro]

    if df.empty:
        st.info("Nenhum item para os filtros selecionados.")
        return

    df_show = df.rename(columns={"setor": "Setor"}).copy()
    df_show["Status"] = df_show["Status"].map(lambda x: STATUS_LABEL.get(x, x))
    cols = ["Equipamento", "Setor", "Item", "Produto", "Controle", "Atual", "Última troca", "Próxima troca", "Falta", "Status"]
    col_exp = st.columns([5,1])[1]
    with col_exp:
        botao_exportar_excel(df_show[cols], "lubrificacoes_pendencias", label="⬇️ Excel", key="exp_lub_pend")
    st.dataframe(df_show[cols], use_container_width=True, hide_index=True)


def _render_execucao(equipamentos, responsaveis):
    st.subheader("Registrar Lubrificação")
    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return
    if not responsaveis:
        st.info("Cadastre responsáveis primeiro.")
        return

    eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_exec_eqp")
    if not eqp:
        return

    itens_pendentes = lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"])
    vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op = {v["responsavel_id"] for v in vinculos_op}
    resp_lista = [r for r in responsaveis if r["id"] in ids_op] or responsaveis

    with st.form("form_lub_exec", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            resp = st.selectbox("Responsável", resp_lista, format_func=lambda r: r["nome"])
            data_exec = st.date_input("Data da execução")
            opcoes = ["— informar manualmente —"] + [
                f"{i['item']} ({i['tipo_produto']}) [{STATUS_LABEL.get(i['status'], i['status'])}]"
                for i in itens_pendentes
            ]
            item_idx = st.selectbox("Item do template", range(len(opcoes)),
                                    format_func=lambda i: opcoes[i])
        with c2:
            nome_manual = st.text_input("Nome do item (se manual)")
            prod_manual = st.text_input("Produto (se manual)")
            km_exec = st.number_input("KM atual", min_value=0.0,
                                      value=float(eqp.get("km_atual") or 0), step=1.0)
            horas_exec = st.number_input("Horas atuais", min_value=0.0,
                                         value=float(eqp.get("horas_atual") or 0), step=1.0)

        obs = st.text_area("Observações")
        salvar = st.form_submit_button("Registrar lubrificação", use_container_width=True)

        if salvar:
            item_id = None
            nome_item = nome_manual.strip() or None
            tipo_produto = prod_manual.strip() or None

            if item_idx > 0:
                obj = itens_pendentes[item_idx - 1]
                item_id = obj["item_id"]
                nome_item = nome_item or obj["item"]
                tipo_produto = tipo_produto or obj["tipo_produto"]

            if not nome_item:
                st.error("Informe o nome do item de lubrificação.")
            else:
                lubrificacoes_service.registrar_execucao({
                    "equipamento_id": eqp["id"],
                    "item_id": item_id,
                    "responsavel_id": resp["id"] if resp else None,
                    "nome_item": nome_item,
                    "tipo_produto": tipo_produto,
                    "data_execucao": data_exec,
                    "km_execucao": km_exec,
                    "horas_execucao": horas_exec,
                    "observacoes": obs,
                })
                st.success("Lubrificação registrada com sucesso.")
                st.rerun()


def _render_historico(equipamentos):
    st.subheader("Histórico de Lubrificações")
    historico = lubrificacoes_service.listar_todos()
    if historico:
        df_hist = pd.DataFrame(historico)
        col_exp = st.columns([5,1])[1]
        with col_exp:
            botao_exportar_excel(df_hist, "lubrificacoes_historico", label="⬇️ Excel", key="exp_lub_hist")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma lubrificação registrada ainda.")

    with st.expander("Histórico por equipamento"):
        if not equipamentos:
            return
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_hist_eqp")
        if eqp:
            dados = lubrificacoes_service.listar_por_equipamento(eqp["id"])
            if dados:
                st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum histórico para este equipamento.")


def render():
    st.title("Controle de Lubrificações")
    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()
    pendencias_df = _carregar_pendencias(equipamentos)

    tab1, tab2, tab3 = st.tabs(["Pendências", "Registrar", "Histórico"])
    with tab1:
        _render_pendencias(pendencias_df, equipamentos)
    with tab2:
        _render_execucao(equipamentos, responsaveis)
    with tab3:
        _render_historico(equipamentos)
