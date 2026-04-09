import datetime

import pandas as pd
import streamlit as st

from ui.constants  import STATUS_LABEL, STATUS_ORDEM
from ui.exportacao import botao_exportar_excel
import html


from services import (
    equipamentos_service,
    execucoes_service,
    responsaveis_service,
    revisoes_service,
    templates_integracao_service,
    templates_lubrificacao_service,
    vinculos_service,
)



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


def _render_page_header() -> None:
    st.markdown(
        """
        <style>
        .integration-card {
            border: 1px solid rgba(148,163,184,.16);
            border-radius: 16px;
            padding: .95rem 1rem;
            background: rgba(15,23,42,.62);
            margin: .65rem 0 .35rem 0;
        }
        .integration-card.status-warning {
            border-color: rgba(245,158,11,.32);
            background: linear-gradient(135deg, rgba(120,53,15,.22), rgba(15,23,42,.72));
        }
        .integration-card.status-muted {
            border-color: rgba(148,163,184,.16);
            background: linear-gradient(135deg, rgba(30,41,59,.55), rgba(15,23,42,.72));
        }
        .integration-head {
            display:flex;
            justify-content:space-between;
            gap:.75rem;
            align-items:center;
            margin-bottom:.35rem;
        }
        .integration-title {
            font-size:.82rem;
            font-weight:800;
            color:#e2e8f0;
            letter-spacing:.01em;
        }
        .integration-pill {
            font-size:.72rem;
            font-weight:700;
            padding:.2rem .55rem;
            border-radius:999px;
            background: rgba(255,255,255,.06);
            color:#dbeafe;
            white-space:nowrap;
        }
        .integration-name {font-size:.98rem;font-weight:800;color:#f8fafc;}
        .integration-sub {font-size:.8rem;color:#94a3b8;margin-top:.18rem;}
        .integration-items {font-size:.84rem;color:#e2e8f0;margin-top:.55rem;line-height:1.45;}
        .integration-check-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.6rem;margin-top:.7rem;}
        .integration-check {display:flex;align-items:center;gap:.55rem;padding:.65rem .75rem;border:1px solid rgba(148,163,184,.14);border-radius:12px;background:rgba(255,255,255,.03);}
        .integration-check input {width:16px;height:16px;accent-color:#60a5fa;}
        .integration-check label {font-size:.82rem;color:#dbeafe;}
        .integration-origin {font-size:.76rem;color:#93c5fd;margin-top:.4rem;font-weight:700;}
        </style>
        <div class="page-header-card">
            <div class="eyebrow">🔧 Operação</div>
            <h2>Controle de revisões</h2>
            <p>Acompanhe pendências, priorize itens vencidos e registre execuções com menos ruído visual e mais foco operacional.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(contagem: dict[str, int]) -> None:
    cards = [
        ("status-danger", "🔴 Vencidos", contagem.get("VENCIDO", 0), "Exigem ação imediata"),
        ("status-warning", "🟡 Próximos", contagem.get("PROXIMO", 0), "Janela de atenção"),
        ("status-success", "🟢 Em dia", contagem.get("EM DIA", 0), "Dentro do ciclo"),
        ("status-info", "✅ Realizados", contagem.get("REALIZADO", 0), "Execuções registradas"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{html.escape(str(label))}</div><div class='value'>{int(value)}</div><div class='sub'>{html.escape(str(sub))}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)




# ── integração revisão × lubrificação ────────────────────────────────────────

def _normalizar_chave(texto):
    return " ".join(str(texto or "").strip().lower().split())


def _montar_contexto_integracao():
    mapa_vinculos = templates_integracao_service.obter_mapa_vinculos_por_template_revisao()
    templates_lub = {
        str(t["id"]): t for t in templates_lubrificacao_service.listar_com_itens() if t.get("id") is not None
    }
    cache_analises = {}
    return mapa_vinculos, templates_lub, cache_analises


def _obter_integracao_item(item, mapa_vinculos, templates_lub, cache_analises):
    return templates_integracao_service.obter_integracao_automatica_por_item(
        item,
        mapa_vinculos=mapa_vinculos,
        templates_lub=templates_lub,
        cache_analises=cache_analises,
    )


def _render_bloco_integracao_lubrificacao(item, integracao):
    unidade = _fmt_unidade(item.get("tipo_controle"))
    gatilho = float(item.get("gatilho_valor") or 0)
    titulo = html.escape(str(integracao.get("template_lubrificacao_nome") or "Lubrificação vinculada"))
    etiqueta = "🟠 Executar junto" if integracao.get("dispara") else "⚪ Não entra nesta etapa"
    classe = "status-warning" if integracao.get("dispara") else "status-muted"
    origem = "Vínculo salvo em Templates" if integracao.get("origem") == "vinculo" else "Associação automática pelo equipamento"
    checked_etapa = "checked" if integracao.get("dispara") else ""
    checked_auto = "checked" if integracao.get("aplica_automatico") else ""
    st.markdown(
        f"""
        <div class="integration-card {classe}">
            <div class="integration-head">
                <div class="integration-title">🛢️ Lubrificação vinculada</div>
                <div class="integration-pill">{html.escape(etiqueta)}</div>
            </div>
            <div class="integration-name">{titulo}</div>
            <div class="integration-sub">Etapa atual: {int(gatilho) if gatilho.is_integer() else gatilho:g} {unidade} · Equipamentos usando este par: {int(integracao.get('equipamentos_vinculados') or 0)}</div>
            <div class="integration-origin">{html.escape(origem)}</div>
            <div class="integration-check-grid">
                <div class="integration-check"><input type="checkbox" disabled {checked_etapa}><label>Etapa marcada para puxar lubrificação</label></div>
                <div class="integration-check"><input type="checkbox" disabled {checked_auto}><label>Compatibilidade automática pelo intervalo</label></div>
            </div>
            <div class="integration-items">{html.escape(str(integracao.get('itens_acionados') or '—'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if integracao.get("observacoes"):
        st.caption(f"Observação do vínculo: {integracao['observacoes']}")




def _fmt_data_br(data_valor):
    if not data_valor:
        return '—'
    try:
        return pd.to_datetime(data_valor).strftime('%d/%m/%Y')
    except Exception:
        return str(data_valor)


def _chip_item_execucao(item_exec):
    nome = html.escape(str(item_exec.get("item_nome") or "Item"))
    produto = str(item_exec.get("produto") or "-").strip()
    if produto and produto != '-':
        nome = f"{nome} · {html.escape(produto)}"
    intervalo = item_exec.get("intervalo_valor")
    if intervalo not in (None, ""):
        try:
            intervalo_num = float(intervalo)
            intervalo_txt = f"{int(intervalo_num)}" if intervalo_num.is_integer() else f"{intervalo_num:g}"
            nome = f"{nome} · {intervalo_txt}"
        except Exception:
            pass
    return f"<span class='exec-item-chip'>✓ {nome}</span>"


def _render_historico_execucoes(equipamento_id, tipo_controle):
    historico = execucoes_service.listar_revisoes_por_equipamento(equipamento_id, limite=5)
    if not historico:
        st.caption('Sem histórico recente de revisões para este equipamento.')
        return

    unidade = _fmt_unidade(tipo_controle)
    st.markdown("**Histórico recente**")
    for execucao in historico:
        valor_ref = execucao.get('horas') if tipo_controle == 'horas' else execucao.get('km')
        try:
            valor_num = float(valor_ref or 0)
            valor_txt = f"{int(valor_num)}" if valor_num.is_integer() else f"{valor_num:g}"
        except Exception:
            valor_txt = str(valor_ref or '0')
        etapa = execucao.get('etapa_referencia') or 'Etapa não informada'
        itens = execucao.get('itens_executados') or []
        itens_html = ''.join(_chip_item_execucao(item_exec) for item_exec in itens) if itens else "<span class='exec-item-empty'>Sem itens estruturados nesta execução</span>"
        obs = str(execucao.get('observacoes') or '').strip()
        obs_html = f"<div class='exec-obs'>{html.escape(obs)}</div>" if obs else ''
        st.markdown(
            f"""
            <div class="exec-history-card">
                <div class="exec-history-top">
                    <div class="exec-history-title">{html.escape(str(etapa))}</div>
                    <div class="exec-history-meta">{_fmt_data_br(execucao.get('data'))} · {html.escape(valor_txt)} {unidade} · {html.escape(str(execucao.get('responsavel') or '-'))}</div>
                </div>
                <div class="exec-history-result">{html.escape(str(execucao.get('resultado') or 'Realizado'))}</div>
                <div class="exec-history-items">{itens_html}</div>
                {obs_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
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
    col_exp = st.columns([5,1])[1]
    with col_exp:
        botao_exportar_excel(df, "revisoes", label="⬇️ Excel", key=f"exp_rev_{titulo[:8]}")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── modal de registro rápido ─────────────────────────────────────────────────

def _rotulo_item_lubrificacao(item_lub):
    nome = str(item_lub.get("nome_item") or item_lub.get("item_nome") or "Item sem nome")
    produto = str(item_lub.get("tipo_produto") or item_lub.get("produto") or "-")
    intervalo = float(item_lub.get("intervalo_valor") or 0)
    intervalo_txt = f"{int(intervalo)}" if float(intervalo).is_integer() else f"{intervalo:g}"
    return f"{nome} · {produto} · intervalo {intervalo_txt}"


def _form_registrar(item, key_suffix, integracao=None):
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

    itens_template = list((integracao or {}).get("todos_itens_template") or [])
    itens_sugeridos = {
        str(i.get("id") or i.get("nome_item") or i.get("item_nome"))
        for i in ((integracao or {}).get("itens_acionados_lista") or [])
    }

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
            obs = st.text_area(
                "Observações opcionais",
                height=80,
                key=f"obs_{key_suffix}",
                placeholder="Ex.: executado sem intercorrências / material conferido / ajuste adicional realizado",
            )

        itens_marcados = []
        if itens_template:
            st.markdown("**Itens complementares da lubrificação**")
            st.caption("Marque diretamente o que foi executado junto nesta etapa. Isso substitui a dependência de texto livre em observações.")
            for idx_item, item_lub in enumerate(itens_template):
                item_key = str(item_lub.get("id") or item_lub.get("nome_item") or item_lub.get("item_nome") or idx_item)
                default = item_key in itens_sugeridos
                marcado = st.checkbox(
                    _rotulo_item_lubrificacao(item_lub),
                    value=default,
                    key=f"item_lub_{key_suffix}_{idx_item}",
                )
                if marcado:
                    itens_marcados.append(item_lub)
            if itens_sugeridos:
                st.caption("Os itens já marcados são a sugestão do sistema para esta etapa.")

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
                "itens_executados": itens_marcados,
                "status":          "concluida",
            })
            if hasattr(revisoes_service, "listar_controle_revisoes"):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
            st.success("Revisão registrada com sucesso!")
            st.rerun()


# ── card de item pendente ────────────────────────────────────────────────────

def _card_pendencia(item, idx, mapa_vinculos=None, templates_lub=None, cache_analises=None):
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

        integracao = _obter_integracao_item(
            item,
            mapa_vinculos or {},
            templates_lub or {},
            cache_analises or {},
        )
        if integracao:
            st.divider()
            _render_bloco_integracao_lubrificacao(item, integracao)

        st.divider()
        st.markdown("**Registrar execução agora**")
        _form_registrar(item, key_suffix=f"{item['equipamento_id']}_{item.get('etapa_id', idx)}", integracao=integracao)

        st.divider()
        _render_historico_execucoes(item['equipamento_id'], item.get('tipo_controle'))


# ── página principal ─────────────────────────────────────────────────────────

def render():
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("<div class='section-caption'>Acompanhe o ciclo de revisões de cada equipamento e registre execuções diretamente desta página.</div>", unsafe_allow_html=True)

    dados = revisoes_service.listar_controle_revisoes()
    mapa_vinculos, templates_lub, cache_analises = _montar_contexto_integracao()

    if not dados:
        st.info("Nenhuma revisão encontrada. Verifique se os equipamentos possuem template de revisão configurado.")
        return

    # ── Filtros ──────────────────────────────────────────────────────────────
    setores  = sorted({d.get("setor_nome", "-") for d in dados})
    eqps     = sorted({f"{d['codigo']} — {d['equipamento_nome']}" for d in dados})
    status_opts = ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"]

    st.markdown("<div class='filters-shell'><div class='filters-title'>Filtros operacionais</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        setor_f  = st.multiselect("Setor",        setores,     key="rev_setor")
    with col2:
        eqp_f    = st.multiselect("Equipamento",  eqps,        key="rev_eqp")
    with col3:
        status_f = st.selectbox("Status",         status_opts, key="rev_status")
    st.markdown("</div>", unsafe_allow_html=True)

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
    _render_kpi_cards(contagem)
    revisoes_com_lub = sum(1 for d in filtrados if _obter_integracao_item(d, mapa_vinculos, templates_lub, cache_analises))
    if revisoes_com_lub:
        st.caption(f"🛢️ {revisoes_com_lub} item(ns) filtrados possuem template de lubrificação vinculado. Ao expandir a etapa, o sistema mostra se a lubrificação entra junto nesta revisão.")

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
                _card_pendencia(item, i, mapa_vinculos, templates_lub, cache_analises)

    with tab_prox:
        if not proximos:
            st.success("Nenhum item próximo do vencimento.")
        else:
            st.caption("Expanda um item para registrar a execução diretamente.")
            for i, item in enumerate(proximos):
                _card_pendencia(item, i, mapa_vinculos, templates_lub, cache_analises)

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
