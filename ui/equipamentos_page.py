import pandas as pd
import streamlit as st
from services import (
    equipamentos_service,
    execucoes_service,
    leituras_service,
    lubrificacoes_service,
    revisoes_service,
    setores_service,
    templates_lubrificacao_service,
    templates_revisao_service,
    vinculos_service,
)

TIPOS_EQUIPAMENTO = [
    "Caminhão", "Trator", "Colheitadeira", "Pulverizador",
    "Implemento", "Máquina", "Outro",
]

STATUS_LABEL = {
    "VENCIDO": "🔴 Vencido",
    "PROXIMO": "🟡 Próximo",
    "EM DIA": "🟢 Em dia",
}



def _formatar_status(status):
    return STATUS_LABEL.get(status, status)



def _resumo_status(itens):
    return {
        "vencidos": sum(1 for item in itens if item.get("status") == "VENCIDO"),
        "proximos": sum(1 for item in itens if item.get("status") == "PROXIMO"),
        "em_dia": sum(1 for item in itens if item.get("status") == "EM DIA"),
    }



def _mostrar_painel_360(equipamento_id):
    equipamento = equipamentos_service.obter(equipamento_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    revisoes = revisoes_service.calcular_proximas_revisoes(equipamento_id)
    lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
    leituras = leituras_service.listar_por_equipamento(equipamento_id, limite=10)
    historico_lub = lubrificacoes_service.listar_por_equipamento(equipamento_id)[:10]
    vinculos = vinculos_service.listar_por_equipamento(equipamento_id)

    st.subheader(f"Painel 360° — {equipamento['codigo']} - {equipamento['nome']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Setor", equipamento.get("setor_nome") or "-")
    c2.metric("Tipo", equipamento.get("tipo") or "-")
    c3.metric("KM atual", f"{equipamento['km_atual']:.0f}")
    c4.metric("Horas atuais", f"{equipamento['horas_atual']:.0f}")

    c5, c6, c7, c8 = st.columns(4)
    resumo_rev = _resumo_status(revisoes)
    resumo_lub = _resumo_status(lubrificacoes)
    c5.metric("Revisões vencidas", resumo_rev["vencidos"])
    c6.metric("Lubrificações vencidas", resumo_lub["vencidos"])
    c7.metric("Revisões próximas", resumo_rev["proximos"])
    c8.metric("Lubrificações próximas", resumo_lub["proximos"])

    with st.expander("Dados do equipamento", expanded=True):
        meta1, meta2 = st.columns(2)
        with meta1:
            st.write(f"**Template de revisão:** {equipamento.get('template_revisao_nome') or '-'}")
            st.write(f"**Template de lubrificação:** {equipamento.get('template_lubrificacao_nome') or '-'}")
        with meta2:
            st.write(f"**Status do cadastro:** {'Ativo' if equipamento.get('ativo') else 'Inativo'}")
            st.write(f"**Vínculos operacionais:** {len(vinculos)}")

    tabs = st.tabs([
        "Próximas revisões",
        "Próximas lubrificações",
        "Leituras recentes",
        "Histórico de lubrificações",
        "Responsáveis",
    ])

    with tabs[0]:
        if revisoes:
            df_rev = pd.DataFrame(revisoes)[[
                "etapa", "tipo_controle", "atual", "ultima_execucao", "vencimento", "diferenca", "status"
            ]].rename(columns={
                "etapa": "Etapa",
                "tipo_controle": "Controle",
                "atual": "Atual",
                "ultima_execucao": "Última execução",
                "vencimento": "Vencimento",
                "diferenca": "Falta",
                "status": "Status",
            })
            df_rev["Status"] = df_rev["Status"].map(_formatar_status)
            st.dataframe(df_rev, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma revisão configurada para este equipamento.")

    with tabs[1]:
        if lubrificacoes:
            df_lub = pd.DataFrame(lubrificacoes)[[
                "item", "tipo_produto", "tipo_controle", "atual", "ultima_execucao", "vencimento", "diferenca", "status"
            ]].rename(columns={
                "item": "Item",
                "tipo_produto": "Produto",
                "tipo_controle": "Controle",
                "atual": "Atual",
                "ultima_execucao": "Última execução",
                "vencimento": "Vencimento",
                "diferenca": "Falta",
                "status": "Status",
            })
            df_lub["Status"] = df_lub["Status"].map(_formatar_status)
            st.dataframe(df_lub, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma lubrificação configurada para este equipamento.")

    with tabs[2]:
        if leituras:
            df_leituras = pd.DataFrame(leituras).rename(columns={
                "data_leitura": "Data",
                "tipo_leitura": "Tipo",
                "km_valor": "KM",
                "horas_valor": "Horas",
                "responsavel": "Responsável",
                "observacoes": "Observações",
            })
            st.dataframe(df_leituras, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma leitura registrada para este equipamento.")

    with tabs[3]:
        if historico_lub:
            df_hist_lub = pd.DataFrame(historico_lub).rename(columns={
                "data": "Data",
                "item": "Item",
                "produto": "Produto",
                "km": "KM",
                "horas": "Horas",
                "responsavel": "Responsável",
                "observacoes": "Observações",
            })
            st.dataframe(df_hist_lub, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma execução de lubrificação registrada.")

    with tabs[4]:
        if vinculos:
            df_vinc = pd.DataFrame(vinculos).rename(columns={
                "responsavel_nome": "Responsável",
                "responsavel_telefone": "Telefone",
                "tipo_vinculo": "Vínculo",
                "principal": "Principal",
            })
            st.dataframe(df_vinc[["Responsável", "Telefone", "Vínculo", "Principal"]], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum responsável vinculado a este equipamento.")



def render():
    st.title("Equipamentos")
    equipamentos = equipamentos_service.listar()
    setores = [item for item in setores_service.listar() if item.get("ativo")]
    templates_rev = templates_revisao_service.listar()
    templates_lub = templates_lubrificacao_service.listar()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de equipamentos", len(equipamentos))
    c2.metric("Com setor vinculado", sum(1 for e in equipamentos if e.get("setor_id")))
    c3.metric("Com template revisão", sum(1 for e in equipamentos if e.get("template_revisao_id")))
    c4.metric("Com template lubrificação", sum(1 for e in equipamentos if e.get("template_lubrificacao_id")))

    tab1, tab2, tab3 = st.tabs(["Cadastrar equipamento", "Lista de equipamentos", "Painel 360°"])

    with tab1:
        st.subheader("Novo equipamento")
        if not setores:
            st.warning("Cadastre pelo menos um setor antes de criar equipamentos.")

        with st.form("form_equipamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código")
                nome = st.text_input("Nome do equipamento")
                tipo = st.selectbox("Tipo", TIPOS_EQUIPAMENTO)
                setor = st.selectbox(
                    "Setor",
                    setores,
                    format_func=lambda x: x["nome"],
                    disabled=not setores,
                ) if setores else None
            with col2:
                km_atual = st.number_input("KM atual", min_value=0.0, step=1.0)
                horas_atual = st.number_input("Horas atuais", min_value=0.0, step=1.0)
                template_rev = st.selectbox(
                    "Template de revisão",
                    [None] + templates_rev,
                    format_func=lambda t: t["nome"] if t else "— nenhum —",
                )
                template_lub = st.selectbox(
                    "Template de lubrificação",
                    [None] + templates_lub,
                    format_func=lambda t: t["nome"] if t else "— nenhum —",
                )
            ativo = st.checkbox("Ativo", value=True)
            submitted = st.form_submit_button(
                "Salvar equipamento", use_container_width=True, disabled=not setores
            )

        if submitted:
            if not codigo.strip() or not nome.strip():
                st.error("Informe código e nome do equipamento.")
            elif not setor:
                st.error("Selecione um setor.")
            else:
                equipamentos_service.criar_completo(
                    codigo=codigo.strip(),
                    nome=nome.strip(),
                    tipo=tipo,
                    setor_id=setor["id"],
                    km_atual=km_atual,
                    horas_atual=horas_atual,
                    template_revisao_id=template_rev["id"] if template_rev else None,
                    template_lubrificacao_id=template_lub["id"] if template_lub else None,
                    ativo=ativo,
                )
                st.success("Equipamento cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if equipamentos:
            busca = st.text_input("Buscar equipamento por código, nome ou setor")
            filtrados = equipamentos
            if busca.strip():
                termo = busca.strip().lower()
                filtrados = [
                    e for e in equipamentos
                    if termo in (e.get("codigo") or "").lower()
                    or termo in (e.get("nome") or "").lower()
                    or termo in (e.get("setor_nome") or "").lower()
                ]

            df = pd.DataFrame(filtrados)
            df = df.rename(columns={
                "codigo": "Código", "nome": "Nome", "tipo": "Tipo",
                "km_atual": "KM atual", "horas_atual": "Horas",
                "template_revisao_id": "T.Revisão", "template_lubrificacao_id": "T.Lubrificação",
                "setor_nome": "Setor", "ativo": "Ativo",
            })
            cols = ["Código", "Nome", "Tipo", "Setor", "KM atual", "Horas", "T.Revisão", "T.Lubrificação", "Ativo"]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento encontrado.")

    with tab3:
        if not equipamentos:
            st.info("Nenhum equipamento encontrado.")
        else:
            mapa = {f"{e['codigo']} - {e['nome']}": e["id"] for e in equipamentos}
            selecionado = st.selectbox("Escolha um equipamento", list(mapa.keys()))
            _mostrar_painel_360(mapa[selecionado])
