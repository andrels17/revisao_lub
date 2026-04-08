"""Página de Configurações do sistema."""
import streamlit as st

from services import configuracoes_service, dashboard_service
from ui.theme import render_page_intro


def get_tolerancia() -> int:
    return configuracoes_service.get_tolerancia_padrao()


def get_ttl_cache() -> int:
    return configuracoes_service.get_ttl_cache()


def render():
    render_page_intro(
        "Parâmetros operacionais do sistema",
        "Ajuste tolerâncias, cache e automações com uma visualização mais limpa e padronizada.",
        "Ferramentas",
    )

    cfg = configuracoes_service.carregar_todas()

    with st.form("form_configuracoes"):
        st.markdown("### Alertas de vencimento")
        nova_tolerancia = st.number_input(
            "Tolerância de 'Próximo do vencimento' (km / horas)",
            min_value=1,
            max_value=500,
            value=int(cfg["tolerancia_padrao"]),
            step=5,
            help="Itens com diferença até este valor são marcados como Próximo em vez de Em dia.",
        )

        st.markdown("### Cache de dados")
        novo_ttl = st.slider(
            "Tempo de cache do Dashboard e Alertas (segundos)",
            min_value=10,
            max_value=600,
            value=int(cfg["ttl_cache"]),
            step=10,
            help="Valores menores deixam os dados mais atualizados, mas aumentam consultas.",
        )

        st.markdown("### Leituras e operação")
        dias_sem_leitura = st.number_input(
            "Dias sem leitura para atenção operacional",
            min_value=1,
            max_value=180,
            value=int(cfg["dias_sem_leitura"]),
            step=1,
            help="Usado como referência operacional e preparado para dashboards e alertas futuros.",
        )

        st.markdown("### Automação assistida de alertas")
        cooldown_horas = st.slider(
            "Cooldown entre alertas do mesmo equipamento/tipo (horas)",
            min_value=1,
            max_value=168,
            value=int(cfg.get("alerta_cooldown_horas", 24)),
            step=1,
            help="Evita reenvio excessivo na fila sugerida.",
        )
        fila_limite = st.number_input(
            "Limite padrão da fila sugerida",
            min_value=20,
            max_value=1000,
            value=int(cfg.get("fila_alertas_limite", 200)),
            step=10,
            help="Quantidade máxima de itens sugeridos por tipo na aba de fila.",
        )

        col_salvar, col_reset = st.columns(2)
        salvar = col_salvar.form_submit_button("Salvar configurações", type="primary", use_container_width=True)
        reset = col_reset.form_submit_button("Restaurar padrões", use_container_width=True)

    if salvar:
        configuracoes_service.salvar({
            "tolerancia_padrao": int(nova_tolerancia),
            "ttl_cache": int(novo_ttl),
            "dias_sem_leitura": int(dias_sem_leitura),
            "alerta_cooldown_horas": int(cooldown_horas),
            "fila_alertas_limite": int(fila_limite),
        })
        try:
            dashboard_service.carregar_alertas.clear()
        except Exception:
            pass
        st.success(
            f"Configurações salvas. Tolerância: {int(nova_tolerancia)} | Cache: {int(novo_ttl)}s | Dias sem leitura: {int(dias_sem_leitura)} | Cooldown: {int(cooldown_horas)}h"
        )
        st.rerun()

    if reset:
        configuracoes_service.resetar()
        try:
            dashboard_service.carregar_alertas.clear()
        except Exception:
            pass
        st.success("Padrões restaurados com sucesso.")
        st.rerun()

    st.caption("As configurações ficam salvas para todos os usuários e passam a ser aplicadas logo após o salvamento.")
