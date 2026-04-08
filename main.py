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
    relatorio_page,
    configuracoes_page,
)

st.set_page_config(
    page_title="Revisão e Lubrificação",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS global — responsividade mobile + ajustes visuais ─────────────────────
st.markdown(
    """
    <style>
    /* Cards de métrica com quebra de linha no mobile */
    @media (max-width: 640px) {
        [data-testid="column"] { min-width: 48% !important; }
        [data-testid="stMetric"] { font-size: 0.85rem; }
        .stDataFrame { font-size: 0.75rem; }
    }

    /* Botões do menu lateral — melhor toque em mobile */
    section[data-testid="stSidebar"] button {
        min-height: 2.6rem;
        font-size: 0.88rem;
    }

    /* Expanders com visual mais suave */
    details summary {
        font-size: 0.92rem;
    }

    /* Tabelas com scroll horizontal em telas pequenas */
    [data-testid="stDataFrame"] {
        overflow-x: auto;
    }

    /* Remover padding excessivo em containers estreitos */
    @media (max-width: 768px) {
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
        "📈 Relatório de Manutenção": relatorio_page,
        "⚙️ Configurações": configuracoes_page,
    },
}

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

# ── Renderiza página com tratamento de erro global ───────────────────────────
pagina_atual = st.session_state.get("pagina_atual", "📊 Dashboard")
try:
    _PAGINAS[pagina_atual].render()
except Exception as exc:
    st.error(
        f"**Erro ao carregar a página '{pagina_atual}'.**\n\n"
        f"`{type(exc).__name__}: {exc}`\n\n"
        "Tente atualizar a página. Se o erro persistir, verifique a conexão com o banco de dados."
    )
    with st.expander("🔍 Detalhes técnicos"):
        import traceback
        st.code(traceback.format_exc(), language="python")
    if st.button("🔄 Tentar novamente"):
        st.rerun()
