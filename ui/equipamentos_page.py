from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from services import (
    comentarios_service,
    equipamentos_service,
    lubrificacoes_service,
    painel_360_service,
    responsaveis_service,
    revisoes_service,
    setores_service,
)
from ui.constants import STATUS_LABEL, TIPOS_EQUIPAMENTO
from ui.theme import render_page_intro


def _inject_css():
    st.markdown(
        """
        <style>
        .eq-kpi-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap: .55rem;
            margin-bottom: 1rem;
        }
        .eq-kpi {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 10px;
            padding: .65rem .85rem;
            background: #0d1929;
        }
        .eq-kpi .lbl  { font-size: .70rem; color: #6b84a0; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: .22rem; }
        .eq-kpi .val  { font-size: 1.45rem; font-weight: 700; line-height: 1; color: #e8f1ff; }
        .eq-kpi .val.ok     { color: #86efac; }
        .eq-kpi .val.warn   { color: #fcd34d; }
        .eq-kpi .val.danger { color: #fca5a5; }

        .eq-card {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem 1rem;
            background: #0d1929;
            margin-bottom: .5rem;
            transition: border-color .15s;
        }
        .eq-card:hover { border-color: rgba(148,163,184,.24); }
        .eq-card-code  { font-size: .70rem; color: #6b84a0; font-weight: 600; letter-spacing: .04em; margin-bottom: .08rem; }
        .eq-card-title { font-size: .95rem; font-weight: 700; color: #e8f1ff; }
        .eq-card-meta  { font-size: .78rem; color: #8fa4c0; margin-top: .14rem; }
        .eq-card-badges { margin-top: .42rem; display: flex; flex-wrap: wrap; gap: .3rem; }

        .eq-score-wrap {
            position: relative; width: 44px; height: 44px; flex-shrink: 0;
        }
        .eq-score-num {
            position: absolute; inset: 0;
            display: flex; align-items: center; justify-content: center;
            font-size: .65rem; font-weight: 700;
        }

        .eq-b {
            display: inline-block;
            padding: .14rem .45rem;
            border-radius: 999px;
            font-size: .69rem; font-weight: 700;
        }
        .eq-ok      { background: rgba(34,197,94,.10);  color: #86efac; }
        .eq-warn    { background: rgba(245,158,11,.10); color: #fcd34d; }
        .eq-danger  { background: rgba(239,68,68,.10);  color: #fca5a5; }
        .eq-neutral { background: rgba(148,163,184,.09); color: #94a8c4; }

        .eq-modal-head {
            display:flex; align-items:flex-start; justify-content:space-between; gap:1rem;
            margin-bottom:.5rem;
        }
        .eq-modal-title {
            font-size: 1.15rem; font-weight: 800; color: #e8f1ff; line-height: 1.2;
            margin: 0 0 .2rem 0;
        }
        .eq-modal-sub {
            font-size: .85rem; color: #8fa4c0; margin: 0;
        }
        .eq-modal-metrics {
            display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:.5rem; margin:.85rem 0 .65rem;
        }
        .eq-mini {
            background: rgba(255,255,255,.025); border: 1px solid rgba(148,163,184,.1);
            border-radius: 10px; padding:.55rem .7rem;
        }
        .eq-mini .k { font-size:.68rem; color:#6b84a0; text-transform:uppercase; letter-spacing:.04em; font-weight:700; }
        .eq-mini .v { font-size:1.05rem; color:#e8f1ff; font-weight:800; line-height:1.15; margin-top:.15rem; }
        .eq-inline-strip {
            display:flex; flex-wrap:wrap; gap:.45rem; margin:.35rem 0 .9rem;
        }
        .eq-chip {
            padding:.34rem .55rem; border-radius:999px; background:rgba(255,255,255,.035);
            border:1px solid rgba(148,163,184,.1); color:#d9e6f7; font-size:.78rem;
        }
        .eq-chip strong { color:#8fb7ff; font-weight:700; }
        .eq-section {
            border-top:1px solid rgba(148,163,184,.12); padding-top:.75rem; margin-top:.4rem;
        }
        .eq-modal-shell {
            animation: eqFadeSlide .18s ease-out;
        }
        @keyframes eqFadeSlide {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .eq-priority {
            border: 1px solid rgba(148,163,184,.1);
            border-radius: 12px;
            padding: .8rem .9rem;
            background: rgba(255,255,255,.02);
            min-height: 104px;
        }
        .eq-priority.danger { border-color: rgba(239,68,68,.28); background: rgba(239,68,68,.07); }
        .eq-priority.warn { border-color: rgba(245,158,11,.28); background: rgba(245,158,11,.06); }
        .eq-priority.ok { border-color: rgba(34,197,94,.2); background: rgba(34,197,94,.05); }
        .eq-priority .t { font-size:.72rem; color:#8fa4c0; text-transform:uppercase; letter-spacing:.04em; font-weight:700; margin-bottom:.25rem; }
        .eq-priority .h { font-size:.95rem; color:#e8f1ff; font-weight:800; line-height:1.25; margin-bottom:.28rem; }
        .eq-priority .d { font-size:.8rem; color:#b9cae0; line-height:1.35; }
        .eq-health-line { display:flex; align-items:center; gap:.5rem; margin:.35rem 0 .6rem; }
        .eq-health-dot { width:10px; height:10px; border-radius:999px; display:inline-block; }
        .eq-health-note { font-size:.82rem; color:#b9cae0; }
        .eq-timeline-item {
            border-left: 2px solid rgba(148,163,184,.18);
            padding: 0 0 .85rem .85rem;
            margin-left: .32rem;
            position: relative;
        }
        .eq-timeline-item::before {
            content: '';
            position: absolute; left: -6px; top: 4px;
            width: 10px; height: 10px; border-radius: 999px;
            background: #8fb7ff; box-shadow: 0 0 0 4px rgba(143,183,255,.08);
        }
        .eq-timeline-top { display:flex; justify-content:space-between; gap:.75rem; align-items:flex-start; }
        .eq-timeline-type { font-size:.72rem; color:#8fb7ff; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
        .eq-timeline-title { font-size:.92rem; color:#e8f1ff; font-weight:700; margin:.08rem 0; }
        .eq-timeline-meta, .eq-timeline-detail { font-size:.8rem; color:#b9cae0; line-height:1.35; }
        .eq-soft-card {
            border: 1px solid rgba(148,163,184,.1); border-radius:12px; padding:.8rem .9rem; background:rgba(255,255,255,.02);
        }
        div[data-testid="stRadio"] label p { font-size:.92rem; }
        .eq-config-wrap {
            border: 1px solid rgba(148,163,184,.1);
            border-radius: 12px;
            padding: .85rem;
            background: rgba(255,255,255,.02);
            margin-top:.35rem;
        }
        @media (max-width: 900px) {
            .eq-kpi-strip, .eq-modal-metrics { grid-template-columns: repeat(2,minmax(0,1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value, css_class: str = ""):
    st.markdown(
        f'<div class="eq-kpi"><div class="lbl">{label}</div><div class="val {css_class}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def _badge(saude: str) -> str:
    css = {
        "Saudável": "eq-b eq-ok",
        "Atenção": "eq-b eq-warn",
        "Crítico": "eq-b eq-danger",
        "Sem plano": "eq-b eq-neutral",
    }.get(saude, "eq-b eq-neutral")
    return f'<span class="{css}">{saude}</span>'


def _score_ring(score: int) -> str:
    radius = 18
    circumference = 2 * 3.14159 * radius
    dash = circumference * score / 100
    color = "#22c55e" if score >= 80 else ("#f59e0b" if score >= 50 else "#ef4444")
    return (
        f'<div class="eq-score-wrap">'
        f'<svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;width:44px;height:44px">'
        f'<circle cx="22" cy="22" r="{radius}" fill="none" stroke="rgba(148,163,184,.15)" stroke-width="3.5"/>'
        f'<circle cx="22" cy="22" r="{radius}" fill="none" stroke="{color}" stroke-width="3.5" '
        f'stroke-dasharray="{dash:.1f} {circumference:.1f}" stroke-linecap="round" transform="rotate(-90 22 22)"/>'
        f'</svg>'
        f'<div class="eq-score-num" style="color:{color}">{score}%</div>'
        f'</div>'
    )


def _build_export_df(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "Código": row.get("codigo"),
            "Equipamento": row.get("nome"),
            "Tipo": row.get("tipo"),
            "Setor": row.get("setor_nome"),
            "Responsável principal": row.get("responsavel_principal_nome"),
            "Saúde": row.get("saude"),
            "Score saúde": row.get("score_saude"),
            "Vencidos": row.get("vencidos"),
            "Próximos": row.get("proximos"),
            "KM atual": row.get("km_atual"),
            "Horas atual": row.get("horas_atual"),
            "KM inicial plano": row.get("km_inicial_plano", row.get("km_base_plano")),
            "Horas iniciais plano": row.get("horas_inicial_plano", row.get("horas_base_plano")),
            "Ativo": "Sim" if row.get("ativo") else "Não",
        }
        for row in rows
    ])


def _csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro):
    termo_norm = (termo or "").strip().lower()
    filtrados = rows
    if termo_norm:
        filtrados = [
            r for r in filtrados if termo_norm in f'{r.get("codigo","")} {r.get("nome","")} {r.get("setor_nome","")} {r.get("responsavel_principal_nome","")}'.lower()
        ]
    if setores_filtro:
        filtrados = [r for r in filtrados if (r.get("setor_nome") or "-") in setores_filtro]
    if status_filtro != "Todos":
        ativo_bool = status_filtro == "Ativos"
        filtrados = [r for r in filtrados if bool(r.get("ativo")) == ativo_bool]
    if tipo_filtro != "Todos":
        filtrados = [r for r in filtrados if (r.get("tipo") or "-") == tipo_filtro]
    if saude_filtro != "Todas":
        filtrados = [r for r in filtrados if (r.get("saude") or "-") == saude_filtro]
    return filtrados


def _render_summary(rows):
    total = len(rows)
    ativos = sum(1 for r in rows if r.get("ativo"))
    criticos = sum(1 for r in rows if r.get("saude") == "Crítico")
    sem_plano = sum(1 for r in rows if r.get("saude") == "Sem plano")

    st.markdown('<div class="eq-kpi-strip">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        _kpi("Total", total)
    with c2:
        _kpi("Ativos", ativos, "ok")
    with c3:
        _kpi("Críticos", criticos, "danger" if criticos else "")
    with c4:
        _kpi("Sem plano", sem_plano, "warn" if sem_plano else "")
    st.markdown("</div>", unsafe_allow_html=True)


def _slice(rows, page, page_size):
    start = max(0, (page - 1) * page_size)
    return rows[start : start + page_size]


@st.cache_data(ttl=120, show_spinner=False)
def _responsaveis_ativos():
    try:
        return [r for r in responsaveis_service.listar() if r.get("ativo")]
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def _setores():
    try:
        return setores_service.listar()
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _carregar_equipamento(eq_id: str):
    return equipamentos_service.obter(eq_id)


@st.cache_data(ttl=60, show_spinner=False)
def _revisoes_eq(eq_id: str):
    return revisoes_service.listar_controle_revisoes_por_equipamento().get(eq_id, [])


@st.cache_data(ttl=60, show_spinner=False)
def _lubrificacoes_eq(eq_id: str):
    return lubrificacoes_service.calcular_proximas_lubrificacoes_batch([eq_id]).get(eq_id, [])


@st.cache_data(ttl=60, show_spinner=False)
def _timeline_eq(eq_id: str):
    return painel_360_service.montar_timeline_equipamento(eq_id, limite=20)


def _health_descriptor(score: int) -> tuple[str, str, str]:
    if score >= 80:
        return ('Verde', 'Operação estável, sem sinais críticos no momento.', '#22c55e')
    if score >= 50:
        return ('Amarelo', 'Há itens próximos do vencimento que pedem programação.', '#f59e0b')
    return ('Vermelho', 'Existem pendências críticas ou necessidade de ação imediata.', '#ef4444')


def _format_num(v) -> str:
    try:
        return f"{float(v or 0):,.0f}"
    except Exception:
        return '0'


def _build_prioridade(revisoes: list[dict], lubrificacoes: list[dict]):
    pend = painel_360_service.resumir_pendencias(revisoes, lubrificacoes)
    if not pend:
        return {
            'css': 'ok',
            'titulo': 'Nenhuma pendência crítica',
            'detalhe': 'Equipamento sem revisões ou lubrificações vencidas/próximas no momento.',
        }
    top = pend[0]
    unidade = 'h' if (top.get('controle') or '').lower() == 'horas' else 'km'
    status = (top.get('status') or '').upper()
    if status == 'VENCIDO':
        diff = abs(float(top.get('falta') or 0))
        css = 'danger'
        titulo = f"{top.get('origem')} atrasada"
        detalhe = f"{top.get('item')} · atraso de {_format_num(diff)} {unidade}."
    else:
        diff = float(top.get('falta') or 0)
        css = 'warn'
        titulo = f"Próxima ação: {top.get('origem')}"
        detalhe = f"{top.get('item')} · faltam {_format_num(diff)} {unidade}."
    return {'css': css, 'titulo': titulo, 'detalhe': detalhe, 'raw': top}


def _setor_options():
    return {str(s["id"]): s.get("nome", "-") for s in _setores()}


def _responsavel_options():
    return {str(r["id"]): r.get("nome", "-") for r in _responsaveis_ativos()}


def _render_card(row: dict):
    venc = int(row.get("vencidos", 0) or 0)
    prox = int(row.get("proximos", 0) or 0)
    score = int(row.get("score_saude", 0) or 0)
    ativo = row.get("ativo")

    km = float(row.get("km_atual") or 0)
    hrs = float(row.get("horas_atual") or 0)
    medidor = f"{km:,.0f} km" if km else (f"{hrs:,.0f} h" if hrs else "—")

    badge_saude = _badge(row.get("saude", "-"))
    badge_venc = f'<span class="eq-b {"eq-danger" if venc else "eq-neutral"}">{venc} vencida{"s" if venc != 1 else ""}</span>'
    badge_prox = f'<span class="eq-b {"eq-warn" if prox else "eq-neutral"}">{prox} próxima{"s" if prox != 1 else ""}</span>'
    badge_status = f'<span class="eq-b {"eq-ok" if ativo else "eq-neutral"}">{"Ativo" if ativo else "Inativo"}</span>'

    col_info, col_score, col_btn = st.columns([6, 1, 1], gap="small")
    with col_info:
        st.markdown(
            f'<div class="eq-card-code">{row.get("codigo", "-")}</div>'
            f'<div class="eq-card-title">{row.get("nome", "-")}</div>'
            f'<div class="eq-card-meta">{row.get("setor_nome", "-")} · {row.get("tipo", "-")} · {medidor}</div>'
            f'<div class="eq-card-badges">{badge_saude}{badge_venc}{badge_prox}{badge_status}</div>',
            unsafe_allow_html=True,
        )
    with col_score:
        st.markdown(_score_ring(score), unsafe_allow_html=True)
    with col_btn:
        if st.button("Detalhes", key=f"det_{row['id']}", use_container_width=True):
            st.session_state["eq_modal_id"] = row["id"]
            st.session_state["eq_modal_row"] = row
            st.session_state[f"eq_section_{row['id']}"] = "Resumo"


def _render_metric_mini(label: str, value):
    st.markdown(
        f'<div class="eq-mini"><div class="k">{label}</div><div class="v">{value}</div></div>',
        unsafe_allow_html=True,
    )


def _render_resumo_section(eq_id: str, equipamento: dict, snap: dict):
    km_atual = float(equipamento.get("km_atual", snap.get("km_atual", 0)) or 0)
    horas_atual = float(equipamento.get("horas_atual", snap.get("horas_atual", 0)) or 0)
    km_ini = float(equipamento.get("km_inicial_plano", equipamento.get("km_base_plano", km_atual)) or 0)
    horas_ini = float(equipamento.get("horas_inicial_plano", equipamento.get("horas_base_plano", horas_atual)) or 0)

    score = int(equipamento.get("score_saude", snap.get("score_saude", 0)) or 0)
    faixa, leitura_saude, cor = _health_descriptor(score)

    revisoes = _revisoes_eq(eq_id)
    lubrificacoes = _lubrificacoes_eq(eq_id)
    prioridade = _build_prioridade(revisoes, lubrificacoes)

    st.markdown('<div class="eq-health-line"><span class="eq-health-dot" style="background:' + cor + '"></span>'
                f'<span class="eq-chip"><strong>Saúde {faixa}</strong></span>'
                f'<span class="eq-health-note">{leitura_saude}</span></div>', unsafe_allow_html=True)

    p1, p2 = st.columns([1.4, 1], gap="small")
    with p1:
        st.markdown(
            f'<div class="eq-priority {prioridade["css"]}"><div class="t">Prioridade operacional</div>'
            f'<div class="h">{prioridade["titulo"]}</div><div class="d">{prioridade["detalhe"]}</div></div>',
            unsafe_allow_html=True,
        )
    with p2:
        with st.container(border=False):
            st.markdown('<div class="eq-soft-card">', unsafe_allow_html=True)
            st.caption('Ações rápidas')
            a1, a2 = st.columns(2, gap="small")
            with a1:
                if st.button('Abrir revisões', key=f'quick_rev_{eq_id}', use_container_width=True):
                    st.session_state['pagina_atual'] = '🔧 Controle de Revisões'
                    st.session_state.pop('eq_modal_id', None)
                    st.rerun()
            with a2:
                if st.button('Abrir lubrificações', key=f'quick_lub_{eq_id}', use_container_width=True):
                    st.session_state['pagina_atual'] = '🛢️ Controle de Lubrificações'
                    st.session_state.pop('eq_modal_id', None)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="eq-inline-strip">', unsafe_allow_html=True)
    chips = [
        f'<span class="eq-chip"><strong>KM atual</strong> {km_atual:,.0f}</span>',
        f'<span class="eq-chip"><strong>Horas</strong> {horas_atual:,.0f}</span>',
        f'<span class="eq-chip"><strong>KM inicial</strong> {km_ini:,.0f}</span>',
        f'<span class="eq-chip"><strong>Horas iniciais</strong> {horas_ini:,.0f}</span>',
    ]
    st.markdown("".join(chips) + "</div>", unsafe_allow_html=True)

    if prioridade.get('raw'):
        raw = prioridade['raw']
        unidade = 'h' if (raw.get('controle') or '').lower() == 'horas' else 'km'
        ref = _format_num(raw.get('referencia'))
        st.caption(f"Referência do próximo marco: {ref} {unidade} · Origem: {raw.get('origem')} · Item: {raw.get('item')}")


def _render_revisoes_section(eq_id: str):
    with st.spinner("Carregando revisões..."):
        rev = _revisoes_eq(eq_id)
    if rev:
        df = pd.DataFrame(rev)[["etapa", "tipo_controle", "atual", "proximo_vencimento", "diferenca", "status"]].rename(
            columns={
                "etapa": "Etapa",
                "tipo_controle": "Controle",
                "atual": "Atual",
                "proximo_vencimento": "Próx. vencimento",
                "diferenca": "Falta",
                "status": "Status",
            }
        )
        df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma revisão encontrada.")


def _render_lubrificacoes_section(eq_id: str):
    with st.spinner("Carregando lubrificações..."):
        lub = _lubrificacoes_eq(eq_id)
    if lub:
        df = pd.DataFrame(lub)[["item", "tipo_controle", "atual", "vencimento", "diferenca", "status"]].rename(
            columns={
                "item": "Item",
                "tipo_controle": "Controle",
                "atual": "Atual",
                "vencimento": "Vencimento",
                "diferenca": "Falta",
                "status": "Status",
            }
        )
        df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma lubrificação encontrada.")


def _render_historico_section(eq_id: str):
    top1, top2 = st.columns([1.6, 1], gap='small')
    with top1:
        novo_comentario = st.text_area('Comentário rápido', key=f'coment_eq_{eq_id}', height=90, placeholder='Registrar observação, contexto ou atualização rápida...')
    with top2:
        st.caption('Ações')
        if st.button('Salvar comentário', key=f'coment_btn_{eq_id}', use_container_width=True, type='primary'):
            ok, msg = comentarios_service.criar(eq_id, novo_comentario)
            if ok:
                _timeline_eq.clear()
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        st.caption('O histórico reúne leituras, revisões, lubrificações, comentários e alertas.')

    timeline = _timeline_eq(eq_id)
    if not timeline:
        st.info('Nenhum evento recente encontrado.')
        return

    for evento in timeline[:12]:
        data = evento.get('data')
        data_txt = data.strftime('%d/%m/%Y %H:%M') if hasattr(data, 'strftime') else str(data or '-')
        observacoes = (evento.get('observacoes') or '').strip()
        detalhe_extra = f"<div class='eq-timeline-detail'>{observacoes}</div>" if observacoes and observacoes != (evento.get('detalhe') or '').strip() else ''
        st.markdown(
            f"<div class='eq-timeline-item'><div class='eq-timeline-top'><div><div class='eq-timeline-type'>{evento.get('tipo','Evento')}</div>"
            f"<div class='eq-timeline-title'>{evento.get('titulo','-')}</div>"
            f"<div class='eq-timeline-detail'>{evento.get('detalhe','')}</div>{detalhe_extra}</div>"
            f"<div class='eq-timeline-meta'>{data_txt}<br>{evento.get('responsavel') or '-'}</div></div></div>",
            unsafe_allow_html=True,
        )


def _render_config_section(eq_id: str, equipamento: dict, setor_map: dict, responsavel_map: dict):
    st.markdown('<div class="eq-config-wrap">', unsafe_allow_html=True)
    e1, e2, e3 = st.columns([2.2, 1.3, 0.8])
    with e1:
        nome_edit = st.text_input("Nome", value=equipamento.get("nome", ""), key=f"edit_nome_{eq_id}")
    with e2:
        tipos_list = list(TIPOS_EQUIPAMENTO)
        tipo_edit = st.selectbox(
            "Tipo",
            options=tipos_list,
            index=max(0, tipos_list.index(equipamento.get("tipo"))) if equipamento.get("tipo") in tipos_list else 0,
            key=f"edit_tipo_{eq_id}",
        )
    with e3:
        ativo_edit = st.checkbox("Ativo", value=bool(equipamento.get("ativo")), key=f"edit_ativo_{eq_id}")

    setor_ids = list(setor_map.keys())
    setor_labels = [setor_map[k] for k in setor_ids]
    setor_atual = str(equipamento.get("setor_id") or "")
    setor_index = setor_ids.index(setor_atual) if setor_atual in setor_ids else 0

    s1, s2 = st.columns([2.5, 1.5])
    with s1:
        setor_idx = st.selectbox(
            "Setor",
            options=range(len(setor_ids)),
            index=setor_index,
            format_func=lambda i: setor_labels[i],
            key=f"edit_setor_{eq_id}",
        )

    km_inicial_atual = float(equipamento.get("km_inicial_plano", equipamento.get("km_base_plano", equipamento.get("km_atual", 0))) or 0)
    horas_inicial_atual = float(equipamento.get("horas_inicial_plano", equipamento.get("horas_base_plano", equipamento.get("horas_atual", 0))) or 0)

    b1, b2 = st.columns(2)
    with b1:
        km_inicial_edit = st.number_input(
            "KM inicial do plano", min_value=0.0, value=km_inicial_atual, step=1.0, key=f"edit_km_inicial_{eq_id}"
        )
    with b2:
        horas_inicial_edit = st.number_input(
            "Horas iniciais do plano", min_value=0.0, value=horas_inicial_atual, step=1.0, key=f"edit_horas_inicial_{eq_id}"
        )

    resp_ids = [""] + list(responsavel_map.keys())
    resp_labels = ["— sem principal —"] + list(responsavel_map.values())
    resp_atual = str(equipamento.get("responsavel_principal_id") or "")
    resp_index = resp_ids.index(resp_atual) if resp_atual in resp_ids else 0

    r1, r2, r3 = st.columns([2.4, 1, 1])
    with r1:
        resp_idx = st.selectbox(
            "Responsável principal",
            options=range(len(resp_ids)),
            index=resp_index,
            format_func=lambda i: resp_labels[i],
            key=f"edit_resp_{eq_id}",
        )
    with r2:
        st.caption(f"KM atual: {float(equipamento.get('km_atual', 0) or 0):,.0f}")
    with r3:
        st.caption(f"Horas atuais: {float(equipamento.get('horas_atual', 0) or 0):,.0f}")

    a1, a2 = st.columns([1.3, 1])
    with a1:
        if st.button("Salvar alterações", key=f"edit_salvar_{eq_id}", use_container_width=True, type="primary"):
            equipamentos_service.atualizar_inline(
                eq_id,
                nome=nome_edit.strip() or equipamento.get("nome"),
                tipo=tipo_edit,
                setor_id=setor_ids[setor_idx],
                ativo=ativo_edit,
                km_inicial_plano=km_inicial_edit,
                horas_inicial_plano=horas_inicial_edit,
            )
            equipamentos_service.definir_responsavel_principal(eq_id, resp_ids[resp_idx] or None)
            _carregar_equipamento.clear()
            _revisoes_eq.clear()
            _lubrificacoes_eq.clear()
            _timeline_eq.clear()
            equipamentos_service.limpar_cache()
            st.success("Equipamento atualizado.")
            st.rerun()
    with a2:
        if st.button("Fechar ficha", key=f"fechar_ficha_{eq_id}", use_container_width=True):
            st.session_state.pop("eq_modal_id", None)
            st.session_state.pop("eq_modal_row", None)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_ficha_conteudo(eq_id: str, setor_map: dict, responsavel_map: dict):
    snap = st.session_state.get("eq_modal_row") or {}
    equipamento = _carregar_equipamento(eq_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    codigo = equipamento.get("codigo") or snap.get("codigo") or "-"
    nome = equipamento.get("nome") or snap.get("nome") or "-"
    setor_nome = equipamento.get("setor_nome") or snap.get("setor_nome") or "-"
    tipo = equipamento.get("tipo") or snap.get("tipo") or "-"
    ativo = "Ativo" if equipamento.get("ativo", snap.get("ativo")) else "Inativo"
    saude = equipamento.get("saude") or snap.get("saude") or "Sem plano"
    score = int(equipamento.get("score_saude", snap.get("score_saude", 0)) or 0)
    venc = int(snap.get("vencidos", 0) or 0)
    prox = int(snap.get("proximos", 0) or 0)
    total_rev = int(snap.get("revisoes", snap.get("total_revisoes", 0)) or 0)
    total_lub = int(snap.get("lubrificacoes", snap.get("total_lubrificacoes", 0)) or 0)

    st.markdown(
        f'<div class="eq-modal-head"><div>'
        f'<div class="eq-modal-title">{codigo} — {nome}</div>'
        f'<p class="eq-modal-sub">{setor_nome} · {tipo} · {ativo}</p>'
        f'</div><div>{_score_ring(score)}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="eq-card-badges">' + _badge(saude) + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="eq-modal-metrics">', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _render_metric_mini("Vencidos", venc)
    with m2:
        _render_metric_mini("Próximos", prox)
    with m3:
        _render_metric_mini("Revisões", total_rev)
    with m4:
        _render_metric_mini("Lubrificações", total_lub)
    st.markdown("</div>", unsafe_allow_html=True)

    sec_key = f"eq_section_{eq_id}"
    if sec_key not in st.session_state:
        st.session_state[sec_key] = "Resumo"

    st.markdown('<div class="eq-modal-shell">', unsafe_allow_html=True)
    secao = st.radio(
        "Seção",
        ["Resumo", "Revisões", "Lubrificações", "Histórico", "Configurações"],
        key=sec_key,
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown('<div class="eq-section">', unsafe_allow_html=True)
    if secao == "Resumo":
        _render_resumo_section(eq_id, equipamento, snap)
    elif secao == "Revisões":
        _render_revisoes_section(eq_id)
    elif secao == "Lubrificações":
        _render_lubrificacoes_section(eq_id)
    elif secao == "Histórico":
        _render_historico_section(eq_id)
    else:
        _render_config_section(eq_id, equipamento, setor_map, responsavel_map)
    st.markdown("</div></div>", unsafe_allow_html=True)


@st.dialog("Ficha do equipamento", width="large")
def _render_detalhe(setor_map: dict, responsavel_map: dict):
    eq_id = st.session_state.get("eq_modal_id")
    if not eq_id:
        return
    _render_ficha_conteudo(eq_id, setor_map, responsavel_map)


def render():
    _inject_css()

    h_left, h_right = st.columns([5, 1])
    with h_left:
        render_page_intro(
            "Equipamentos",
            "Cadastre, pesquise e gerencie a frota.",
            "Cadastros",
        )
    with h_right:
        st.write("")
        if st.button("↺ Atualizar", use_container_width=True):
            equipamentos_service.limpar_cache()
            _carregar_equipamento.clear()
            _revisoes_eq.clear()
            _lubrificacoes_eq.clear()
            _timeline_eq.clear()
            st.rerun()

    rows = equipamentos_service.carregar_snapshot_equipamentos()

    if not rows:
        st.info("Nenhum equipamento cadastrado.")
        return

    setores_disp = sorted({r.get("setor_nome") or "-" for r in rows})
    tipos_disp = ["Todos"] + list(TIPOS_EQUIPAMENTO)

    f1, f2, f3, f4, f5 = st.columns([2.5, 1.5, 1.2, 1.2, 1.1], gap="small")
    with f1:
        termo = st.text_input("Buscar", placeholder="Código, nome, setor ou responsável", label_visibility="collapsed")
    with f2:
        setores_filtro = st.multiselect("Setor", setores_disp, placeholder="Setor", label_visibility="collapsed")
    with f3:
        status_filtro = st.selectbox("Status", ["Todos", "Ativos", "Inativos"], label_visibility="collapsed")
    with f4:
        tipo_filtro = st.selectbox("Tipo", tipos_disp, label_visibility="collapsed")
    with f5:
        saude_filtro = st.selectbox(
            "Saúde", ["Todas", "Crítico", "Atenção", "Saudável", "Sem plano"], label_visibility="collapsed"
        )

    filtrados = _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro)
    _render_summary(filtrados)

    bar1, bar2, bar3 = st.columns([3, 1, 1.2], gap="small")
    with bar1:
        st.caption(f"{len(filtrados)} equipamento(s)")
    with bar2:
        page_size = st.selectbox("Itens/pág", [8, 12, 20, 30], index=1, label_visibility="collapsed")
    with bar3:
        export_df = _build_export_df(filtrados)
        st.download_button(
            "⬇ CSV",
            data=_csv_bytes(export_df),
            file_name="equipamentos_filtrados.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not filtrados:
        st.info("Nenhum equipamento encontrado para os filtros selecionados.")
        return

    total_pages = max(1, math.ceil(len(filtrados) / page_size))
    if total_pages > 1:
        nav1, _ = st.columns([1, 5])
        with nav1:
            page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
    else:
        page = 1

    setor_map = _setor_options()
    resp_map = _responsavel_options()

    for row in _slice(filtrados, int(page), int(page_size)):
        st.markdown('<div class="eq-card">', unsafe_allow_html=True)
        _render_card(row)
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("eq_modal_id"):
        _render_detalhe(setor_map, resp_map)
