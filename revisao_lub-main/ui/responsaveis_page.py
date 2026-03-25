import streamlit as st
import pandas as pd
from services import responsaveis_service

def render():
    st.title("Responsáveis")
    dados = responsaveis_service.listar()
    if dados:
        st.dataframe(pd.DataFrame(dados), use_container_width=True)
    else:
        st.info("Nenhum responsável encontrado.")
