import pandas as pd
import streamlit as st

from services import (
    equipamentos_service,
    setores_service,
    templates_revisao_service,
    templates_lubrificacao_service,
    leituras_service,
    lubrificacoes_service,
    revisoes_service,
    vinculos_service,
)

TIPOS_EQUIPAMENTO = [
    "Caminhão", "Trator", "Colheitadeira", "Pulverizador",
    "Implemento", "Máquina", "Outro",
]


def _status_emoji(status):
    return {
        "VENCIDO": "🔴",
        "PROXIMO": "🟡",
        "EM DIA": "🟢",
    }.get(status, "⚪")


def _mostrar_lista_equipamentos(equipamentos):
    termo = st.text_input("Buscar equipamento", placeholder="Código, nome, tipo ou setor")
    filtrados = equipamentos_service.buscar(termo)

    if filtrados:
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
        st.info("Nenhum equipamento encontrado para o filtro informado.")


def _mostrar_painel_360(equipamento):
    equipamento_id = equipamento["id"]
    revisoes = revisoes_service.calcular_proximas_revisoes(equipamento_id)
    lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
    leituras = leituras_service.listar_por_equipamento(equipamento_id, limite=10)
    vinculos = vinculos_service.listar_por_equipamento(equipamento_id)
    vinculos_setor = vinculos_service.listar_por_setor(equipamento.get("setor_id")) if equipamento.get("setor_id") else []
    historico_lub = lubrificacoes_service.listar_por_equipamento(equipamento_id)[:10]

    st.subheader(f"Painel 360° — {equipamento['codigo']} - {equipamento['nome']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Setor", equipamento.get("setor_nome") or "-")
    c2.metric("Tipo", equipamento.get("tipo") or "-")
    c3.metric("KM atual", f"{equipamento.get('km_atual', 0):.0f}")
    c4.metric("Horas atuais", f"{equipamento.get('horas_atual', 0):.0f}")

    rev_vencidas = sum(1 for item in revisoes if item["status"] == "VENCIDO")
    rev_proximas = sum(1 for item in revisoes if item["status"] == "PROXIMO")
    lub_vencidas = sum(1 for item in lubrificacoes if item["status"] == "VENCIDO")
    lub_proximas = sum(1 for item in lubrificacoes if item["status"] == "PROXIMO")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Revisões vencidas", rev_vencidas)
    c6.metric("Revisões próximas", rev_proximas)
    c7.metric("Lubrificações vencidas", lub_vencidas)
    c8.metric("Lubrificações próximas", lub_proximas)

    tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs([
        "Próximas revisões",
        "Próximas lubrificações",
        "Leituras recentes",
        "Histórico de lubrificações",
        "Responsáveis",
    ])

    with tab_a:
        if revisoes:
            df = pd.DataFrame([
                {
                    "Status": f"{_status_emoji(item['status'])} {item['status']}",
                    "Etapa": item["etapa"],
                    "Controle": item["tipo_controle"],
                    "Atual": item["leitura_atual"],
                    "Última execução": item["ultima_execucao"],
                    "Vencimento": item["vencimento"],
                    "Falta": item["falta"],
                }
                for item in revisoes
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem revisões calculadas para este equipamento.")

    with tab_b:
        if lubrificacoes:
            df = pd.DataFrame([
                {
                    "Status": f"{_status_emoji(item['status'])} {item['status']}",
                    "Item": item["item"],
                    "Produto": item["tipo_produto"],
                    "Controle": item["tipo_controle"],
                    "Atual": item["atual"],
                    "Última execução": item["ultima_execucao"],
                    "Vencimento": item["vencimento"],
                    "Falta": item["diferenca"],
                }
                for item in lubrificacoes
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem lubrificações calculadas para este equipamento.")

    with tab_c:
        if leituras:
            df = pd.DataFrame([
                {
                    "Data": item["data_leitura"],
                    "Tipo": item["tipo_leitura"],
                    "KM": item["km_valor"],
                    "Horas": item["horas_valor"],
                    "Responsável": item["responsavel"],
                    "Observações": item["observacoes"],
                }
                for item in leituras
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem leituras registradas ou tabela de leituras ainda não disponível.")

    with tab_d:
        if historico_lub:
            df = pd.DataFrame([
                {
                    "Data": item["data"],
                    "Item": item["item"],
                    "Produto": item["produto"],
                    "KM": item["km"],
                    "Horas": item["horas"],
                    "Responsável": item["responsavel"],
                    "Observações": item["observacoes"],
                }
                for item in historico_lub
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem histórico de lubrificações ou tabela ainda não disponível.")

    with tab_e:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Responsáveis do equipamento**")
            if vinculos:
                for item in vinculos:
                    principal = " (principal)" if item.get("principal") else ""
                    st.write(f"- {item['responsavel_nome']} — {item.get('tipo_vinculo', '-')}{principal}")
            else:
                st.caption("Nenhum vínculo operacional encontrado.")
        with col2:
            st.markdown("**Responsáveis do setor**")
            if vinculos_setor:
                for item in vinculos_setor:
                    principal = " (principal)" if item.get("principal") else ""
                    st.write(f"- {item['responsavel_nome']} — {item.get('tipo_responsabilidade', '-')}{principal}")
            else:
                st.caption("Nenhum vínculo de gestão encontrado.")


def render():
    st.title("Equipamentos")
    equipamentos = equipamentos_service.listar()
    setores = [item for item in setores_service.listar() if item.get("ativo")]
    templates_rev = templates_revisao_service.listar()
    templates_lub = templates_lubrificacao_service.listar()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de equipamentos", len(equipamentos))
    c2.metric("Com setor vinculado", sum(1 for e in equipamentos if e.get("setor_id")))
    c3.metric("Com template revisão", sum(1 for e in equipamentos if e.get("template_revisao_id")))

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
        _mostrar_lista_equipamentos(equipamentos)

    with tab3:
        if not equipamentos:
            st.info("Nenhum equipamento encontrado.")
        else:
            termo_360 = st.text_input("Localizar no painel 360°", placeholder="Digite código ou nome")
            base_360 = equipamentos_service.buscar(termo_360)
            if not base_360:
                st.info("Nenhum equipamento encontrado para abrir o painel.")
                return
            mapa = {f"{item['codigo']} - {item['nome']}": item for item in base_360}
            selecionado = st.selectbox("Equipamento", list(mapa.keys()))
            _mostrar_painel_360(mapa[selecionado])
