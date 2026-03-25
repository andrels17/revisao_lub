
import streamlit as st
from database.connection import get_conn

def render():
    st.title("Equipamentos")

    codigo = st.text_input("Código")
    nome = st.text_input("Nome")
    tipo = st.text_input("Tipo")

    if st.button("Salvar"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "insert into equipamentos (codigo, nome, tipo) values (%s, %s, %s)",
            (codigo, nome, tipo)
        )
        conn.commit()
        conn.close()
        st.success("Equipamento salvo!")
