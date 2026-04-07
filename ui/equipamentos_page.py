import pandas as pd
import streamlit as st
from services import (
    equipamentos_service,
    execucoes_service,
    leituras_service,
    lubrificacoes_service,
    responsaveis_service,
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



def _calcular_saude_equipamento(revisoes, lubrificacoes):
    total_itens = len(revisoes) + len(lubrificacoes)
    vencidos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "VENCIDO")
    proximos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "PROXIMO")

    if total_itens == 0:
        return {
            "score": 100,
            "faixa": "Sem pendências configuradas",
            "detalhe": "Equipamento sem revisão ou lubrificação configurada.",
        }

    score = max(0, 100 - (vencidos * 25) - (proximos * 8))
    if vencidos >= 3 or score < 45:
        faixa = "Crítico"
    elif vencidos >= 1 or score < 70:
        faixa = "Atenção"
    else:
        faixa = "Saudável"

    return {
        "score": score,
        "faixa": faixa,
        "detalhe": f"{vencidos} vencido(s) e {proximos} próximo(s) entre {total_itens} item(ns).",
    }



def _mostrar_faixa_saude(saude):
    score = saude["score"]
    faixa = saude["faixa"]
    detalhe = saude["detalhe"]

    if faixa == "Crítico":
        st.error(f"Saúde do equipamento: {faixa} — {score}%")
    elif faixa == "Atenção":
        st.warning(f"Saúde do equipamento: {faixa} — {score}%")
    else:
        st.success(f"Saúde do equipamento: {faixa} — {score}%")

    st.progress(int(max(0, min(100, score))))
    st.caption(detalhe)



def _tabela_revisoes(revisoes):
    if not revisoes:
        st.info("Nenhuma revisão configurada para este equipamento.")
        return

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



def _tabela_lubrificacoes(lubrificacoes):
    if not lubrificacoes:
        st.info("Nenhuma lubrificação configurada para este equipamento.")
        return

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



def _carregar_responsaveis():
    try:
        return responsaveis_service.listar()
    except Exception:
        return []



def _render_acoes_rapidas(equipamento, revisoes, lubrificacoes, vinculos):
    equipamento_id = equipamento["id"]
    responsaveis = _carregar_responsaveis()

    ids_vinculados = {v.get("responsavel_id") for v in vinculos}
    responsaveis_sugeridos = [r for r in responsaveis if r.get("id") in ids_vinculados] or responsaveis

    subtabs = st.tabs(["Registrar leitura", "Lançar revisão", "Lançar lubrificação"])

    with subtabs[0]:
        with st.form(f"form_leitura_rapida_{equipamento_id}", clear_on_submit=True):
            tipo_leitura = st.selectbox(
                "O que atualizar",
                ["ambos", "horas", "km"],
                format_func=lambda x: {
                    "ambos": "KM e Horas",
                    "km": "Apenas KM",
                    "horas": "Apenas Horas",
                }[x],
                key=f"tipo_leitura_{equipamento_id}",
            )
            c1, c2 = st.columns(2)
            with c1:
                km_valor = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(equipamento.get("km_atual") or 0),
                    step=1.0,
                    disabled=(tipo_leitura == "horas"),
                    key=f"km_leitura_{equipamento_id}",
                )
            with c2:
                horas_valor = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(equipamento.get("horas_atual") or 0),
                    step=1.0,
                    disabled=(tipo_leitura == "km"),
                    key=f"horas_leitura_{equipamento_id}",
                )
            c3, c4 = st.columns(2)
            with c3:
                data_leitura = st.date_input("Data da leitura", key=f"data_leitura_{equipamento_id}")
            with c4:
                if responsaveis_sugeridos:
                    resp = st.selectbox(
                        "Responsável",
                        [None] + responsaveis_sugeridos,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                        key=f"resp_leitura_{equipamento_id}",
                    )
                else:
                    resp = None
                    st.caption("Nenhum responsável cadastrado.")
            obs = st.text_input("Observações", key=f"obs_leitura_{equipamento_id}")
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True)

        if salvar:
            leituras_service.registrar(
                equipamento_id=equipamento_id,
                tipo_leitura=tipo_leitura,
                km_valor=km_valor if tipo_leitura in ("km", "ambos") else None,
                horas_valor=horas_valor if tipo_leitura in ("horas", "ambos") else None,
                data_leitura=data_leitura,
                responsavel_id=resp["id"] if resp else None,
                observacoes=obs.strip() or None,
            )
            st.success("Leitura registrada com sucesso.")
            st.rerun()

    with subtabs[1]:
        opcoes_rev = ["— selecionar automaticamente depois —"] + [
            f"{r['etapa']} [{_formatar_status(r['status'])}]"
            for r in revisoes
        ]
        with st.form(f"form_rev_rapida_{equipamento_id}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                etapa_idx = st.selectbox(
                    "Etapa sugerida",
                    range(len(opcoes_rev)),
                    format_func=lambda i: opcoes_rev[i],
                    key=f"etapa_rev_{equipamento_id}",
                )
                data_exec = st.date_input("Data da revisão", key=f"data_rev_{equipamento_id}")
                status_exec = st.selectbox(
                    "Status da execução",
                    ["concluida", "pendente"],
                    format_func=lambda x: "Concluída" if x == "concluida" else "Pendente",
                    key=f"status_rev_{equipamento_id}",
                )
            with c2:
                if responsaveis_sugeridos:
                    resp_rev = st.selectbox(
                        "Responsável",
                        [None] + responsaveis_sugeridos,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                        key=f"resp_rev_{equipamento_id}",
                    )
                else:
                    resp_rev = None
                    st.caption("Nenhum responsável cadastrado.")
                km_exec = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(equipamento.get("km_atual") or 0),
                    step=1.0,
                    key=f"km_rev_{equipamento_id}",
                )
                horas_exec = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(equipamento.get("horas_atual") or 0),
                    step=1.0,
                    key=f"horas_rev_{equipamento_id}",
                )
            observacoes = st.text_area(
                "Observações",
                value=(
                    f"Etapa sugerida: {revisoes[etapa_idx - 1]['etapa']}"
                    if etapa_idx > 0 and revisoes
                    else ""
                ),
                key=f"obs_rev_{equipamento_id}",
            )
            salvar_rev = st.form_submit_button("Registrar revisão", use_container_width=True)

        if salvar_rev:
            execucoes_service.criar_execucao(
                {
                    "equipamento_id": equipamento_id,
                    "responsavel_id": resp_rev["id"] if resp_rev else None,
                    "tipo": "revisao",
                    "data_execucao": data_exec,
                    "km_execucao": km_exec,
                    "horas_execucao": horas_exec,
                    "observacoes": observacoes.strip() or None,
                    "status": status_exec,
                }
            )
            st.success("Revisão registrada com sucesso.")
            st.rerun()

    with subtabs[2]:
        opcoes_lub = ["— informar manualmente —"] + [
            f"{i['item']} ({i['tipo_produto']}) [{_formatar_status(i['status'])}]"
            for i in lubrificacoes
        ]
        with st.form(f"form_lub_rapida_{equipamento_id}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                item_idx = st.selectbox(
                    "Item do template",
                    range(len(opcoes_lub)),
                    format_func=lambda i: opcoes_lub[i],
                    key=f"item_lub_{equipamento_id}",
                )
                data_exec_lub = st.date_input("Data da lubrificação", key=f"data_lub_{equipamento_id}")
                if responsaveis_sugeridos:
                    resp_lub = st.selectbox(
                        "Responsável",
                        [None] + responsaveis_sugeridos,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                        key=f"resp_lub_{equipamento_id}",
                    )
                else:
                    resp_lub = None
                    st.caption("Nenhum responsável cadastrado.")
            with c2:
                nome_manual = st.text_input("Nome do item (se manual)", key=f"nome_lub_{equipamento_id}")
                prod_manual = st.text_input("Produto (se manual)", key=f"prod_lub_{equipamento_id}")
                km_exec_lub = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(equipamento.get("km_atual") or 0),
                    step=1.0,
                    key=f"km_lub_{equipamento_id}",
                )
                horas_exec_lub = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(equipamento.get("horas_atual") or 0),
                    step=1.0,
                    key=f"horas_lub_{equipamento_id}",
                )
            obs_lub = st.text_area("Observações", key=f"obs_lub_{equipamento_id}")
            salvar_lub = st.form_submit_button("Registrar lubrificação", use_container_width=True)

        if salvar_lub:
            item_id = None
            nome_item = nome_manual.strip() or None
            tipo_produto = prod_manual.strip() or None

            if item_idx > 0 and lubrificacoes:
                item_sel = lubrificacoes[item_idx - 1]
                item_id = item_sel.get("item_id")
                nome_item = nome_item or item_sel.get("item")
                tipo_produto = tipo_produto or item_sel.get("tipo_produto")

            if not nome_item:
                st.error("Informe o nome do item de lubrificação.")
            else:
                lubrificacoes_service.registrar_execucao(
                    {
                        "equipamento_id": equipamento_id,
                        "item_id": item_id,
                        "responsavel_id": resp_lub["id"] if resp_lub else None,
                        "nome_item": nome_item,
                        "tipo_produto": tipo_produto,
                        "data_execucao": data_exec_lub,
                        "km_execucao": km_exec_lub,
                        "horas_execucao": horas_exec_lub,
                        "observacoes": obs_lub.strip() or None,
                    }
                )
                st.success("Lubrificação registrada com sucesso.")
                st.rerun()



def _mostrar_painel_360(equipamento_id):
    equipamento = equipamentos_service.obter(equipamento_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    revisoes = revisoes_service.calcular_proximas_revisoes(equipamento_id)
    lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
    leituras = leituras_service.listar_por_equipamento(equipamento_id, limite=10)
    historico_lub = lubrificacoes_service.listar_por_equipamento(equipamento_id)[:10]
    historico_rev = execucoes_service.listar_revisoes_por_equipamento(equipamento_id, limite=10)
    resumo_exec_rev = execucoes_service.resumo_revisoes_por_equipamento(equipamento_id)
    vinculos = vinculos_service.listar_por_equipamento(equipamento_id)
    vinculos_setor = vinculos_service.listar_por_setor(equipamento.get("setor_id")) if equipamento.get("setor_id") else []
    saude = _calcular_saude_equipamento(revisoes, lubrificacoes)

    st.subheader(f"Painel 360° — {equipamento['codigo']} - {equipamento['nome']}")
    _mostrar_faixa_saude(saude)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Setor", equipamento.get("setor_nome") or "-")
    c2.metric("Tipo", equipamento.get("tipo") or "-")
    c3.metric("KM atual", f"{equipamento['km_atual']:.0f}")
    c4.metric("Horas atuais", f"{equipamento['horas_atual']:.0f}")

    resumo_rev = _resumo_status(revisoes)
    resumo_lub = _resumo_status(lubrificacoes)
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Revisões vencidas", resumo_rev["vencidos"])
    c6.metric("Lubrificações vencidas", resumo_lub["vencidos"])
    c7.metric("Revisões próximas", resumo_rev["proximos"])
    c8.metric("Lubrificações próximas", resumo_lub["proximos"])

    c9, c10, c11 = st.columns(3)
    c9.metric("Execuções de revisão", resumo_exec_rev["total"])
    c10.metric("Concluídas", resumo_exec_rev["concluidas"])
    c11.metric("Pendentes", resumo_exec_rev["pendentes"])

    with st.expander("Dados do equipamento", expanded=True):
        meta1, meta2 = st.columns(2)
        with meta1:
            st.write(f"**Template de revisão:** {equipamento.get('template_revisao_nome') or '-'}")
            st.write(f"**Template de lubrificação:** {equipamento.get('template_lubrificacao_nome') or '-'}")
            st.write(f"**Última revisão registrada:** {resumo_exec_rev.get('ultima_data') or '-'}")
        with meta2:
            st.write(f"**Status do cadastro:** {'Ativo' if equipamento.get('ativo') else 'Inativo'}")
            st.write(f"**Vínculos operacionais:** {len(vinculos)}")
            st.write(f"**Responsáveis do setor:** {len(vinculos_setor)}")

    tabs = st.tabs([
        "Ações rápidas",
        "Próximas revisões",
        "Próximas lubrificações",
        "Leituras recentes",
        "Histórico de revisões",
        "Histórico de lubrificações",
        "Responsáveis",
    ])

    with tabs[0]:
        _render_acoes_rapidas(equipamento, revisoes, lubrificacoes, vinculos)

    with tabs[1]:
        _tabela_revisoes(revisoes)

    with tabs[2]:
        _tabela_lubrificacoes(lubrificacoes)

    with tabs[3]:
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

    with tabs[4]:
        if historico_rev:
            df_hist_rev = pd.DataFrame(historico_rev).rename(columns={
                "data": "Data",
                "km": "KM",
                "horas": "Horas",
                "responsavel": "Responsável",
                "status": "Status",
                "observacoes": "Observações",
                "resultado": "Resultado",
            })
            st.dataframe(
                df_hist_rev[["Data", "Resultado", "KM", "Horas", "Responsável", "Status", "Observações"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma execução de revisão registrada.")

    with tabs[5]:
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

    with tabs[6]:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Responsáveis por equipamento**")
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
        with col_b:
            st.markdown("**Responsáveis do setor**")
            if vinculos_setor:
                df_setor = pd.DataFrame(vinculos_setor).rename(columns={
                    "responsavel_nome": "Responsável",
                    "responsavel_telefone": "Telefone",
                    "tipo_responsabilidade": "Tipo",
                    "principal": "Principal",
                })
                st.dataframe(df_setor[["Responsável", "Telefone", "Tipo", "Principal"]], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum responsável de setor cadastrado.")



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
            busca = st.text_input("Buscar equipamento por código, nome, tipo ou setor")
            filtrados = equipamentos
            if busca.strip():
                termo = busca.strip().lower()
                filtrados = [
                    e for e in equipamentos
                    if termo in (e.get("codigo") or "").lower()
                    or termo in (e.get("nome") or "").lower()
                    or termo in (e.get("tipo") or "").lower()
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
