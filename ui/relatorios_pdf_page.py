"""
Página de Relatórios PDF — Usina Monte Alegre
Oferece 4 tipos de relatório PDF prontos para impressão:
  1. Histórico de Lubrificações por Equipamento
  2. Conformidade de Revisões Predefinidas
  3. Relatório Executivo de Frota
  4. Ficha Técnica do Equipamento
"""
from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from database.connection import get_conn, release_conn
from services import (
    dashboard_service,
    equipamentos_service,
    inteligencia_service,
    relatorio_pdf_service,
)
from ui.relatorio_page import (
    _carregar_revisoes as _rel_revisoes,
    _carregar_lubrificacoes as _rel_lubrificacoes,
)
from ui.theme import render_page_intro

try:
    import psycopg2
except Exception:
    psycopg2 = None


# ── helpers de dados ─────────────────────────────────────────────────────────

def _carregar_setores() -> list[tuple]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome FROM setores WHERE ativo = true ORDER BY nome")
        return cur.fetchall()
    finally:
        release_conn(conn)


def _carregar_equipamentos(setor_id=None) -> list[tuple]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if setor_id:
            cur.execute(
                """SELECT id, codigo, nome, setor_id,
                          (SELECT nome FROM setores s WHERE s.id = e.setor_id) AS setor_nome
                   FROM equipamentos e
                   WHERE ativo = true AND setor_id = %s ORDER BY codigo""",
                (setor_id,),
            )
        else:
            cur.execute(
                """SELECT id, codigo, nome, setor_id,
                          (SELECT nome FROM setores s WHERE s.id = e.setor_id) AS setor_nome
                   FROM equipamentos e
                   WHERE ativo = true ORDER BY codigo"""
            )
        return cur.fetchall()
    finally:
        release_conn(conn)


def _carregar_revisoes_periodo(data_ini, data_fim, setor_id=None, eqp_id=None):
    """Wrapper sobre a função já existente em relatorio_page (com tratamento de UndefinedTable)."""
    try:
        import pandas as pd
        df = _rel_revisoes(data_ini, data_fim, setor_id, eqp_id)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return __import__("pandas").DataFrame()


def _carregar_lubrificacoes_periodo(data_ini, data_fim, setor_id=None, eqp_id=None):
    """Wrapper sobre a função já existente em relatorio_page (com tratamento de UndefinedTable)."""
    try:
        import pandas as pd
        df = _rel_lubrificacoes(data_ini, data_fim, setor_id, eqp_id)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return __import__("pandas").DataFrame()


def _carregar_historico_equipamento(eqp_id, limite=20) -> tuple[list[dict], list[dict]]:
    """Retorna (historico_revisoes, historico_lubrificacoes) para a ficha técnica."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT em.data_execucao, COALESCE(em.status, 'concluida'),
                      em.km_execucao, em.horas_execucao,
                      COALESCE(r.nome, '-'), em.observacoes
               FROM execucoes_manutencao em
               LEFT JOIN responsaveis r ON r.id = em.responsavel_id
               WHERE em.equipamento_id = %s AND em.tipo = 'revisao'
               ORDER BY em.data_execucao DESC LIMIT %s""",
            (eqp_id, limite),
        )
        revisoes = [
            {"Data": r[0], "Status": r[1], "KM": r[2], "Horas": r[3],
             "Responsável": r[4], "Observações": r[5]}
            for r in cur.fetchall()
        ]
        try:
            cur.execute(
                """SELECT el.data_execucao, el.nome_item,
                          COALESCE(el.tipo_produto, '-'),
                          el.km_execucao, el.horas_execucao,
                          COALESCE(r.nome, '-')
                   FROM execucoes_lubrificacao el
                   LEFT JOIN responsaveis r ON r.id = el.responsavel_id
                   WHERE el.equipamento_id = %s
                   ORDER BY el.data_execucao DESC LIMIT %s""",
                (eqp_id, limite),
            )
            lubrificacoes = [
                {"Data": r[0], "Item": r[1], "Produto": r[2],
                 "KM": r[3], "Horas": r[4], "Responsável": r[5]}
                for r in cur.fetchall()
            ]
        except Exception:
            conn.rollback()
            lubrificacoes = []
        return revisoes, lubrificacoes
    finally:
        release_conn(conn)


def _ultima_leitura_equipamento(eqp_id) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT l.data_leitura, l.km_valor, l.horas_valor,
                      COALESCE(r.nome, '-') AS responsavel
               FROM leituras l
               LEFT JOIN responsaveis r ON r.id = l.responsavel_id
               WHERE l.equipamento_id = %s
               ORDER BY l.data_leitura DESC LIMIT 1""",
            (eqp_id,),
        )
        row = cur.fetchone()
        if row:
            return {"data_leitura": row[0], "km_valor": row[1], "horas_valor": row[2], "responsavel": row[3]}
        return None
    finally:
        release_conn(conn)


def _status_revisoes_equipamento(eqp_id) -> list[dict]:
    """Retorna status atual de cada etapa de revisão do equipamento."""
    from services import revisoes_service
    try:
        itens = revisoes_service.listar_controle_revisoes_por_equipamento().get(eqp_id, [])
        return [
            {
                "etapa": i.get("etapa", "-"),
                "tipo_controle": i.get("tipo_controle", "km"),
                "atual": float(i.get("atual", 0) or 0),
                "vencimento": float(i.get("vencimento", 0) or 0),
                "diferenca": float(i.get("diferenca", 0) or 0),
                "status": i.get("status", "EM_DIA"),
                "unidade": "h" if str(i.get("tipo_controle", "km")).lower().startswith("h") else "km",
            }
            for i in itens
        ]
    except Exception:
        return []


def _status_lubrificacoes_equipamento(eqp_id) -> list[dict]:
    """Retorna status atual de cada item de lubrificação do equipamento."""
    from services import lubrificacoes_service
    try:
        itens = lubrificacoes_service.calcular_proximas_lubrificacoes_batch([eqp_id]).get(eqp_id, [])
        return [
            {
                "item": i.get("item", "-"),
                "tipo_produto": i.get("tipo_produto", "-"),
                "tipo_controle": i.get("tipo_controle", "km"),
                "atual": float(i.get("atual", 0) or 0),
                "vencimento": float(i.get("vencimento", 0) or 0),
                "diferenca": float(i.get("diferenca", 0) or 0),
                "status": i.get("status", "EM_DIA"),
                "unidade": "h" if str(i.get("tipo_controle", "km")).lower().startswith("h") else "km",
            }
            for i in itens
        ]
    except Exception:
        return []


# ── estilos da página ─────────────────────────────────────────────────────────

def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .pdf-shell { margin-top: .1rem; }
        .pdf-card {
            border: 1px solid rgba(148,163,184,.13);
            border-radius: 16px;
            padding: 1.1rem 1.15rem 1rem;
            background: rgba(9,18,33,.55);
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
            transition: border-color .18s, box-shadow .18s;
        }
        .pdf-card:hover {
            border-color: rgba(79,140,255,.28);
            box-shadow: 0 4px 24px rgba(79,140,255,.08);
        }
        .pdf-card-accent {
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 4px;
            border-radius: 4px 0 0 4px;
        }
        .pdf-card-icon {
            font-size: 1.6rem;
            margin-bottom: .35rem;
        }
        .pdf-card-title {
            font-size: 1rem;
            font-weight: 800;
            color: #f0f6ff;
            margin: 0 0 .18rem;
            letter-spacing: -.01em;
        }
        .pdf-card-desc {
            font-size: .81rem;
            color: #7fa8cc;
            line-height: 1.5;
            margin: 0 0 .7rem;
        }
        .pdf-card-badge {
            display: inline-block;
            padding: .08rem .45rem;
            border-radius: 999px;
            font-size: .67rem;
            font-weight: 700;
            letter-spacing: .05em;
            text-transform: uppercase;
            margin-bottom: .55rem;
        }
        .pdf-card-badge.badge-blue   { background: rgba(79,140,255,.12); color: #93c5fd; border: 1px solid rgba(79,140,255,.2); }
        .pdf-card-badge.badge-green  { background: rgba(34,197,94,.10);  color: #86efac; border: 1px solid rgba(34,197,94,.2); }
        .pdf-card-badge.badge-amber  { background: rgba(245,158,11,.10); color: #fcd34d; border: 1px solid rgba(245,158,11,.2); }
        .pdf-card-badge.badge-purple { background: rgba(139,92,246,.12); color: #c4b5fd; border: 1px solid rgba(139,92,246,.2); }
        .pdf-filters-box {
            background: rgba(9,18,33,.45);
            border: 1px solid rgba(148,163,184,.10);
            border-radius: 12px;
            padding: .75rem .85rem .5rem;
            margin-bottom: .75rem;
        }
        .pdf-filters-title {
            font-size: .72rem;
            font-weight: 700;
            color: #7fa8cc;
            text-transform: uppercase;
            letter-spacing: .07em;
            margin-bottom: .4rem;
        }
        .pdf-empresa-note {
            font-size: .74rem;
            color: #4f8cff;
            background: rgba(79,140,255,.07);
            border: 1px solid rgba(79,140,255,.12);
            border-radius: 8px;
            padding: .4rem .65rem;
            margin-bottom: .8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── componentes de card ───────────────────────────────────────────────────────

def _card_header(icon: str, title: str, desc: str, badge_txt: str, badge_cls: str, accent_color: str):
    st.markdown(
        f"""
        <div class="pdf-card">
          <div class="pdf-card-accent" style="background:{accent_color}"></div>
          <div class="pdf-card-icon">{icon}</div>
          <span class="pdf-card-badge {badge_cls}">{badge_txt}</span>
          <div class="pdf-card-title">{title}</div>
          <div class="pdf-card-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── página principal ──────────────────────────────────────────────────────────

def render() -> None:
    _inject_styles()

    render_page_intro(
        "📄 Relatórios PDF",
        f"Gere relatórios profissionais prontos para impressão e apresentação aos responsáveis — {relatorio_pdf_service.NOME_EMPRESA}.",
        badge="Relatórios",
    )

    # Nota do nome da empresa
    st.markdown(
        f"""<div class="pdf-empresa-note">
            🏭 <strong>Empresa nos cabeçalhos:</strong> {relatorio_pdf_service.NOME_EMPRESA}
            &nbsp;·&nbsp; Para alterar, edite a constante <code>NOME_EMPRESA</code>
            em <code>services/relatorio_pdf_service.py</code>
        </div>""",
        unsafe_allow_html=True,
    )

    hoje = datetime.date.today()

    # ── Filtros globais de período e setor ────────────────────────────────────
    st.markdown("<div class='pdf-filters-box'><div class='pdf-filters-title'>⚙️ Filtros globais (usados nos Relatórios 1, 2 e 3)</div>", unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([1, 1, 1.4, 1.4])
    with fc1:
        data_ini = st.date_input("Data inicial", value=hoje - datetime.timedelta(days=29), key="pdf_ini")
    with fc2:
        data_fim = st.date_input("Data final", value=hoje, key="pdf_fim")
    with fc3:
        setores = _carregar_setores()
        setor_sel = st.selectbox(
            "Setor",
            [None] + list(setores),
            format_func=lambda s: "Todos os setores" if s is None else s[1],
            key="pdf_setor",
        )
        setor_id = setor_sel[0] if setor_sel else None
        setor_nome = setor_sel[1] if setor_sel else None
    with fc4:
        eqps_global = _carregar_equipamentos(setor_id)
        eqp_sel_global = st.selectbox(
            "Equipamento (opcional)",
            [None] + list(eqps_global),
            format_func=lambda e: "Todos" if e is None else f"{e[1]} — {e[2]}",
            key="pdf_eqp_global",
        )
        eqp_id_global = eqp_sel_global[0] if eqp_sel_global else None
    st.markdown("</div>", unsafe_allow_html=True)

    if data_ini > data_fim:
        st.error("A data inicial deve ser anterior à data final.")
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    # ── Grid de 2 colunas para os 4 relatórios ───────────────────────────────
    col_a, col_b = st.columns(2, gap="medium")

    # ─────────────────────────────────────────────────────────────────────────
    # RELATÓRIO 1 — Histórico de Lubrificações
    # ─────────────────────────────────────────────────────────────────────────
    with col_a:
        with st.container(border=True):
            st.markdown(
                """<div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>
                    <span style='font-size:1.5rem'>🛢️</span>
                    <div>
                        <div style='font-size:.95rem;font-weight:800;color:#f0f6ff'>Histórico de Lubrificações</div>
                        <span style='font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
                            background:rgba(34,197,94,.10);color:#86efac;border:1px solid rgba(34,197,94,.2);
                            border-radius:999px;padding:.06rem .4rem'>Por equipamento</span>
                    </div>
                </div>
                <div style='font-size:.8rem;color:#7fa8cc;line-height:1.5;margin-bottom:.6rem'>
                    Lista todas as trocas de lubrificante realizadas no período, agrupadas por máquina.
                    Inclui produtos utilizados e equipamentos <strong style='color:#fca5a5'>sem nenhuma troca</strong>.
                    Ideal para auditorias com o mecânico responsável.
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("⬇️ Gerar PDF — Lubrificações", key="btn_pdf_lub", use_container_width=True, type="primary"):
                with st.spinner("Gerando relatório de lubrificações…"):
                    try:
                        df_lub = _carregar_lubrificacoes_periodo(data_ini, data_fim, setor_id, eqp_id_global)
                        todos_eqps_raw = _carregar_equipamentos(setor_id)
                        todos_eqps = [
                            {"codigo": e[1], "nome": e[2], "setor_nome": e[4]}
                            for e in todos_eqps_raw
                        ]
                        pdf_bytes = relatorio_pdf_service.gerar_pdf_historico_lubrificacoes(
                            df_lub, data_ini, data_fim, todos_eqps, setor_nome
                        )
                        st.download_button(
                            label="📥 Baixar PDF — Histórico de Lubrificações",
                            data=pdf_bytes,
                            file_name=f"lubrificacoes_{ts}.pdf",
                            mime="application/pdf",
                            key=f"dl_lub_{ts}",
                            use_container_width=True,
                        )
                        total = len(df_lub) if not df_lub.empty else 0
                        st.success(f"✅ PDF gerado com {total} registro(s).")
                    except Exception as exc:
                        st.error(f"Erro ao gerar PDF: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # RELATÓRIO 2 — Conformidade de Revisões
    # ─────────────────────────────────────────────────────────────────────────
    with col_b:
        with st.container(border=True):
            st.markdown(
                """<div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>
                    <span style='font-size:1.5rem'>🔧</span>
                    <div>
                        <div style='font-size:.95rem;font-weight:800;color:#f0f6ff'>Conformidade de Revisões</div>
                        <span style='font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
                            background:rgba(79,140,255,.12);color:#93c5fd;border:1px solid rgba(79,140,255,.2);
                            border-radius:999px;padding:.06rem .4rem'>Ciclo atual</span>
                    </div>
                </div>
                <div style='font-size:.8rem;color:#7fa8cc;line-height:1.5;margin-bottom:.6rem'>
                    Mostra quantas revisões predefinidas foram realizadas no período e o status
                    atual de cada equipamento: <strong style='color:#86efac'>em dia</strong>,
                    <strong style='color:#fcd34d'>próximo</strong> ou
                    <strong style='color:#fca5a5'>vencido</strong>.
                    Perfeito para apresentar à supervisão.
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("⬇️ Gerar PDF — Revisões", key="btn_pdf_rev", use_container_width=True, type="primary"):
                with st.spinner("Gerando relatório de conformidade…"):
                    try:
                        df_rev = _carregar_revisoes_periodo(data_ini, data_fim, setor_id, eqp_id_global)
                        # Status atual de todos os equipamentos
                        alertas_raw, _ = dashboard_service.carregar_alertas()
                        alertas_rev = [
                            a for a in alertas_raw
                            if a.get("origem") == "Revisão"
                            and (not setor_id or str(a.get("setor_id", "")) == str(setor_id))
                        ]
                        status_atual = [
                            {
                                "codigo": a.get("codigo"),
                                "nome": a.get("equipamento"),
                                "setor_nome": a.get("setor"),
                                "etapa": a.get("etapa"),
                                "status": a.get("status"),
                                "falta": abs(float(a.get("falta", 0) or 0)),
                                "unidade": "h" if str(a.get("tipo", "km")).lower().startswith("h") else "km",
                            }
                            for a in alertas_rev
                        ]
                        pdf_bytes = relatorio_pdf_service.gerar_pdf_conformidade_revisoes(
                            df_rev, status_atual, data_ini, data_fim, setor_nome
                        )
                        st.download_button(
                            label="📥 Baixar PDF — Conformidade de Revisões",
                            data=pdf_bytes,
                            file_name=f"conformidade_revisoes_{ts}.pdf",
                            mime="application/pdf",
                            key=f"dl_rev_{ts}",
                            use_container_width=True,
                        )
                        total = len(df_rev) if not df_rev.empty else 0
                        st.success(f"✅ PDF gerado com {total} revisão(ões).")
                    except Exception as exc:
                        st.error(f"Erro ao gerar PDF: {exc}")

    col_c, col_d = st.columns(2, gap="medium")

    # ─────────────────────────────────────────────────────────────────────────
    # RELATÓRIO 3 — Executivo de Frota
    # ─────────────────────────────────────────────────────────────────────────
    with col_c:
        with st.container(border=True):
            st.markdown(
                """<div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>
                    <span style='font-size:1.5rem'>📊</span>
                    <div>
                        <div style='font-size:.95rem;font-weight:800;color:#f0f6ff'>Relatório Executivo de Frota</div>
                        <span style='font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
                            background:rgba(245,158,11,.10);color:#fcd34d;border:1px solid rgba(245,158,11,.2);
                            border-radius:999px;padding:.06rem .4rem'>Diretoria / Gerência</span>
                    </div>
                </div>
                <div style='font-size:.8rem;color:#7fa8cc;line-height:1.5;margin-bottom:.6rem'>
                    Visão consolidada com <strong style='color:#fcd34d'>Fleet Health Score</strong>,
                    KPIs gerais, top 5 equipamentos críticos e top 5 setores com mais alertas.
                    Inclui detalhamento de execuções do período. Ideal para reuniões gerenciais.
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("⬇️ Gerar PDF — Executivo", key="btn_pdf_exec", use_container_width=True, type="primary"):
                with st.spinner("Gerando relatório executivo…"):
                    try:
                        alertas_raw, total_eqp = dashboard_service.carregar_alertas()
                        kpis = dashboard_service.resumo_kpis(alertas_raw, total_eqp)
                        mov = dashboard_service.carregar_movimentacao()
                        health_score = inteligencia_service.calcular_health_score(kpis, mov)
                        ranking_set = dashboard_service.ranking_setores(alertas_raw)
                        ranking_eqp = dashboard_service.ranking_equipamentos_criticos(alertas_raw, limite=10)
                        df_rev = _carregar_revisoes_periodo(data_ini, data_fim, setor_id)
                        df_lub = _carregar_lubrificacoes_periodo(data_ini, data_fim, setor_id)
                        pdf_bytes = relatorio_pdf_service.gerar_pdf_executivo_frota(
                            kpis, mov, ranking_set, ranking_eqp,
                            health_score, df_rev, df_lub,
                            data_ini, data_fim,
                        )
                        st.download_button(
                            label="📥 Baixar PDF — Relatório Executivo",
                            data=pdf_bytes,
                            file_name=f"executivo_frota_{ts}.pdf",
                            mime="application/pdf",
                            key=f"dl_exec_{ts}",
                            use_container_width=True,
                        )
                        st.success(f"✅ PDF executivo gerado — Health Score: {health_score.get('score', 0):.0f}%")
                    except Exception as exc:
                        st.error(f"Erro ao gerar PDF: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # RELATÓRIO 4 — Ficha Técnica do Equipamento
    # ─────────────────────────────────────────────────────────────────────────
    with col_d:
        with st.container(border=True):
            st.markdown(
                """<div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>
                    <span style='font-size:1.5rem'>📋</span>
                    <div>
                        <div style='font-size:.95rem;font-weight:800;color:#f0f6ff'>Ficha Técnica do Equipamento</div>
                        <span style='font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
                            background:rgba(139,92,246,.12);color:#c4b5fd;border:1px solid rgba(139,92,246,.2);
                            border-radius:999px;padding:.06rem .4rem'>Individual por máquina</span>
                    </div>
                </div>
                <div style='font-size:.8rem;color:#7fa8cc;line-height:1.5;margin-bottom:.55rem'>
                    Documento completo por equipamento com status de revisões e lubrificações,
                    histórico das últimas execuções, leitura atual e
                    <strong style='color:#c4b5fd'>campo de assinatura</strong> para conferência.
                </div>""",
                unsafe_allow_html=True,
            )
            # Seletor de equipamento específico para a ficha
            eqps_ficha = _carregar_equipamentos(None)
            eqp_ficha_sel = st.selectbox(
                "Selecione o equipamento",
                [None] + list(eqps_ficha),
                format_func=lambda e: "— selecione —" if e is None else f"{e[1]} — {e[2]}",
                key="pdf_eqp_ficha",
            )

            if eqp_ficha_sel is None:
                st.caption("Selecione um equipamento para gerar a ficha técnica.")
            else:
                if st.button("⬇️ Gerar Ficha Técnica", key="btn_pdf_ficha", use_container_width=True, type="primary"):
                    with st.spinner(f"Gerando ficha técnica — {eqp_ficha_sel[1]}…"):
                        try:
                            eqp_id_ficha = eqp_ficha_sel[0]
                            # Dados do equipamento
                            lista_eqps = equipamentos_service.listar()
                            eqp_dict = next(
                                (e for e in lista_eqps if str(e.get("id")) == str(eqp_id_ficha)),
                                {
                                    "codigo": eqp_ficha_sel[1],
                                    "nome": eqp_ficha_sel[2],
                                    "setor_nome": eqp_ficha_sel[4] if len(eqp_ficha_sel) > 4 else "-",
                                    "tipo": "-",
                                    "km_atual": 0,
                                    "horas_atual": 0,
                                }
                            )
                            # Status e histórico
                            status_rev  = _status_revisoes_equipamento(eqp_id_ficha)
                            status_lub  = _status_lubrificacoes_equipamento(eqp_id_ficha)
                            hist_rev, hist_lub = _carregar_historico_equipamento(eqp_id_ficha, limite=15)
                            ultima_leit = _ultima_leitura_equipamento(eqp_id_ficha)

                            pdf_bytes = relatorio_pdf_service.gerar_pdf_ficha_tecnica(
                                eqp_dict, status_rev, status_lub,
                                hist_rev, hist_lub, ultima_leit,
                            )
                            nome_arq = f"ficha_{eqp_ficha_sel[1].replace(' ', '_')}_{ts}.pdf"
                            st.download_button(
                                label=f"📥 Baixar Ficha — {eqp_ficha_sel[1]}",
                                data=pdf_bytes,
                                file_name=nome_arq,
                                mime="application/pdf",
                                key=f"dl_ficha_{ts}",
                                use_container_width=True,
                            )
                            n_rev = len(hist_rev)
                            n_lub = len(hist_lub)
                            st.success(f"✅ Ficha gerada — {n_rev} revisão(ões) e {n_lub} lubrificação(ões) no histórico.")
                        except Exception as exc:
                            st.error(f"Erro ao gerar ficha técnica: {exc}")

    # ── Dica de impressão ─────────────────────────────────────────────────────
    st.markdown(
        """
        <div style='margin-top:.5rem;padding:.6rem .8rem;border-radius:10px;
            background:rgba(79,140,255,.06);border:1px solid rgba(79,140,255,.10);
            font-size:.78rem;color:#7fa8cc;line-height:1.5'>
            💡 <strong style='color:#93c5fd'>Dica de impressão:</strong>
            Os PDFs são gerados no formato A4, otimizados para impressão em preto e branco ou colorido.
            Use as configurações de impressão do seu navegador para ajustar margens se necessário.
            Todos os relatórios incluem número de página e data de geração.
        </div>
        """,
        unsafe_allow_html=True,
    )
