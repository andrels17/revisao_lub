import streamlit as st
from ui.components import global_search
from ui import (
    dashboard_page,
    equipamentos_page,
    setores_page,
    responsaveis_page,
    controle_revisoes_page,
    lubrificacoes_page,
    templates_page,
    vinculos_page,
    leituras_page,
    alertas_page,
    importacao_page,
)

st.set_page_config(page_title="Revisão e Lubrificação", layout="wide")

MENU = {
    "📊 Dashboard":              dashboard_page,
    "─── CADASTROS ───":         None,
    "🏢 Setores":                setores_page,
    "🚜 Equipamentos":           equipamentos_page,
    "👷 Responsáveis":           responsaveis_page,
    "🔗 Vínculos":               vinculos_page,
    "📋 Templates":              templates_page,
    "─── OPERAÇÃO ───":          None,
    "📏 Leituras KM / Horas":    leituras_page,
    "🔧 Controle de Revisões":   controle_revisoes_page,
    "🛢️ Controle de Lubrificações": lubrificacoes_page,
    "─── COMUNICAÇÃO ───":       None,
    "📱 Alertas WhatsApp":       alertas_page,
    "─── FERRAMENTAS ───":       None,
    "📥 Importar Equipamentos":  importacao_page,
}

opcoes_validas = [k for k, v in MENU.items() if v is not None and not k.startswith("─")]
separadores    = [k for k, v in MENU.items() if v is None or k.startswith("─")]

# Sidebar com seções visuais
st.sidebar.title("Menu")
if 'main_menu' not in st.session_state or st.session_state['main_menu'] not in opcoes_validas:
    st.session_state['main_menu'] = opcoes_validas[0]

menu = st.sidebar.selectbox(
    "Navegar",
    opcoes_validas,
    index=opcoes_validas.index(st.session_state['main_menu']),
)
st.session_state['main_menu'] = menu

with st.container():
    global_search.render()
    st.divider()

MENU[menu].render()
