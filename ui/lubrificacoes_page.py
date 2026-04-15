
import datetime
import html

import pandas as pd
import streamlit as st

from ui.constants import STATUS_LABEL, STATUS_ORDEM
from ui.exportacao import botao_exportar_excel

from services import (
    equipamentos_service,
    lubrificacoes_service,
    responsaveis_service,
    vinculos_service,
    execucoes_service,
)


def _fmt_eqp(e):
    return f"{e['codigo']} - {e['nome']}"


def _fmt_unidade(tipo_controle):
    return "h" if tipo_controle == "horas" else "km"


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">🛢️ Operação</div>
            <h2>Controle de lubrificações</h2>
            <p>Priorize itens críticos, acompanhe o ciclo por equipamento e registre execuções com uma leitura mais limpa e objetiva.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(contagem: dict[str, int]) -> None:
    cards = [
        ("status-info", "🟣 Primeira troca", contagem.get("SEM_BASE", 0), "Sem referência inicial"),
        ("status-danger", "🔴 Vencidos", contagem.get("VENCIDO", 0), "Trocas urgentes"),
        ("status-warning", "🟡 Próximos", contagem.get("PROXIMO", 0), "Janela de atenção"),
        ("status-success", "🟢 Em dia", contagem.get("EM DIA", 0), "Dentro do ciclo"),
        ("status-info", "✅ Realizados", contagem.get("REALIZADO", 0), "Execuções registradas"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{html.escape(str(label))}</div><div class='value'>{int(value)}</div><div class='sub'>{html.escape(str(sub))}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _carregar_pendencias_batch():
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], {}
    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    pendencias = []
    for eqp_id, itens in lub_idx.items():
        eqp = eqp_map.get(eqp_id)
        if not eqp:
            continue
        for item in itens:
            pendencias.append({"eqp": eqp, "item": item})
    pendencias.sort(
        key=lambda x: (
            STATUS_ORDEM.get(x["item"]["status"], 99),
            x["item"].get("diferenca", 0),
            x["eqp"]["codigo"],
        )
    )
    return pendencias, eqp_map


def _calc_progresso(item: dict) -> int:
    if item.get("status") == "SEM_BASE":
        return 0

    atual = float(item.get("atual", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    intervalo = float(item.get("intervalo") or item.get("intervalo_valor", 0) or vencimento or 1)
    inicio_ciclo = max(0.0, vencimento - intervalo)
    span = vencimento - inicio_ciclo
    if span <= 0:
        return 100
    return int(max(0, min(100, (atual - inicio_ciclo) / span * 100)))


def _status_resumo(item: dict) -> str:
    unidade = _fmt_unidade(item.get("tipo_controle", "km"))
    if item.get("status") == "SEM_BASE":
        atual = float(item.get("atual", 0) or 0)
        intervalo = float(item.get("intervalo", item.get("intervalo_valor", 0)) or 0)
        return f"Registrar 1ª troca na leitura atual ({atual:.0f} {unidade}) • ciclo {intervalo:.0f} {unidade}"

    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    if falta <= 0:
        return f"Vencido há {abs(falta):.0f} {unidade}"
    return f"Faltam {falta:.0f} {unidade}"


def _render_card_lub(eqp: dict, item: dict, idx: int) -> None:
    status = item["status"]
    badge = STATUS_LABEL.get(status, status)
    unidade = _fmt_unidade(item.get("tipo_controle", "km"))
    atual = float(item.get("atual", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    progresso = _calc_progresso(item)

    codigo = str(eqp.get("codigo", "—"))
    nome = str(eqp.get("nome", "—"))
    grupo = eqp.get("grupo_nome") or eqp.get("grupo") or "—"
    setor = eqp.get("setor_nome") or "—"
    item_nome = item.get("item") or "Lubrificação"
    produto = item.get("tipo_produto") or "Lubrificação"
    resumo_status = _status_resumo(item)

    left, right = st.columns([7, 2], vertical_alignment="center")

    with left:
        st.markdown(f"##### {codigo}")
        st.markdown(f"**{nome}**")
        meta1, meta2 = st.columns([2, 3])
        with meta1:
            st.caption(f"**Item:** {item_nome}")
        with meta2:
            st.caption(f"**Produto:** {produto}")

        meta3, meta4, meta5 = st.columns([2, 2, 2])
        with meta3:
            st.caption(f"**Grupo:** {grupo}")
        with meta4:
            st.caption(f"**Departamento:** {setor}")
        with meta5:
            st.caption(f"**Próxima troca:** {vencimento:.0f} {unidade}")

        badge_cols = st.columns([1.5, 2.5, 2, 1.5])
        with badge_cols[0]:
            st.caption(badge)
        with badge_cols[1]:
            st.caption(resumo_status)
        with badge_cols[2]:
            st.caption(f"Leitura atual {atual:.0f} {unidade}")
        with badge_cols[3]:
            st.caption("Ativo")

    with right:
        if status == "SEM_BASE":
            st.metric("Ciclo", f"{float(item.get('intervalo', 0) or 0):.0f} {unidade}")
        else:
            st.metric("Progresso", f"{progresso}%")
        if st.button("Detalhes", key=f"det_lub_{eqp['id']}_{idx}", use_container_width=True):
            st.session_state["lub_detalhe"] = {
                "eqp_id": eqp["id"],
                "item_id": item.get("item_id"),
                "idx": idx,
            }
            st.rerun()

    st.divider()


def _encontrar_detalhe_atual(pendencias: list[dict]):
    detalhe = st.session_state.get("lub_detalhe")
    if not detalhe:
        return None, None, None

    for i, p in enumerate(pendencias):
        eqp = p["eqp"]
        item = p["item"]
        if (
            eqp.get("id") == detalhe.get("eqp_id")
            and item.get("item_id") == detalhe.get("item_id")
        ):
            return eqp, item, i

    if pendencias:
        p = pendencias[0]
        return p["eqp"], p["item"], 0
    return None, None, None


def _render_detalhe_lub(eqp: dict, item: dict, idx: int) -> None:
    if not eqp or not item:
        return

    unidade = _fmt_unidade(item.get("tipo_controle", "km"))
    atual = float(item.get("atual", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    ult = float(item.get("ultima_execucao", 0) or 0)
    progresso = _calc_progresso(item)
    badge = STATUS_LABEL.get(item.get("status"), item.get("status"))
    grupo = eqp.get("grupo_nome") or eqp.get("grupo") or "—"
    setor = eqp.get("setor_nome") or "—"

    st.markdown("### Detalhes da lubrificação")
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        st.markdown(f"**{eqp['codigo']} — {eqp['nome']}**")
        st.caption(f"{grupo} • {setor} • {item.get('item') or 'Lubrificação'} • {badge}")
    with head_r:
        if st.button("Fechar", key=f"fechar_lub_{eqp['id']}_{idx}", use_container_width=True):
            st.session_state.pop("lub_detalhe", None)
            st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Leitura atual ({unidade})", f"{atual:.0f}")
    c2.metric(f"Próxima troca ({unidade})", f"{vencimento:.0f}")
    c3.metric("Progresso do ciclo", f"{progresso}%")
    if falta <= 0:
        c4.metric("Situação", f"Vencido há {abs(falta):.0f} {unidade}")
    else:
        c4.metric("Situação", f"Faltam {falta:.0f} {unidade}")

    st.caption(f"Produto: **{item.get('tipo_produto') or '—'}**")
    st.progress(progresso)

    intervalo = float(item.get("intervalo", item.get("intervalo_valor", 0)) or 0)
    st.caption(f"Intervalo configurado do item: **{intervalo:.0f} {unidade}**")

    if ult > 0:
        st.caption(f"Última execução registrada: {ult:.0f} {unidade}")
    else:
        st.caption("Sem referência inicial registrada. Faça a primeira baixa informando a leitura real da troca para iniciar o ciclo.")

    st.markdown("**Registrar lubrificação agora**")
    _form_rapido(eqp, item, key_suffix=f"lub_{eqp['id']}_{item.get('item_id', idx)}")
    st.divider()


def _form_rapido(eqp, item, key_suffix):
    tipo = item.get("tipo_controle", "km")
    unidade = _fmt_unidade(tipo)
    leitura_sug = float(item.get("vencimento", item.get("atual", 0)))

    vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op = {v["responsavel_id"] for v in vinculos_op}
    todos_resp = [r for r in responsaveis_service.listar() if r.get("ativo")]
    resp_lista = [r for r in todos_resp if r["id"] in ids_op] or todos_resp

    with st.form(f"form_{key_suffix}", clear_on_submit=True):
        st.caption(f"Equipamento: **{eqp['codigo']} — {eqp['nome']}** | Item: **{item['item']}**")

        c1, c2 = st.columns(2)
        with c1:
            if tipo == "horas":
                horas_exec = st.number_input(
                    f"Horímetro na execução ({unidade})",
                    min_value=0.0,
                    value=leitura_sug,
                    step=1.0,
                    key=f"h_{key_suffix}",
                )
                km_exec = None
            else:
                km_exec = st.number_input(
                    f"Hodômetro na execução ({unidade})",
                    min_value=0.0,
                    value=leitura_sug,
                    step=1.0,
                    key=f"k_{key_suffix}",
                )
                horas_exec = None
            data_exec = st.date_input("Data da execução", value=datetime.date.today(), key=f"d_{key_suffix}")

        with c2:
            resp = st.selectbox(
                "Responsável",
                [None] + resp_lista,
                format_func=lambda r: "— não informar —" if r is None else r["nome"],
                key=f"r_{key_suffix}",
            )
            obs = st.text_area("Observações", height=80, key=f"o_{key_suffix}")

        if st.form_submit_button("✅ Registrar lubrificação", use_container_width=True, type="primary"):
            lubrificacoes_service.registrar_execucao(
                {
                    "equipamento_id": eqp["id"],
                    "item_id": item.get("item_id"),
                    "responsavel_id": resp["id"] if resp else None,
                    "nome_item": item["item"],
                    "tipo_produto": item.get("tipo_produto"),
                    "data_execucao": data_exec,
                    "km_execucao": km_exec,
                    "horas_execucao": horas_exec,
                    "observacoes": obs.strip() or None,
                }
            )
            _carregar_pendencias_batch.clear()
            st.success("Lubrificação registrada!")
            st.session_state.pop("lub_detalhe", None)
            st.rerun()


def _render_cards_listagem(itens: list[dict], vazio_msg: str, prefixo: str):
    if not itens:
        st.success(vazio_msg)
        return

    st.caption("Lista compacta para carregamento mais leve. Abra os detalhes só quando precisar.")

    batch_key = f"lub_batch_{prefixo}"
    if batch_key not in st.session_state:
        st.session_state[batch_key] = 20

    limite = st.session_state[batch_key]
    visiveis = itens[:limite]

    for i, p in enumerate(visiveis):
        _render_card_lub(p["eqp"], p["item"], i)

    if limite < len(itens):
        if st.button(f"Carregar mais ({len(itens) - limite} restantes)", key=f"mais_{prefixo}", use_container_width=True):
            st.session_state[batch_key] += 20
            st.rerun()

    eqp_det, item_det, idx_det = _encontrar_detalhe_atual(itens)
    if eqp_det and item_det:
        _render_detalhe_lub(eqp_det, item_det, idx_det)


def _render_tabela(itens, titulo):
    if not itens:
        st.info(f"Nenhum item em {titulo.lower()}.")
        return

    rows = []
    for p in itens:
        eqp = p["eqp"]
        item = p["item"]
        unidade = _fmt_unidade(item.get("tipo_controle", "km"))
        atual = float(item.get("atual", 0) or 0)
        vencimento = float(item.get("vencimento", 0) or 0)
        diferenca = float(item.get("diferenca", item.get("falta", 0)) or 0)
        rows.append(
            {
                "Código": eqp.get("codigo"),
                "Equipamento": eqp.get("nome"),
                "Grupo": eqp.get("grupo_nome") or eqp.get("grupo") or "—",
                "Departamento": eqp.get("setor_nome", "-"),
                "Item": item.get("item"),
                "Produto": item.get("tipo_produto") or "—",
                "Status": STATUS_LABEL.get(item.get("status"), item.get("status")),
                "Leitura atual": f"{atual:.0f} {unidade}",
                "Próxima troca": f"{vencimento:.0f} {unidade}",
                "Diferença": f"{diferenca:.0f} {unidade}",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_pendencias():
    pendencias, _ = _carregar_pendencias_batch()
    if not pendencias:
        st.success("Nenhuma lubrificação pendente no momento.")
        return

    setores = sorted({p["eqp"].get("setor_nome", "-") for p in pendencias})
    grupos = sorted({(p["eqp"].get("grupo_nome") or p["eqp"].get("grupo") or "—") for p in pendencias})
    eqps = sorted({f"{p['eqp']['codigo']} — {p['eqp']['nome']}" for p in pendencias})
    status_opts = ["Todos", "VENCIDO", "PROXIMO", "EM DIA", "REALIZADO"]

    st.markdown("<div class='filters-shell'><div class='filters-title'>Filtros operacionais</div>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        setor_f = st.multiselect("Departamento", setores, key="lub_setor")
    with col2:
        grupo_f = st.multiselect("Grupo", grupos, key="lub_grupo")
    with col3:
        eqp_f = st.multiselect("Equipamento", eqps, key="lub_eqp")
    with col4:
        status_f = st.selectbox("Status", status_opts, key="lub_status")
    st.markdown("</div>", unsafe_allow_html=True)

    filtradas = pendencias
    if setor_f:
        filtradas = [p for p in filtradas if p["eqp"].get("setor_nome", "-") in setor_f]
    if grupo_f:
        filtradas = [p for p in filtradas if (p["eqp"].get("grupo_nome") or p["eqp"].get("grupo") or "—") in grupo_f]
    if eqp_f:
        codigos_sel = {e.split(" — ", 1)[0] for e in eqp_f}
        filtradas = [p for p in filtradas if p["eqp"]["codigo"] in codigos_sel]
    if status_f != "Todos":
        filtradas = [p for p in filtradas if p["item"]["status"] == status_f]

    contagem = {s: sum(1 for p in filtradas if p["item"]["status"] == s) for s in STATUS_ORDEM}
    _render_kpi_cards(contagem)

    st.divider()

    vencidos = [p for p in filtradas if p["item"]["status"] == "VENCIDO"]
    proximos = [p for p in filtradas if p["item"]["status"] == "PROXIMO"]
    em_dia = [p for p in filtradas if p["item"]["status"] == "EM DIA"]
    realizados = [p for p in filtradas if p["item"]["status"] == "REALIZADO"]

    tab_v, tab_p, tab_d, tab_r, tab_tabela = st.tabs(
        [
            f"🔴 Vencidos ({len(vencidos)})",
            f"🟡 Próximos ({len(proximos)})",
            f"🟢 Em dia ({len(em_dia)})",
            f"✅ Realizados ({len(realizados)})",
            "📋 Tabela completa",
        ]
    )

    with tab_v:
        _render_cards_listagem(vencidos, "Nenhuma lubrificação vencida.", "vencidos")

    with tab_p:
        _render_cards_listagem(proximos, "Nenhuma lubrificação próxima do vencimento.", "proximos")

    with tab_d:
        _render_tabela([p for p in em_dia], "Em dia")

    with tab_r:
        _render_tabela([p for p in realizados], "Realizados neste ciclo")

    with tab_tabela:
        st.caption("Visão consolidada de todos os itens filtrados.")
        _render_tabela(filtradas, "Todos os itens")


def _render_execucao():
    st.subheader("Registrar Lubrificação")
    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_exec_eqp")
    if not eqp:
        return

    itens_pendentes = lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"])
    vinculos_op = vinculos_service.listar_por_equipamento(eqp["id"])
    ids_op = {v["responsavel_id"] for v in vinculos_op}
    resp_lista = [r for r in responsaveis if r["id"] in ids_op] or responsaveis

    with st.form("form_lub_exec_manual", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            resp = st.selectbox("Responsável", resp_lista, format_func=lambda r: r["nome"])
            data_exec = st.date_input("Data da execução")
            opcoes = ["— informar manualmente —"] + [
                f"{i['item']} ({i.get('tipo_produto','-')}) [{STATUS_LABEL.get(i['status'], i['status'])}]"
                for i in itens_pendentes
            ]
            item_idx = st.selectbox("Item do template", range(len(opcoes)), format_func=lambda i: opcoes[i])
        with c2:
            nome_manual = st.text_input("Nome do item (se manual)")
            prod_manual = st.text_input("Produto (se manual)")
            km_exec = st.number_input(
                "KM atual", min_value=0.0, value=float(eqp.get("km_atual") or 0), step=1.0
            )
            horas_exec = st.number_input(
                "Horas atuais", min_value=0.0, value=float(eqp.get("horas_atual") or 0), step=1.0
            )

        obs = st.text_area("Observações")
        salvar = st.form_submit_button("Registrar lubrificação", use_container_width=True)

        if salvar:
            item_id = None
            nome_item = nome_manual.strip() or None
            tipo_produto = prod_manual.strip() or None
            if item_idx > 0:
                obj = itens_pendentes[item_idx - 1]
                item_id = obj["item_id"]
                nome_item = nome_item or obj["item"]
                tipo_produto = tipo_produto or obj.get("tipo_produto")
            if not nome_item:
                st.error("Informe o nome do item de lubrificação.")
            else:
                lubrificacoes_service.registrar_execucao(
                    {
                        "equipamento_id": eqp["id"],
                        "item_id": item_id,
                        "responsavel_id": resp["id"] if resp else None,
                        "nome_item": nome_item,
                        "tipo_produto": tipo_produto,
                        "data_execucao": data_exec,
                        "km_execucao": km_exec,
                        "horas_execucao": horas_exec,
                        "observacoes": obs,
                    }
                )
                _carregar_pendencias_batch.clear()
                st.success("Lubrificação registrada com sucesso.")
                st.rerun()


def _render_historico():
    st.subheader("Histórico de Lubrificações")
    historico = lubrificacoes_service.listar_todos()
    if historico:
        df_hist = pd.DataFrame(historico)
        col_exp = st.columns([5, 1])[1]
        with col_exp:
            botao_exportar_excel(df_hist, "lubrificacoes_historico", label="⬇️ Excel", key="exp_lub_hist")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma lubrificação registrada ainda.")

    with st.expander("Histórico por equipamento"):
        equipamentos = equipamentos_service.listar()
        if not equipamentos:
            return
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="lub_hist_eqp")
        if eqp:
            dados = lubrificacoes_service.listar_por_equipamento(eqp["id"])
            if dados:
                st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum histórico para este equipamento.")


def render():
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True):
            _carregar_pendencias_batch.clear()
            st.rerun()

    st.markdown(
        "<div class='section-caption'>Acompanhe e registre lubrificações por equipamento em um fluxo mais direto, mais leve e com abertura de detalhes sob demanda.</div>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["Pendências", "Registrar", "Histórico"])
    with tab1:
        _render_pendencias()
    with tab2:
        _render_execucao()
    with tab3:
        _render_historico()
