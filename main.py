import streamlit as st
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

st.set_page_config(
    page_title="Revisão e Lubrificação",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navegação estruturada ────────────────────────────────────────────────────
SECOES = {
    "📊 Painel": {
        "📊 Dashboard": dashboard_page,
    },
    "📁 Cadastros": {
        "🏢 Setores": setores_page,
        "🚜 Equipamentos": equipamentos_page,
        "👷 Responsáveis": responsaveis_page,
        "🔗 Vínculos": vinculos_page,
        "📋 Templates": templates_page,
    },
    "⚙️ Operação": {
        "📏 Leituras KM / Horas": leituras_page,
        "🔧 Controle de Revisões": controle_revisoes_page,
        "🛢️ Controle de Lubrificações": lubrificacoes_page,
    },
    "📡 Comunicação": {
        "📱 Alertas WhatsApp": alertas_page,
    },
    "🔧 Ferramentas": {
        "📥 Importar Equipamentos": importacao_page,
    },
}

# Mapa plano nome → módulo (para lookup rápido)
_PAGINAS = {nome: mod for sec in SECOES.values() for nome, mod in sec.items()}

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Menu")
    st.divider()

    if "pagina_atual" not in st.session_state:
        st.session_state["pagina_atual"] = "📊 Dashboard"

    for secao, paginas in SECOES.items():
        st.caption(secao)
        for nome_pagina in paginas:
            selecionado = st.session_state["pagina_atual"] == nome_pagina
            if st.button(
                nome_pagina,
                key=f"nav_{nome_pagina}",
                use_container_width=True,
                type="primary" if selecionado else "secondary",
            ):
                st.session_state["pagina_atual"] = nome_pagina
                st.rerun()

# ── Renderiza página ─────────────────────────────────────────────────────────
pagina_atual = st.session_state.get("pagina_atual", "📊 Dashboard")
_PAGINAS[pagina_atual].render()

