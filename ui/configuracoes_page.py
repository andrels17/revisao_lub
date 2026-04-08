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
    st.markdown(
        """
        <div style="padding:1.1rem 1.2rem;border-radius:22px;border:1px solid rgba(148,163,184,.16);background:linear-gradient(135deg, rgba(15,23,42,.92), rgba(30,41,59,.88));box-shadow:0 18px 50px rgba(2,6,23,.2);margin-bottom:.9rem;">
            <div style="display:inline-block;padding:.2rem .55rem;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:.72rem;font-weight:700;color:#e2e8f0;">Ajustes centrais</div>
            <h2 style="margin:.35rem 0 0 0;color:#f8fafc;">⚙️ Configurações</h2>
            <p style="margin:.35rem 0 0 0;color:#cbd5e1;">Ajuste parâmetros operacionais do sistema. As alterações ficam salvas no banco e seguem o novo padrão visual.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cfg = configuracoes_service.carregar_todas()

    st.markdown('<div style="padding:1rem;border:1px solid rgba(148,163,184,.16);border-radius:20px;background:rgba(15,23,42,.55);box-shadow:0 10px 25px rgba(2,6,23,.14);">', unsafe_allow_html=True)
    st.subheader("Alertas de vencimento")
    nova_tolerancia = st.number_input(
        "Tolerância de 'Próximo do vencimento' (km / horas)",
        min_value=1,
        max_value=500,
        value=int(cfg["tolerancia_padrao"]),
        step=5,
        help="Itens com diferença até este valor são marcados como 🟡 Próximo em vez de 🟢 Em dia.",
    )

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")
    st.markdown('<div style="padding:1rem;border:1px solid rgba(148,163,184,.16);border-radius:20px;background:rgba(15,23,42,.55);box-shadow:0 10px 25px rgba(2,6,23,.14);">', unsafe_allow_html=True)
    st.subheader("Cache de dados")
    novo_ttl = st.slider(
        "Tempo de cache do Dashboard e Alertas (segundos)",
        min_value=10,
        max_value=600,
        value=int(cfg["ttl_cache"]),
        step=10,
        help="Valores menores deixam os dados mais atualizados, mas aumentam consultas.",
    )

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")
    st.markdown('<div style="padding:1rem;border:1px solid rgba(148,163,184,.16);border-radius:20px;background:rgba(15,23,42,.55);box-shadow:0 10px 25px rgba(2,6,23,.14);">', unsafe_allow_html=True)
    st.subheader("Leituras e operação")
    dias_sem_leitura = st.number_input(
        "Dias sem leitura para atenção operacional",
        min_value=1,
        max_value=180,
        value=int(cfg["dias_sem_leitura"]),
        step=1,
        help="Usado como referência operacional e preparado para dashboards/alertas futuros.",
    )

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")
    st.markdown('<div style="padding:1rem;border:1px solid rgba(148,163,184,.16);border-radius:20px;background:rgba(15,23,42,.55);box-shadow:0 10px 25px rgba(2,6,23,.14);">', unsafe_allow_html=True)
    st.subheader("Automação assistida de alertas")
    cooldown_horas = st.slider(
        "Cooldown entre alertas do mesmo equipamento/tipo (horas)",
        min_value=1,
        max_value=168,
        value=int(cfg.get("alerta_cooldown_horas", 24)),
        step=1,
        help="Evita reenvio excessivo na fila sugerida. Itens dentro do cooldown aparecem bloqueados.",
    )
    fila_limite = st.number_input(
        "Limite padrão da fila sugerida",
        min_value=20,
        max_value=1000,
        value=int(cfg.get("fila_alertas_limite", 200)),
        step=10,
        help="Quantidade máxima de itens sugeridos por tipo na aba de fila.",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    col_salvar, col_reset, _ = st.columns([1, 1, 3])
    with col_salvar:
        if st.button("💾 Salvar configurações", type="primary", use_container_width=True):
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
    st.caption("As configurações ficam salvas para todos os usuários. A tolerância já é aplicada imediatamente nas regras de revisão e lubrificação, e a fila sugerida passa a respeitar cooldown e limite padrão.")
