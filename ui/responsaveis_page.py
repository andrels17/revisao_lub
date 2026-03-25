
import streamlit as st
from database.connection import get_conn

def render():
    st.title("Responsáveis")

    nome = st.text_input("Nome")
    funcao = st.text_input("Função")

    if st.button("Salvar"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "insert into responsaveis (nome, funcao_principal) values (%s, %s)",
            (nome, funcao)
        )
        conn.commit()
        conn.close()
        st.success("Responsável salvo!")
