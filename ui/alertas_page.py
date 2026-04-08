import datetime

import pandas as pd
import streamlit as st

from services import (
    alertas_service,
    equipamentos_service,
    revisoes_service,
    lubrificacoes_service,
    vinculos_service,
    configuracoes_service,
)
from ui.constants import STATUS_LABEL
from ui.exportacao import botao_exportar_excel


@st.cache_data(ttl=60, show_spinner="Carregando pendências…")
def _carregar_pendencias():
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], [], {}

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}

    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    enviados_hoje = alertas_service.alertas_enviados_hoje_batch(ids)

    pendencias_rev = []
    pendencias_lub = []

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]
        for rev in rev_idx.get(eqp_id, []):
            if rev["status"] in ("VENCIDO", "PROXIMO"):
                pendencias_rev.append({
                    "eqp": eqp,
                    "item": rev,
                    "enviado_hoje": enviados_hoje.get((eqp_id, "revisao"), False),
                })
        for lub in lub_idx.get(eqp_id, []):
            if lub["status"] in ("VENCIDO", "PROXIMO"):
                pendencias_lub.append({
                    "eqp": eqp,
                    "item": lub,
                    "enviado_hoje": enviados_hoje.get((eqp_id, "lubrificacao"), False),
                })

    return pendencias_rev, pendencias_lub, enviados_hoje


def _card_alerta(eqp, item, tipo, enviado_hoje: bool):
    label_status = STATUS_LABEL.get(item["status"], item["status"])
    unidade = "h" if item.get("tipo_controle") == "horas" else "km"
    etapa_label = item.get("etapa", item.get("item", "-"))
    falta = float(item.get("diferenca", item.get("falta", 0)))
    sufixo = "  ✉️ enviado hoje" if enviado_hoje else ""

    with st.expander(f"{label_status}  |  {eqp['codigo']} — {eqp['nome']}  |  {etapa_label}{sufixo}"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Setor", eqp.get("setor_nome", "-"))
        col2.metric(f"Leitura atual ({unidade})", f"{float(item.get('atual', item.get('leitura_atual', 0))):.0f}")
        col3.metric(f"Vencimento ({unidade})", f"{float(item.get('vencimento', 0)):.0f}")

        if falta <= 0:
            st.error(f"⚠️ Vencido há {abs(falta):.0f} {unidade}")
        else:
            st.warning(f"⏰ Faltam {falta:.0f} {unidade}")

        if enviado_hoje:
            st.info("✉️ Um alerta já foi enviado para este equipamento hoje.")

        vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
        resp_gestao = vinculos_service.responsavel_gestao_setor(eqp.get("setor_id")) if eqp.get("setor_id") else None

        st.markdown("**Responsáveis operacionais**")
        if vinculos_op:
            for v in vinculos_op:
                msg = alertas_service.montar_mensagem_revisao(eqp, item, v["responsavel_nome"]) if tipo == "revisao" else alertas_service.montar_mensagem_lubrificacao(eqp, item, v["responsavel_nome"])
                link = alertas_service.gerar_link_whatsapp(v["responsavel_telefone"], msg)

                ca, cb = st.columns([4, 1])
                ca.write(f"{v['responsavel_nome']} ({v['tipo_vinculo']})")
                if v["responsavel_telefone"]:
                    key_wa = f"wa_{tipo}_{eqp['id']}_{item.get('item_id', item.get('etapa_id', 0))}_{v['id']}"
                    if cb.link_button("📱 WhatsApp", link, key=key_wa):
                        alertas_service.registrar_alerta(eqp["id"], v["responsavel_id"], tipo, "operacional", msg)
                        _carregar_pendencias.clear()
                        st.rerun()
                else:
                    cb.caption("Sem telefone")
        else:
            st.caption("Nenhum responsável operacional vinculado.")

        if resp_gestao:
            st.markdown("**Responsável de gestão**")
            msg_g = alertas_service.montar_mensagem_revisao(eqp, item, resp_gestao["nome"]) if tipo == "revisao" else alertas_service.montar_mensagem_lubrificacao(eqp, item, resp_gestao["nome"])
            link_g = alertas_service.gerar_link_whatsapp(resp_gestao["telefone"], msg_g)
            ca, cb = st.columns([4, 1])
            ca.write(f"{resp_gestao['nome']} (gestor do setor)")
            if resp_gestao["telefone"]:
                key_g = f"wa_gest_{tipo}_{eqp['id']}_{item.get('item_id', item.get('etapa_id', 0))}"
                if cb.link_button("📱 WhatsApp", link_g, key=key_g):
                    alertas_service.registrar_alerta(eqp["id"], resp_gestao.get("id"), tipo, "gestao", msg_g)
                    _carregar_pendencias.clear()
                    st.rerun()
            else:
                cb.caption("Sem telefone")


def _render_historico():
    st.subheader("Histórico de alertas enviados")
    hoje = datetime.date.today()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        data_ini = st.date_input("De", value=hoje - datetime.timedelta(days=30), key="hist_ini")
    with col2:
        data_fim = st.date_input("Até", value=hoje, key="hist_fim")
    with col3:
        tipo_f = st.selectbox("Tipo", ["Todos", "revisao", "lubrificacao"], key="hist_tipo")
    with col4:
        perfil_f = st.selectbox("Perfil", ["Todos", "operacional", "gestao"], key="hist_perfil")

    historico = alertas_service.listar_historico(
        limite=500,
        data_inicio=data_ini,
        data_fim=data_fim,
        tipo=None if tipo_f == "Todos" else tipo_f,
        perfil=None if perfil_f == "Todos" else perfil_f,
    )
    if not historico:
        st.info("Nenhum alerta registrado para os filtros selecionados.")
        return
    df = pd.DataFrame(historico)
    st.caption(f"{len(df)} alerta(s) encontrado(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)
    botao_exportar_excel(df, "historico_alertas", label="⬇️ Excel", key="exp_hist_alertas")


def _render_cobertura(fila: dict):
    resumo = fila.get("resumo", {})
    cobertura = fila.get("cobertura", {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total sugerido", resumo.get("total", 0))
    c2.metric("Prontos para envio", resumo.get("prontos_envio", 0))
    c3.metric("Cobertura operacional", f"{cobertura.get('percentual_operacional', 0)}%")
    c4.metric("Cobertura gestão", f"{cobertura.get('percentual_gestao', 0)}%")
    c5.metric("Bloqueados cooldown", resumo.get("bloqueados", 0))
    setores = cobertura.get("setores", [])
    if setores:
        st.caption("Cobertura por setor")
        st.dataframe(pd.DataFrame(setores), use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de cobertura por setor.")


def _render_fila_sugerida(fila: dict):
    st.subheader("Fila sugerida do dia")
    st.caption("Organiza prioridade, bloqueio por cooldown e cobertura operacional x gestão. O envio em massa abaixo apenas registra o disparo feito fora do sistema.")
    _render_cobertura(fila)
    st.divider()

    itens = fila.get("revisao", []) + fila.get("lubrificacao", [])
    if not itens:
        st.info("Nenhuma fila sugerida para hoje.")
        return

    df = pd.DataFrame(itens)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tipo = st.selectbox("Tipo da fila", ["Todos", "revisao", "lubrificacao"], key="fila_tipo")
    with col2:
        modo = st.selectbox("Mostrar", ["Todos", "Somente prontos", "Sem cobertura"], key="fila_modo")
    with col3:
        status = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO"], key="fila_status")
    with col4:
        limite = st.number_input("Limite visual", min_value=10, max_value=500, value=min(len(df), 100), step=10, key="fila_limite")

    dfv = df.copy()
    if tipo != "Todos":
        dfv = dfv[dfv["tipo_alerta"] == tipo]
    if modo == "Somente prontos":
        dfv = dfv[~dfv["bloqueado_cooldown"]]
    elif modo == "Sem cobertura":
        dfv = dfv[(~dfv["tem_operacional"]) | (~dfv["tem_gestao"])]
    if status != "Todos":
        dfv = dfv[dfv["status"] == status]

    dfv = dfv.sort_values(["prioridade", "status", "equipamento"], ascending=[False, True, True]).head(int(limite))
    col_exp1, col_exp2 = st.columns([5, 1])
    with col_exp2:
        botao_exportar_excel(dfv, "fila_alertas", label="⬇️ Excel", key="exp_fila_alertas")
    st.dataframe(dfv, use_container_width=True, hide_index=True)

    opcoes = [f"{r.equipamento} | {r.tipo_alerta} | {r.item}" for r in dfv.itertuples()]
    mapa = {f"{r.equipamento} | {r.tipo_alerta} | {r.item}": r._asdict() for r in dfv.itertuples()}
    selecionados = st.multiselect("Itens para registrar envio em lote", opcoes, key="fila_select")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ Registrar lote operacional", use_container_width=True, key="reg_lote_op") and selecionados:
            payload = []
            for chave in selecionados:
                item = mapa[chave]
                payload.append({
                    "equipamento_id": item["equipamento_id"],
                    "responsavel_id": None,
                    "tipo_alerta": item["tipo_alerta"],
                    "mensagem": f"registro_lote_operacional: {item['equipamento']} / {item['item']}",
                })
            qtd = alertas_service.registrar_alerta_lote(payload, perfil="operacional")
            _carregar_pendencias.clear()
            st.success(f"{qtd} alerta(s) registrados em lote para operacional.")
            st.rerun()
    with col_b:
        if st.button("✅ Registrar lote gestão", use_container_width=True, key="reg_lote_gest") and selecionados:
            payload = []
            for chave in selecionados:
                item = mapa[chave]
                payload.append({
                    "equipamento_id": item["equipamento_id"],
                    "responsavel_id": None,
                    "tipo_alerta": item["tipo_alerta"],
                    "mensagem": f"registro_lote_gestao: {item['equipamento']} / {item['item']}",
                })
            qtd = alertas_service.registrar_alerta_lote(payload, perfil="gestao")
            _carregar_pendencias.clear()
            st.success(f"{qtd} alerta(s) registrados em lote para gestão.")
            st.rerun()


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

    pendencias_rev, pendencias_lub, _ = _carregar_pendencias()
    fila = alertas_service.gerar_fila_sugerida(max_por_tipo=configuracoes_service.get_fila_alertas_limite())

    tab1, tab2, tab3, tab4 = st.tabs([
        f"Revisão ({len(pendencias_rev)})",
        f"Lubrificação ({len(pendencias_lub)})",
        "Fila sugerida do dia",
        "Histórico",
    ])

    with tab1:
        if not pendencias_rev:
            st.success("Nenhuma revisão vencida ou próxima do vencimento.")
        else:
            for p in pendencias_rev:
                _card_alerta(p["eqp"], p["item"], "revisao", p["enviado_hoje"])

    with tab2:
        if not pendencias_lub:
            st.success("Nenhuma lubrificação vencida ou próxima do vencimento.")
        else:
            for p in pendencias_lub:
                _card_alerta(p["eqp"], p["item"], "lubrificacao", p["enviado_hoje"])

    with tab3:
        _render_fila_sugerida(fila)

    with tab4:
        _render_historico()
