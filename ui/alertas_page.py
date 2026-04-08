import pandas as pd
import streamlit as st

from services import (
    alertas_service,
    equipamentos_service,
    revisoes_service,
    lubrificacoes_service,
    vinculos_service,
)

STATUS_LABEL = {"VENCIDO": "🔴 Vencido", "PROXIMO": "🟡 Próximo", "EM DIA": "🟢 Em dia"}


@st.cache_data(ttl=60, show_spinner="Carregando pendências…")
def _carregar_pendencias():
    """
    Carrega revisões e lubrificações pendentes em batch.
    Antes: 1 query por equipamento × 2 tipos = N*2 queries.
    Agora: 2 queries totais.
    """
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], []

    ids    = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}

    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)

    pendencias_rev = []
    pendencias_lub = []

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]
        for rev in rev_idx.get(eqp_id, []):
            if rev["status"] in ("VENCIDO", "PROXIMO"):
                pendencias_rev.append({"eqp": eqp, "item": rev})
        for lub in lub_idx.get(eqp_id, []):
            if lub["status"] in ("VENCIDO", "PROXIMO"):
                pendencias_lub.append({"eqp": eqp, "item": lub})

    return pendencias_rev, pendencias_lub


def _card_alerta(eqp, item, tipo):
    """Renderiza expander com info + botões WhatsApp para um item."""
    label_status = STATUS_LABEL.get(item["status"], item["status"])
    unidade = "h" if item.get("tipo_controle") == "horas" else "km"
    etapa_label = item.get("etapa", item.get("item", "-"))

    with st.expander(f"{label_status} | {eqp['codigo']} - {eqp['nome']} | {etapa_label}"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Setor",         eqp.get("setor_nome", "-"))
        col2.metric(f"Leitura atual ({unidade})", f"{float(item.get('atual', item.get('leitura_atual', 0))):.0f}")
        col3.metric(f"Vencimento ({unidade})",    f"{float(item.get('vencimento', 0)):.0f}")

        falta = float(item.get("diferenca", item.get("falta", 0)))
        if falta <= 0:
            st.error(f"Vencido há {abs(falta):.0f} {unidade}")
        else:
            st.warning(f"Faltam {falta:.0f} {unidade}")

        vinculos_op  = vinculos_service.listar_por_equipamento(eqp["id"])
        resp_gestao  = vinculos_service.responsavel_gestao_setor(eqp.get("setor_id")) if eqp.get("setor_id") else None

        st.markdown("**Responsáveis operacionais**")
        if vinculos_op:
            for v in vinculos_op:
                if tipo == "revisao":
                    msg  = alertas_service.montar_mensagem_revisao(eqp, item, v["responsavel_nome"])
                else:
                    msg  = alertas_service.montar_mensagem_lubrificacao(eqp, item, v["responsavel_nome"])
                link = alertas_service.gerar_link_whatsapp(v["responsavel_telefone"], msg)

                ca, cb = st.columns([4, 1])
                ca.write(f"{v['responsavel_nome']} ({v['tipo_vinculo']})")
                if v["responsavel_telefone"]:
                    key_wa = f"wa_{tipo}_{eqp['id']}_{item.get('item_id', item.get('etapa_id', 0))}_{v['id']}"
                    if cb.link_button("📱 WhatsApp", link, key=key_wa):
                        alertas_service.registrar_alerta(eqp["id"], v["responsavel_id"], tipo, "operacional", msg)
                else:
                    cb.caption("Sem telefone")
        else:
            st.caption("Nenhum responsável operacional vinculado.")

        if resp_gestao:
            st.markdown("**Responsável de gestão**")
            if tipo == "revisao":
                msg_g  = alertas_service.montar_mensagem_revisao(eqp, item, resp_gestao["nome"])
            else:
                msg_g  = alertas_service.montar_mensagem_lubrificacao(eqp, item, resp_gestao["nome"])
            link_g = alertas_service.gerar_link_whatsapp(resp_gestao["telefone"], msg_g)
            ca, cb = st.columns([4, 1])
            ca.write(f"{resp_gestao['nome']} (gestor do setor)")
            if resp_gestao["telefone"]:
                key_g = f"wa_gest_{tipo}_{eqp['id']}_{item.get('item_id', item.get('etapa_id', 0))}"
                cb.link_button("📱 WhatsApp", link_g, key=key_g)
            else:
                cb.caption("Sem telefone")


def _render_historico():
    st.subheader("Histórico de alertas enviados")
    historico = alertas_service.listar_historico()

    if not historico:
        st.info("Nenhum alerta registrado ainda.")
        return

    df = pd.DataFrame(historico)

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        tipos = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist())
        tipo_f = st.selectbox("Tipo", tipos, key="hist_tipo")
    with col2:
        perfis = ["Todos"] + sorted(df["perfil"].dropna().unique().tolist())
        perfil_f = st.selectbox("Perfil", perfis, key="hist_perfil")
    with col3:
        eqps = ["Todos"] + sorted(df["equipamento"].dropna().unique().tolist())
        eqp_f = st.selectbox("Equipamento", eqps, key="hist_eqp")

    if tipo_f   != "Todos": df = df[df["tipo"]        == tipo_f]
    if perfil_f != "Todos": df = df[df["perfil"]       == perfil_f]
    if eqp_f    != "Todos": df = df[df["equipamento"]  == eqp_f]

    st.dataframe(df, use_container_width=True, hide_index=True)


def render():
    col_t, col_b = st.columns([5, 1])
    with col_t:
        st.title("Alertas — WhatsApp")
        st.caption("Clique em 📱 WhatsApp para abrir o app com a mensagem pré-preenchida.")
    with col_b:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega pendências"):
            _carregar_pendencias.clear()
            st.rerun()

    pendencias_rev, pendencias_lub = _carregar_pendencias()

    tab1, tab2, tab3 = st.tabs([
        f"Revisão ({len(pendencias_rev)})",
        f"Lubrificação ({len(pendencias_lub)})",
        "Histórico",
    ])

    with tab1:
        if not pendencias_rev:
            st.success("Nenhuma revisão vencida ou próxima do vencimento.")
        else:
            for p in pendencias_rev:
                _card_alerta(p["eqp"], p["item"], "revisao")

    with tab2:
        if not pendencias_lub:
            st.success("Nenhuma lubrificação vencida ou próxima do vencimento.")
        else:
            for p in pendencias_lub:
                _card_alerta(p["eqp"], p["item"], "lubrificacao")

    with tab3:
        _render_historico()
