import streamlit as st
import pandas as pd
from services import equipamentos_service

def render():
    st.title("Equipamentos")
    dados = equipamentos_service.listar()
    if dados:
        st.dataframe(pd.DataFrame(dados), use_container_width=True)
    else:
        st.info("Nenhum equipamento encontrado.")
