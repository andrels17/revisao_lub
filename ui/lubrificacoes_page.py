import datetime

import pandas as pd
import streamlit as st

from ui.constants  import STATUS_LABEL, STATUS_ORDEM
from ui.exportacao import botao_exportar_excel
from ui.theme import render_page_intro
from services import (
    equipamentos_service,
    lubrificacoes_service,
    responsaveis_service,
    vinculos_service,
    execucoes_service,
)


def _fmt_eqp(e):
    return f"{e['codigo']} - {e['nome']}"


def _fmt_unidade(tipo_controle):
    return "h" if tipo_controle == "horas" else "km"


# ── batch de pendências (evita N+1) ──────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _carregar_pendencias_batch():
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], {}
    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    pendencias = []
    for eqp_id, itens in lub_idx.items():
        eqp = eqp_map.get(eqp_id)
        if not eqp:
            continue
        for item in itens:
            pendencias.append({"eqp": eqp, "item": item})
    pendencias.sort(key=lambda x: (
        STATUS_ORDEM.get(x["item"]["status"], 99),
        x["item"].get("diferenca", 0),
        x["eqp"]["codigo"],
    ))
    return pendencias, eqp_map


# ── card de item ──────────────────────────────────────────────────────────────

def _card_lub(eqp, item, idx):
    status   = item["status"]
    unidade  = _fmt_unidade(item.get("tipo_controle", "km"))
    badge    = STATUS_LABEL.get(status, status)
    falta    = float(item.get("diferenca", item.get("falta", 0)))
    vencimento = float(item.get("vencimento", 0))
    atual      = float(item.get("atual", 0))

    # Progresso no ciclo
    intervalo = float(item.get("intervalo_valor", 0) or vencimento or 1)
    inicio_ciclo = max(0.0, vencimento - intervalo)
    span = vencimento - inicio_ciclo
    progresso = int(max(0, min(100, (atual - inicio_ciclo) / span * 100))) if span > 0 else 100

    with st.expander(
        f"{badge}  |  {eqp['codigo']} — {eqp['nome']}  |  {item['item']}",
        expanded=(status == "VENCIDO"),
    ):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Setor",                   eqp.get("setor_nome", "-"))
        col2.metric(f"Leitura atual ({unidade})", f"{atual:.0f}")
        col3.metric(f"Próxima troca ({unidade})", f"{vencimento:.0f}")
        if falta <= 0:
            col4.metric("Situação", f"Vencido há {abs(falta):.0f} {unidade}")
        else:
            col4.metric("Falta", f"{falta:.0f} {unidade}")

        st.caption(f"Produto: **{item.get('tipo_produto') or '—'}** | Progresso no ciclo: {progresso}%")
        st.progress(progresso)

        ult = float(item.get("ultima_execucao", 0) or 0)
        if ult > 0:
            st.caption(f"Última execução registrada: {ult:.0f} {unidade}")
        else:
            st.caption("Sem execução registrada neste ciclo.")

        st.divider()
        st.markdown("**Registrar lubrificação agora**")
        _form_rapido(eqp, item, key_suffix=f"lub_{eqp['id']}_{item.get('item_id', idx)}")


def _form_rapido(eqp, item, key_suffix):
    tipo       = item.get("tipo_controle", "km")
    unidade    = _fmt_unidade(tipo)
    leitura_sug = float(item.get("vencimento", item.get("atual", 0)))

    vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op      = {v["responsavel_id"] for v in vinculos_op}
    todos_resp  = [r for r in responsaveis_service.listar() if r.get("ativo")]
    resp_lista  = [r for r in todos_resp if r["id"] in ids_op] or todos_resp

    with st.form(f"form_{key_suffix}", clear_on_submit=True):
        st.caption(f"Equipamento: **{eqp['codigo']} — {eqp['nome']}** | Item: **{item['item']}**")

        c1, c2 = st.columns(2)
        with c1:
            if tipo == "horas":
                horas_exec = st.number_input(
                    f"Horímetro na execução ({unidade})",
                    min_value=0.0, value=leitura_sug, step=1.0, key=f"h_{key_suffix}",
                )
                km_exec = None
            else:
                km_exec = st.number_input(
                    f"Hodômetro na execução ({unidade})",
                    min_value=0.0, value=leitura_sug, step=1.0, key=f"k_{key_suffix}",
                )
                horas_exec = None
            data_exec = st.date_input("Data da execução", value=datetime.date.today(), key=f"d_{key_suffix}")

        with c2:
            resp = st.selectbox(
                "Responsável",
                [None] + resp_lista,
                format_func=lambda r: "— não informar —" if r is None else r["nome"],
                key=f"r_{key_suffix}",
            )
            obs = st.text_area("Observações", height=80, key=f"o_{key_suffix}")

        if st.form_submit_button("✅ Registrar lubrificação", use_container_width=True, type="primary"):
            lubrificacoes_service.registrar_execucao({
                "equipamento_id": eqp["id"],
                "item_id":        item.get("item_id"),
                "responsavel_id": resp["id"] if resp else None,
                "nome_item":      item["item"],
                "tipo_produto":   item.get("tipo_produto"),
                "data_execucao":  data_exec,
                "km_execucao":    km_exec,
                "horas_execucao": horas_exec,
                "observacoes":    obs.strip() or None,
            })
            _carregar_pendencias_batch.clear()
            st.success("Lubrificação registrada!")
            st.rerun()


# ── aba de pendências com cards ───────────────────────────────────────────────

def _render_pendencias():
    with st.spinner("Carregando pendências…"):
        pendencias, _ = _carregar_pendencias_batch()

    if not pendencias:
        st.info("Nenhuma lubrificação configurada. Vincule um template de lubrificação aos equipamentos.")
        return

    # KPIs rápidos
    from collections import Counter
    contagem = Counter(p["item"]["status"] for p in pendencias)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔴 Vencidos",  contagem.get("VENCIDO",   0))
    k2.metric("🟡 Próximos",  contagem.get("PROXIMO",   0))
    k3.metric("🟢 Em dia",    contagem.get("EM DIA",    0))
    k4.metric("✅ Realizados", contagem.get("REALIZADO", 0))

    st.divider()

    # Filtros
    setores = sorted({p["eqp"].get("setor_nome") or "-" for p in pendencias})
    c1, c2 = st.columns([2, 1])
    with c1:
        setores_sel   = st.multiselect("Filtrar por setor", setores, key="lub_setor")
    with c2:
        status_filtro = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"], key="lub_status")

    filtradas = pendencias
    if setores_sel:
        filtradas = [p for p in filtradas if p["eqp"].get("setor_nome", "-") in setores_sel]
    if status_filtro != "Todos":
        filtradas = [p for p in filtradas if p["item"]["status"] == status_filtro]

    # Tabs por status
    vencidos   = [p for p in filtradas if p["item"]["status"] == "VENCIDO"]
    proximos   = [p for p in filtradas if p["item"]["status"] == "PROXIMO"]
    em_dia     = [p for p in filtradas if p["item"]["status"] == "EM DIA"]
    realizados = [p for p in filtradas if p["item"]["status"] == "REALIZADO"]

    tab_v, tab_p, tab_d, tab_r, tab_tabela = st.tabs([
        f"🔴 Vencidos ({len(vencidos)})",
        f"🟡 Próximos ({len(proximos)})",
        f"🟢 Em dia ({len(em_dia)})",
        f"✅ Realizados ({len(realizados)})",
        "📋 Tabela",
    ])

    with tab_v:
        if not vencidos:
            st.success("Nenhuma lubrificação vencida.")
        else:
            st.caption("Expanda um item para registrar diretamente.")
            for i, p in enumerate(vencidos):
                _card_lub(p["eqp"], p["item"], i)

    with tab_p:
        if not proximos:
            st.success("Nenhuma lubrificação próxima do vencimento.")
        else:
            st.caption("Expanda um item para registrar diretamente.")
            for i, p in enumerate(proximos):
                _card_lub(p["eqp"], p["item"], i)

    with tab_d:
        _render_tabela([p for p in em_dia], "Em dia")

    with tab_r:
        _render_tabela([p for p in realizados], "Realizados neste ciclo")

    with tab_tabela:
        _render_tabela(filtradas, "Todos os itens")


def _render_tabela(pendencias, titulo):
    if not pendencias:
        st.info(f"Nenhum item em '{titulo}'.")
        return
    rows = []
    for p in pendencias:
        eqp, item = p["eqp"], p["item"]
        rows.append({
            "Equipamento":  f"{eqp['codigo']} — {eqp['nome']}",
            "Setor":        eqp.get("setor_nome") or "-",
            "Item":         item["item"],
            "Produto":      item.get("tipo_produto") or "-",
            "Controle":     item.get("tipo_controle", "-"),
            "Atual":        float(item.get("atual", 0)),
            "Última troca": float(item.get("ultima_execucao", 0) or 0),
            "Próxima troca":float(item.get("vencimento", 0)),
            "Falta":        float(item.get("diferenca", 0)),
            "Status":       STATUS_LABEL.get(item["status"], item["status"]),
        })
    df = pd.DataFrame(rows)
    col_exp = st.columns([5, 1])[1]
    with col_exp:
        botao_exportar_excel(df, f"lub_{titulo[:6]}", label="⬇️ Excel",
                             key=f"exp_lub_{titulo[:6]}")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── aba de registro manual ────────────────────────────────────────────────────

def _render_execucao():
    st.subheader("Registrar Lubrificação")
    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_exec_eqp")
    if not eqp:
        return

    itens_pendentes = lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"])
    vinculos_op     = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op          = {v["responsavel_id"] for v in vinculos_op}
    resp_lista      = [r for r in responsaveis if r["id"] in ids_op] or responsaveis

    with st.form("form_lub_exec_manual", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            resp       = st.selectbox("Responsável", resp_lista, format_func=lambda r: r["nome"])
            data_exec  = st.date_input("Data da execução")
            opcoes     = ["— informar manualmente —"] + [
                f"{i['item']} ({i.get('tipo_produto','-')}) [{STATUS_LABEL.get(i['status'], i['status'])}]"
                for i in itens_pendentes
            ]
            item_idx   = st.selectbox("Item do template", range(len(opcoes)),
                                      format_func=lambda i: opcoes[i])
        with c2:
            nome_manual = st.text_input("Nome do item (se manual)")
            prod_manual = st.text_input("Produto (se manual)")
            km_exec     = st.number_input("KM atual", min_value=0.0,
                                          value=float(eqp.get("km_atual") or 0), step=1.0)
            horas_exec  = st.number_input("Horas atuais", min_value=0.0,
                                          value=float(eqp.get("horas_atual") or 0), step=1.0)

        obs    = st.text_area("Observações")
        salvar = st.form_submit_button("Registrar lubrificação", use_container_width=True)

        if salvar:
            item_id      = None
            nome_item    = nome_manual.strip() or None
            tipo_produto = prod_manual.strip() or None
            if item_idx > 0:
                obj          = itens_pendentes[item_idx - 1]
                item_id      = obj["item_id"]
                nome_item    = nome_item    or obj["item"]
                tipo_produto = tipo_produto or obj.get("tipo_produto")
            if not nome_item:
                st.error("Informe o nome do item de lubrificação.")
            else:
                lubrificacoes_service.registrar_execucao({
                    "equipamento_id": eqp["id"],
                    "item_id":        item_id,
                    "responsavel_id": resp["id"] if resp else None,
                    "nome_item":      nome_item,
                    "tipo_produto":   tipo_produto,
                    "data_execucao":  data_exec,
                    "km_execucao":    km_exec,
                    "horas_execucao": horas_exec,
                    "observacoes":    obs,
                })
                _carregar_pendencias_batch.clear()
                st.success("Lubrificação registrada com sucesso.")
                st.rerun()


# ── aba histórico ─────────────────────────────────────────────────────────────

def _render_historico():
    st.subheader("Histórico de Lubrificações")
    historico = lubrificacoes_service.listar_todos()
    if historico:
        df_hist = pd.DataFrame(historico)
        col_exp = st.columns([5, 1])[1]
        with col_exp:
            botao_exportar_excel(df_hist, "lubrificacoes_historico", label="⬇️ Excel", key="exp_lub_hist")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma lubrificação registrada ainda.")

    with st.expander("Histórico por equipamento"):
        equipamentos = equipamentos_service.listar()
        if not equipamentos:
            return
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_hist_eqp")
        if eqp:
            dados = lubrificacoes_service.listar_por_equipamento(eqp["id"])
            if dados:
                st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum histórico para este equipamento.")


# ── página ────────────────────────────────────────────────────────────────────

def render():
    col_t, col_b = st.columns([5, 1])
    with col_t:
        render_page_intro("Controle de lubrificações", "Gerencie trocas e execuções com um layout mais leve, consistente e confortável no tema escuro.", "Operação")
        st.caption("Acompanhe e registre lubrificações por equipamento.")
    with col_b:
        st.write("")
        if st.button("🔄 Atualizar"):
            _carregar_pendencias_batch.clear()
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["Pendências", "Registrar", "Histórico"])
    with tab1:
        _render_pendencias()
    with tab2:
        _render_execucao()
    with tab3:
        _render_historico()
