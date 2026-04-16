from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from services import dashboard_service, inteligencia_service, prioridades_service
from ui.theme import render_page_intro


def _css() -> None:
    st.markdown(
        """
        <style>
        .exec-hero {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 22px;
            padding: 1.15rem 1.2rem;
            background: linear-gradient(135deg, rgba(16,26,44,.96) 0%, rgba(11,23,38,.98) 62%, rgba(14,33,56,.98) 100%);
            margin-bottom: 1rem;
            box-shadow: 0 12px 40px rgba(0,0,0,.18);
        }
        .exec-hero::after {
            content: "";
            position: absolute;
            right: -70px;
            top: -80px;
            width: 240px;
            height: 240px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(79,140,255,.22) 0%, rgba(79,140,255,0) 72%);
            pointer-events: none;
        }
        .exec-badge {
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            padding: .22rem .62rem;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,.08);
            background: rgba(255,255,255,.05);
            color: #dbeafe;
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .02em;
        }
        .exec-badge.crit { background: rgba(239,68,68,.14); color: #fecaca; }
        .exec-badge.alt { background: rgba(245,158,11,.14); color: #fde68a; }
        .exec-badge.ok { background: rgba(34,197,94,.14); color: #bbf7d0; }
        .exec-hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(320px, .95fr);
            gap: 1rem;
            align-items: start;
            position: relative;
            z-index: 1;
        }
        .exec-hero h2 {
            margin: .3rem 0 .35rem;
            font-size: 2rem;
            line-height: 1.03;
            color: #eff6ff;
            letter-spacing: -.03em;
        }
        .exec-hero p {
            margin: 0;
            color: #9fb2ca;
            font-size: .92rem;
            max-width: 760px;
        }
        .exec-status-box {
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 18px;
            padding: .9rem 1rem;
            background: rgba(255,255,255,.03);
        }
        .exec-status-box .label {
            font-size: .72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: #8fa4c0;
        }
        .exec-status-box .value {
            margin-top: .35rem;
            font-size: 1.62rem;
            font-weight: 900;
            color: #f8fbff;
            line-height: 1;
        }
        .exec-status-box .sub {
            margin-top: .35rem;
            color: #9fb2ca;
            font-size: .8rem;
            line-height: 1.4;
        }
        .exec-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap: .8rem;
            margin-bottom: 1rem;
        }
        .exec-kpi {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 18px;
            padding: .95rem 1rem;
            background: linear-gradient(180deg, rgba(16,26,44,.96) 0%, rgba(12,22,37,.98) 100%);
            min-height: 138px;
        }
        .exec-kpi::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: var(--accent, #4f8cff);
        }
        .exec-kpi .eyebrow {
            font-size: .72rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: #8fa4c0;
            font-weight: 800;
        }
        .exec-kpi .number {
            margin-top: .45rem;
            font-size: 2.15rem;
            font-weight: 900;
            line-height: .95;
            color: #f8fbff;
        }
        .exec-kpi .headline {
            margin-top: .35rem;
            font-size: .94rem;
            font-weight: 700;
            color: #e8f1ff;
        }
        .exec-kpi .desc {
            margin-top: .22rem;
            color: #8fa4c0;
            font-size: .78rem;
            line-height: 1.4;
        }
        .exec-kpi.crit { --accent: #ef4444; }
        .exec-kpi.alt { --accent: #f59e0b; }
        .exec-kpi.info { --accent: #4f8cff; }
        .exec-kpi.ok { --accent: #22c55e; }
        .exec-kpi .mini-bar {
            margin-top: .7rem;
            height: 8px;
            border-radius: 999px;
            background: rgba(255,255,255,.06);
            overflow: hidden;
        }
        .exec-kpi .mini-bar > span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, rgba(255,255,255,.1), var(--accent, #4f8cff));
        }
        .exec-section {
            border: 1px solid rgba(148,163,184,.14);
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(15,24,39,.96) 0%, rgba(11,20,33,.98) 100%);
            padding: 1rem;
            margin-bottom: .95rem;
        }
        .exec-section-head {
            display: flex;
            justify-content: space-between;
            gap: .8rem;
            align-items: start;
            margin-bottom: .9rem;
        }
        .exec-section-head h3 {
            margin: 0;
            font-size: 1rem;
            color: #eff6ff;
        }
        .exec-section-head p {
            margin: .18rem 0 0;
            font-size: .8rem;
            color: #8fa4c0;
        }
        .exec-priority {
            border: 1px solid rgba(255,255,255,.07);
            border-radius: 16px;
            background: rgba(255,255,255,.03);
            padding: .92rem 1rem;
            margin-bottom: .68rem;
        }
        .exec-priority-top {
            display: flex;
            justify-content: space-between;
            align-items: start;
            gap: .7rem;
        }
        .exec-priority h4 {
            margin: 0;
            color: #eff6ff;
            font-size: .97rem;
            line-height: 1.25;
        }
        .exec-priority .subtitle {
            margin-top: .18rem;
            color: #9fb2ca;
            font-size: .8rem;
            line-height: 1.45;
        }
        .exec-tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: .36rem;
            margin-top: .55rem;
        }
        .exec-tag {
            display: inline-flex;
            padding: .16rem .48rem;
            border-radius: 999px;
            background: rgba(255,255,255,.04);
            border: 1px solid rgba(255,255,255,.06);
            color: #dbeafe;
            font-size: .68rem;
            font-weight: 700;
        }
        .exec-priority-action {
            margin-top: .7rem;
            padding: .62rem .72rem;
            border-radius: 12px;
            background: rgba(79,140,255,.08);
            border: 1px solid rgba(79,140,255,.14);
        }
        .exec-priority-action .lbl {
            font-size: .66rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: #8fb6ff;
            font-weight: 800;
            margin-bottom: .18rem;
        }
        .exec-priority-action .txt {
            color: #e8f1ff;
            font-size: .8rem;
            line-height: 1.4;
        }
        .exec-severity {
            display: inline-flex;
            align-items: center;
            gap: .3rem;
            padding: .18rem .55rem;
            border-radius: 999px;
            font-size: .7rem;
            font-weight: 800;
            border: 1px solid rgba(255,255,255,.08);
        }
        .exec-severity.crit { background: rgba(239,68,68,.14); color: #fecaca; }
        .exec-severity.alt { background: rgba(245,158,11,.14); color: #fde68a; }
        .exec-severity.med { background: rgba(79,140,255,.14); color: #bfdbfe; }
        .exec-severity.low { background: rgba(34,197,94,.14); color: #bbf7d0; }
        .exec-risk-list { display: grid; gap: .55rem; }
        .exec-risk-row {
            padding: .72rem .78rem;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,.06);
            background: rgba(255,255,255,.025);
        }
        .exec-risk-top {
            display: flex;
            justify-content: space-between;
            gap: .7rem;
            align-items: center;
            margin-bottom: .42rem;
        }
        .exec-risk-name { color: #eff6ff; font-size: .84rem; font-weight: 700; }
        .exec-risk-value { color: #f8fbff; font-size: .88rem; font-weight: 800; }
        .exec-progress {
            height: 9px;
            border-radius: 999px;
            background: rgba(255,255,255,.06);
            overflow: hidden;
        }
        .exec-progress > span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, rgba(79,140,255,.55), rgba(79,140,255,1));
        }
        .exec-progress.danger > span { background: linear-gradient(90deg, rgba(239,68,68,.55), rgba(239,68,68,1)); }
        .exec-progress.warn > span { background: linear-gradient(90deg, rgba(245,158,11,.55), rgba(245,158,11,1)); }
        .exec-insight {
            display: grid;
            grid-template-columns: repeat(2, minmax(0,1fr));
            gap: .7rem;
        }
        .exec-insight-card {
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,.06);
            background: rgba(255,255,255,.03);
            padding: .85rem .9rem;
        }
        .exec-insight-card .label {
            color: #8fa4c0;
            font-size: .72rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            font-weight: 800;
        }
        .exec-insight-card .value {
            margin-top: .3rem;
            color: #eff6ff;
            font-size: 1.28rem;
            font-weight: 900;
            line-height: 1;
        }
        .exec-insight-card .sub {
            margin-top: .3rem;
            color: #9fb2ca;
            font-size: .78rem;
            line-height: 1.4;
        }
        .exec-empty {
            border: 1px dashed rgba(148,163,184,.18);
            border-radius: 16px;
            padding: .95rem 1rem;
            color: #9fb2ca;
            background: rgba(255,255,255,.02);
        }
        div[data-baseweb="tab-list"] {
            gap: .35rem;
        }
        button[data-baseweb="tab"] {
            border-radius: 999px !important;
            padding: .35rem .82rem !important;
        }
        @media (max-width: 1100px) {
            .exec-kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
            .exec-hero-grid { grid-template-columns: 1fr; }
            .exec-insight { grid-template-columns: 1fr; }
        }
        @media (max-width: 680px) {
            .exec-kpi-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sev_class(criticidade: str) -> str:
    return {"Crítica": "crit", "Alta": "alt", "Média": "med", "Baixa": "low"}.get(criticidade, "low")


def _safe_int(valor) -> int:
    try:
        return int(float(valor or 0))
    except Exception:
        return 0


def _safe_float(valor) -> float:
    try:
        return float(valor or 0)
    except Exception:
        return 0.0


def _resumo_status(kpis: dict) -> tuple[str, str, str, str]:
    crit = _safe_int(kpis.get("criticos"))
    altos = _safe_int(kpis.get("altos"))
    parados = _safe_int(kpis.get("parados"))
    cobertura = _safe_float(kpis.get("cobertura"))
    if crit >= 8 or parados >= 50:
        return "Operação exige intervenção", "Criticidade elevada", "crit", f"{crit} críticos e {parados} equipamentos sem leitura recente." 
    if crit > 0 or altos >= 8 or parados >= 15:
        return "Atenção executiva", "Monitoramento reforçado", "alt", f"{crit} críticos, {altos} alertas altos e {parados} equipamentos em observação." 
    if cobertura >= 95:
        return "Operação estável", "Cenário controlado", "ok", "Sem sinais relevantes de exposição operacional no momento." 
    return "Rotina sob controle", "Monitoramento diário", "ok", f"Cobertura operacional em {cobertura:.1f}% com baixo volume de criticidades." 


def _hero(dados: dict) -> None:
    k = dados.get("kpis", {})
    titulo, badge_txt, badge_css, subtitulo = _resumo_status(k)
    total = _safe_int(k.get("total_equipamentos"))
    alerta = _safe_int(k.get("equipamentos_com_alerta"))
    cobertura = _safe_float(k.get("cobertura"))
    st.markdown(
        f"""
        <div class="exec-hero">
            <div class="exec-hero-grid">
                <div>
                    <span class="exec-badge {badge_css}">{html.escape(badge_txt)}</span>
                    <h2>{html.escape(titulo)}</h2>
                    <p>{html.escape(subtitulo)}</p>
                </div>
                <div class="exec-status-box">
                    <div class="label">Leitura executiva</div>
                    <div class="value">{total - alerta} estáveis / {total} ativos</div>
                    <div class="sub">{alerta} equipamentos concentram algum tipo de atenção operacional. Cobertura atual em <strong>{cobertura:.1f}%</strong>.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, valor: str, headline: str, desc: str, css: str, fill: float) -> None:
    fill = max(0.0, min(100.0, fill))
    st.markdown(
        f"""
        <div class="exec-kpi {css}">
            <div class="eyebrow">{html.escape(label)}</div>
            <div class="number">{valor}</div>
            <div class="headline">{html.escape(headline)}</div>
            <div class="desc">{html.escape(desc)}</div>
            <div class="mini-bar"><span style="width:{fill:.1f}%"></span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_priority_card(item: dict, pos: int) -> None:
    criticidade = str(item.get("Criticidade") or "Baixa")
    sev = _sev_class(criticidade)
    equipamento = str(item.get("Equipamento") or "-")
    resumo = str(item.get("Resumo") or "Sem detalhe")
    acao = str(item.get("Ação sugerida") or "Acompanhar rotina")
    setor = str(item.get("Setor") or "-")
    origem = str(item.get("Origem") or "-")
    status = str(item.get("Status") or "-")
    st.markdown(
        f"""
        <div class="exec-priority">
            <div class="exec-priority-top">
                <div>
                    <h4>{pos}. {html.escape(equipamento)}</h4>
                    <div class="subtitle">{html.escape(resumo)}</div>
                </div>
                <span class="exec-severity {sev}">{html.escape(criticidade)}</span>
            </div>
            <div class="exec-tag-row">
                <span class="exec-tag">{html.escape(setor)}</span>
                <span class="exec-tag">{html.escape(origem)}</span>
                <span class="exec-tag">{html.escape(status)}</span>
            </div>
            <div class="exec-priority-action">
                <div class="lbl">Ação recomendada</div>
                <div class="txt">{html.escape(acao)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_risk_rows(registros: list[dict], total_ref: int) -> None:
    if not registros:
        st.markdown('<div class="exec-empty">Operação estável, sem concentração relevante de exposição por setor.</div>', unsafe_allow_html=True)
        return
    total_ref = max(1, total_ref)
    blocos = []
    for item in registros[:6]:
        nome = html.escape(str(item.get("Setor") or "-"))
        score = _safe_int(item.get("Score"))
        alertas = _safe_int(item.get("Alertas"))
        vencidos = _safe_int(item.get("Vencidos"))
        proximos = _safe_int(item.get("Próximos"))
        pct = min(100.0, (score / total_ref) * 100)
        progress_cls = "danger" if vencidos > 0 else ("warn" if proximos > 0 else "")
        blocos.append(
            f"<div class='exec-risk-row'><div class='exec-risk-top'><div class='exec-risk-name'>{nome}</div><div class='exec-risk-value'>{alertas} alertas</div></div><div class='exec-progress {progress_cls}'><span style='width:{pct:.1f}%'></span></div><div style='margin-top:.38rem;color:#8fa4c0;font-size:.76rem;'>Score {score} • {vencidos} vencidos • {proximos} próximos</div></div>"
        )
    st.markdown(f"<div class='exec-risk-list'>{''.join(blocos)}</div>", unsafe_allow_html=True)


def _render_category_cards(categorias: list[dict]) -> None:
    if not categorias:
        st.markdown('<div class="exec-empty">Sem categorias críticas para consolidar.</div>', unsafe_allow_html=True)
        return
    top = sorted(categorias, key=lambda x: -_safe_int(x.get("Qtd")))[:4]
    cols = st.columns(len(top))
    max_qtd = max([_safe_int(i.get("Qtd")) for i in top] + [1])
    for col, item in zip(cols, top):
        qtd = _safe_int(item.get("Qtd"))
        nome = str(item.get("Categoria") or "-")
        if qtd > 0:
            headline = "Ponto sensível"
            css = "crit" if qtd >= max_qtd else "alt"
        else:
            headline = "Sem ocorrência"
            css = "ok"
        with col:
            _metric_card(nome, str(qtd), headline, "Visão resumida para tomada de decisão.", css, (qtd / max_qtd) * 100 if max_qtd else 0)


def _insights(dados: dict) -> None:
    mov = dados.get("movimentacao") or {}
    anom = mov.get("anomalias") or {}
    ranking = dados.get("ranking_movimentacao") or []
    topo = ranking[0] if ranking else {}
    parados = dados.get("parados") or []
    top_setor = (dados.get("exposicao_setores") or [{}])[0] if (dados.get("exposicao_setores") or []) else {}
    st.markdown(
        f"""
        <div class="exec-insight">
            <div class="exec-insight-card">
                <div class="label">Foco imediato</div>
                <div class="value">{html.escape(str(top_setor.get('Setor') or 'Operação geral'))}</div>
                <div class="sub">Maior concentração atual de exposição executiva, considerando vencidos e itens próximos.</div>
            </div>
            <div class="exec-insight-card">
                <div class="label">Equipamento em evidência</div>
                <div class="value">{html.escape(str(topo.get('Equipamento') or topo.get('codigo_nome') or 'Sem destaque'))}</div>
                <div class="sub">Maior movimentação recente. Ajuda a explicar pressão operacional e próximos vencimentos.</div>
            </div>
            <div class="exec-insight-card">
                <div class="label">Anomalias de leitura</div>
                <div class="value">{len(anom.get('travadas', [])) + len(anom.get('saltos', [])) + len(anom.get('inconsistencias', []))}</div>
                <div class="sub">Travadas, saltos anormais e inconsistências KM/H identificadas pelo motor de inteligência.</div>
            </div>
            <div class="exec-insight-card">
                <div class="label">Equipamentos parados</div>
                <div class="value">{len(parados)}</div>
                <div class="sub">Itens com maior indício de baixa utilização dentro da janela atual do painel.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    _css()

    top1, top2 = st.columns([5, 1])
    with top1:
        render_page_intro(
            "Painel Executivo",
            "Visão de diretoria com prioridades, exposição operacional e ações recomendadas.",
            chip="Diretoria",
        )
    with top2:
        st.write("")
        if st.button("Atualizar painel", use_container_width=True):
            dashboard_service.carregar_alertas.clear()
            try:
                dashboard_service.carregar_movimentacao.clear()
            except Exception:
                pass
            try:
                prioridades_service.limpar_cache()
            except Exception:
                pass
            inteligencia_service.limpar_cache()
            st.rerun()

    with st.spinner("Consolidando visão executiva…"):
        dados = inteligencia_service.carregar_painel_executivo()

    _hero(dados)

    k = dados.get("kpis", {})
    total = max(1, _safe_int(k.get("total_equipamentos")))
    criticos = _safe_int(k.get("criticos"))
    altos = _safe_int(k.get("altos"))
    parados = _safe_int(k.get("parados"))
    cobertura = _safe_float(k.get("cobertura"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("Críticos", str(criticos), "Exigem ação imediata", "Combine parada operacional, vencimento e ausência de leitura para priorização diária.", "crit", (criticos / total) * 100)
    with c2:
        _metric_card("Atenção alta", str(altos), "Acompanhar no dia", "Itens relevantes que ainda permitem atuação preventiva antes de virar crise.", "alt", (altos / total) * 100)
    with c3:
        _metric_card("Equipamentos parados", str(parados), "Impacto na utilização", "Sem leitura recente dentro da janela configurada. Útil para validar operação e disponibilidade.", "info", (parados / total) * 100)
    with c4:
        _metric_card("Cobertura operacional", f"{cobertura:.1f}%", "Base sob controle", "Percentual estimado de equipamentos sem alerta ativo relevante no cenário atual.", "ok", cobertura)

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown('<div class="exec-section">', unsafe_allow_html=True)
        st.markdown('<div class="exec-section-head"><div><h3>Ações prioritárias</h3><p>O que a diretoria precisa enxergar primeiro para direcionar a rotina.</p></div><div class="exec-badge crit">Top 5</div></div>', unsafe_allow_html=True)
        top_alertas = dados.get("top_alertas") or []
        if top_alertas:
            for idx, item in enumerate(top_alertas[:5], start=1):
                _render_priority_card(item, idx)
        else:
            st.markdown('<div class="exec-empty">Nenhuma ação prioritária aberta no momento.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="exec-section">', unsafe_allow_html=True)
        st.markdown('<div class="exec-section-head"><div><h3>Resumo de risco</h3><p>Leitura sintética por categoria para facilitar a discussão executiva.</p></div></div>', unsafe_allow_html=True)
        _render_category_cards(dados.get("categorias") or [])
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="exec-section">', unsafe_allow_html=True)
        st.markdown('<div class="exec-section-head"><div><h3>Exposição por setor</h3><p>Onde o risco está mais concentrado neste momento.</p></div></div>', unsafe_allow_html=True)
        expos = dados.get("exposicao_setores") or []
        maior_score = max([_safe_int(x.get("Score")) for x in expos] + [1])
        _render_risk_rows(expos, maior_score)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="exec-section">', unsafe_allow_html=True)
        st.markdown('<div class="exec-section-head"><div><h3>Leitura rápida</h3><p>Insights resumidos para orientar decisão sem abrir detalhes.</p></div></div>', unsafe_allow_html=True)
        _insights(dados)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="exec-section">', unsafe_allow_html=True)
    st.markdown('<div class="exec-section-head"><div><h3>Desdobramento executivo</h3><p>Visões complementares para aprofundar a decisão sem poluir a leitura principal.</p></div></div>', unsafe_allow_html=True)

    col_mov, col_par = st.columns(2, gap="large")

    with col_mov:
        st.markdown('<div class="exec-subsection-head"><h4>Ranking de movimentação</h4><p>Equipamentos com maior uso recente, úteis para antecipar pressão sobre revisão e lubrificação.</p></div>', unsafe_allow_html=True)
        df_mov = pd.DataFrame(dados.get("ranking_movimentacao") or [])
        if df_mov.empty:
            st.markdown('<div class="exec-empty">Sem movimentação suficiente para consolidar ranking.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(df_mov, use_container_width=True, hide_index=True)

    with col_par:
        st.markdown('<div class="exec-subsection-head"><h4>Equipamentos parados</h4><p>Itens que merecem validação operacional por baixa movimentação ou ausência de leitura recente.</p></div>', unsafe_allow_html=True)
        df_par = pd.DataFrame(dados.get("parados") or [])
        if df_par.empty:
            st.markdown('<div class="exec-empty">Nenhum equipamento parado acima da janela configurada.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(df_par, use_container_width=True, hide_index=True)

    st.markdown('<div class="exec-subsection-head exec-subsection-full"><h4>Plano de ação sugerido</h4><p>Desdobramento prático das prioridades para orientar reunião rápida de gestão.</p></div>', unsafe_allow_html=True)
    plano = pd.DataFrame(dados.get("plano_acao") or [])
    if plano.empty:
        st.markdown('<div class="exec-empty">Sem plano de ação sugerido no momento.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(plano, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
