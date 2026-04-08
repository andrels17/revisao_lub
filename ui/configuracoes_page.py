"""
Página de Configurações do sistema.
Agora os valores são persistidos no banco e reaplicados a cada login/sessão.
"""
import streamlit as st

from services import configuracoes_service, dashboard_service


def get_tolerancia() -> int:
    return configuracoes_service.get_tolerancia_padrao()


def get_ttl_cache() -> int:
    return configuracoes_service.get_ttl_cache()


def render():
    st.title("⚙️ Configurações")
    st.caption("Ajuste parâmetros operacionais do sistema. As alterações ficam salvas no banco.")

    cfg = configuracoes_service.carregar_todas()

    st.subheader("Alertas de vencimento")
    nova_tolerancia = st.number_input(
        "Tolerância de 'Próximo do vencimento' (km / horas)",
        min_value=1,
        max_value=500,
        value=int(cfg["tolerancia_padrao"]),
        step=5,
        help="Itens com diferença até este valor são marcados como 🟡 Próximo em vez de 🟢 Em dia.",
    )

    st.divider()
    st.subheader("Cache de dados")
    novo_ttl = st.slider(
        "Tempo de cache do Dashboard e Alertas (segundos)",
        min_value=10,
        max_value=600,
        value=int(cfg["ttl_cache"]),
        step=10,
        help="Valores menores deixam os dados mais atualizados, mas aumentam consultas.",
    )

    st.divider()
    st.subheader("Leituras e operação")
    dias_sem_leitura = st.number_input(
        "Dias sem leitura para atenção operacional",
        min_value=1,
        max_value=180,
        value=int(cfg["dias_sem_leitura"]),
        step=1,
        help="Usado como referência operacional e preparado para dashboards/alertas futuros.",
    )

    col_salvar, col_reset, _ = st.columns([1, 1, 3])
    with col_salvar:
        if st.button("💾 Salvar configurações", type="primary", use_container_width=True):
            configuracoes_service.salvar({
                "tolerancia_padrao": int(nova_tolerancia),
                "ttl_cache": int(novo_ttl),
                "dias_sem_leitura": int(dias_sem_leitura),
            })
            try:
                dashboard_service.carregar_alertas.clear()
            except Exception:
                pass
            st.success(
                f"Configurações salvas. Tolerância: {int(nova_tolerancia)} | Cache: {int(novo_ttl)}s | Dias sem leitura: {int(dias_sem_leitura)}"
            )
            st.rerun()

    with col_reset:
        if st.button("↩️ Restaurar padrões", use_container_width=True):
            configuracoes_service.resetar()
            try:
                dashboard_service.carregar_alertas.clear()
            except Exception:
                pass
            st.success("Padrões restaurados com sucesso.")
            st.rerun()

    st.divider()
    st.caption("As configurações ficam salvas para todos os usuários. A tolerância já é aplicada imediatamente nas regras de revisão e lubrificação.")
