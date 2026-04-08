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
        .wa-hero{
            padding: 1.1rem 1.2rem;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(3,105,161,.95), rgba(15,23,42,.95));
            color: #f8fafc;
            border: 1px solid rgba(148,163,184,.18);
            box-shadow: 0 18px 50px rgba(2,6,23,.16);
            margin-bottom: .9rem;
        }
        .wa-hero h2{margin:0;font-size:1.28rem;font-weight:800;}
        .wa-hero p{margin:.35rem 0 0 0;color:#dbeafe;font-size:.92rem;}
        .lite-card{
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 18px;
            padding: 1rem;
            background: rgba(255,255,255,.98);
            box-shadow: 0 10px 25px rgba(15,23,42,.05);
            margin-bottom: .8rem;
        }
        .status-badge{
            display:inline-block;
            padding:.2rem .55rem;
            border-radius:999px;
            font-size:.73rem;
            font-weight:700;
            background:#f8fafc;
            border:1px solid rgba(148,163,184,.28);
            margin-right:.35rem;
        }
        .meta{
            color:#64748b;
            font-size:.82rem;
            margin-top:.35rem;
        }
        .section-card{
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 20px;
            padding: 1rem;
            background: rgba(255,255,255,.98);
            box-shadow: 0 10px 25px rgba(15,23,42,.05);
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


def _meta_cards(pendencias_rev, pendencias_lub):
    total = len(pendencias_rev) + len(pendencias_lub)
    vencidos = sum(1 for p in pendencias_rev + pendencias_lub if p["item"].get("status") == "VENCIDO")
    enviados = sum(1 for p in pendencias_rev + pendencias_lub if p.get("enviado_hoje"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Pendências totais", total)
    c2.metric("Vencidos", vencidos)
    c3.metric("Já enviados hoje", enviados)


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

    st.markdown('<div class="lite-card">', unsafe_allow_html=True)
    left, right = st.columns([3.6, 1.5])

    with left:
        badges = [f'<span class="status-badge">{status_label}</span>']
        if enviado_hoje:
            badges.append('<span class="status-badge">📩 Já enviado hoje</span>')
        st.markdown("".join(badges), unsafe_allow_html=True)
        st.markdown(f"**{eqp.get('codigo', '-') } - {eqp.get('nome', '-') }**")
        st.caption(f"{'Revisão' if tipo == 'revisao' else 'Lubrificação'} • {titulo_item}")
        st.markdown(
            f"""
            <div class="meta">
                Setor: <strong>{eqp.get('setor_nome', '-')}</strong> &nbsp;•&nbsp;
                Atual: <strong>{float(item.get('atual', 0) or 0):.0f} {unidade}</strong> &nbsp;•&nbsp;
                Vencimento: <strong>{float(item.get('vencimento', item.get('vencimento_ciclo', 0)) or 0):.0f} {unidade}</strong> &nbsp;•&nbsp;
                Diferença: <strong>{falta:.0f} {unidade}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Responsável principal: {responsavel_nome}")

    with right:
        mensagem = _mensagem_alerta(tipo, eqp, item, responsavel_nome)
        telefone = ""
        if responsavel:
            telefone = responsavel.get("telefone") or ""
        link = alertas_service.gerar_link_whatsapp(telefone, mensagem) if telefone else ""

        if link:
            st.link_button("📱 WhatsApp", link, use_container_width=True)

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
        st.code(mensagem)
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
    filtros = st.columns([2.4, 1.2, 1.2, 1])
    with filtros[0]:
        busca = st.text_input("Buscar equipamento / etapa", key=f"busca_{tipo}")
    with filtros[1]:
        status = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO"], key=f"status_{tipo}")
    with filtros[2]:
        enviados = st.selectbox("Envio", ["Todos", "Pendentes hoje", "Já enviados hoje"], key=f"enviados_{tipo}")
    with filtros[3]:
        page_size = st.selectbox("Por página", [5, 10, 20, 30], index=1, key=f"page_size_{tipo}")

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
        st.info("Nenhum item para os filtros selecionados.")
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Histórico de envios")

    hoje = datetime.date.today()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        data_ini = st.date_input("De", value=hoje - datetime.timedelta(days=30), key="hist_ini")
    with col2:
        data_fim = st.date_input("Até", value=hoje, key="hist_fim")
    with col3:
        tipo_f = st.selectbox("Tipo", ["Todos", "revisao", "lubrificacao"], key="hist_tipo")
    with col4:
        perfil_f = st.selectbox("Perfil", ["Todos", "operacional", "gestao"], key="hist_perfil")

    historico = alertas_service.listar_historico(
        limite=500,
        data_inicio=data_ini,
        data_fim=data_fim,
        tipo=None if tipo_f == "Todos" else tipo_f,
        perfil=None if perfil_f == "Todos" else perfil_f,
    )

    if not historico:
        st.info("Nenhum alerta registrado para os filtros selecionados.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df = pd.DataFrame(historico)
    st.caption(f"{len(df)} alerta(s) encontrado(s)")
    botao_exportar_excel(df, "historico_alertas", label="⬇️ Excel", key="exp_hist_alertas")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render():
    _inject_styles()

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.title("📱 Alertas WhatsApp")
    with top_right:
        st.write("")
        if st.button("🔄 Atualizar", help="Recarrega pendências"):
            _carregar_pendencias.clear()
            st.rerun()

    pendencias_rev, pendencias_lub, _ = _carregar_pendencias()

    st.markdown(
        """
        <div class="wa-hero">
            <h2>Central de alertas operacionais</h2>
            <p>Fluxo mais leve e organizado: filtros rápidos, paginação e registro de envio sem travar a tela.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _meta_cards(pendencias_rev, pendencias_lub)

    tab1, tab2, tab3 = st.tabs([
        f"Revisão ({len(pendencias_rev)})",
        f"Lubrificação ({len(pendencias_lub)})",
        "Histórico",
    ])

    with tab1:
        _render_lista(pendencias_rev, "revisao")

    with tab2:
        _render_lista(pendencias_lub, "lubrificacao")

    with tab3:
        _render_historico()
