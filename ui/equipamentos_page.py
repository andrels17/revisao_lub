import pandas as pd
import streamlit as st
from services import (
    equipamentos_service, setores_service,
    templates_revisao_service, templates_lubrificacao_service,
    revisoes_service, lubrificacoes_service,
)

TIPOS_EQUIPAMENTO = [
    "Caminhão", "Trator", "Colheitadeira", "Pulverizador",
    "Implemento", "Máquina", "Outro",
]


def _render_acesso_rapido(equipamentos):
    st.subheader("Acesso rápido")
    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    mapa = {e['id']: e for e in equipamentos}
    busca = st.text_input(
        "Buscar equipamento para acesso rápido",
        key="equip_quick_search",
        placeholder="Digite código, nome, setor ou tipo...",
    ).strip().lower()

    filtrados = equipamentos
    if busca:
        filtrados = [
            e for e in equipamentos
            if busca in (e.get('codigo') or '').lower()
            or busca in (e.get('nome') or '').lower()
            or busca in (e.get('setor_nome') or '').lower()
            or busca in (e.get('tipo') or '').lower()
        ]

    if not filtrados:
        st.warning("Nenhum equipamento encontrado para essa busca.")
        return

    quick_id = st.session_state.get('quick_equipment_id')
    if quick_id not in {e['id'] for e in filtrados}:
        quick_id = filtrados[0]['id']

    opcoes = {f"{e['codigo']} - {e['nome']} ({e.get('setor_nome') or '-'})": e['id'] for e in filtrados}
    labels = list(opcoes.keys())
    label_padrao = next((lbl for lbl, eid in opcoes.items() if eid == quick_id), labels[0])
    selecionado_label = st.selectbox(
        "Equipamento",
        labels,
        index=labels.index(label_padrao),
        key='equip_quick_select'
    )
    equipamento_id = opcoes[selecionado_label]
    st.session_state['quick_equipment_id'] = equipamento_id
    equipamento = mapa[equipamento_id]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Código", equipamento.get('codigo') or '-')
    c2.metric("Setor", equipamento.get('setor_nome') or '-')
    c3.metric("KM atual", f"{float(equipamento.get('km_atual', 0) or 0):,.0f}".replace(',', '.'))
    c4.metric("Horas atuais", f"{float(equipamento.get('horas_atual', 0) or 0):,.0f}".replace(',', '.'))

    st.caption(f"Tipo: {equipamento.get('tipo') or '-'}")

    revs = revisoes_service.calcular_proximas_revisoes(equipamento_id)
    lubs = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revisões vencidas", sum(1 for r in revs if r.get('status') == 'VENCIDO'))
    c2.metric("Revisões próximas", sum(1 for r in revs if r.get('status') == 'PROXIMO'))
    c3.metric("Lubrificações vencidas", sum(1 for r in lubs if r.get('status') == 'VENCIDO'))
    c4.metric("Lubrificações próximas", sum(1 for r in lubs if r.get('status') == 'PROXIMO'))

    t1, t2 = st.tabs(["Próximas revisões", "Próximas lubrificações"])
    with t1:
        if revs:
            df = pd.DataFrame(revs)
            colmap = {
                'etapa': 'Etapa',
                'tipo_controle': 'Controle',
                'gatilho_valor': 'Gatilho',
                'leitura_atual': 'Leitura atual',
                'ultima_execucao': 'Última execução',
                'vencimento': 'Vencimento',
                'falta': 'Falta',
                'status': 'Status',
            }
            cols = [c for c in ['etapa','tipo_controle','gatilho_valor','leitura_atual','ultima_execucao','vencimento','falta','status'] if c in df.columns]
            st.dataframe(df[cols].rename(columns=colmap), use_container_width=True, hide_index=True)
        else:
            st.info('Nenhuma revisão encontrada para este equipamento.')
    with t2:
        if lubs:
            df = pd.DataFrame(lubs)
            colmap = {
                'item': 'Item',
                'tipo_produto': 'Produto',
                'tipo_controle': 'Controle',
                'intervalo': 'Intervalo',
                'atual': 'Leitura atual',
                'ultima_execucao': 'Última execução',
                'vencimento': 'Vencimento',
                'diferenca': 'Falta',
                'status': 'Status',
            }
            cols = [c for c in ['item','tipo_produto','tipo_controle','intervalo','atual','ultima_execucao','vencimento','diferenca','status'] if c in df.columns]
            st.dataframe(df[cols].rename(columns=colmap), use_container_width=True, hide_index=True)
        else:
            st.info('Nenhuma lubrificação encontrada para este equipamento.')


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

    tab1, tab2, tab3 = st.tabs(["Cadastrar equipamento", "Lista de equipamentos", "Acesso rápido"])

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
            df = pd.DataFrame(equipamentos)
            df = df.rename(columns={
                "codigo": "Código", "nome": "Nome", "tipo": "Tipo",
                "km_atual": "KM atual", "horas_atual": "Horas",
                "template_revisao_id": "T.Revisão", "setor_nome": "Setor",
            })
            cols = ["Código", "Nome", "Tipo", "Setor", "KM atual", "Horas", "T.Revisão"]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento encontrado.")

    with tab3:
        _render_acesso_rapido(equipamentos)
