import datetime

import pandas as pd
import streamlit as st

from services import (
    equipamentos_service,
    execucoes_service,
    responsaveis_service,
    revisoes_service,
    vinculos_service,
)

STATUS_LABEL = {
    "VENCIDO":   "🔴 Vencido",
    "PROXIMO":   "🟡 Próximo",
    "EM DIA":    "🟢 Em dia",
    "REALIZADO": "✅ Realizado",
}
STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_unidade(tipo_controle):
    return "h" if tipo_controle == "horas" else "km"


def _badge(status):
    return STATUS_LABEL.get(status, status)


def _barra_progresso(leitura_atual, inicio_ciclo, fim_ciclo):
    """Retorna valor 0..100 do progresso dentro do ciclo atual."""
    span = fim_ciclo - inicio_ciclo
    if span <= 0:
        return 100
    prog = (leitura_atual - inicio_ciclo) / span * 100
    return max(0, min(100, prog))


# ── tabela de pendências ─────────────────────────────────────────────────────

def _render_tabela(dados, titulo, vazio_msg):
    st.subheader(titulo)
    if not dados:
        st.info(vazio_msg)
        return

    df = pd.DataFrame(dados)[[
        "codigo", "equipamento_nome", "setor_nome",
        "etapa", "tipo_controle",
        "leitura_atual", "ultima_execucao",
        "vencimento_ciclo", "proximo_vencimento",
        "falta", "status",
    ]].rename(columns={
        "codigo":             "Código",
        "equipamento_nome":   "Equipamento",
        "setor_nome":         "Setor",
        "etapa":              "Etapa",
        "tipo_controle":      "Controle",
        "leitura_atual":      "Atual",
        "ultima_execucao":    "Última exec.",
        "vencimento_ciclo":   "Ref. ciclo",
        "proximo_vencimento": "Próx. vencimento",
        "falta":              "Falta",
        "status":             "Status",
    })
    df["Status"] = df["Status"].map(_badge)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── modal de registro rápido ─────────────────────────────────────────────────

def _form_registrar(item, key_suffix):
    """
    Formulário inline para registrar uma execução de revisão
    diretamente da lista, sem precisar ir a outra página.
    """
    eqp = equipamentos_service.obter(item["equipamento_id"])
    if not eqp:
        st.warning("Equipamento não encontrado.")
        return

    tipo = item["tipo_controle"]
    unidade = _fmt_unidade(tipo)
    leitura_sugerida = float(item.get("vencimento_ciclo") or item.get("leitura_atual") or 0)

    vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op = {v["responsavel_id"] for v in vinculos_op}
    responsaveis_todos = [r for r in responsaveis_service.listar() if r.get("ativo")]
    resp_lista = [r for r in responsaveis_todos if r["id"] in ids_op] or responsaveis_todos

    with st.form(f"form_rev_{key_suffix}", clear_on_submit=True):
        st.caption(f"Equipamento: **{eqp['codigo']} — {eqp['nome']}** | Etapa: **{item['etapa']}**")

        c1, c2 = st.columns(2)
        with c1:
            if tipo == "horas":
                horas_exec = st.number_input(
                    f"Horímetro na execução ({unidade})",
                    min_value=0.0, value=leitura_sugerida, step=1.0,
                    key=f"horas_{key_suffix}",
                )
                km_exec = None
            else:
                km_exec = st.number_input(
                    f"Hodômetro na execução ({unidade})",
                    min_value=0.0, value=leitura_sugerida, step=1.0,
                    key=f"km_{key_suffix}",
                )
                horas_exec = None

            data_exec = st.date_input("Data da execução", value=datetime.date.today(), key=f"data_{key_suffix}")

        with c2:
            resp = st.selectbox(
                "Responsável",
                [None] + resp_lista,
                format_func=lambda r: "— não informar —" if r is None else f"{r['nome']} ({r.get('funcao_principal') or 'sem função'})",
                key=f"resp_{key_suffix}",
            )
            obs = st.text_area("Observações", height=80, key=f"obs_{key_suffix}",
                               value=f"Etapa: {item['etapa']}")

        salvar = st.form_submit_button("✅ Registrar execução", use_container_width=True, type="primary")

        if salvar:
            execucoes_service.criar_execucao({
                "equipamento_id":  eqp["id"],
                "responsavel_id":  resp["id"] if resp else None,
                "tipo":            "revisao",
                "data_execucao":   data_exec,
                "km_execucao":     km_exec,
                "horas_execucao":  horas_exec,
                "observacoes":     obs.strip() or None,
                "status":          "concluida",
            })
            # Invalida cache para refletir o novo registro
            if hasattr(revisoes_service, "listar_controle_revisoes"):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
            st.success("Revisão registrada com sucesso!")
            st.rerun()


# ── card de item pendente ────────────────────────────────────────────────────

def _card_pendencia(item, idx):
    tipo    = item["tipo_controle"]
    unidade = _fmt_unidade(tipo)
    badge   = _badge(item["status"])
    falta   = float(item.get("falta", item.get("diferenca", 0)))
    progresso = _barra_progresso(
        item["leitura_atual"],
        item.get("ciclo_atual_inicio", 0),
        item.get("ciclo_atual_fim",    item.get("proximo_vencimento", item["leitura_atual"] + 1)),
    )

    with st.expander(
        f"{badge}  |  {item['codigo']} — {item['equipamento_nome']}  |  {item['etapa']}",
        expanded=(item["status"] == "VENCIDO"),
    ):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Setor",          item.get("setor_nome", "-"))
        col2.metric(f"Atual ({unidade})",      f"{item['leitura_atual']:.0f}")
        col3.metric(f"Vencimento ({unidade})", f"{item.get('vencimento_ciclo', item.get('proximo_vencimento', 0)):.0f}")

        if falta <= 0:
            col4.metric("Situação", f"Vencido há {abs(falta):.0f} {unidade}")
        else:
            col4.metric("Falta", f"{falta:.0f} {unidade}")

        # Barra de progresso do ciclo
        st.caption(f"Progresso no ciclo atual: {progresso:.0f}%")
        st.progress(int(progresso))

        # Última execução
        ult = float(item.get("ultima_execucao", 0))
        if ult > 0:
            st.caption(f"Última execução registrada: {ult:.0f} {unidade}")
        else:
            st.caption("Sem execução registrada neste ciclo.")

        st.divider()
        st.markdown("**Registrar execução agora**")
        _form_registrar(item, key_suffix=f"{item['equipamento_id']}_{item.get('etapa_id', idx)}")


# ── página principal ─────────────────────────────────────────────────────────

def render():
    col_t, col_b = st.columns([5, 1])
    with col_t:
        st.title("Controle de Revisões")
        st.caption("Acompanhe o ciclo de revisões de cada equipamento e registre execuções diretamente desta página.")
    with col_b:
        st.write("")
        if st.button("🔄 Atualizar"):
            st.cache_data.clear()
            st.rerun()

    dados = revisoes_service.listar_controle_revisoes()

    if not dados:
        st.info("Nenhuma revisão encontrada. Verifique se os equipamentos possuem template de revisão configurado.")
        return

    # ── Filtros ──────────────────────────────────────────────────────────────
    setores  = sorted({d.get("setor_nome", "-") for d in dados})
    eqps     = sorted({f"{d['codigo']} — {d['equipamento_nome']}" for d in dados})
    status_opts = ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"]

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        setor_f  = st.multiselect("Setor",        setores,     key="rev_setor")
    with col2:
        eqp_f    = st.multiselect("Equipamento",  eqps,        key="rev_eqp")
    with col3:
        status_f = st.selectbox("Status",         status_opts, key="rev_status")

    filtrados = dados
    if setor_f:
        filtrados = [d for d in filtrados if d.get("setor_nome", "-") in setor_f]
    if eqp_f:
        nomes_sel = {e.split(" — ", 1)[0] for e in eqp_f}
        filtrados = [d for d in filtrados if d["codigo"] in nomes_sel]
    if status_f != "Todos":
        filtrados = [d for d in filtrados if d["status"] == status_f]

    # ── KPIs rápidos ─────────────────────────────────────────────────────────
    contagem = {s: sum(1 for d in filtrados if d["status"] == s) for s in STATUS_ORDEM}
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔴 Vencidos",   contagem.get("VENCIDO",   0))
    k2.metric("🟡 Próximos",   contagem.get("PROXIMO",   0))
    k3.metric("🟢 Em dia",     contagem.get("EM DIA",    0))
    k4.metric("✅ Realizados", contagem.get("REALIZADO", 0))

    st.divider()

    # ── Tabs por estado ───────────────────────────────────────────────────────
    vencidos   = [d for d in filtrados if d["status"] == "VENCIDO"]
    proximos   = [d for d in filtrados if d["status"] == "PROXIMO"]
    em_dia     = [d for d in filtrados if d["status"] == "EM DIA"]
    realizados = [d for d in filtrados if d["status"] == "REALIZADO"]

    tab_venc, tab_prox, tab_dia, tab_real, tab_tabela = st.tabs([
        f"🔴 Vencidos ({len(vencidos)})",
        f"🟡 Próximos ({len(proximos)})",
        f"🟢 Em dia ({len(em_dia)})",
        f"✅ Realizados ({len(realizados)})",
        "📋 Tabela completa",
    ])

    with tab_venc:
        if not vencidos:
            st.success("Nenhum item vencido para os filtros selecionados.")
        else:
            st.caption("Expanda um item para registrar a execução diretamente.")
            for i, item in enumerate(vencidos):
                _card_pendencia(item, i)

    with tab_prox:
        if not proximos:
            st.success("Nenhum item próximo do vencimento.")
        else:
            st.caption("Expanda um item para registrar a execução diretamente.")
            for i, item in enumerate(proximos):
                _card_pendencia(item, i)

    with tab_dia:
        _render_tabela(
            em_dia,
            f"Programados ({len(em_dia)})",
            "Nenhum item em dia para os filtros selecionados.",
        )

    with tab_real:
        _render_tabela(
            realizados,
            f"Realizados neste ciclo ({len(realizados)})",
            "Nenhuma execução registrada neste ciclo.",
        )

    with tab_tabela:
        st.caption("Visão consolidada de todos os itens filtrados.")
        _render_tabela(filtrados, f"Todos os itens ({len(filtrados)})", "Nenhum item para exibir.")
