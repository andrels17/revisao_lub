from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from services import cache_service, prioridades_service
from ui import nav
from ui.exportacao import botao_exportar_excel
from ui.theme import pill_html, render_hero, render_kpi_grid


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Hero, KPI grid e badges agora vêm de ui/theme.py
           (render_hero / render_kpi_grid / pill_html). */

        .prio-filters, .prio-section {
            border:1px solid rgba(148,163,184,.12);
            border-radius:14px; background:#0d1929;
            padding:.85rem .95rem; margin-bottom:.75rem;
        }
        .prio-section-title { font-size:.78rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:#8fa4c0; margin-bottom:.6rem; }

        .prio-card {
            border:1px solid rgba(148,163,184,.12);
            border-radius:14px;
            background:rgba(15,23,42,.7);
            padding:.85rem .95rem; margin-bottom:.55rem;
        }
        .prio-card.vencido { border-left:4px solid #ef4444; }
        .prio-card.proximo { border-left:4px solid #f59e0b; }
        .prio-card.sem_leitura { border-left:4px solid #60a5fa; }
        .prio-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.75rem; }
        .prio-title { font-size:.95rem; font-weight:800; color:#eff6ff; }
        .prio-sub { font-size:.77rem; color:#8fa4c0; margin-top:.15rem; }
        .prio-badges { display:flex; flex-wrap:wrap; gap:.28rem; margin-top:.5rem; }
        .prio-table-note { font-size:.74rem; color:#8fa4c0; margin-top:.35rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


_TONE_POR_SIGLA = {"danger": "danger", "warn": "warning", "info": "info", "ok": "success", "": "neutral"}


def _status_css(status: str) -> str:
    return {
        "VENCIDO": "danger",
        "PROXIMO": "warn",
        "SEM_LEITURA": "info",
        "EM DIA": "ok",
    }.get(status, "")


def _status_label(status: str) -> str:
    return {
        "VENCIDO": "Vencido",
        "PROXIMO": "Próximo",
        "SEM_LEITURA": "Sem leitura",
        "EM DIA": "Em dia",
    }.get(status, status.title())


def _destino_label(destino: str) -> str:
    return {
        "revisoes": "🔧 Controle de Revisões",
        "lubrificacoes": "🛢️ Controle de Lubrificações",
        "leituras": "📏 Leituras KM / Horas",
        "equipamentos": "🚜 Equipamentos",
    }.get(destino, "🧭 Painel Operacional")


def _ir_para_destino(item: dict) -> None:
    destino = item.get("destino")
    equipamento_label = item.get("equipamento_label")
    codigo = item.get("codigo") or ""
    if destino == "revisoes":
        nav.ir_para(
            "🔧 Controle de Revisões",
            rev_eqp=[equipamento_label],
            rev_status="Todos",
        )
    elif destino == "lubrificacoes":
        nav.ir_para(
            "🛢️ Controle de Lubrificações",
            lub_eqp=[equipamento_label],
            lub_status="Todos",
        )
    elif destino == "leituras":
        nav.ir_para("📏 Leituras KM / Horas")
    else:
        nav.ir_para("🚜 Equipamentos", eq_busca=codigo)


def _render_card(item: dict, idx: int) -> None:
    status = str(item.get("status") or "")
    css = status.lower()
    st.markdown(f"<div class='prio-card {css}'>", unsafe_allow_html=True)
    top1, top2 = st.columns([5, 1.2], vertical_alignment="top")
    with top1:
        st.markdown(
            f"<div class='prio-top'><div><div class='prio-title'>{html.escape(str(item.get('titulo') or '-'))}</div>"
            f"<div class='prio-sub'>{html.escape(str(item.get('descricao') or '-'))}</div></div></div>",
            unsafe_allow_html=True,
        )
        badges = [
            (item.get("origem") or "-", ""),
            (_status_label(status), _status_css(status)),
            (item.get("setor_nome") or "-", ""),
        ]
        unidade = item.get("unidade") or ""
        if status == "VENCIDO":
            badges.append((f"Atraso: {float(item.get('atraso', 0)):.0f} {unidade}", "danger"))
        elif status == "PROXIMO":
            badges.append((f"Falta: {max(float(item.get('falta', 0)), 0):.0f} {unidade}", "warn"))
        elif status == "SEM_LEITURA":
            badges.append((f"{int(float(item.get('dias_sem_leitura', 0)))} dia(s)", "info"))
        badges_html = "".join(
            pill_html(txt, _TONE_POR_SIGLA.get(cls, "neutral")) for txt, cls in badges
        )
        st.markdown(f"<div class='prio-badges'>{badges_html}</div>", unsafe_allow_html=True)
    with top2:
        if st.button("Abrir", key=f"prio_open_{idx}", use_container_width=True):
            _ir_para_destino(item)
        st.caption(_destino_label(item.get("destino") or ""))
    st.markdown("</div>", unsafe_allow_html=True)


def _filtrar_itens(itens: list[dict], setor_f: list[str], eqp_f: list[str], origem_f: str, status_f: str) -> list[dict]:
    filtrados = itens
    if setor_f:
        filtrados = [i for i in filtrados if (i.get("setor_nome") or "-") in setor_f]
    if eqp_f:
        filtrados = [i for i in filtrados if (i.get("equipamento_label") or "-") in eqp_f]
    if origem_f != "Todos":
        filtrados = [i for i in filtrados if i.get("origem") == origem_f]
    if status_f != "Todos":
        filtrados = [i for i in filtrados if i.get("status") == status_f]
    return filtrados


def _build_export_df(itens: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Equipamento": item.get("equipamento_label"),
            "Setor": item.get("setor_nome"),
            "Origem": item.get("origem"),
            "Item": item.get("subtipo"),
            "Status": _status_label(item.get("status") or ""),
            "Descrição": item.get("descricao"),
            "Atual": item.get("atual"),
            "Vencimento": item.get("vencimento"),
            "Falta": item.get("falta"),
            "Atraso": item.get("atraso"),
            "Unidade": item.get("unidade"),
            "Destino": _destino_label(item.get("destino") or ""),
        }
        for item in itens
    ])


def render() -> None:
    _inject_css()

    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        render_hero(
            "Prioridades do dia",
            "Veja o que precisa de ação imediata, acompanhe equipamentos críticos e abra o fluxo certo com um clique.",
            badge="🔥 Operação diária",
        )
    with right:
        st.write("")
        if st.button("↺ Atualizar", use_container_width=True):
            cache_service.invalidate_planejamento()
            prioridades_service.limpar_cache()
            st.rerun()

    payload = prioridades_service.carregar_prioridades()
    itens = payload.get("itens") or []
    resumo = payload.get("resumo") or {}
    if not itens:
        st.success("Nenhuma prioridade aberta no momento.")
        return

    render_kpi_grid([
        {"label": "Pendências abertas", "value": int(resumo.get("total_pendencias", 0)), "hint": "Tudo que pede ação hoje", "tone": "danger"},
        {"label": "Equipamentos críticos", "value": int(resumo.get("equipamentos_criticos", 0)), "hint": "Com atraso ou sem leitura", "tone": "warning"},
        {"label": "Vencidos", "value": int(resumo.get("vencidos", 0)), "hint": "Ações urgentes", "tone": "danger"},
        {"label": "Sem leitura recente", "value": int(resumo.get("sem_leitura", 0)), "hint": "Acima da janela de 7 dias", "tone": "neutral"},
    ])

    filtros = prioridades_service.listar_opcoes_filtro()
    st.markdown("<div class='prio-filters'><div class='prio-section-title'>Filtros operacionais</div>", unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.4, 1.8, 1.2, 1.2])
    with f1:
        setor_f = st.multiselect("Setor", filtros.get("setores") or [], key="prio_setor")
    with f2:
        eqp_f = st.multiselect("Equipamento", filtros.get("equipamentos") or [], key="prio_eqp")
    with f3:
        origem_f = st.selectbox("Origem", filtros.get("origens") or ["Todos"], key="prio_origem")
    with f4:
        status_f = st.selectbox("Status", filtros.get("status") or ["Todos"], key="prio_status")
    st.markdown("</div>", unsafe_allow_html=True)

    filtrados = _filtrar_itens(itens, setor_f, eqp_f, origem_f, status_f)

    sec1, sec2 = st.tabs([f"Fila operacional ({len(filtrados)})", "Rankings e apoio à gestão"])

    with sec1:
        topbar1, topbar2 = st.columns([4, 1.2])
        with topbar1:
            st.caption(
                f"{len(filtrados)} item(ns) após filtros · Revisões {int(resumo.get('rev', 0))} · "
                f"Lubrificações {int(resumo.get('lub', 0))} · Leituras {int(resumo.get('leitura', 0))}"
            )
        with topbar2:
            export_df = _build_export_df(filtrados)
            if not export_df.empty:
                botao_exportar_excel(export_df, "prioridades_do_dia.xlsx", label="⬇ Excel")

        if not filtrados:
            st.info("Nenhuma prioridade encontrada para os filtros selecionados.")
        else:
            for idx, item in enumerate(filtrados[:80]):
                _render_card(item, idx)
            if len(filtrados) > 80:
                st.caption(f"Mostrando 80 de {len(filtrados)} prioridades para manter a leitura rápida.")

            tabela = export_df.copy()
            if not tabela.empty:
                st.markdown("<div class='prio-section'><div class='prio-section-title'>Tabela rápida</div>", unsafe_allow_html=True)
                st.dataframe(tabela, use_container_width=True, hide_index=True)
                st.markdown("<div class='prio-table-note'>Use os botões Abrir nos cards para cair direto no fluxo operacional correto.</div></div>", unsafe_allow_html=True)

    with sec2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='prio-section'><div class='prio-section-title'>Setores mais pressionados</div>", unsafe_allow_html=True)
            ranking_setores = pd.DataFrame(payload.get("ranking_setores") or [])
            if ranking_setores.empty:
                st.caption("Sem dados.")
            else:
                st.dataframe(ranking_setores, use_container_width=True, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='prio-section'><div class='prio-section-title'>Top 10 equipamentos críticos</div>", unsafe_allow_html=True)
            ranking_eq = pd.DataFrame(payload.get("ranking_equipamentos") or [])
            if ranking_eq.empty:
                st.caption("Sem dados.")
            else:
                st.dataframe(ranking_eq, use_container_width=True, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='prio-section'><div class='prio-section-title'>Equipamentos sem leitura recente</div>", unsafe_allow_html=True)
        sem_leitura = pd.DataFrame([
            {
                "Equipamento": item.get("equipamento_label"),
                "Setor": item.get("setor_nome"),
                "Dias sem leitura": int(float(item.get("dias_sem_leitura", 0))),
                "Descrição": item.get("descricao"),
            }
            for item in payload.get("sem_leitura") or []
        ])
        if sem_leitura.empty:
            st.caption("Sem pendências de leitura.")
        else:
            st.dataframe(sem_leitura, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
