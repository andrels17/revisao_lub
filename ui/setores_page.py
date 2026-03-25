import streamlit as st
import pandas as pd
from services import setores_service

def render():
    st.title("Setores")
    dados = setores_service.listar()
    if dados:
        st.dataframe(pd.DataFrame(dados), use_container_width=True)
    else:
        st.info("Nenhum setor encontrado.")
