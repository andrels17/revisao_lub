import datetime
import math

import pandas as pd
import streamlit as st

from services import (
    alertas_service,
    equipamentos_service,
    lubrificacoes_service,
    revisoes_service,
    vinculos_service,
)
from ui.constants import STATUS_LABEL
from ui.exportacao import botao_exportar_excel


def _inject_styles():
    st.markdown(
        """
        <style>
        .alerts-shell{margin-top:.15rem;}
        .alerts-card{
            border:1px solid rgba(148,163,184,.14);
            border-radius:18px;
            padding:1rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:0 14px 30px rgba(0,0,0,.18);
            margin-bottom:.8rem;
        }
        .alerts-card .top{display:flex;justify-content:space-between;gap:.9rem;align-items:flex-start;}
        .alerts-card .eqp{font-size:1rem;font-weight:800;color:#f2f7ff;margin:.25rem 0 .15rem 0;}
        .alerts-card .item{color:#a9bdd8;font-size:.84rem;font-weight:700;}
        .alerts-card .meta{color:#9db0c7;font-size:.82rem;margin-top:.45rem;line-height:1.5;}
        .alerts-card .resp{color:#c7d7ec;font-size:.83rem;margin-top:.45rem;}
        .alerts-card .actions{display:flex;flex-direction:column;gap:.55rem;min-width:180px;}
        .alert-badges{display:flex;gap:.45rem;flex-wrap:wrap;}
        .alert-badge{
            display:inline-flex;align-items:center;padding:.22rem .6rem;border-radius:999px;
            font-size:.72rem;font-weight:800;border:1px solid transparent;
        }
        .alert-badge-danger{background:rgba(239,68,68,.12);color:#fecaca;border-color:rgba(239,68,68,.18);}
        .alert-badge-warning{background:rgba(245,158,11,.12);color:#fde68a;border-color:rgba(245,158,11,.18);}
        .alert-badge-info{background:rgba(79,140,255,.12);color:#dcebff;border-color:rgba(79,140,255,.18);}
        .alert-message pre {
            background:rgba(7,17,31,.72) !important;border:1px solid rgba(148,163,184,.1) !important;
            border-radius:14px !important;color:#e7f0ff !important;
        }
        .alert-empty{
            border:1px dashed rgba(148,163,184,.18);border-radius:18px;padding:1rem;background:rgba(10,19,34,.4);color:#9db0c7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60, show_spinner="Carregando pendências…")
def _carregar_pendencias():
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], [], {}

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    enviados_hoje = alertas_service.alertas_enviados_hoje_batch(ids)

    pendencias_rev = []
    pendencias_lub = []

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]

        for rev in rev_idx.get(eqp_id, []):
            if rev.get("status") in ("VENCIDO", "PROXIMO"):
                pendencias_rev.append({"eqp": eqp, "item": rev, "enviado_hoje": enviados_hoje.get((eqp_id, "revisao"), False)})

        for lub in lub_idx.get(eqp_id, []):
            if lub.get("status") in ("VENCIDO", "PROXIMO"):
                pendencias_lub.append({"eqp": eqp, "item": lub, "enviado_hoje": enviados_hoje.get((eqp_id, "lubrificacao"), False)})

    pendencias_rev.sort(key=lambda x: (x["item"].get("status") != "VENCIDO", float(x["item"].get("diferenca", 0) or 0)))
    pendencias_lub.sort(key=lambda x: (x["item"].get("status") != "VENCIDO", float(x["item"].get("diferenca", 0) or 0)))
    return pendencias_rev, pendencias_lub, enviados_hoje


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">📱 Comunicação</div>
            <h2>Alertas WhatsApp</h2>
            <p>Priorize pendências críticas, revise mensagens antes do envio e acompanhe o histórico em uma central mais enxuta e operacional.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _meta_cards(pendencias_rev, pendencias_lub):
    total = len(pendencias_rev) + len(pendencias_lub)
    vencidos = sum(1 for p in pendencias_rev + pendencias_lub if p["item"].get("status") == "VENCIDO")
    proximos = sum(1 for p in pendencias_rev + pendencias_lub if p["item"].get("status") == "PROXIMO")
    enviados = sum(1 for p in pendencias_rev + pendencias_lub if p.get("enviado_hoje"))
    cards = [
        ("status-danger", "🔴 Vencidos", vencidos, "Exigem contato imediato"),
        ("status-warning", "🟡 Próximos", proximos, "Janela de atenção"),
        ("status-info", "📦 Total na fila", total, "Pendências carregadas"),
        ("status-success", "✅ Enviados hoje", enviados, "Histórico do dia"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{label}</div><div class='value'>{int(value)}</div><div class='sub'>{sub}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def _responsaveis_para_equipamento(eqp_id: str):
    try:
        return vinculos_service.listar_por_equipamento(eqp_id)
    except Exception:
        return []


def _formatar_responsavel(vinculos):
    if not vinculos:
        return None, "-"
    principal = next((v for v in vinculos if v.get("principal")), vinculos[0])
    nome = principal.get("responsavel_nome") or principal.get("nome") or "-"
    return principal, nome


def _mensagem_alerta(tipo: str, eqp: dict, item: dict, responsavel_nome: str):
    if tipo == "revisao":
        return alertas_service.montar_mensagem_revisao(eqp, item, responsavel_nome)
    return alertas_service.montar_mensagem_lubrificacao(eqp, item, responsavel_nome)


def _badge_css(status_raw: str) -> str:
    if status_raw == "VENCIDO":
        return "alert-badge alert-badge-danger"
    if status_raw == "PROXIMO":
        return "alert-badge alert-badge-warning"
    return "alert-badge alert-badge-info"


def _render_card_alerta(item_payload: dict, tipo: str):
    eqp = item_payload["eqp"]
    item = item_payload["item"]
    enviado_hoje = bool(item_payload.get("enviado_hoje"))
    vinculos = _responsaveis_para_equipamento(eqp["id"])
    responsavel, responsavel_nome = _formatar_responsavel(vinculos)

    unidade = "h" if item.get("tipo_controle") == "horas" else "km"
    status_raw = item.get("status", "-")
    status_label = STATUS_LABEL.get(status_raw, status_raw)
    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    titulo_item = item.get("etapa") or item.get("item") or "-"

    st.markdown("<div class='alerts-card'>", unsafe_allow_html=True)
    left, right = st.columns([3.6, 1.4], vertical_alignment="top")

    with left:
        badges = [f"<span class='{_badge_css(status_raw)}'>{status_label}</span>"]
        if enviado_hoje:
            badges.append("<span class='alert-badge alert-badge-info'>📩 Enviado hoje</span>")
        badges.append(
            f"<span class='alert-badge alert-badge-info'>{'Revisão' if tipo == 'revisao' else 'Lubrificação'}</span>"
        )
        st.markdown(f"<div class='alert-badges'>{''.join(badges)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='eqp'>{eqp.get('codigo', '-')} — {eqp.get('nome', '-')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='item'>{titulo_item}</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="meta">
                Setor: <strong>{eqp.get('setor_nome', '-')}</strong> &nbsp;•&nbsp;
                Atual: <strong>{float(item.get('atual', 0) or 0):.0f} {unidade}</strong> &nbsp;•&nbsp;
                Vencimento: <strong>{float(item.get('vencimento', item.get('vencimento_ciclo', 0)) or 0):.0f} {unidade}</strong> &nbsp;•&nbsp;
                Diferença: <strong>{falta:.0f} {unidade}</strong>
            </div>
            <div class='resp'>Responsável principal: <strong>{responsavel_nome}</strong></div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        mensagem = _mensagem_alerta(tipo, eqp, item, responsavel_nome)
        telefone = ""
        if responsavel:
            telefone = responsavel.get("telefone") or ""
        link = alertas_service.gerar_link_whatsapp(telefone, mensagem) if telefone else ""

        if link:
            st.link_button("📱 Abrir WhatsApp", link, use_container_width=True)

        if st.button(
            "✅ Registrar envio",
            key=f"reg_{tipo}_{eqp['id']}_{titulo_item}",
            use_container_width=True,
        ):
            alertas_service.registrar_alerta(
                equipamento_id=eqp["id"],
                responsavel_id=responsavel.get("responsavel_id") if responsavel else None,
                tipo_alerta=tipo,
                perfil="operacional",
                mensagem=mensagem,
            )
            _carregar_pendencias.clear()
            st.success("Envio registrado.")
            st.rerun()

    with st.expander("Ver mensagem"):
        st.markdown("<div class='alert-message'>", unsafe_allow_html=True)
        st.code(mensagem)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _payloads_to_df(payloads: list, tipo: str) -> pd.DataFrame:
    rows = []
    for p in payloads:
        eqp = p["eqp"]
        item = p["item"]
        rows.append(
            {
                "Tipo": "Revisão" if tipo == "revisao" else "Lubrificação",
                "Equipamento": f'{eqp.get("codigo", "-")} - {eqp.get("nome", "-")}',
                "Setor": eqp.get("setor_nome", "-"),
                "Etapa / Item": item.get("etapa") or item.get("item") or "-",
                "Controle": item.get("tipo_controle", "-"),
                "Atual": float(item.get("atual", 0) or 0),
                "Vencimento": float(item.get("vencimento", item.get("vencimento_ciclo", 0)) or 0),
                "Diferença": float(item.get("diferenca", item.get("falta", 0)) or 0),
                "Status": STATUS_LABEL.get(item.get("status"), item.get("status")),
                "Já enviado hoje": "Sim" if p.get("enviado_hoje") else "Não",
            }
        )
    return pd.DataFrame(rows)


def _slice_payloads(payloads: list, page: int, page_size: int) -> list:
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return payloads[start:end]


def _render_lista(payloads: list, tipo: str):
    st.markdown("<div class='filters-shell'><div class='filters-title'>Fila operacional</div>", unsafe_allow_html=True)
    filtros = st.columns([2.4, 1.2, 1.2, 1])
    with filtros[0]:
        busca = st.text_input("Buscar equipamento / etapa", key=f"busca_{tipo}")
    with filtros[1]:
        status = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO"], key=f"status_{tipo}")
    with filtros[2]:
        enviados = st.selectbox("Envio", ["Todos", "Pendentes hoje", "Já enviados hoje"], key=f"enviados_{tipo}")
    with filtros[3]:
        page_size = st.selectbox("Por página", [5, 10, 20, 30], index=1, key=f"page_size_{tipo}")
    st.markdown("</div>", unsafe_allow_html=True)

    termo = (busca or "").strip().lower()
    filtrados = payloads
    if termo:
        filtrados = [
            p for p in filtrados
            if termo in f'{p["eqp"].get("codigo","")} {p["eqp"].get("nome","")} {p["item"].get("etapa","")} {p["item"].get("item","")}'.lower()
        ]
    if status != "Todos":
        filtrados = [p for p in filtrados if p["item"].get("status") == status]
    if enviados == "Pendentes hoje":
        filtrados = [p for p in filtrados if not p.get("enviado_hoje")]
    elif enviados == "Já enviados hoje":
        filtrados = [p for p in filtrados if p.get("enviado_hoje")]

    df = _payloads_to_df(filtrados, tipo)
    top1, top2 = st.columns([3, 1])
    with top1:
        st.caption(f"{len(filtrados)} item(ns) após filtros")
    with top2:
        botao_exportar_excel(df, f"alertas_{tipo}", label="⬇️ Excel", key=f"exp_{tipo}")

    if not filtrados:
        st.markdown("<div class='alert-empty'>Nenhum item para os filtros selecionados.</div>", unsafe_allow_html=True)
        return

    total_pages = max(1, math.ceil(len(filtrados) / page_size))
    nav1, nav2 = st.columns([1, 4])
    with nav1:
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, key=f"page_{tipo}")
    with nav2:
        st.caption(f"{total_pages} página(s) • paginação aplicada para evitar lentidão em listas grandes.")

    for payload in _slice_payloads(filtrados, int(page), int(page_size)):
        _render_card_alerta(payload, tipo)


def _render_historico():
    st.markdown("<div class='section-card'><h3>Histórico de envios</h3><p>Filtre o que já foi comunicado e exporte a trilha operacional quando precisar auditar.</p></div>", unsafe_allow_html=True)

    hoje = datetime.date.today()
    st.markdown("<div class='filters-shell'><div class='filters-title'>Consulta de histórico</div>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        data_ini = st.date_input("De", value=hoje - datetime.timedelta(days=30), key="hist_ini")
    with col2:
        data_fim = st.date_input("Até", value=hoje, key="hist_fim")
    with col3:
        tipo_f = st.selectbox("Tipo", ["Todos", "revisao", "lubrificacao"], key="hist_tipo")
    with col4:
        perfil_f = st.selectbox("Perfil", ["Todos", "operacional", "gestao"], key="hist_perfil")
    st.markdown("</div>", unsafe_allow_html=True)

    historico = alertas_service.listar_historico(
        limite=500,
        data_inicio=data_ini,
        data_fim=data_fim,
        tipo=None if tipo_f == "Todos" else tipo_f,
        perfil=None if perfil_f == "Todos" else perfil_f,
    )

    if not historico:
        st.info("Nenhum alerta registrado para os filtros selecionados.")
        return

    df = pd.DataFrame(historico)
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.caption(f"{len(df)} alerta(s) encontrado(s)")
    with top_r:
        botao_exportar_excel(df, "historico_alertas", label="⬇️ Excel", key="exp_hist_alertas")
    st.dataframe(df, use_container_width=True, hide_index=True)


def render():
    _inject_styles()

    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", help="Recarrega pendências", use_container_width=True):
            _carregar_pendencias.clear()
            st.rerun()

    st.markdown(
        "<div class='section-caption'>Central única para revisar pendências de revisão e lubrificação, com foco em prioridade, agilidade de envio e menos ruído visual.</div>",
        unsafe_allow_html=True,
    )

    pendencias_rev, pendencias_lub, _ = _carregar_pendencias()
    _meta_cards(pendencias_rev, pendencias_lub)

    tab1, tab2, tab3 = st.tabs([
        f"Revisões ({len(pendencias_rev)})",
        f"Lubrificações ({len(pendencias_lub)})",
        "Histórico",
    ])

    with tab1:
        _render_lista(pendencias_rev, "revisao")

    with tab2:
        _render_lista(pendencias_lub, "lubrificacao")

    with tab3:
        _render_historico()
