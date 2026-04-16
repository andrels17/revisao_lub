from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from services import dashboard_service, inteligencia_service, prioridades_service
from ui.theme import render_page_intro


def _css() -> None:
    st.markdown("""
    <style>
    .exec-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.7rem; margin-bottom:.85rem;}
    .exec-kpi {border:1px solid rgba(148,163,184,.12); border-radius:16px; padding:.9rem 1rem; background:#0d1929;}
    .exec-kpi .lbl {font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; color:#8fa4c0; font-weight:800;}
    .exec-kpi .val {font-size:2rem; font-weight:900; color:#f8fbff; margin:.22rem 0 .14rem; line-height:1;}
    .exec-kpi .sub {font-size:.74rem; color:#8fa4c0;}
    .exec-kpi.crit .val {color:#fca5a5;}
    .exec-kpi.alt .val {color:#fde68a;}
    .exec-kpi.ok .val {color:#86efac;}
    .exec-kpi.info .val {color:#93c5fd;}
    .exec-card {border:1px solid rgba(148,163,184,.12); border-radius:16px; padding:.9rem 1rem; background:#0d1929; margin-bottom:.8rem;}
    .exec-title {font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; color:#8fa4c0; font-weight:800; margin-bottom:.65rem;}
    .exec-alert {border:1px solid rgba(148,163,184,.10); border-radius:14px; padding:.75rem .8rem; background:rgba(15,23,42,.58); margin-bottom:.55rem;}
    .exec-alert-top {display:flex; justify-content:space-between; gap:.7rem; align-items:flex-start;}
    .exec-alert h4 {margin:0; font-size:.92rem; color:#eff6ff;}
    .exec-alert p {margin:.16rem 0 0; font-size:.76rem; color:#8fa4c0;}
    .exec-pill {display:inline-flex; padding:.14rem .48rem; border-radius:999px; font-size:.66rem; font-weight:800; border:1px solid rgba(255,255,255,.07);}
    .exec-pill.crit {background:rgba(239,68,68,.12); color:#fecaca;}
    .exec-pill.alt {background:rgba(245,158,11,.12); color:#fde68a;}
    .exec-pill.med {background:rgba(96,165,250,.12); color:#bfdbfe;}
    .exec-chip-row {display:flex; flex-wrap:wrap; gap:.32rem; margin-top:.45rem;}
    .exec-chip {display:inline-flex; padding:.12rem .42rem; border-radius:999px; font-size:.66rem; font-weight:700; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); color:#dbeafe;}
    @media (max-width: 960px) {.exec-grid {grid-template-columns:repeat(2,minmax(0,1fr));}}
    </style>
    """, unsafe_allow_html=True)


def _kpi(label: str, valor: str, subtitulo: str, css: str = "") -> None:
    st.markdown(
        f"<div class='exec-kpi {css}'><div class='lbl'>{html.escape(label)}</div><div class='val'>{valor}</div><div class='sub'>{html.escape(subtitulo)}</div></div>",
        unsafe_allow_html=True,
    )


def _pill_css(criticidade: str) -> str:
    return {"Crítica": "crit", "Alta": "alt", "Média": "med"}.get(criticidade, "")


def render():
    _css()

    top1, top2 = st.columns([5, 1])
    with top1:
        render_page_intro(
            "Painel Executivo",
            "Visão consolidada para diretoria: risco, exposição por setor, equipamentos parados e ações prioritárias.",
            chip="Diretoria",
        )
    with top2:
        st.write("")
        if st.button("Atualizar", use_container_width=True):
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

    k = dados.get("kpis", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi("Alertas críticos", str(int(k.get("criticos", 0))), "Itens que exigem ação imediata", "crit")
    with c2:
        _kpi("Alertas altos", str(int(k.get("altos", 0))), "Acompanhar ainda hoje", "alt")
    with c3:
        _kpi("Equipamentos parados", str(int(k.get("parados", 0))), "Sem leitura dentro da janela", "info")
    with c4:
        _kpi("Cobertura operacional", f"{k.get('cobertura', 0):.1f}%", "Equipamentos sem alerta ativo", "ok")

    col_a, col_b = st.columns([1.25, 1], gap="medium")
    with col_a:
        st.markdown("<div class='exec-card'><div class='exec-title'>Top alertas executivos</div>", unsafe_allow_html=True)
        top_alertas = dados.get("top_alertas") or []
        if not top_alertas:
            st.info("Nenhum alerta executivo no momento.")
        else:
            for item in top_alertas[:6]:
                criticidade = item.get("Criticidade") or "-"
                st.markdown(
                    f"<div class='exec-alert'><div class='exec-alert-top'><div><h4>{html.escape(str(item.get('Equipamento') or '-'))}</h4><p>{html.escape(str(item.get('Resumo') or '-'))}</p></div><span class='exec-pill {_pill_css(str(criticidade))}'>{html.escape(str(criticidade))}</span></div><div class='exec-chip-row'><span class='exec-chip'>{html.escape(str(item.get('Setor') or '-'))}</span><span class='exec-chip'>{html.escape(str(item.get('Origem') or '-'))}</span><span class='exec-chip'>{html.escape(str(item.get('Status') or '-'))}</span><span class='exec-chip'>{html.escape(str(item.get('Ação sugerida') or '-'))}</span></div></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown("<div class='exec-card'><div class='exec-title'>Exposição por setor</div>", unsafe_allow_html=True)
        df_setor = pd.DataFrame(dados.get("exposicao_setores") or [])
        if df_setor.empty:
            st.info("Nenhum setor com exposição relevante.")
        else:
            st.dataframe(df_setor, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='exec-card'><div class='exec-title'>Categorias de risco</div>", unsafe_allow_html=True)
        df_cat = pd.DataFrame(dados.get("categorias") or [])
        if df_cat.empty:
            st.info("Sem categorias para exibir.")
        else:
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    col_c, col_d = st.columns(2, gap="medium")
    with col_c:
        st.markdown("<div class='exec-card'><div class='exec-title'>Ranking de movimentação</div>", unsafe_allow_html=True)
        df_mov = pd.DataFrame(dados.get("ranking_movimentacao") or [])
        if df_mov.empty:
            st.info("Sem movimentação suficiente para ranking.")
        else:
            st.dataframe(df_mov, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_d:
        st.markdown("<div class='exec-card'><div class='exec-title'>Equipamentos parados</div>", unsafe_allow_html=True)
        df_par = pd.DataFrame(dados.get("parados") or [])
        if df_par.empty:
            st.success("Nenhum equipamento parado acima da janela configurada.")
        else:
            st.dataframe(df_par, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='exec-card'><div class='exec-title'>Plano de ação sugerido</div>", unsafe_allow_html=True)
    plano = pd.DataFrame(dados.get("plano_acao") or [])
    if plano.empty:
        st.info("Sem plano de ação no momento.")
    else:
        st.dataframe(plano, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
