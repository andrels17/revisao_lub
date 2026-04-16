from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from services import dashboard_service, inteligencia_service
from ui.exportacao import botao_exportar_excel
from utils.formatters import format_decimal_br, format_int_br


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .exec-hero, .exec-section {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 16px;
            background: #0d1929;
            padding: .95rem 1rem;
            margin-bottom: .8rem;
        }
        .exec-hero .chip {
            display:inline-flex; align-items:center; gap:.35rem;
            padding:.18rem .55rem; border-radius:999px;
            background:rgba(168,85,247,.10); color:#e9d5ff;
            border:1px solid rgba(168,85,247,.20);
            font-size:.68rem; font-weight:700; margin-bottom:.45rem;
        }
        .exec-hero h2 { margin:0; font-size:1.08rem; font-weight:800; }
        .exec-hero p { margin:.22rem 0 0; color:#8fa4c0; font-size:.83rem; }
        .exec-kpis { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin-bottom:.8rem; }
        .exec-kpi {
            border:1px solid rgba(148,163,184,.12); border-radius:14px; padding:.9rem .95rem;
            background:linear-gradient(180deg, rgba(16,31,52,.96), rgba(11,24,40,.98));
        }
        .exec-kpi .lbl { font-size:.72rem; color:#8fa4c0; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
        .exec-kpi .val { font-size:1.95rem; font-weight:800; color:#f8fbff; line-height:1.02; margin:.22rem 0; }
        .exec-kpi .sub { font-size:.74rem; color:#89a2bd; }
        .exec-kpi.crit .val { color:#fca5a5; }
        .exec-kpi.warn .val { color:#fde68a; }
        .exec-kpi.info .val { color:#93c5fd; }
        .exec-kpi.ok .val { color:#86efac; }
        .exec-section-title { font-size:.78rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; color:#8fa4c0; margin-bottom:.65rem; }
        .exec-list { display:flex; flex-direction:column; gap:.55rem; }
        .exec-item {
            border:1px solid rgba(148,163,184,.12); border-radius:14px; padding:.85rem .9rem;
            background:rgba(15,23,42,.66);
        }
        .exec-item.critico { border-left:4px solid #ef4444; }
        .exec-item.alto { border-left:4px solid #f59e0b; }
        .exec-item.medio { border-left:4px solid #60a5fa; }
        .exec-item.baixo { border-left:4px solid #22c55e; }
        .exec-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.8rem; }
        .exec-title { font-size:.95rem; font-weight:800; color:#eff6ff; }
        .exec-sub { font-size:.77rem; color:#8fa4c0; margin-top:.18rem; }
        .exec-badges { display:flex; flex-wrap:wrap; gap:.28rem; margin-top:.45rem; }
        .exec-badge {
            display:inline-flex; align-items:center; gap:.3rem; border-radius:999px; padding:.14rem .48rem;
            font-size:.68rem; font-weight:700; border:1px solid rgba(255,255,255,.06); background:rgba(255,255,255,.04); color:#dbeafe;
        }
        .exec-badge.critico { background:rgba(239,68,68,.10); color:#fecaca; }
        .exec-badge.alto { background:rgba(245,158,11,.10); color:#fde68a; }
        .exec-badge.medio { background:rgba(96,165,250,.10); color:#bfdbfe; }
        .exec-badge.baixo { background:rgba(34,197,94,.10); color:#bbf7d0; }
        @media (max-width: 900px) {
            .exec-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fmt_data(value):
    if not value:
        return "-"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _kpi(label: str, valor: int | str, subtitulo: str, css: str = "") -> None:
    st.markdown(
        f"<div class='exec-kpi {css}'><div class='lbl'>{html.escape(label)}</div>"
        f"<div class='val'>{valor}</div><div class='sub'>{html.escape(subtitulo)}</div></div>",
        unsafe_allow_html=True,
    )


def _render_alerta(item: dict, idx: int) -> None:
    sev = str(item.get("severidade") or "medio")
    badges = [
        (item.get("origem") or "-", ""),
        (str(item.get("setor") or "-"), ""),
        (str(item.get("status") or "-").title(), sev),
    ]
    badges_html = "".join(
        f"<span class='exec-badge {cls}'>{html.escape(str(txt))}</span>" for txt, cls in badges
    )
    st.markdown(f"<div class='exec-item {sev}'>", unsafe_allow_html=True)
    c1, c2 = st.columns([4.4, 1.6], vertical_alignment="top")
    with c1:
        st.markdown(
            f"<div class='exec-top'><div><div class='exec-title'>{html.escape(str(item.get('titulo') or '-'))}</div>"
            f"<div class='exec-sub'>{html.escape(str(item.get('descricao') or '-'))}</div></div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='exec-badges'>{badges_html}</div>", unsafe_allow_html=True)
    with c2:
        st.caption("Ação recomendada")
        st.write(item.get("acao") or "-")
    st.markdown("</div>", unsafe_allow_html=True)


def render() -> None:
    _inject_css()

    h1, h2 = st.columns([5, 1])
    with h1:
        st.title("Painel Executivo")
    with h2:
        st.write("")
        if st.button("Atualizar", help="Recarrega dados e inteligência"):
            dashboard_service.carregar_alertas.clear()
            dashboard_service.carregar_movimentacao.clear()
            inteligencia_service.gerar_alertas_inteligentes.clear()
            st.rerun()

    dados = inteligencia_service.gerar_alertas_inteligentes()
    resumo = dados.get("resumo") or {}
    movimentacao = dados.get("movimentacao") or {}
    kpis_mov = movimentacao.get("kpis") or {}

    st.markdown(
        f"<div class='exec-hero'><div class='chip'>Diretoria · visão consolidada</div>"
        f"<h2>Risco operacional concentrado em {html.escape(str(resumo.get('setor_mais_exposto') or '-'))}</h2>"
        f"<p>{format_int_br(resumo.get('criticos', 0))} alertas críticos, {format_int_br(resumo.get('altos', 0))} alertas altos e {format_int_br(resumo.get('equipamentos_parados', 0))} equipamentos sem movimentação relevante.</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='exec-kpis'>", unsafe_allow_html=True)
    _kpi("Alertas críticos", format_int_br(resumo.get("criticos", 0)), "Exigem ação imediata", "crit")
    _kpi("Alertas altos", format_int_br(resumo.get("altos", 0)), "Priorizar no curto prazo", "warn")
    _kpi("Equipamentos parados", format_int_br(resumo.get("equipamentos_parados", 0)), "Sem leitura recente", "info")
    _kpi("Base monitorada", format_int_br(resumo.get("total_equipamentos", 0)), "Equipamentos acompanhados", "ok")
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1], gap="medium")
    with c1:
        st.markdown("<div class='exec-section'><div class='exec-section-title'>Top alertas executivos</div>", unsafe_allow_html=True)
        itens = dados.get("itens") or []
        if not itens:
            st.success("Nenhum alerta inteligente ativo no momento.")
        else:
            for idx, item in enumerate(itens[:8]):
                _render_alerta(item, idx)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='exec-section'><div class='exec-section-title'>Exposição por setor</div>", unsafe_allow_html=True)
        df_setores = pd.DataFrame(dados.get("setores") or [])
        if df_setores.empty:
            st.info("Sem exposição consolidada para exibir.")
        else:
            st.dataframe(df_setores.head(12), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='exec-section'><div class='exec-section-title'>Categorias de risco</div>", unsafe_allow_html=True)
        df_cat = pd.DataFrame(dados.get("categorias") or [])
        if df_cat.empty:
            st.info("Sem categorias ativas.")
        else:
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    c3, c4 = st.columns(2, gap="medium")
    with c3:
        st.markdown("<div class='exec-section'><div class='exec-section-title'>Ranking de movimentação</div>", unsafe_allow_html=True)
        df_rank = pd.DataFrame(movimentacao.get("ranking_rodados") or [])
        if df_rank.empty:
            st.info("Sem leituras recentes para compor o ranking.")
        else:
            if "Última leitura" in df_rank.columns:
                df_rank["Última leitura"] = df_rank["Última leitura"].apply(_fmt_data)
            st.dataframe(df_rank.head(10), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown("<div class='exec-section'><div class='exec-section-title'>Parados / sem leitura</div>", unsafe_allow_html=True)
        df_parados = pd.DataFrame(movimentacao.get("alertas_parados") or [])
        if df_parados.empty:
            st.success("Nenhum equipamento parado dentro do critério atual.")
        else:
            if "Última leitura" in df_parados.columns:
                df_parados["Última leitura"] = df_parados["Última leitura"].apply(_fmt_data)
            st.dataframe(df_parados.head(10), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='exec-section'>", unsafe_allow_html=True)
    t1, t2, t3 = st.columns([2, 2, 1], gap="small")
    with t1:
        st.markdown("<div class='exec-section-title'>Plano de ação sugerido</div>", unsafe_allow_html=True)
        df_acoes = pd.DataFrame(dados.get("recomendacoes") or [])
        if df_acoes.empty:
            st.info("Sem recomendações geradas.")
        else:
            st.dataframe(df_acoes, use_container_width=True, hide_index=True)
    with t2:
        st.markdown("<div class='exec-section-title'>Inteligência de leituras</div>", unsafe_allow_html=True)
        anom = movimentacao.get("anomalias") or {}
        resumo_anom = pd.DataFrame([
            {"Indicador": "Leituras travadas", "Ocorrências": len(anom.get("travadas") or [])},
            {"Indicador": "Saltos anormais", "Ocorrências": len(anom.get("saltos") or [])},
            {"Indicador": "Inconsistências KM/H", "Ocorrências": len(anom.get("inconsistencias") or [])},
            {"Indicador": "Leituras na janela", "Ocorrências": int(kpis_mov.get("leituras_na_janela") or 0)},
        ])
        st.dataframe(resumo_anom, use_container_width=True, hide_index=True)
    with t3:
        botao_exportar_excel(pd.DataFrame(dados.get("itens") or []), "painel_executivo_alertas", label="⬇ Excel", key="exp_exec")
        st.caption(f"Janela analisada: {format_int_br(kpis_mov.get('janela_dias', 0))} dias")
        st.caption(f"Critério parado: {format_int_br(kpis_mov.get('threshold_parado', 0))} dias")
    st.markdown("</div>", unsafe_allow_html=True)
