import streamlit as st
from ui import dashboard_page, equipamentos_page, setores_page, responsaveis_page, controle_revisoes_page

st.set_page_config(page_title="Revisão e Lubrificação", layout="wide")

menu = st.sidebar.selectbox(
    "Menu",
    [
        "Dashboard",
        "Setores",
        "Equipamentos",
        "Responsáveis",
        "Controle de Revisões",
    ],
)

if menu == "Dashboard":
    dashboard_page.render()
elif menu == "Setores":
    setores_page.render()
elif menu == "Equipamentos":
    equipamentos_page.render()
elif menu == "Responsáveis":
    responsaveis_page.render()
elif menu == "Controle de Revisões":
    controle_revisoes_page.render()
