import datetime
import html

import pandas as pd
import streamlit as st

from ui.constants  import STATUS_LABEL, STATUS_ORDEM
from ui.exportacao import botao_exportar_excel

from services import (
    equipamentos_service,
    cache_service,
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
    span = fim_ciclo - inicio_ciclo
    if span <= 0:
        return 100
    prog = (leitura_atual - inicio_ciclo) / span * 100
    return max(0, min(100, prog))


def _inject_css():
    st.markdown(
        """
        <style>
        /* ── Controle de revisões ──────────────────────────────────── */

        /* Card de pendência */
        .rev-card {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            background: #0d1929;
            margin-bottom: .5rem;
            overflow: hidden;
        }
        .rev-card.status-vencido { border-left: 3px solid #ef4444; }
        .rev-card.status-proximo { border-left: 3px solid #f59e0b; }
        .rev-card.status-emdia   { border-left: 3px solid #22c55e; }

        .rev-card-header {
            display: flex;
            align-items: center;
            gap: .75rem;
            padding: .75rem 1rem;
        }
        .rev-dot {
            width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        }
        .rev-dot.vencido { background: #ef4444; }
        .rev-dot.proximo { background: #f59e0b; }
        .rev-dot.emdia   { background: #22c55e; }

        .rev-card-title { font-size: .9rem; font-weight: 700; color: #e8f1ff; }
        .rev-card-sub   { font-size: .76rem; color: #8fa4c0; margin-top: .08rem; }

        .rev-b {
            display: inline-block;
            padding: .13rem .44rem;
            border-radius: 999px;
            font-size: .68rem; font-weight: 700;
            flex-shrink: 0;
        }
        .rev-b-danger  { background: rgba(239,68,68,.12);  color: #fca5a5; }
        .rev-b-warning { background: rgba(245,158,11,.12); color: #fcd34d; }
        .rev-b-ok      { background: rgba(34,197,94,.12);  color: #86efac; }
        .rev-b-neutral { background: rgba(148,163,184,.09); color: #94a8c4; }

        /* Barra de progresso do ciclo */
        .rev-progress-track {
            height: 3px;
            background: rgba(148,163,184,.12);
        }
        .rev-progress-fill {
            height: 3px;
            transition: width .3s;
        }
        .rev-progress-fill.vencido { background: #ef4444; }
        .rev-progress-fill.proximo { background: #f59e0b; }
        .rev-progress-fill.emdia   { background: #22c55e; }

        /* Detalhe expandido */
        .rev-detail-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0,1fr));
            gap: .5rem;
            padding: .75rem 1rem 0;
        }
        .rev-detail-cell {
            background: rgba(255,255,255,.025);
            border: 1px solid rgba(148,163,184,.08);
            border-radius: 8px;
            padding: .55rem .75rem;
        }
        .rev-detail-label { font-size: .68rem; color: #6b84a0; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; margin-bottom: .18rem; }
        .rev-detail-val   { font-size: 1rem; font-weight: 700; color: #e8f1ff; }
        .rev-detail-val.danger { color: #fca5a5; }

        /* Formulário de execução */
        .rev-exec-shell {
            margin: .75rem 1rem 1rem;
            border-top: 1px solid rgba(148,163,184,.10);
            padding-top: .75rem;
        }
        .rev-exec-label {
            font-size: .70rem; font-weight: 700; color: #6b84a0;
            text-transform: uppercase; letter-spacing: .05em;
            margin-bottom: .55rem;
        }

        /* Histórico */
        .exec-history-card {
            border: 1px solid rgba(148,163,184,.10);
            border-radius: 8px;
            padding: .6rem .8rem;
            background: rgba(255,255,255,.02);
            margin-bottom: .4rem;
        }
        .exec-history-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .5rem; }
        .exec-history-title { font-size: .82rem; font-weight: 700; color: #e2e8f0; }
        .exec-history-meta  { font-size: .72rem; color: #8fa4c0; margin-top: .1rem; white-space: nowrap; }
        .exec-history-result { font-size: .78rem; color: #6b84a0; margin-top: .3rem; }
        .exec-history-items { margin-top: .3rem; display: flex; flex-wrap: wrap; gap: .25rem; }
        .exec-item-chip {
            background: rgba(79,140,255,.10); color: #a8caff;
            border-radius: 999px; padding: .12rem .4rem;
            font-size: .68rem; font-weight: 600;
        }
        .exec-item-empty { font-size: .72rem; color: #6b84a0; }
        .exec-obs { font-size: .75rem; color: #8fa4c0; margin-top: .3rem; font-style: italic; }

        /* Integração lubrificação */
        .integration-card {
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 10px;
            padding: .8rem .9rem;
            background: rgba(15,23,42,.55);
            margin: .5rem 0;
        }
        .integration-card.status-warning {
            border-color: rgba(245,158,11,.28);
            background: rgba(120,53,15,.18);
        }
        .integration-head { display:flex; justify-content:space-between; gap:.75rem; align-items:center; margin-bottom:.3rem; }
        .integration-title { font-size:.78rem; font-weight:700; color:#e2e8f0; }
        .integration-pill { font-size:.70rem; font-weight:700; padding:.18rem .5rem; border-radius:999px; background:rgba(255,255,255,.06); color:#dbeafe; white-space:nowrap; }
        .integration-name { font-size:.9rem; font-weight:700; color:#f8fafc; }
        .integration-sub  { font-size:.77rem; color:#94a3b8; margin-top:.15rem; }
        .integration-items { font-size:.80rem; color:#e2e8f0; margin-top:.45rem; line-height:1.4; }
        .integration-check-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:.5rem; margin-top:.6rem; }
        .integration-check { display:flex; align-items:center; gap:.5rem; padding:.55rem .65rem; border:1px solid rgba(148,163,184,.12); border-radius:8px; background:rgba(255,255,255,.025); }
        .integration-check input { width:15px; height:15px; accent-color:#60a5fa; }
        .integration-check label { font-size:.78rem; color:#dbeafe; }
        .integration-origin { font-size:.72rem; color:#93c5fd; margin-top:.35rem; font-weight:700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── integração revisão × lubrificação ────────────────────────────────────────

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
    titulo  = html.escape(str(integracao.get("template_lubrificacao_nome") or "Lubrificação vinculada"))
    etiqueta = "Executar junto" if integracao.get("dispara") else "Não entra nesta etapa"
    classe   = "status-warning" if integracao.get("dispara") else ""
    origem   = "Vínculo salvo em Templates" if integracao.get("origem") == "vinculo" else "Associação automática pelo equipamento"
    checked_etapa = "checked" if integracao.get("dispara") else ""
    checked_auto  = "checked" if integracao.get("aplica_automatico") else ""
    st.markdown(
        f"""
        <div class="integration-card {classe}">
            <div class="integration-head">
                <div class="integration-title">Lubrificação vinculada</div>
                <div class="integration-pill">{html.escape(etiqueta)}</div>
            </div>
            <div class="integration-name">{titulo}</div>
            <div class="integration-sub">Etapa: {int(gatilho) if gatilho.is_integer() else gatilho:g} {unidade} · Equipamentos com este par: {int(integracao.get('equipamentos_vinculados') or 0)}</div>
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
        st.caption(f"Observação: {integracao['observacoes']}")


# ── histórico de execuções ────────────────────────────────────────────────────

def _fmt_data_br(data_valor):
    if not data_valor:
        return '—'
    try:
        return pd.to_datetime(data_valor).strftime('%d/%m/%Y')
    except Exception:
        return str(data_valor)


def _chip_item_execucao(item_exec):
    nome     = html.escape(str(item_exec.get("item_nome") or "Item"))
    produto  = str(item_exec.get("produto") or "-").strip()
    if produto and produto != '-':
        nome = f"{nome} · {html.escape(produto)}"
    intervalo = item_exec.get("intervalo_valor")
    if intervalo not in (None, ""):
        try:
            n = float(intervalo)
            nome = f"{nome} · {int(n) if float(n).is_integer() else f'{n:g}'}"
        except Exception:
            pass
    return f"<span class='exec-item-chip'>{nome}</span>"


def _render_historico_execucoes(equipamento_id, tipo_controle):
    historico = execucoes_service.listar_revisoes_por_equipamento(equipamento_id, limite=5)
    if not historico:
        st.caption("Sem histórico recente de revisões.")
        return

    unidade = _fmt_unidade(tipo_controle)
    st.markdown("**Histórico recente**")
    for execucao in historico:
        valor_ref = execucao.get('horas') if tipo_controle == 'horas' else execucao.get('km')
        try:
            n = float(valor_ref or 0)
            valor_txt = f"{int(n)}" if n.is_integer() else f"{n:g}"
        except Exception:
            valor_txt = str(valor_ref or '0')
        etapa  = execucao.get('etapa_referencia') or 'Etapa não informada'
        itens  = execucao.get('itens_executados') or []
        itens_html = ''.join(_chip_item_execucao(i) for i in itens) if itens else "<span class='exec-item-empty'>Sem itens estruturados</span>"
        obs    = str(execucao.get('observacoes') or '').strip()
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


# ── tabela consolidada ───────────────────────────────────────────────────────

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
    col_exp = st.columns([5, 1])[1]
    with col_exp:
        botao_exportar_excel(df, "revisoes", label="⬇️ Excel", key=f"exp_rev_{titulo[:8]}")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── helpers do formulário ────────────────────────────────────────────────────

def _rotulo_item_lubrificacao(item_lub):
    nome      = str(item_lub.get("nome_item") or item_lub.get("item_nome") or "Item sem nome")
    produto   = str(item_lub.get("tipo_produto") or item_lub.get("produto") or "-")
    intervalo = float(item_lub.get("intervalo_valor") or 0)
    itxt      = f"{int(intervalo)}" if float(intervalo).is_integer() else f"{intervalo:g}"
    return f"{nome} · {produto} · intervalo {itxt}"


def _form_registrar(item, key_suffix, integracao=None):
    eqp = equipamentos_service.obter(item["equipamento_id"])
    if not eqp:
        st.warning("Equipamento não encontrado.")
        return

    tipo            = item["tipo_controle"]
    unidade         = _fmt_unidade(tipo)
    leitura_sugerida = float(item.get("vencimento_ciclo") or item.get("leitura_atual") or 0)

    vinculos_op       = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op            = {v["responsavel_id"] for v in vinculos_op}
    responsaveis_todos = [r for r in responsaveis_service.listar() if r.get("ativo")]
    resp_lista        = [r for r in responsaveis_todos if r["id"] in ids_op] or responsaveis_todos

    itens_template = list((integracao or {}).get("todos_itens_template") or [])
    itens_sugeridos = {
        str(i.get("id") or i.get("nome_item") or i.get("item_nome"))
        for i in ((integracao or {}).get("itens_acionados_lista") or [])
    }

    with st.form(f"form_rev_{key_suffix}", clear_on_submit=True):
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
                "Observações (opcional)",
                height=78,
                key=f"obs_{key_suffix}",
                placeholder="Ex.: executado sem intercorrências / ajuste adicional realizado",
            )

        itens_marcados = []
        if itens_template:
            st.markdown("**Itens complementares da lubrificação**")
            for idx_item, item_lub in enumerate(itens_template):
                item_key = str(item_lub.get("id") or item_lub.get("nome_item") or item_lub.get("item_nome") or idx_item)
                default  = item_key in itens_sugeridos
                marcado  = st.checkbox(
                    _rotulo_item_lubrificacao(item_lub),
                    value=default,
                    key=f"item_lub_{key_suffix}_{idx_item}",
                )
                if marcado:
                    itens_marcados.append(item_lub)
            if itens_sugeridos:
                st.caption("Os itens marcados são a sugestão do sistema para esta etapa.")

        salvar = st.form_submit_button("Registrar execução", use_container_width=True, type="primary")

        if salvar:
            execucoes_service.criar_execucao({
                "equipamento_id":   eqp["id"],
                "responsavel_id":   resp["id"] if resp else None,
                "tipo":             "revisao",
                "data_execucao":    data_exec,
                "km_execucao":      km_exec,
                "horas_execucao":   horas_exec,
                "observacoes":      obs.strip() or None,
                "itens_executados": itens_marcados,
                "status":           "concluida",
            })
            if hasattr(revisoes_service, "listar_controle_revisoes"):
                try:
                    cache_service.invalidate_planejamento()
                    cache_service.invalidate_execucoes()
                except Exception:
                    pass
            st.success("Revisão registrada com sucesso!")
            st.rerun()


# ── card de item (expander simplificado) ─────────────────────────────────────

def _card_pendencia(item, idx, mapa_vinculos=None, templates_lub=None, cache_analises=None):
    tipo      = item["tipo_controle"]
    unidade   = _fmt_unidade(tipo)
    falta     = float(item.get("falta", item.get("diferenca", 0)))
    progresso = _barra_progresso(
        item["leitura_atual"],
        item.get("ciclo_atual_inicio", 0),
        item.get("ciclo_atual_fim", item.get("proximo_vencimento", item["leitura_atual"] + 1)),
    )
    status = item["status"]
    dot_cls  = {"VENCIDO": "vencido", "PROXIMO": "proximo"}.get(status, "emdia")
    card_cls = {"VENCIDO": "status-vencido", "PROXIMO": "status-proximo"}.get(status, "status-emdia")
    badge_cls = {"VENCIDO": "rev-b-danger", "PROXIMO": "rev-b-warning"}.get(status, "rev-b-ok")
    badge_txt = _badge(status)

    if falta <= 0:
        situacao = f"Vencido há {abs(falta):.0f} {unidade}"
    else:
        situacao = f"Falta {falta:.0f} {unidade}"

    vencimento = float(item.get("vencimento_ciclo") or item.get("proximo_vencimento") or 0)

    expander_label = f"{item['codigo']} — {item['equipamento_nome']}  ·  {item['etapa']}"

    with st.expander(expander_label, expanded=(status == "VENCIDO")):
        # cabeçalho do card
        st.markdown(
            f'<div class="rev-card {card_cls}" style="margin-bottom:0">'
            f'<div class="rev-card-header">'
            f'<div class="rev-dot {dot_cls}"></div>'
            f'<div style="flex:1;min-width:0">'
            f'<div class="rev-card-title">{html.escape(item["codigo"])} — {html.escape(item["equipamento_nome"])} · {html.escape(item["etapa"])}</div>'
            f'<div class="rev-card-sub">{html.escape(item.get("setor_nome","—"))} · {situacao}</div>'
            f'</div>'
            f'<span class="rev-b {badge_cls}">{html.escape(badge_txt)}</span>'
            f'</div>'
            f'<div class="rev-progress-track"><div class="rev-progress-fill {dot_cls}" style="width:{progresso:.0f}%"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # grade de detalhe
        st.markdown(
            f'<div class="rev-detail-grid">'
            f'<div class="rev-detail-cell"><div class="rev-detail-label">Hodômetro atual</div><div class="rev-detail-val">{item["leitura_atual"]:.0f} {unidade}</div></div>'
            f'<div class="rev-detail-cell"><div class="rev-detail-label">Vencimento</div><div class="rev-detail-val{"" if falta > 0 else " danger"}">{vencimento:.0f} {unidade}</div></div>'
            f'<div class="rev-detail-cell"><div class="rev-detail-label">Progresso do ciclo</div><div class="rev-detail-val">{progresso:.0f}%</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        ult = float(item.get("ultima_execucao", 0))
        if ult > 0:
            st.caption(f"Última execução registrada: {ult:.0f} {unidade}")
        else:
            st.caption("Sem execução registrada neste ciclo.")

        integracao = _obter_integracao_item(item, mapa_vinculos or {}, templates_lub or {}, cache_analises or {})
        if integracao:
            _render_bloco_integracao_lubrificacao(item, integracao)

        # formulário de execução
        st.markdown('<div class="rev-exec-shell"><div class="rev-exec-label">Registrar execução</div></div>', unsafe_allow_html=True)
        _form_registrar(item, key_suffix=f"{item['equipamento_id']}_{item.get('etapa_id', idx)}", integracao=integracao)

        st.divider()
        _render_historico_execucoes(item['equipamento_id'], item.get('tipo_controle'))


# ── página principal ─────────────────────────────────────────────────────────

def render():
    _inject_css()

    # ── Cabeçalho ──────────────────────────────────────────────────
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        st.markdown(
            """
            <div class="page-hero">
                <span class="section-chip">Operação</span>
                <h2>Controle de revisões</h2>
                <p>Acompanhe pendências e registre execuções diretamente desta página.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("Atualizar", use_container_width=True):
            cache_service.invalidate_planejamento()
            cache_service.invalidate_execucoes()
            st.rerun()

    dados = revisoes_service.listar_controle_revisoes()
    mapa_vinculos, templates_lub, cache_analises = _montar_contexto_integracao()

    if not dados:
        st.info("Nenhuma revisão encontrada. Verifique se os equipamentos possuem template configurado.")
        return

    # ── Filtros ──────────────────────────────────────────────────────
    setores  = sorted({d.get("setor_nome", "-") for d in dados})
    eqps     = sorted({f"{d['codigo']} — {d['equipamento_nome']}" for d in dados})

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        setor_f = st.multiselect("Setor", setores, key="rev_setor", label_visibility="collapsed", placeholder="Filtrar por setor")
    with col2:
        eqp_f   = st.multiselect("Equipamento", eqps, key="rev_eqp", label_visibility="collapsed", placeholder="Filtrar por equipamento")
    with col3:
        status_f = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"], key="rev_status", label_visibility="collapsed")

    filtrados = dados
    if setor_f:
        filtrados = [d for d in filtrados if d.get("setor_nome", "-") in setor_f]
    if eqp_f:
        nomes_sel = {e.split(" — ", 1)[0] for e in eqp_f}
        filtrados = [d for d in filtrados if d["codigo"] in nomes_sel]
    if status_f != "Todos":
        filtrados = [d for d in filtrados if d["status"] == status_f]

    # ── Tabs por status (com contadores — sem KPI cards duplicados) ──
    vencidos   = [d for d in filtrados if d["status"] == "VENCIDO"]
    proximos   = [d for d in filtrados if d["status"] == "PROXIMO"]
    em_dia     = [d for d in filtrados if d["status"] == "EM DIA"]
    realizados = [d for d in filtrados if d["status"] == "REALIZADO"]

    revisoes_com_lub = sum(1 for d in filtrados if _obter_integracao_item(d, mapa_vinculos, templates_lub, cache_analises))
    if revisoes_com_lub:
        st.caption(f"{revisoes_com_lub} item(ns) com template de lubrificação vinculado.")

    tab_venc, tab_prox, tab_dia, tab_real, tab_tabela = st.tabs([
        f"Vencidos  {len(vencidos)}",
        f"Próximos  {len(proximos)}",
        f"Em dia  {len(em_dia)}",
        f"Realizados  {len(realizados)}",
        "Tabela completa",
    ])

    with tab_venc:
        if not vencidos:
            st.success("Nenhum item vencido para os filtros selecionados.")
        else:
            for i, item in enumerate(vencidos):
                _card_pendencia(item, i, mapa_vinculos, templates_lub, cache_analises)

    with tab_prox:
        if not proximos:
            st.success("Nenhum item próximo do vencimento.")
        else:
            for i, item in enumerate(proximos):
                _card_pendencia(item, i, mapa_vinculos, templates_lub, cache_analises)

    with tab_dia:
        _render_tabela(em_dia, f"Em dia ({len(em_dia)})", "Nenhum item em dia.")

    with tab_real:
        _render_tabela(realizados, f"Realizados neste ciclo ({len(realizados)})", "Nenhuma execução registrada neste ciclo.")

    with tab_tabela:
        _render_tabela(filtrados, f"Todos os itens ({len(filtrados)})", "Nenhum item para exibir.")
