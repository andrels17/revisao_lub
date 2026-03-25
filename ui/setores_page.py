
import streamlit as st
from database.connection import get_conn

def render():
    st.title("Setores")

    nome = st.text_input("Nome")
    tipo = st.selectbox("Tipo", ["unidade", "departamento", "setor", "grupo"])

    if st.button("Salvar"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("insert into setores (nome, tipo_nivel) values (%s, %s)", (nome, tipo))
        conn.commit()
        conn.close()
        st.success("Salvo!")

