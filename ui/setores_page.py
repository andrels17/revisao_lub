import pandas as pd
import streamlit as st
from services import setores_service
from ui.theme import render_page_intro

TIPOS_NIVEL = ["empresa", "unidade", "departamento", "setor", "subsetor"]


def render():
    setores = setores_service.listar()
    render_page_intro(
        "Estrutura organizacional",
        "Cadastre e organize os setores para padronizar equipamentos, responsáveis e fluxos do sistema.",
        "Cadastros",
    )

    c1, c2 = st.columns([1, 1])
    c1.metric("Total de setores", len(setores))
    c2.metric("Setores ativos", sum(1 for item in setores if item.get("ativo")))

    tab1, tab2 = st.tabs(["Cadastrar setor", "Lista de setores"])

    with tab1:
        st.markdown("### Novo setor")
        st.caption("Use nomes claros e mantenha a hierarquia sempre que existir setor pai.")
        pais = [item for item in setores if item.get("ativo")]
        with st.form("form_setor", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome do setor", placeholder="Ex: Oficina Central")
                tipo_nivel = st.selectbox("Tipo/Nível", TIPOS_NIVEL, index=3)
            with c2:
                ativo = st.checkbox("Ativo", value=True)
                usar_pai = st.checkbox("Vincular a um setor pai")

            setor_pai = None
            if usar_pai:
                if pais:
                    setor_pai = st.selectbox("Setor pai", pais, format_func=lambda x: x["nome"])
                else:
                    st.info("Cadastre um setor base antes de vincular um setor pai.")

            submitted = st.form_submit_button("Salvar setor", type="primary", use_container_width=True)

        if submitted:
            if not nome.strip():
                st.error("Informe o nome do setor.")
            else:
                setores_service.criar(
                    nome=nome.strip(),
                    tipo_nivel=tipo_nivel,
                    setor_pai_id=setor_pai["id"] if setor_pai else None,
                    ativo=ativo,
                )
                st.success("Setor cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if setores:
            df = pd.DataFrame(setores).rename(columns={
                "nome": "Nome",
                "tipo_nivel": "Nível",
                "setor_pai_id": "Setor pai",
                "ativo": "Ativo",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum setor encontrado.")
