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


def _render_alertas_revisao(equipamentos):
    st.subheader("Alertas de Revisão")

    pendentes = []
    for eqp in equipamentos:
        for rev in revisoes_service.calcular_proximas_revisoes(eqp["id"]):
            if rev["status"] in ("VENCIDO", "PROXIMO"):
                pendentes.append({"eqp": eqp, "item": rev, "tipo": "revisao"})

    if not pendentes:
        st.success("Nenhuma revisão vencida ou próxima do vencimento.")
        return

    for p in pendentes:
        eqp = p["eqp"]
        rev = p["item"]
        label = STATUS_LABEL.get(rev["status"], rev["status"])
        with st.expander(f"{label} | {eqp['codigo']} - {eqp['nome']} | {rev.get('etapa', '-')}"):
            tipo = rev.get("tipo_controle", "")
            unidade = "h" if tipo == "horas" else "km"
            col1, col2 = st.columns(2)
            col1.write(f"**Setor:** {eqp.get('setor_nome', '-')}")
            col1.write(f"**Etapa:** {rev.get('etapa', '-')}")
            col2.write(f"**Leitura atual:** {float(rev.get('atual', rev.get('leitura_atual', 0))):.0f} {unidade}")
            col2.write(f"**Vencimento:** {float(rev.get('vencimento', 0)):.0f} {unidade}")

            # Responsáveis operacionais
            vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
            # Responsável de gestão do setor
            resp_gestao = vinculos_service.responsavel_gestao_setor(eqp.get("setor_id")) if eqp.get("setor_id") else None

            st.markdown("**Enviar alerta operacional (campo)**")
            if vinculos_op:
                for v in vinculos_op:
                    mensagem = alertas_service.montar_mensagem_revisao(eqp, rev, v["responsavel_nome"])
                    link = alertas_service.gerar_link_whatsapp(v["responsavel_telefone"], mensagem)
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(f"{v['responsavel_nome']} ({v['tipo_vinculo']})")
                    if v["responsavel_telefone"]:
                        if col_b.link_button("📱 WhatsApp", link):
                            alertas_service.registrar_alerta(
                                eqp["id"], v["responsavel_id"], "revisao", "operacional", mensagem
                            )
                    else:
                        col_b.caption("Sem telefone")
            else:
                st.caption("Nenhum responsável operacional vinculado a este equipamento.")

            st.markdown("**Enviar alerta de gestão (setor)**")
            if resp_gestao:
                mensagem_g = alertas_service.montar_mensagem_revisao(eqp, rev, resp_gestao["nome"])
                link_g = alertas_service.gerar_link_whatsapp(resp_gestao["telefone"], mensagem_g)
                col_a, col_b = st.columns([3, 1])
                col_a.write(f"{resp_gestao['nome']} (gestor do setor)")
                if resp_gestao["telefone"]:
                    if col_b.link_button("📱 WhatsApp", link_g, key=f"wa_gest_rev_{eqp['id']}"):
                        pass
                else:
                    col_b.caption("Sem telefone")
            else:
                st.caption("Nenhum responsável de gestão vinculado ao setor.")


def _render_alertas_lubrificacao(equipamentos):
    st.subheader("Alertas de Lubrificação")

    pendentes = []
    for eqp in equipamentos:
        for item in lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"]):
            if item["status"] in ("VENCIDO", "PROXIMO"):
                pendentes.append({"eqp": eqp, "item": item})

    if not pendentes:
        st.success("Nenhuma lubrificação vencida ou próxima do vencimento.")
        return

    for p in pendentes:
        eqp = p["eqp"]
        item = p["item"]
        label = STATUS_LABEL.get(item["status"], item["status"])
        with st.expander(f"{label} | {eqp['codigo']} - {eqp['nome']} | {item['item']}"):
            tipo = item.get("tipo_controle", "")
            unidade = "h" if tipo == "horas" else "km"
            col1, col2 = st.columns(2)
            col1.write(f"**Setor:** {eqp.get('setor_nome', '-')}")
            col1.write(f"**Item:** {item['item']} ({item['tipo_produto']})")
            col2.write(f"**Leitura atual:** {float(item['atual']):.0f} {unidade}")
            col2.write(f"**Próxima troca:** {float(item['vencimento']):.0f} {unidade}")

            vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
            resp_gestao = vinculos_service.responsavel_gestao_setor(eqp.get("setor_id")) if eqp.get("setor_id") else None

            st.markdown("**Enviar alerta operacional**")
            if vinculos_op:
                for v in vinculos_op:
                    mensagem = alertas_service.montar_mensagem_lubrificacao(eqp, item, v["responsavel_nome"])
                    link = alertas_service.gerar_link_whatsapp(v["responsavel_telefone"], mensagem)
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(f"{v['responsavel_nome']} ({v['tipo_vinculo']})")
                    if v["responsavel_telefone"]:
                        if col_b.link_button("📱 WhatsApp", link, key=f"wa_lub_op_{eqp['id']}_{item['item_id']}_{v['id']}"):
                            alertas_service.registrar_alerta(
                                eqp["id"], v["responsavel_id"], "lubrificacao", "operacional", mensagem
                            )
                    else:
                        col_b.caption("Sem telefone")
            else:
                st.caption("Nenhum responsável operacional vinculado.")

            st.markdown("**Enviar alerta de gestão**")
            if resp_gestao:
                mensagem_g = alertas_service.montar_mensagem_lubrificacao(eqp, item, resp_gestao["nome"])
                link_g = alertas_service.gerar_link_whatsapp(resp_gestao["telefone"], mensagem_g)
                col_a, col_b = st.columns([3, 1])
                col_a.write(f"{resp_gestao['nome']} (gestor)")
                if resp_gestao["telefone"]:
                    col_b.link_button("📱 WhatsApp", link_g, key=f"wa_lub_gest_{eqp['id']}_{item['item_id']}")
                else:
                    col_b.caption("Sem telefone")
            else:
                st.caption("Nenhum responsável de gestão vinculado ao setor.")


def _render_historico():
    st.subheader("Histórico de Alertas Enviados")
    historico = alertas_service.listar_historico()
    if historico:
        st.dataframe(pd.DataFrame(historico), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum alerta registrado ainda.")


def render():
    st.title("Alertas — WhatsApp")
    st.caption(
        "O sistema gera a mensagem automaticamente. Clique em 📱 WhatsApp para abrir "
        "o aplicativo com o texto pré-preenchido e envie manualmente."
    )

    equipamentos = equipamentos_service.listar()

    tab1, tab2, tab3 = st.tabs(["Revisão", "Lubrificação", "Histórico"])
    with tab1:
        _render_alertas_revisao(equipamentos)
    with tab2:
        _render_alertas_lubrificacao(equipamentos)
    with tab3:
        _render_historico()
