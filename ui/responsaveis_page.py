import pandas as pd
import streamlit as st
from services import responsaveis_service
from ui.theme import render_page_intro

FUNCOES_SUGERIDAS = [
    "Gestor",
    "Supervisor",
    "Mecânico",
    "Lubrificador",
    "Operador",
    "Planejamento",
]


def render():
    responsaveis = responsaveis_service.listar()
    render_page_intro(
        "Cadastro de responsáveis",
        "Mantenha a base de pessoas organizada para vínculos, alertas e controle operacional.",
        "Cadastros",
    )

    c1, c2 = st.columns([1, 1])
    c1.metric("Total de responsáveis", len(responsaveis))
    c2.metric("Responsáveis ativos", sum(1 for item in responsaveis if item.get("ativo")))

    tab1, tab2 = st.tabs(["Cadastrar responsável", "Lista de responsáveis"])

    with tab1:
        st.markdown("### Novo responsável")
        st.caption("Preencha os dados principais para facilitar filtros, alertas e rastreabilidade.")
        with st.form("form_responsavel", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome", placeholder="Ex: André Lima")
                funcao_principal = st.selectbox(
                    "Função principal",
                    options=[""] + FUNCOES_SUGERIDAS,
                    format_func=lambda x: x or "Selecione",
                )
            with col2:
                telefone = st.text_input("Telefone", placeholder="(83) 99999-9999")
                email = st.text_input("E-mail", placeholder="nome@empresa.com")
            ativo = st.checkbox("Ativo", value=True)
            submitted = st.form_submit_button("Salvar responsável", type="primary", use_container_width=True)

        if submitted:
            if not nome.strip():
                st.error("Informe o nome do responsável.")
            else:
                responsaveis_service.criar(
                    nome=nome.strip(),
                    funcao_principal=funcao_principal or None,
                    telefone=telefone.strip() or None,
                    email=email.strip() or None,
                    ativo=ativo,
                )
                st.success("Responsável cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if responsaveis:
            df = pd.DataFrame(responsaveis).rename(columns={
                "nome": "Nome",
                "funcao_principal": "Função",
                "telefone": "Telefone",
                "email": "E-mail",
                "ativo": "Ativo",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum responsável encontrado.")
