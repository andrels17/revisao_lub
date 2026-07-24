import traceback
import unicodedata
import re
import streamlit as st
import os

from ui import (
    alertas_page,
    auditoria_page,
    auth_page,
    configuracoes_page,
    controle_revisoes_page,
    dashboard_page,
    dashboard_executivo_page,
    equipamentos_page,
    grupos_page,
    prioridades_page,
    importacao_page,
    leituras_page,
    lubrificacoes_page,
    relatorio_page,
    relatorios_pdf_page,
    responsaveis_page,
    setores_page,
    templates_page,
    usuarios_page,
    vinculos_page,
)
from services import auth_service, configuracoes_service
from ui.nav import registrar_paginas

# Import seguro do tema
try:
    from ui.theme import apply_global_theme, render_sidebar_user
except ModuleNotFoundError:
    try:
        from theme import apply_global_theme, render_sidebar_user
    except ModuleNotFoundError:
        def apply_global_theme():
            return None

        def render_sidebar_user(usuario: dict, role_label: str):
            nome = usuario.get("nome") or "Usuário"
            email = usuario.get("email") or "-"
            st.sidebar.markdown(f"**{nome}**")
            st.sidebar.caption(f"{role_label} · {email}")


st.set_page_config(
    page_title="Revisão e Lubrificação",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()

# ── Verificação de configuração na inicialização ──────────────────────
def _verificar_env():
    """Verifica variáveis críticas e exibe alerta claro para o admin."""
    dsn_candidates = [
        os.getenv("DATABASE_URL"),
        os.getenv("DB_URL"),
        os.getenv("NEON_DATABASE_URL"),
        st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None,
        st.secrets.get("DB_URL") if hasattr(st, "secrets") else None,
        st.secrets.get("NEON_DATABASE_URL") if hasattr(st, "secrets") else None,
    ]
    if not any(dsn_candidates):
        st.error(
            "⚠️ **Configuração ausente:** Nenhuma string de conexão com o banco de dados foi encontrada.\n\n"
            "Defina `DATABASE_URL`, `DB_URL` ou `NEON_DATABASE_URL` em:\n"
            "- `.streamlit/secrets.toml` (local)\n"
            "- Variáveis de ambiente do servidor"
        )
        st.stop()

_verificar_env()

# Guard de autenticação
if not auth_service.usuario_logado():
    auth_page.render()
    st.stop()

try:
    configuracoes_service.aplicar_no_session_state()
except Exception:
    pass

# Estrutura de navegação: seção -> {"nome exibido" (com emoji): módulo da página}
SECOES = {
    "Painéis": {
        "🧭 Painel Operacional": dashboard_page,
        "🧠 Painel Executivo": dashboard_executivo_page,
        "🔥 Prioridades do Dia": prioridades_page,
    },
    "Operação": {
        "📏 Leituras KM / Horas": leituras_page,
        "🔧 Controle de Revisões": controle_revisoes_page,
        "🛢️ Controle de Lubrificações": lubrificacoes_page,
    },
    "Gestão": {
        "📈 Relatório de Manutenção": relatorio_page,
        "📄 Relatórios PDF": relatorios_pdf_page,
        "📱 Alertas WhatsApp": alertas_page,
        "⚙️ Configurações": configuracoes_page,
        "👥 Usuários": usuarios_page,
        "📋 Log de Auditoria": auditoria_page,
    },
    "Cadastros e Planejamento": {
        "📥 Importar Equipamentos": importacao_page,
        "🏢 Setores": setores_page,
        "🗂️ Grupos": grupos_page,
        "🚜 Equipamentos": equipamentos_page,
        "👷 Responsáveis": responsaveis_page,
        "🔗 Vínculos": vinculos_page,
        "📋 Templates": templates_page,
    },
}


def _slugify(texto: str) -> str:
    texto = (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")

    return slug or "pagina"


def _split_icon_titulo(label: str) -> tuple[str | None, str]:
    """Separa o emoji do título em labels como '🧭 Painel Operacional'."""
    partes = label.split(" ", 1)
    if len(partes) == 2 and partes[0]:
        return partes[0], partes[1]
    return None, label


def _com_tratamento_de_erro(mod, nome_pagina: str):
    """Envolve o render() de cada página com o mesmo tratamento de erro de antes,
    preservando o comportamento ao migrar para st.navigation."""

    def _render():
        try:
            mod.render()
        except Exception as exc:
            st.error(
                f"**Erro ao carregar a página '{nome_pagina}'.**\n\n"
                f"`{type(exc).__name__}: {exc}`\n\n"
                "Tente atualizar a página. Se o erro persistir, verifique a conexão com o banco de dados."
            )
            with st.expander("🔍 Detalhes técnicos"):
                st.code(traceback.format_exc(), language="python")
            if st.button("🔄 Tentar novamente", key=f"retry_{nome_pagina}"):
                st.rerun()

    return _render


usuario = auth_service.usuario_logado()
role = usuario["role"]
role_label = auth_service.ROLE_LABELS.get(role, role)
usuario = {**usuario, "role_label": role_label}

# Monta as seções de navegação já filtradas por permissão do usuário
paginas_por_secao: dict[str, list[st.Page]] = {}
registro_flat: dict[str, st.Page] = {}
slugs_usados: set[str] = set()

for secao, paginas in SECOES.items():
    lista_paginas = []
    for nome_pagina, mod in paginas.items():
        permitido = auth_service.pode_acessar(nome_pagina) or (
            nome_pagina == "👥 Usuários" and role == "admin"
        )
        if not permitido:
            continue

        icone, titulo = _split_icon_titulo(nome_pagina)
        slug_base = _slugify(titulo)
        slug = slug_base
        contador = 2
        while slug in slugs_usados:
            slug = f"{slug_base}-{contador}"
            contador += 1
        slugs_usados.add(slug)

        page_obj = st.Page(
            _com_tratamento_de_erro(mod, nome_pagina),
            title=titulo,
            icon=icone,
            url_path=slug,
        )
        lista_paginas.append(page_obj)
        registro_flat[nome_pagina] = page_obj
    if lista_paginas:
        paginas_por_secao[secao] = lista_paginas

registrar_paginas(registro_flat)

with st.sidebar:
    render_sidebar_user(usuario.get("nome"), role_label, usuario.get("email"))

if not paginas_por_secao:
    st.warning("Nenhuma página disponível para o seu perfil de acesso.")
    st.stop()

pg = st.navigation(paginas_por_secao, position="sidebar")

with st.sidebar:
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)
    if st.button("🚪 Sair", key="sidebar_logout", use_container_width=True):
        auth_service.logout()
        st.rerun()

pg.run()
