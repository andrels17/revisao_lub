"""
Página de Configurações do sistema.
Permite ajustar parâmetros operacionais sem mexer no código.
Os valores são persistidos no st.session_state e relidos pelos serviços
via ui.constants.get_tolerancia().
"""
import streamlit as st

import ui.constants as _constants
from services import dashboard_service, revisoes_service


_KEY_TOLERANCIA = "cfg_tolerancia_padrao"
_KEY_TTL        = "cfg_ttl_cache"


def get_tolerancia() -> int:
    """Retorna a tolerância ativa (session_state > constante padrão)."""
    return st.session_state.get(_KEY_TOLERANCIA, _constants.TOLERANCIA_PADRAO)


def get_ttl_cache() -> int:
    """Retorna o TTL de cache em segundos."""
    return st.session_state.get(_KEY_TTL, dashboard_service.TTL_ALERTAS)


def render():
    st.title("⚙️ Configurações")
    st.caption("Ajuste parâmetros operacionais do sistema. As alterações valem enquanto a sessão estiver aberta.")

    st.subheader("Alertas de vencimento")

    tolerancia_atual = get_tolerancia()
    nova_tolerancia = st.number_input(
        "Tolerância de 'Próximo do vencimento' (km / horas)",
        min_value=1,
        max_value=500,
        value=tolerancia_atual,
        step=5,
        help=(
            "Itens com diferença até este valor são marcados como 🟡 Próximo "
            "em vez de 🟢 Em dia. Valor padrão: "
            f"{_constants.TOLERANCIA_PADRAO} km/h."
        ),
    )

    st.divider()
    st.subheader("Cache de dados")

    ttl_atual = get_ttl_cache()
    novo_ttl = st.slider(
        "Tempo de cache do Dashboard e Alertas (segundos)",
        min_value=10,
        max_value=600,
        value=ttl_atual,
        step=10,
        help="Intervalo entre recargas automáticas dos dados do banco. Valores menores = mais atualizado, mais consultas.",
    )

    st.divider()

    col_salvar, col_reset, _ = st.columns([1, 1, 3])

    with col_salvar:
        if st.button("💾 Aplicar", type="primary", use_container_width=True):
            st.session_state[_KEY_TOLERANCIA] = int(nova_tolerancia)
            st.session_state[_KEY_TTL]        = int(novo_ttl)

            # Propaga tolerância para os módulos de serviço em runtime
            import ui.constants as c
            c.TOLERANCIA_PADRAO = int(nova_tolerancia)

            # Invalida caches para que o novo valor seja usado imediatamente
            try:
                dashboard_service.carregar_alertas.clear()
            except Exception:
                pass

            st.success(
                f"Configurações aplicadas! "
                f"Tolerância: **{nova_tolerancia} km/h** | "
                f"Cache: **{novo_ttl}s**"
            )

    with col_reset:
        if st.button("↩️ Restaurar padrões", use_container_width=True):
            st.session_state.pop(_KEY_TOLERANCIA, None)
            st.session_state.pop(_KEY_TTL, None)
            import ui.constants as c
            c.TOLERANCIA_PADRAO = _constants.__class__.__dict__.get(
                "TOLERANCIA_PADRAO", 10
            ) if False else 10
            try:
                dashboard_service.carregar_alertas.clear()
            except Exception:
                pass
            st.success("Padrões restaurados.")
            st.rerun()

    st.divider()
    st.caption(
        "💡 **Dica:** A tolerância afeta revisões e lubrificações simultaneamente. "
        "Para mudanças permanentes, edite `TOLERANCIA_PADRAO` em `ui/constants.py`."
    )
