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
from ui import auth_page, usuarios_page
from services import auth_service, configuracoes_service, escopo_service

st.set_page_config(
    page_title="Revisão e Lubrificação",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        [data-testid="column"] { min-width: 48% !important; }
        [data-testid="stMetric"] { font-size: 0.85rem; }
        .stDataFrame { font-size: 0.75rem; }
    }
    section[data-testid="stSidebar"] button {
        min-height: 2.6rem;
        font-size: 0.88rem;
    }
    details summary { font-size: 0.92rem; }
    [data-testid="stDataFrame"] { overflow-x: auto; }
    @media (max-width: 768px) {
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Guard de autenticação ─────────────────────────────────────────────────────
if not auth_service.usuario_logado():
    auth_page.render()
    st.stop()

# ── Carrega configurações persistentes ──────────────────────────────────────
configuracoes_service.aplicar_no_session_state()

# ── Estrutura completa de páginas ─────────────────────────────────────────────
SECOES = {
    "📊 Painel": {
        "📊 Dashboard": dashboard_page,
    },
    "📁 Cadastros": {
        "🏢 Setores":        setores_page,
        "🚜 Equipamentos":   equipamentos_page,
        "👷 Responsáveis":   responsaveis_page,
        "🔗 Vínculos":       vinculos_page,
        "📋 Templates":      templates_page,
    },
    "⚙️ Operação": {
        "📏 Leituras KM / Horas":        leituras_page,
        "🔧 Controle de Revisões":       controle_revisoes_page,
        "🛢️ Controle de Lubrificações": lubrificacoes_page,
    },
    "📡 Comunicação": {
        "📱 Alertas WhatsApp": alertas_page,
    },
    "🔧 Ferramentas": {
        "📥 Importar Equipamentos":  importacao_page,
        "📈 Relatório de Manutenção": relatorio_page,
        "⚙️ Configurações":          configuracoes_page,
        "👥 Usuários":               usuarios_page,   # visível só para admin
    },
}

# Filtra páginas pelo role do usuário logado
usuario = auth_service.usuario_logado()
role    = usuario["role"]

SECOES_FILTRADAS = {}
for secao, paginas in SECOES.items():
    paginas_permitidas = {
        nome: mod
        for nome, mod in paginas.items()
        if auth_service.pode_acessar(nome)
        # Usuários é especial: aparece para admin via role_paginas
        or (nome == "👥 Usuários" and role == "admin")
    }
    if paginas_permitidas:
        SECOES_FILTRADAS[secao] = paginas_permitidas

_PAGINAS = {nome: mod for sec in SECOES_FILTRADAS.values() for nome, mod in sec.items()}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Cabeçalho do usuário logado
    role_label = auth_service.ROLE_LABELS.get(role, role)
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 0.25rem;">
            <div style="font-weight: 600; font-size: 0.9rem;">{usuario['nome']}</div>
            <div style="font-size: 0.75rem; opacity: 0.65;">{role_label} · {usuario['email']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚪 Sair", use_container_width=True, type="secondary"):
        auth_service.logout()
        st.rerun()

    st.divider()
    st.caption(f"Escopo: {escopo_service.resumo_escopo()}")

    # Define página padrão (primeira disponível para o role)
    if "pagina_atual" not in st.session_state:
        primeira = next(iter(_PAGINAS), None)
        st.session_state["pagina_atual"] = primeira or ""

    # Garante que a página atual ainda é acessível após mudança de role
    if st.session_state.get("pagina_atual") not in _PAGINAS:
        st.session_state["pagina_atual"] = next(iter(_PAGINAS), "")

    for secao, paginas in SECOES_FILTRADAS.items():
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

# ── Renderiza página com tratamento de erro global ────────────────────────────
pagina_atual = st.session_state.get("pagina_atual", "")

if not pagina_atual or pagina_atual not in _PAGINAS:
    st.warning("Selecione uma página no menu lateral.")
else:
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
