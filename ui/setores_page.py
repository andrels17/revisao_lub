import pandas as pd
import streamlit as st
from services import setores_service


TIPOS_NIVEL = ["empresa", "unidade", "departamento", "setor", "subsetor"]


def render():
    st.title("Setores")
    setores = setores_service.listar()

    c1, c2 = st.columns([1, 2])
    c1.metric("Total de setores", len(setores))
    c2.metric("Setores ativos", sum(1 for item in setores if item.get("ativo")))

    tab1, tab2 = st.tabs(["Cadastrar setor", "Lista de setores"])

    with tab1:
        st.subheader("Novo setor")
        pais = [item for item in setores if item.get("ativo")]
        with st.form("form_setor", clear_on_submit=True):
            nome = st.text_input("Nome do setor")
            tipo_nivel = st.selectbox("Tipo/Nível", TIPOS_NIVEL, index=3)
            usar_pai = st.checkbox("Vincular a um setor pai")
            setor_pai = None
            if usar_pai:
                if pais:
                    setor_pai = st.selectbox(
                        "Setor pai",
                        pais,
                        format_func=lambda x: x["nome"],
                    )
                else:
                    st.info("Cadastre um setor base antes de vincular um setor pai.")
            ativo = st.checkbox("Ativo", value=True)
            submitted = st.form_submit_button("Salvar setor", use_container_width=True)

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
            df = pd.DataFrame(setores)
            df = df.rename(
                columns={
                    "nome": "Nome",
                    "tipo_nivel": "Nível",
                    "setor_pai_id": "Setor pai",
                    "ativo": "Ativo",
                }
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum setor encontrado.")
