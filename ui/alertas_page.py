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


QUEUE_READY = "Prontos para envio"
QUEUE_BLOCKED = "Bloqueados / sem cobertura"


def _inject_styles():
    st.markdown(
        """
        <style>
        .alerts-shell{margin-top:.15rem;}
        .alerts-card,.queue-card{
            border:1px solid rgba(148,163,184,.14);
            border-radius:18px;
            padding:1rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:0 14px 30px rgba(0,0,0,.18);
            margin-bottom:.8rem;
        }
        .alerts-card .eqp,.queue-card .eqp{font-size:1rem;font-weight:800;color:#f2f7ff;margin:.2rem 0 .15rem 0;}
        .alerts-card .item,.queue-card .item{color:#a9bdd8;font-size:.84rem;font-weight:700;}
        .alerts-card .meta,.queue-card .meta{color:#9db0c7;font-size:.82rem;margin-top:.45rem;line-height:1.55;}
        .alerts-card .resp,.queue-card .resp{color:#c7d7ec;font-size:.83rem;margin-top:.45rem;}
        .alert-badges{display:flex;gap:.45rem;flex-wrap:wrap;margin-bottom:.35rem;}
        .alert-badge{
            display:inline-flex;align-items:center;padding:.22rem .6rem;border-radius:999px;
            font-size:.72rem;font-weight:800;border:1px solid transparent;
        }
        .alert-badge-danger{background:rgba(239,68,68,.12);color:#fecaca;border-color:rgba(239,68,68,.18);}
        .alert-badge-warning{background:rgba(245,158,11,.12);color:#fde68a;border-color:rgba(245,158,11,.18);}
        .alert-badge-info{background:rgba(79,140,255,.12);color:#dcebff;border-color:rgba(79,140,255,.18);}
        .alert-badge-success{background:rgba(34,197,94,.12);color:#bbf7d0;border-color:rgba(34,197,94,.18);}
        .alert-message pre {
            background:rgba(7,17,31,.72) !important;border:1px solid rgba(148,163,184,.1) !important;
            border-radius:14px !important;color:#e7f0ff !important;
        }
        .alert-empty{
            border:1px dashed rgba(148,163,184,.18);border-radius:18px;padding:1rem;background:rgba(10,19,34,.4);color:#9db0c7;
        }
        .mini-grid{
            display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:.2rem 0 .35rem 0;
        }
        .mini-card{
            border:1px solid rgba(148,163,184,.12);border-radius:16px;padding:.8rem .9rem;
            background:rgba(8,16,29,.38);
        }
        .mini-card .k{font-size:.72rem;color:#8ea6c4;font-weight:700;text-transform:uppercase;letter-spacing:.04em;}
        .mini-card .v{font-size:1.12rem;color:#f7fbff;font-weight:800;margin-top:.1rem;}
        .queue-toolbar{
            border:1px solid rgba(148,163,184,.12);border-radius:18px;padding:.85rem .95rem;margin-bottom:.8rem;
            background:rgba(9,18,33,.52);
        }
        .queue-note{
            border-left:3px solid rgba(79,140,255,.5);padding:.65rem .85rem;border-radius:12px;
            background:rgba(79,140,255,.08);color:#dcebff;margin:.35rem 0 .9rem 0;
        }
        .compact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem;margin-top:.5rem;}
        .compact-item{background:rgba(8,16,29,.36);border:1px solid rgba(148,163,184,.1);border-radius:12px;padding:.55rem .65rem;}
        .compact-item .k{font-size:.68rem;color:#8ea6c4;text-transform:uppercase;font-weight:700;letter-spacing:.04em;}
        .compact-item .v{font-size:.82rem;color:#eef5ff;font-weight:700;margin-top:.12rem;line-height:1.35;}
        .batch-box{border:1px solid rgba(148,163,184,.12);border-radius:18px;padding:1rem;background:rgba(9,18,33,.58);margin:.2rem 0 .95rem 0;}
        .batch-recipient{border:1px solid rgba(148,163,184,.1);border-radius:14px;padding:.8rem .9rem;background:rgba(8,16,29,.36);margin-bottom:.7rem;}
        .batch-recipient .title{font-size:.92rem;font-weight:800;color:#f3f8ff;margin-bottom:.15rem;}
        .batch-recipient .sub{font-size:.78rem;color:#9db0c7;margin-bottom:.35rem;}
        .batch-lines{color:#d8e6f8;font-size:.82rem;line-height:1.5;margin:.2rem 0 .45rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60, show_spinner="Carregando central de alertas…")
def _carregar_central():
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return {
            "pendencias_rev": [],
            "pendencias_lub": [],
            "enviados_hoje": {},
            "fila": {"revisao": [], "lubrificacao": [], "resumo": {}, "cobertura": {"setores": []}},
            "mapa_operacionais": {},
            "mapa_gestao": {},
        }

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    enviados_hoje = alertas_service.alertas_enviados_hoje_batch(ids)
    fila = alertas_service.gerar_fila_sugerida()
    mapa_operacionais = vinculos_service.mapa_responsaveis_operacionais()
    mapa_gestao = vinculos_service.mapa_responsaveis_gestao()

    pendencias_rev = []
    pendencias_lub = []

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]

        for rev in rev_idx.get(eqp_id, []):
            if rev.get("status") in ("VENCIDO", "PROXIMO"):
                pendencias_rev.append(
                    {
                        "eqp": eqp,
                        "item": rev,
                        "enviado_hoje": enviados_hoje.get((eqp_id, "revisao"), False),
                    }
                )

        for lub in lub_idx.get(eqp_id, []):
            if lub.get("status") in ("VENCIDO", "PROXIMO"):
                pendencias_lub.append(
                    {
                        "eqp": eqp,
                        "item": lub,
                        "enviado_hoje": enviados_hoje.get((eqp_id, "lubrificacao"), False),
                    }
                )

    pendencias_rev.sort(key=lambda x: (x["item"].get("status") != "VENCIDO", float(x["item"].get("diferenca", 0) or 0)))
    pendencias_lub.sort(key=lambda x: (x["item"].get("status") != "VENCIDO", float(x["item"].get("diferenca", 0) or 0)))

    return {
        "pendencias_rev": pendencias_rev,
        "pendencias_lub": pendencias_lub,
        "enviados_hoje": enviados_hoje,
        "fila": fila,
        "mapa_operacionais": mapa_operacionais,
        "mapa_gestao": mapa_gestao,
    }


def _refresh_central():
    _carregar_central.clear()
    st.rerun()


def _item_titulo(item: dict) -> str:
    return item.get("etapa") or item.get("item") or "-"


def _payload_key(tipo: str, eqp: dict, item: dict) -> str:
    return f"{tipo}|{eqp.get('id')}|{_item_titulo(item)}"


def _queue_item_key(item: dict) -> str:
    return f"{item.get('tipo_alerta')}|{item.get('equipamento_id')}|{item.get('item')}"


def _destinatario_principal(eqp: dict, mapa_operacionais: dict, mapa_gestao: dict, preferencia: str = "operacional"):
    destinatarios = _formatar_destinatarios(eqp, mapa_operacionais, mapa_gestao)
    if not destinatarios:
        return None

    if preferencia == "gestao":
        for dest in destinatarios:
            if dest.get("papel") == "Gestão" and dest.get("telefone"):
                return dest

    for dest in destinatarios:
        if dest.get("papel") == "Operacional" and dest.get("telefone") and dest.get("principal"):
            return dest
    for dest in destinatarios:
        if dest.get("papel") == "Operacional" and dest.get("telefone"):
            return dest
    for dest in destinatarios:
        if dest.get("papel") == "Gestão" and dest.get("telefone"):
            return dest
    return destinatarios[0]


def _batch_message(recipient_name: str, itens: list[dict]) -> str:
    linhas = [f"Olá, *{recipient_name}*. Segue resumo das pendências priorizadas:", ""]
    for idx, item in enumerate(itens, start=1):
        eqp = item["eqp"]
        detalhe = item["item"]
        tipo = "Revisão" if item["tipo"] == "revisao" else "Lubrificação"
        unidade = "h" if detalhe.get("tipo_controle") == "horas" else "km"
        diferenca = float(detalhe.get("diferenca", detalhe.get("falta", 0)) or 0)
        status = STATUS_LABEL.get(detalhe.get("status"), detalhe.get("status"))
        linhas.extend([
            f"*{idx}. {tipo}*",
            f"Equipamento: {eqp.get('codigo', '-')} - {eqp.get('nome', '-')}",
            f"Item: {_item_titulo(detalhe)}",
            f"Status: {status} | Diferença: {diferenca:.0f} {unidade}",
            f"Setor: {eqp.get('setor_nome', '-')}",
            "",
        ])
    linhas.append("Por favor, priorizar os apontamentos e retornos da operação.")
    return "\n".join(linhas)


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">Comunicação</div>
            <h2>Central de WhatsApp</h2>
            <p>Agora a aba funciona como uma fila operacional real: mostra quem deve ser acionado, o que está pronto para envio, o que está bloqueado e o histórico do que já foi disparado.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _meta_cards(pendencias_rev, pendencias_lub, fila):
    total = len(pendencias_rev) + len(pendencias_lub)
    vencidos = sum(1 for p in pendencias_rev + pendencias_lub if p["item"].get("status") == "VENCIDO")
    proximos = sum(1 for p in pendencias_rev + pendencias_lub if p["item"].get("status") == "PROXIMO")
    resumo = fila.get("resumo", {})
    prontos = resumo.get("prontos_envio", 0)
    bloqueados = resumo.get("bloqueados", 0)
    cards = [
        ("status-danger", "Vencidos", vencidos, "Prioridade imediata"),
        ("status-warning", "Próximos", proximos, "Janela de atenção"),
        ("status-success", "Prontos para envio", prontos, "Fila utilizável agora"),
        ("status-info", "Bloqueados / cooldown", bloqueados, "Exigem espera ou vínculo"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{label}</div><div class='value'>{int(value)}</div><div class='sub'>{sub}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)
    st.caption(f"{total} pendência(s) monitoradas entre revisões e lubrificações.")


def _formatar_destinatarios(eqp: dict, mapa_operacionais: dict, mapa_gestao: dict):
    operacionais = []
    for item in mapa_operacionais.get(eqp.get("id"), []):
        operacionais.append(
            {
                "papel": "Operacional",
                "nome": item.get("responsavel_nome") or "-",
                "telefone": item.get("responsavel_telefone") or "",
                "responsavel_id": item.get("responsavel_id"),
                "principal": bool(item.get("principal")),
            }
        )

    operacionais.sort(key=lambda x: (not x["principal"], x["nome"]))
    gestor_raw = mapa_gestao.get(eqp.get("setor_id")) if eqp.get("setor_id") else None
    gestao = []
    if gestor_raw:
        gestao.append(
            {
                "papel": "Gestão",
                "nome": gestor_raw.get("nome") or "-",
                "telefone": gestor_raw.get("telefone") or "",
                "responsavel_id": None,
                "principal": True,
            }
        )

    return operacionais + gestao


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


def _queue_badge(label: str, kind: str = "info") -> str:
    css = {
        "danger": "alert-badge alert-badge-danger",
        "warning": "alert-badge alert-badge-warning",
        "success": "alert-badge alert-badge-success",
        "info": "alert-badge alert-badge-info",
    }.get(kind, "alert-badge alert-badge-info")
    return f"<span class='{css}'>{label}</span>"


def _recipient_selector(prefix: str, destinatarios: list[dict]):
    if not destinatarios:
        st.warning("Nenhum responsável com vínculo configurado para este item.")
        return None

    opcoes = []
    for idx, dest in enumerate(destinatarios):
        telefone = dest.get("telefone") or "sem telefone"
        principal = " • principal" if dest.get("principal") else ""
        label = f"{dest.get('papel')}: {dest.get('nome')} ({telefone}){principal}"
        opcoes.append((idx, label))

    labels = [label for _, label in opcoes]
    escolhido = st.selectbox("Enviar para", labels, key=f"dest_{prefix}")
    idx_escolhido = next(i for i, label in opcoes if label == escolhido)
    return destinatarios[idx_escolhido]


def _registrar_envio(eqp: dict, destinatario: dict | None, tipo: str, mensagem: str):
    alertas_service.registrar_alerta(
        equipamento_id=eqp["id"],
        responsavel_id=destinatario.get("responsavel_id") if destinatario else None,
        tipo_alerta=tipo,
        perfil=(destinatario or {}).get("papel", "operacional").lower(),
        mensagem=mensagem,
    )



def _render_card_alerta(item_payload: dict, tipo: str, mapa_operacionais: dict, mapa_gestao: dict):
    eqp = item_payload["eqp"]
    item = item_payload["item"]
    enviado_hoje = bool(item_payload.get("enviado_hoje"))
    destinatarios = _formatar_destinatarios(eqp, mapa_operacionais, mapa_gestao)
    destinatario = _recipient_selector(f"{tipo}_{eqp['id']}_{item.get('etapa') or item.get('item')}", destinatarios)

    unidade = "h" if item.get("tipo_controle") == "horas" else "km"
    status_raw = item.get("status", "-")
    status_label = STATUS_LABEL.get(status_raw, status_raw)
    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    titulo_item = _item_titulo(item)
    nome_destinatario = (destinatario or {}).get("nome") or "Responsável"
    mensagem = _mensagem_alerta(tipo, eqp, item, nome_destinatario)
    telefone = (destinatario or {}).get("telefone") or ""
    link = alertas_service.gerar_link_whatsapp(telefone, mensagem) if telefone else ""

    st.markdown("<div class='alerts-card'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='alert-badges'>{_queue_badge(status_label, 'danger' if status_raw == 'VENCIDO' else 'warning')}{_queue_badge('Revisão' if tipo == 'revisao' else 'Lubrificação')}{_queue_badge('Enviado hoje', 'info') if enviado_hoje else ''}</div>",
        unsafe_allow_html=True,
    )
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
        """,
        unsafe_allow_html=True,
    )

    a1, a2 = st.columns(2)
    with a1:
        if link:
            st.link_button("Abrir WhatsApp", link, use_container_width=True)
        else:
            st.button("Sem telefone", disabled=True, key=f"nolink_{tipo}_{eqp['id']}_{titulo_item}", use_container_width=True)
    with a2:
        if st.button(
            "Registrar envio",
            key=f"reg_{tipo}_{eqp['id']}_{titulo_item}",
            use_container_width=True,
        ):
            _registrar_envio(eqp, destinatario, tipo, mensagem)
            st.success("Envio registrado.")
            _refresh_central()

    with st.expander("Mensagem pronta"):
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
                "Status": item.get("status", "-"),
                "Enviado hoje": "Sim" if p.get("enviado_hoje") else "Não",
            }
        )
    return pd.DataFrame(rows)



def _slice_payloads(payloads: list, page: int, page_size: int):
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return payloads[start:end]



def _render_lista(payloads: list, tipo: str, mapa_operacionais: dict, mapa_gestao: dict):
    st.markdown(
        "<div class='section-card'><h3>Pendências detalhadas</h3><p>Visão completa por item, com destinatário editável antes da abertura do WhatsApp.</p></div>",
        unsafe_allow_html=True,
    )

    df = _payloads_to_df(payloads, tipo)
    if df.empty:
        st.markdown("<div class='alert-empty'>Nenhuma pendência encontrada.</div>", unsafe_allow_html=True)
        return

    st.markdown("<div class='filters-shell'><div class='filters-title'>Filtros</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.2, 1.1, 1.4, 1.1])
    with c1:
        status_filter = st.selectbox("Status", ["Todos", "VENCIDO", "PROXIMO"], key=f"status_{tipo}")
    with c2:
        enviado_filter = st.selectbox("Enviado hoje", ["Todos", "Não", "Sim"], key=f"enviado_{tipo}")
    with c3:
        busca = st.text_input("Buscar equipamento/item", key=f"busca_{tipo}")
    with c4:
        page_size = st.selectbox("Itens por página", [5, 10, 20, 50], index=1, key=f"page_size_{tipo}")
    st.markdown("</div>", unsafe_allow_html=True)

    filtrados = []
    texto_busca = (busca or "").strip().lower()
    for p in payloads:
        item = p["item"]
        eqp = p["eqp"]
        if status_filter != "Todos" and item.get("status") != status_filter:
            continue
        if enviado_filter == "Sim" and not p.get("enviado_hoje"):
            continue
        if enviado_filter == "Não" and p.get("enviado_hoje"):
            continue
        base = f"{eqp.get('codigo', '')} {eqp.get('nome', '')} {item.get('etapa', '')} {item.get('item', '')} {eqp.get('setor_nome', '')}".lower()
        if texto_busca and texto_busca not in base:
            continue
        filtrados.append(p)

    top1, top2 = st.columns([3, 1])
    with top1:
        st.caption(f"{len(filtrados)} item(ns) após filtros")
    with top2:
        botao_exportar_excel(_payloads_to_df(filtrados, tipo), f"alertas_{tipo}", label="Excel", key=f"exp_{tipo}")

    if not filtrados:
        st.markdown("<div class='alert-empty'>Nenhum item para os filtros selecionados.</div>", unsafe_allow_html=True)
        return

    total_pages = max(1, math.ceil(len(filtrados) / page_size))
    nav1, nav2 = st.columns([1, 4])
    with nav1:
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, key=f"page_{tipo}")
    with nav2:
        st.caption(f"{total_pages} página(s) • paginação aplicada para manter a tela leve.")

    for payload in _slice_payloads(filtrados, int(page), int(page_size)):
        _render_card_alerta(payload, tipo, mapa_operacionais, mapa_gestao)



def _fila_para_df(itens: list[dict], categoria: str) -> pd.DataFrame:
    rows = []
    for item in itens:
        rows.append(
            {
                "Fila": categoria,
                "Tipo": "Revisão" if item.get("tipo_alerta") == "revisao" else "Lubrificação",
                "Equipamento": item.get("equipamento"),
                "Setor": item.get("setor"),
                "Item": item.get("item"),
                "Status": item.get("status"),
                "Prioridade": item.get("prioridade"),
                "Motivo": item.get("motivo_fila"),
                "Operacional": item.get("responsaveis_operacionais"),
                "Gestão": item.get("gestao"),
                "Último envio": item.get("ultimo_envio"),
            }
        )
    return pd.DataFrame(rows)



def _render_queue_card(item: dict):
    kind = QUEUE_BLOCKED if (item.get("bloqueado_cooldown") or not item.get("tem_operacional")) else QUEUE_READY
    badges = []
    badges.append(_queue_badge(STATUS_LABEL.get(item.get("status"), item.get("status")), "danger" if item.get("status") == "VENCIDO" else "warning"))
    badges.append(_queue_badge("Revisão" if item.get("tipo_alerta") == "revisao" else "Lubrificação"))
    badges.append(_queue_badge("Pronto", "success") if kind == QUEUE_READY else _queue_badge("Bloqueado", "warning"))
    if item.get("enviado_hoje"):
        badges.append(_queue_badge("Enviado hoje", "info"))

    ultimo = item.get("ultimo_envio")
    ultimo_txt = ultimo.strftime("%d/%m/%Y %H:%M") if hasattr(ultimo, "strftime") else "-"
    falta = float(item.get("falta", 0) or 0)
    unidade = "h" if str(item.get("item", "")).lower().find("hora") >= 0 else "km"

    st.markdown("<div class='queue-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='alert-badges'>{''.join(badges)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='eqp'>{item.get('equipamento')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='item'>{item.get('item')}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='compact-grid'>
            <div class='compact-item'><div class='k'>Setor</div><div class='v'>{item.get('setor')}</div></div>
            <div class='compact-item'><div class='k'>Prioridade</div><div class='v'>{int(item.get('prioridade', 0) or 0)}</div></div>
            <div class='compact-item'><div class='k'>Diferença</div><div class='v'>{falta:.0f} {unidade}</div></div>
            <div class='compact-item'><div class='k'>Último envio</div><div class='v'>{ultimo_txt}</div></div>
        </div>
        <div class='resp'>Operacional: <strong>{item.get('responsaveis_operacionais') or '-'}</strong><br>Gestão: <strong>{item.get('gestao') or '-'}</strong></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Motivo da fila: {item.get('motivo_fila') or '-'}")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_fila_sugerida(fila: dict):
    resumo = fila.get("resumo", {})
    cobertura = fila.get("cobertura", {})
    revisoes = fila.get("revisao", [])
    lubrificacoes = fila.get("lubrificacao", [])
    todos = revisoes + lubrificacoes
    prontos = [i for i in todos if not i.get("bloqueado_cooldown") and i.get("tem_operacional")]
    bloqueados = [i for i in todos if i not in prontos]

    st.markdown(
        "<div class='section-card'><h3>Fila sugerida</h3><p>Esta visão mostra o que vale enviar primeiro, respeitando prioridade, cobertura de responsáveis e cooldown.</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class='mini-grid'>
            <div class='mini-card'><div class='k'>Cobertura operacional</div><div class='v'>{float(cobertura.get('percentual_operacional', 0)):.1f}%</div></div>
            <div class='mini-card'><div class='k'>Cobertura gestão</div><div class='v'>{float(cobertura.get('percentual_gestao', 0)):.1f}%</div></div>
            <div class='mini-card'><div class='k'>Sem cobertura</div><div class='v'>{int(resumo.get('sem_cobertura', 0))}</div></div>
            <div class='mini-card'><div class='k'>Itens na fila</div><div class='v'>{int(resumo.get('total', 0))}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='queue-note'>Use esta aba como triagem: primeiro envie os itens prontos, depois corrija vínculos e telefones dos bloqueados para a operação ficar consistente.</div>",
        unsafe_allow_html=True,
    )

    f1, f2, f3 = st.columns([1.2, 1.2, 1.4])
    with f1:
        queue_filter = st.selectbox("Exibir", ["Todos", QUEUE_READY, QUEUE_BLOCKED], key="queue_filter")
    with f2:
        tipo_filter = st.selectbox("Tipo", ["Todos", "revisao", "lubrificacao"], key="queue_tipo_filter")
    with f3:
        texto = st.text_input("Buscar equipamento/setor", key="queue_search")

    base = prontos + bloqueados if queue_filter == "Todos" else (prontos if queue_filter == QUEUE_READY else bloqueados)
    if tipo_filter != "Todos":
        base = [i for i in base if i.get("tipo_alerta") == tipo_filter]
    texto = (texto or "").strip().lower()
    if texto:
        base = [
            i for i in base if texto in f"{i.get('equipamento','')} {i.get('setor','')} {i.get('item','')} {i.get('motivo_fila','')}".lower()
        ]

    tools_l, tools_r = st.columns([3, 1])
    with tools_l:
        st.caption(f"{len(base)} item(ns) após filtros na fila sugerida.")
    with tools_r:
        botao_exportar_excel(_fila_para_df(base, queue_filter), "fila_sugerida_alertas", label="Excel", key="exp_fila")

    if not base:
        st.markdown("<div class='alert-empty'>Nenhum item encontrado na fila sugerida para os filtros selecionados.</div>", unsafe_allow_html=True)
    else:
        for item in base[:80]:
            _render_queue_card(item)
        if len(base) > 80:
            st.info("Exibindo os 80 primeiros itens filtrados para manter a página responsiva. Use o Excel para visão completa.")

    setores = pd.DataFrame(cobertura.get("setores", []))
    if not setores.empty:
        st.markdown("<div class='section-card'><h3>Cobertura por setor</h3><p>Ajuda a identificar onde a comunicação trava por falta de vínculo operacional ou de gestão.</p></div>", unsafe_allow_html=True)
        st.dataframe(setores, use_container_width=True, hide_index=True)



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
        botao_exportar_excel(df, "historico_alertas", label="Excel", key="exp_hist_alertas")
    st.dataframe(df, use_container_width=True, hide_index=True)



def render():
    _inject_styles()

    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("Atualizar", help="Recarrega pendências e fila sugerida", use_container_width=True):
            _refresh_central()

    st.markdown(
        "<div class='section-caption'>A aba foi reorganizada para separar triagem, envio assistido e histórico. Assim o nome da página passa a refletir o que ela realmente entrega.</div>",
        unsafe_allow_html=True,
    )

    central = _carregar_central()
    pendencias_rev = central["pendencias_rev"]
    pendencias_lub = central["pendencias_lub"]
    fila = central["fila"]
    mapa_operacionais = central["mapa_operacionais"]
    mapa_gestao = central["mapa_gestao"]

    _meta_cards(pendencias_rev, pendencias_lub, fila)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Fila sugerida",
        f"Revisões ({len(pendencias_rev)})",
        f"Lubrificações ({len(pendencias_lub)})",
        "Histórico",
    ])

    with tab1:
        _render_envio_lote_assistido(fila, pendencias_rev, pendencias_lub, mapa_operacionais, mapa_gestao)
        _render_fila_sugerida(fila)

    with tab2:
        _render_lista(pendencias_rev, "revisao", mapa_operacionais, mapa_gestao)

    with tab3:
        _render_lista(pendencias_lub, "lubrificacao", mapa_operacionais, mapa_gestao)

    with tab4:
        _render_historico()
