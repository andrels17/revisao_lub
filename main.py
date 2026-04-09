import streamlit as st
from ui import (
    alertas_page,
    auth_page,
    configuracoes_page,
    controle_revisoes_page,
    dashboard_page,
    equipamentos_page,
    importacao_page,
    leituras_page,
    lubrificacoes_page,
    relatorio_page,
    responsaveis_page,
    setores_page,
    templates_page,
    usuarios_page,
    vinculos_page,
)
from services import auth_service, configuracoes_service

# Import seguro do tema
try:
    from ui.theme import apply_global_theme, render_sidebar_user, render_topbar
except ModuleNotFoundError:
    try:
        from theme import apply_global_theme, render_sidebar_user, render_topbar
    except ModuleNotFoundError:
        def apply_global_theme():
            return None

        def render_sidebar_user(usuario: dict, role_label: str):
            nome = usuario.get("nome") or "Usuário"
            email = usuario.get("email") or "-"
            st.sidebar.markdown(f"**{nome}**")
            st.sidebar.caption(f"{role_label} · {email}")

        def render_topbar(usuario: dict, pagina_atual: str):
            st.title(pagina_atual)


st.set_page_config(
    page_title="Revisão e Lubrificação",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()

# Guard de autenticação
if not auth_service.usuario_logado():
    auth_page.render()
    st.stop()

try:
    configuracoes_service.aplicar_no_session_state()
except Exception:
    pass

SECOES = {
    "Painel": {
        "📊 Dashboard": dashboard_page,
    },
    "Operação": {
        "📏 Leituras KM / Horas": leituras_page,
        "🔧 Controle de Revisões": controle_revisoes_page,
        "🛢️ Controle de Lubrificações": lubrificacoes_page,
    },
    "Comunicação": {
        "📱 Alertas WhatsApp": alertas_page,
    },
    "Ferramentas": {
        "📥 Importar Equipamentos": importacao_page,
        "📈 Relatório de Manutenção": relatorio_page,
        "⚙️ Configurações": configuracoes_page,
        "👥 Usuários": usuarios_page,
    },
    "Cadastros": {
        "🏢 Setores": setores_page,
        "🚜 Equipamentos": equipamentos_page,
        "👷 Responsáveis": responsaveis_page,
        "🔗 Vínculos": vinculos_page,
        "📋 Templates": templates_page,
    },
}

usuario = auth_service.usuario_logado()
role = usuario["role"]
role_label = auth_service.ROLE_LABELS.get(role, role)
usuario = {**usuario, "role_label": role_label}

secoes_filtradas = {}
for secao, paginas in SECOES.items():
    paginas_permitidas = {
        nome: mod
        for nome, mod in paginas.items()
        if auth_service.pode_acessar(nome) or (nome == "👥 Usuários" and role == "admin")
    }
    if paginas_permitidas:
        secoes_filtradas[secao] = paginas_permitidas

paginas_map = {nome: mod for sec in secoes_filtradas.values() for nome, mod in sec.items()}

with st.sidebar:
    render_sidebar_user(usuario.get("nome"), role_label, usuario.get("email"))

    if "pagina_atual" not in st.session_state:
        primeira = next(iter(paginas_map), None)
        st.session_state["pagina_atual"] = primeira or ""

    if st.session_state.get("pagina_atual") not in paginas_map:
        st.session_state["pagina_atual"] = next(iter(paginas_map), "")

    for secao, paginas in secoes_filtradas.items():
        st.markdown(f"<div class='sidebar-section'>{secao}</div>", unsafe_allow_html=True)
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

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)

    if st.button("🚪 Sair", key="sidebar_logout", use_container_width=True):
        auth_service.logout()
        st.rerun()

pagina_atual = st.session_state.get("pagina_atual", "")

if not pagina_atual or pagina_atual not in paginas_map:
    st.warning("Selecione uma página no menu lateral.")
else:
    try:
        paginas_map[pagina_atual].render()
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
