import io
from datetime import date, datetime

import pandas as pd
import streamlit as st

from services import (
    alertas_service,
    comentarios_service,
    equipamentos_service,
    execucoes_service,
    leituras_service,
    lubrificacoes_service,
    painel_360_service,
    escopo_service,
    revisoes_service,
    responsaveis_service,
    setores_service,
    templates_lubrificacao_service,
    templates_revisao_service,
    vinculos_service,
)
from ui.constants import STATUS_LABEL, TIPOS_EQUIPAMENTO
from ui.exportacao import botao_exportar_pdf_painel360


def _inject_modern_page_css():
    st.markdown(
        """
        <style>
        .eq-hero {
            padding: 1.15rem 1.2rem;
            border: 1px solid rgba(49, 51, 63, 0.14);
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(17,24,39,0.02), rgba(59,130,246,0.06));
            margin-bottom: 0.9rem;
        }
        .eq-hero-title { font-size: 1.35rem; font-weight: 700; margin-bottom: 0.2rem; }
        .eq-hero-sub { font-size: 0.92rem; opacity: 0.78; }
        .eq-card {
            padding: 0.95rem 1rem;
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 18px;
            background: rgba(255,255,255,0.58);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.75rem;
        }
        .eq-card-label { font-size: 0.78rem; opacity: 0.7; margin-bottom: 0.25rem; }
        .eq-card-value { font-size: 1.55rem; font-weight: 700; line-height: 1.1; }
        .eq-card-note { font-size: 0.8rem; opacity: 0.7; margin-top: 0.2rem; }
        .eq-section-title { font-size: 1rem; font-weight: 700; margin: 0.25rem 0 0.55rem 0; }
        .eq-badge {
            display: inline-block;
            padding: 0.24rem 0.55rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            border: 1px solid rgba(15, 23, 42, 0.08);
        }
        .eq-badge-ok { background: rgba(34,197,94,0.12); color: rgb(22,101,52); }
        .eq-badge-warn { background: rgba(245,158,11,0.14); color: rgb(146,64,14); }
        .eq-badge-danger { background: rgba(239,68,68,0.12); color: rgb(153,27,27); }
        .eq-badge-neutral { background: rgba(148,163,184,0.14); color: rgb(51,65,85); }
        .eq-toolbar {
            padding: 0.85rem 0.95rem;
            border: 1px solid rgba(49,51,63,0.12);
            border-radius: 18px;
            background: rgba(255,255,255,0.45);
            margin-bottom: 0.75rem;
        }
        div[data-testid="stDataEditor"] {
            border: 1px solid rgba(49,51,63,0.12);
            border-radius: 18px;
            overflow: hidden;
        }
        div[data-testid="stMetric"] {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 18px;
            padding: 0.7rem 0.8rem;
            background: rgba(255,255,255,0.52);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _formatar_status(status):
    return STATUS_LABEL.get(status, status)


def _resumo_status(itens):
    return {
        "vencidos": sum(1 for item in itens if item.get("status") == "VENCIDO"),
        "proximos": sum(1 for item in itens if item.get("status") == "PROXIMO"),
        "em_dia": sum(1 for item in itens if item.get("status") == "EM DIA"),
        "realizados": sum(1 for item in itens if item.get("status") == "REALIZADO"),
    }


def _calcular_saude_equipamento(revisoes, lubrificacoes):
    total_itens = len(revisoes) + len(lubrificacoes)
    vencidos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "VENCIDO")
    proximos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "PROXIMO")

    if total_itens == 0:
        return {
            "score": 100,
            "faixa": "Sem pendências configuradas",
            "detalhe": "Equipamento sem revisão ou lubrificação configurada.",
        }

    score = max(0, 100 - (vencidos * 25) - (proximos * 8))
    if vencidos >= 3 or score < 45:
        faixa = "Crítico"
    elif vencidos >= 1 or score < 70:
        faixa = "Atenção"
    else:
        faixa = "Saudável"

    return {
        "score": score,
        "faixa": faixa,
        "detalhe": f"{vencidos} vencido(s) e {proximos} próximo(s) entre {total_itens} item(ns).",
    }


def _mostrar_faixa_saude(saude):
    score = saude["score"]
    faixa = saude["faixa"]
    detalhe = saude["detalhe"]

    if faixa == "Crítico":
        st.error(f"Saúde do equipamento: {faixa} — {score}%")
    elif faixa == "Atenção":
        st.warning(f"Saúde do equipamento: {faixa} — {score}%")
    else:
        st.success(f"Saúde do equipamento: {faixa} — {score}%")

    st.progress(int(max(0, min(100, score))))
    st.caption(detalhe)


def _tabela_revisoes(revisoes):
    if not revisoes:
        st.info("Nenhuma revisão configurada para este equipamento.")
        return

    df = pd.DataFrame(revisoes)[[
        "etapa", "tipo_controle", "atual", "ultima_execucao", "vencimento_ciclo", "proximo_vencimento", "diferenca", "status"
    ]].rename(columns={
        "etapa": "Etapa",
        "tipo_controle": "Controle",
        "atual": "Atual",
        "ultima_execucao": "Executado em",
        "vencimento_ciclo": "Referência do ciclo",
        "proximo_vencimento": "Próximo vencimento",
        "diferenca": "Falta",
        "status": "Status",
    })
    df["Status"] = df["Status"].map(_formatar_status)
    st.caption("Cada etapa mostra o status dentro do ciclo atual. Quando uma etapa já foi lançada neste ciclo, ela aparece como Realizado.")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _tabela_lubrificacoes(lubrificacoes):
    if not lubrificacoes:
        st.info("Nenhuma lubrificação configurada para este equipamento.")
        return

    df = pd.DataFrame(lubrificacoes)[[
        "item", "tipo_produto", "tipo_controle", "atual", "ultima_execucao", "vencimento", "diferenca", "status"
    ]].rename(columns={
        "item": "Item",
        "tipo_produto": "Produto",
        "tipo_controle": "Controle",
        "atual": "Atual",
        "ultima_execucao": "Última execução",
        "vencimento": "Vencimento",
        "diferenca": "Falta",
        "status": "Status",
    })
    df["Status"] = df["Status"].map(_formatar_status)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _opcoes_responsaveis(vinculos):
    responsaveis = [r for r in responsaveis_service.listar() if r.get("ativo")]
    mapa = {r["id"]: r for r in responsaveis}

    ordenados = []
    vistos = set()
    for v in vinculos:
        rid = v.get("responsavel_id")
        if rid in mapa and rid not in vistos:
            ordenados.append(mapa[rid])
            vistos.add(rid)
    for r in responsaveis:
        if r["id"] not in vistos:
            ordenados.append(r)
            vistos.add(r["id"])
    return ordenados


def _select_responsavel(label, responsaveis, key):
    opcoes = [None] + responsaveis
    return st.selectbox(
        label,
        opcoes,
        key=key,
        format_func=lambda r: "— não informar —" if r is None else f'{r["nome"]} ({r.get("funcao_principal") or "sem função"})',
    )


def _render_acoes_rapidas(equipamento, revisoes, lubrificacoes, vinculos):
    st.caption("Use estas ações para lançar registros sem sair do Painel 360°.")
    responsaveis = _opcoes_responsaveis(vinculos)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        with st.form(f'form_leitura_rapida_{equipamento["id"]}', clear_on_submit=True):
            st.markdown("**Registrar leitura**")
            tipo_leitura = st.selectbox("Tipo de leitura", ["km", "horas", "ambos"], key=f'tipo_leitura_{equipamento["id"]}')
            km_valor = st.number_input("KM", min_value=0.0, value=float(equipamento.get("km_atual") or 0), step=1.0, key=f'km_leitura_{equipamento["id"]}')
            horas_valor = st.number_input("Horas", min_value=0.0, value=float(equipamento.get("horas_atual") or 0), step=1.0, key=f'horas_leitura_{equipamento["id"]}')
            data_leitura = st.date_input("Data", key=f'data_leitura_{equipamento["id"]}')
            responsavel = _select_responsavel("Responsável", responsaveis, key=f'resp_leitura_{equipamento["id"]}')
            observacoes = st.text_area("Observações", key=f'obs_leitura_{equipamento["id"]}', height=80)
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True)
            if salvar:
                km = km_valor if tipo_leitura in {"km", "ambos"} else None
                horas = horas_valor if tipo_leitura in {"horas", "ambos"} else None
                leituras_service.registrar(
                    equipamento_id=equipamento["id"], tipo_leitura=tipo_leitura, km_valor=km, horas_valor=horas,
                    data_leitura=data_leitura, responsavel_id=responsavel["id"] if responsavel else None,
                    observacoes=observacoes.strip() or None,
                )
                st.success("Leitura registrada com sucesso.")
                st.rerun()

    with col_b:
        with st.form(f'form_revisao_rapida_{equipamento["id"]}', clear_on_submit=True):
            st.markdown("**Lançar revisão**")
            pendencias_rev = [r for r in revisoes if r.get("status") in {"VENCIDO", "PROXIMO"}] or revisoes
            etapa = st.selectbox(
                "Etapa de referência",
                pendencias_rev if pendencias_rev else [None],
                key=f'etapa_rev_{equipamento["id"]}',
                format_func=lambda r: "Nenhuma revisão disponível" if r is None else f'{r["etapa"]} · {_formatar_status(r["status"])}',
            )
            km_sugerido = float(equipamento.get("km_atual") or 0)
            horas_sugeridas = float(equipamento.get("horas_atual") or 0)
            if etapa is not None:
                if (etapa.get("tipo_controle") or "").lower() == "km":
                    km_sugerido = float(etapa.get("vencimento") or km_sugerido)
                elif (etapa.get("tipo_controle") or "").lower() == "horas":
                    horas_sugeridas = float(etapa.get("vencimento") or horas_sugeridas)
            km_execucao = st.number_input("KM execução", min_value=0.0, value=km_sugerido, step=1.0, key=f'km_exec_{equipamento["id"]}')
            horas_execucao = st.number_input("Horas execução", min_value=0.0, value=horas_sugeridas, step=1.0, key=f'horas_exec_{equipamento["id"]}')
            if etapa is not None:
                st.caption(f"Sugestão baseada no vencimento da etapa: {float(etapa.get('vencimento') or 0):.0f} {(etapa.get('tipo_controle') or '').lower()}")
            data_execucao = st.date_input("Data da revisão", key=f'data_rev_{equipamento["id"]}')
            status_execucao = st.selectbox("Status", ["concluida", "pendente"], key=f'status_rev_{equipamento["id"]}')
            responsavel = _select_responsavel("Responsável", responsaveis, key=f'resp_rev_{equipamento["id"]}')
            observacoes = st.text_area("Observações", key=f'obs_rev_{equipamento["id"]}', height=80)
            salvar = st.form_submit_button("Salvar revisão", use_container_width=True, disabled=not revisoes)
            if salvar:
                obs = observacoes.strip()
                if etapa is not None:
                    prefixo = f'Etapa: {etapa["etapa"]}'
                    obs = f'{prefixo}\n{obs}' if obs else prefixo
                execucoes_service.criar_execucao({
                    "equipamento_id": equipamento["id"], "responsavel_id": responsavel["id"] if responsavel else None,
                    "tipo": "revisao", "data_execucao": data_execucao, "km_execucao": km_execucao,
                    "horas_execucao": horas_execucao, "observacoes": obs or None, "status": status_execucao,
                })
                st.success("Revisão registrada com sucesso.")
                st.rerun()

    with col_c:
        with st.form(f'form_lub_rapida_{equipamento["id"]}', clear_on_submit=True):
            st.markdown("**Lançar lubrificação**")
            pendencias_lub = [l for l in lubrificacoes if l.get("status") in {"VENCIDO", "PROXIMO"}] or lubrificacoes
            item = st.selectbox(
                "Item de lubrificação",
                pendencias_lub if pendencias_lub else [None],
                key=f'item_lub_{equipamento["id"]}',
                format_func=lambda l: "Nenhum item disponível" if l is None else f'{l["item"]} · {l.get("tipo_produto") or "-"} · {_formatar_status(l["status"])}',
            )
            km_sugerido_lub = float(equipamento.get("km_atual") or 0)
            horas_sugeridas_lub = float(equipamento.get("horas_atual") or 0)
            if item is not None:
                if (item.get("tipo_controle") or "").lower() == "km":
                    km_sugerido_lub = float(item.get("vencimento") or km_sugerido_lub)
                elif (item.get("tipo_controle") or "").lower() == "horas":
                    horas_sugeridas_lub = float(item.get("vencimento") or horas_sugeridas_lub)
            km_execucao = st.number_input("KM execução ", min_value=0.0, value=km_sugerido_lub, step=1.0, key=f'km_lub_{equipamento["id"]}')
            horas_execucao = st.number_input("Horas execução ", min_value=0.0, value=horas_sugeridas_lub, step=1.0, key=f'horas_lub_{equipamento["id"]}')
            if item is not None:
                st.caption(f"Sugestão baseada no vencimento do item: {float(item.get('vencimento') or 0):.0f} {(item.get('tipo_controle') or '').lower()}")
            data_execucao = st.date_input("Data da lubrificação", key=f'data_lub_{equipamento["id"]}')
            responsavel = _select_responsavel("Responsável", responsaveis, key=f'resp_lub_{equipamento["id"]}')
            observacoes = st.text_area("Observações", key=f'obs_lub_{equipamento["id"]}', height=80)
            salvar = st.form_submit_button("Salvar lubrificação", use_container_width=True, disabled=not lubrificacoes)
            if salvar and item is not None:
                lubrificacoes_service.registrar_execucao({
                    "equipamento_id": equipamento["id"], "item_id": item.get("item_id"),
                    "responsavel_id": responsavel["id"] if responsavel else None, "nome_item": item.get("item"),
                    "tipo_produto": item.get("tipo_produto"), "data_execucao": data_execucao,
                    "km_execucao": km_execucao, "horas_execucao": horas_execucao,
                    "observacoes": observacoes.strip() or None,
                })
                st.success("Lubrificação registrada com sucesso.")
                st.rerun()


def _render_timeline(eventos):
    if not eventos:
        st.info("Nenhum evento encontrado para a timeline.")
        return
    df = pd.DataFrame(eventos).rename(columns={
        "data": "Data", "tipo": "Tipo", "titulo": "Título", "detalhe": "Detalhe",
        "responsavel": "Responsável", "observacoes": "Observações",
    })
    st.dataframe(df[["Data", "Tipo", "Título", "Detalhe", "Responsável", "Observações"]], use_container_width=True, hide_index=True)


def _render_evolucao(equipamento, serie):
    if not serie:
        st.info("Sem leituras suficientes para evolução.")
        return
    df = pd.DataFrame(serie)
    st.caption("A evolução usa as leituras recentes registradas no sistema.")
    if "data" in df.columns:
        st.line_chart(df.set_index("data")[["km", "horas"]], use_container_width=True)
    st.dataframe(df.rename(columns={"data": "Data", "km": "KM", "horas": "Horas", "tipo": "Tipo"}), use_container_width=True, hide_index=True)
    st.metric("KM atual consolidado", f"{float(equipamento.get('km_atual') or 0):.0f}")
    st.metric("Horas atuais consolidadas", f"{float(equipamento.get('horas_atual') or 0):.0f}")


def _render_pendencias_resumo(pendencias):
    if not pendencias:
        st.success("Sem pendências vencidas ou próximas no momento.")
        return
    df = pd.DataFrame(pendencias).rename(columns={
        "origem": "Origem", "item": "Item", "controle": "Controle", "status": "Status",
        "referencia": "Referência", "atual": "Atual", "falta": "Falta",
    })
    df["Status"] = df["Status"].map(_formatar_status)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_comentarios_equipamento(equipamento_id, comentarios):
    with st.form(f"form_comentario_{equipamento_id}", clear_on_submit=True):
        comentario = st.text_area("Registrar comentário / ocorrência", height=110, placeholder="Ex.: equipamento aguardando janela de manutenção, peça separada, equipe alinhada...")
        enviado = st.form_submit_button("Salvar comentário", use_container_width=True)
    if enviado:
        ok, msg = comentarios_service.criar(equipamento_id, comentario)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    if comentarios:
        for item in comentarios:
            titulo = f"{item.get('autor_nome') or '-'} • {str(item.get('created_at') or '-')[:19]}"
            with st.expander(titulo):
                st.write(item.get('comentario') or '-')
    else:
        st.info("Nenhum comentário registrado para este equipamento.")


def _mostrar_painel_360(equipamento_id):
    equipamento = equipamentos_service.obter(equipamento_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    revisoes = revisoes_service.calcular_proximas_revisoes(equipamento_id)
    lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
    leituras = leituras_service.listar_por_equipamento(equipamento_id, limite=20)
    historico_lub = lubrificacoes_service.listar_por_equipamento(equipamento_id)[:20]
    historico_rev = execucoes_service.listar_revisoes_por_equipamento(equipamento_id, limite=20)
    resumo_exec_rev = execucoes_service.resumo_revisoes_por_equipamento(equipamento_id)
    vinculos = vinculos_service.listar_por_equipamento(equipamento_id)
    saude = _calcular_saude_equipamento(revisoes, lubrificacoes)
    timeline = painel_360_service.montar_timeline_equipamento(equipamento_id, limite=60)
    serie = painel_360_service.serie_evolucao_semanal(equipamento, leituras)
    pendencias = painel_360_service.resumir_pendencias(revisoes, lubrificacoes)
    insights = painel_360_service.gerar_insights(equipamento, revisoes, lubrificacoes, leituras, vinculos)
    hist_alertas = alertas_service.listar_historico_por_equipamento(equipamento_id, limite=20)
    comentarios = comentarios_service.listar_por_equipamento(equipamento_id, limite=30)

    top1, top2 = st.columns([5, 1])
    with top1:
        st.subheader(f"Painel 360° — {equipamento['codigo']} - {equipamento['nome']}")
    with top2:
        st.write("")
        botao_exportar_pdf_painel360(equipamento, saude, pendencias, insights, comentarios, key=f"pdf_360_{equipamento_id}")
    _mostrar_faixa_saude(saude)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Setor", equipamento.get("setor_nome") or "-")
    c2.metric("Tipo", equipamento.get("tipo") or "-")
    c3.metric("KM atual", f"{equipamento['km_atual']:.0f}")
    c4.metric("Horas atuais", f"{equipamento['horas_atual']:.0f}")

    resumo_rev = _resumo_status(revisoes)
    resumo_lub = _resumo_status(lubrificacoes)
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Revisões vencidas", resumo_rev["vencidos"])
    c6.metric("Lubrificações vencidas", resumo_lub["vencidos"])
    c7.metric("Revisões próximas", resumo_rev["proximos"])
    c8.metric("Lubrificações próximas", resumo_lub["proximos"])

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Execuções de revisão", resumo_exec_rev["total"])
    c10.metric("Concluídas", resumo_exec_rev["concluidas"])
    c11.metric("Pendentes", resumo_exec_rev["pendentes"])
    c12.metric("Alertas enviados", len(hist_alertas))

    with st.expander("Dados do equipamento", expanded=True):
        meta1, meta2 = st.columns(2)
        with meta1:
            st.write(f"**Template de revisão:** {equipamento.get('template_revisao_nome') or '-'}")
            st.write(f"**Template de lubrificação:** {equipamento.get('template_lubrificacao_nome') or '-'}")
            st.write(f"**Última revisão registrada:** {resumo_exec_rev.get('ultima_data') or '-'}")
        with meta2:
            st.write(f"**Status do cadastro:** {'Ativo' if equipamento.get('ativo') else 'Inativo'}")
            st.write(f"**Vínculos operacionais:** {len(vinculos)}")
            st.write(f"**Eventos na timeline:** {len(timeline)}")

    st.markdown("**Leitura gerencial**")
    for insight in insights:
        st.caption(f"• {insight}")

    tabs = st.tabs([
        "Pendências prioritárias",
        "Próximas revisões",
        "Próximas lubrificações",
        "Leituras recentes",
        "Timeline",
        "Evolução",
        "Histórico de revisões",
        "Histórico de lubrificações",
        "Alertas enviados",
        "Responsáveis",
        "Comentários / log",
        "Ações rápidas",
    ])

    with tabs[0]:
        _render_pendencias_resumo(pendencias)
    with tabs[1]:
        _tabela_revisoes(revisoes)
    with tabs[2]:
        _tabela_lubrificacoes(lubrificacoes)
    with tabs[3]:
        if leituras:
            df = pd.DataFrame(leituras).rename(columns={
                "data_leitura": "Data", "tipo_leitura": "Tipo", "km_valor": "KM",
                "horas_valor": "Horas", "responsavel": "Responsável", "observacoes": "Observações",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma leitura registrada para este equipamento.")
    with tabs[4]:
        _render_timeline(timeline)
    with tabs[5]:
        _render_evolucao(equipamento, serie)
    with tabs[6]:
        if historico_rev:
            df = pd.DataFrame(historico_rev).rename(columns={
                "data": "Data", "etapa_referencia": "Etapa", "km": "KM", "horas": "Horas",
                "responsavel": "Responsável", "status": "Status", "observacoes": "Observações", "resultado": "Resultado",
            })
            st.dataframe(df[["Data", "Etapa", "Resultado", "KM", "Horas", "Responsável", "Status", "Observações"]], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma execução de revisão registrada.")
    with tabs[7]:
        if historico_lub:
            df = pd.DataFrame(historico_lub).rename(columns={
                "data": "Data", "item": "Item", "produto": "Produto", "km": "KM",
                "horas": "Horas", "responsavel": "Responsável", "observacoes": "Observações",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma execução de lubrificação registrada.")
    with tabs[8]:
        if hist_alertas:
            df = pd.DataFrame(hist_alertas).rename(columns={
                "enviado_em": "Enviado em", "tipo": "Tipo", "perfil": "Perfil", "responsavel": "Responsável", "mensagem": "Mensagem",
            })
            st.dataframe(df[["Enviado em", "Tipo", "Perfil", "Responsável", "Mensagem"]], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta registrado para este equipamento.")
    with tabs[9]:
        if vinculos:
            df = pd.DataFrame(vinculos).rename(columns={
                "responsavel_nome": "Responsável", "responsavel_telefone": "Telefone", "tipo_vinculo": "Vínculo", "principal": "Principal",
            })
            st.dataframe(df[["Responsável", "Telefone", "Vínculo", "Principal"]], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum responsável vinculado a este equipamento.")
    with tabs[10]:
        _render_comentarios_equipamento(equipamento_id, comentarios)
    with tabs[11]:
        _render_acoes_rapidas(equipamento, revisoes, lubrificacoes, vinculos)


def _safe_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _badge_html(faixa):
    faixa = faixa or "-"
    if faixa == "Saudável":
        cls = "eq-badge eq-badge-ok"
    elif faixa == "Atenção":
        cls = "eq-badge eq-badge-warn"
    elif faixa == "Crítico":
        cls = "eq-badge eq-badge-danger"
    else:
        cls = "eq-badge eq-badge-neutral"
    return f'<span class="{cls}">{faixa}</span>'


def _build_health_map(equipamentos):
    cache = {}
    for item in equipamentos:
        equipamento_id = item["id"]
        try:
            revisoes = revisoes_service.calcular_proximas_revisoes(equipamento_id)
            lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
            leituras = leituras_service.listar_por_equipamento(equipamento_id, limite=1)
            saude = _calcular_saude_equipamento(revisoes, lubrificacoes)
            ultima_leitura = _safe_dt(leituras[0]["data_leitura"]) if leituras else None
            cache[equipamento_id] = {
                "faixa": saude["faixa"],
                "score": saude["score"],
                "ultima_leitura": ultima_leitura,
                "vencidos": sum(1 for item2 in revisoes + lubrificacoes if item2.get("status") == "VENCIDO"),
                "proximos": sum(1 for item2 in revisoes + lubrificacoes if item2.get("status") == "PROXIMO"),
            }
        except Exception:
            cache[equipamento_id] = {
                "faixa": "Sem dados",
                "score": 0,
                "ultima_leitura": None,
                "vencidos": 0,
                "proximos": 0,
            }
    return cache


def _setor_options(setores):
    return ["Todos"] + [s["nome"] for s in setores]


def _tipo_options(equipamentos):
    tipos = sorted({(e.get("tipo") or "").strip() for e in equipamentos if (e.get("tipo") or "").strip()})
    return ["Todos"] + tipos


def _filter_equipamentos(equipamentos, health_map, busca, setor, status_cadastro, tipo, criticidade):
    termo = (busca or "").strip().lower()
    filtrados = []
    for item in equipamentos:
        health = health_map.get(item["id"], {})
        if termo:
            alvo = " ".join(
                [
                    str(item.get("codigo") or ""),
                    str(item.get("nome") or ""),
                    str(item.get("tipo") or ""),
                    str(item.get("setor_nome") or ""),
                ]
            ).lower()
            if termo not in alvo:
                continue
        if setor != "Todos" and item.get("setor_nome") != setor:
            continue
        if tipo != "Todos" and (item.get("tipo") or "") != tipo:
            continue
        if status_cadastro == "Somente ativos" and not item.get("ativo"):
            continue
        if status_cadastro == "Somente inativos" and item.get("ativo"):
            continue
        if criticidade != "Todos" and health.get("faixa") != criticidade:
            continue
        filtrados.append(item)
    return filtrados


def _render_summary_cards(filtrados, health_map):
    total = len(filtrados)
    saudaveis = sum(1 for e in filtrados if health_map.get(e["id"], {}).get("faixa") == "Saudável")
    atencao = sum(1 for e in filtrados if health_map.get(e["id"], {}).get("faixa") == "Atenção")
    criticos = sum(1 for e in filtrados if health_map.get(e["id"], {}).get("faixa") == "Crítico")
    sem_setor = sum(1 for e in filtrados if not e.get("setor_id"))

    cols = st.columns(4)
    cards = [
        ("Base visível", str(total), "Filtros e escopo já aplicados"),
        ("Saudáveis", str(saudaveis), "Operação em dia"),
        ("Atenção / Crítico", f"{atencao} / {criticos}", "Prioridade para o time"),
        ("Sem setor", str(sem_setor), "Cadastro precisa ajuste"),
    ]
    for col, (label, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="eq-card">
                    <div class="eq-card-label">{label}</div>
                    <div class="eq-card-value">{value}</div>
                    <div class="eq-card-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _build_editor_df(page_items, health_map, responsavel_options_map):
    rows = []
    for item in page_items:
        health = health_map.get(item["id"], {})
        rows.append(
            {
                "_id": item["id"],
                "Código": item.get("codigo"),
                "Nome": item.get("nome"),
                "Tipo": item.get("tipo"),
                "Setor": item.get("setor_nome"),
                "Ativo": bool(item.get("ativo")),
                "Responsável principal": responsavel_options_map["por_equipamento"].get(item["id"], "— sem responsável —"),
                "Saúde": health.get("faixa", "Sem dados"),
                "Score": int(health.get("score") or 0),
                "Vencidos": int(health.get("vencidos") or 0),
                "Próximos": int(health.get("proximos") or 0),
                "KM atual": float(item.get("km_atual") or 0),
                "Horas": float(item.get("horas_atual") or 0),
            }
        )
    return pd.DataFrame(rows)


def _responsavel_data():
    responsaveis = [r for r in responsaveis_service.listar() if r.get("ativo")]
    labels = ["— sem responsável —"] + [r["nome"] for r in responsaveis]
    label_to_id = {"— sem responsável —": None}
    for r in responsaveis:
        label_to_id[r["nome"]] = r["id"]
    return responsaveis, labels, label_to_id


def _principal_por_equipamento(equipamentos):
    principal_map = {}
    for item in equipamentos:
        vinculos = vinculos_service.listar_por_equipamento(item["id"])
        principal = next((v for v in vinculos if v.get("principal")), None)
        if principal:
            principal_map[item["id"]] = principal.get("responsavel_nome") or "— sem responsável —"
        elif vinculos:
            principal_map[item["id"]] = vinculos[0].get("responsavel_nome") or "— sem responsável —"
        else:
            principal_map[item["id"]] = "— sem responsável —"
    return principal_map


def _exportar_csv(nome, rows):
    if not rows:
        return
    df = pd.DataFrame(rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=nome,
        data=csv_bytes,
        file_name="equipamentos_filtrados.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_lista_moderna(equipamentos, setores):
    st.markdown('<div class="eq-section-title">Operação rápida</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="eq-toolbar">
            Use os filtros para reduzir a lista e faça ajustes direto na grade.
            Depois clique em <b>Salvar alterações inline</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Calculando saúde dos equipamentos..."):
        health_map = _build_health_map(equipamentos)

    colf1, colf2, colf3, colf4, colf5 = st.columns([2.1, 1.3, 1.2, 1.1, 1.2])
    with colf1:
        busca = st.text_input("Busca rápida", placeholder="Código, nome, tipo ou setor")
    with colf2:
        setor = st.selectbox("Setor", _setor_options(setores))
    with colf3:
        status_cadastro = st.selectbox("Cadastro", ["Todos", "Somente ativos", "Somente inativos"])
    with colf4:
        tipo = st.selectbox("Tipo", _tipo_options(equipamentos))
    with colf5:
        criticidade = st.selectbox("Saúde", ["Todos", "Saudável", "Atenção", "Crítico"])

    filtrados = _filter_equipamentos(
        equipamentos=equipamentos,
        health_map=health_map,
        busca=busca,
        setor=setor,
        status_cadastro=status_cadastro,
        tipo=tipo,
        criticidade=criticidade,
    )

    _render_summary_cards(filtrados, health_map)

    colxp1, colxp2, colxp3 = st.columns([1.2, 1.2, 2.2])
    with colxp1:
        _exportar_csv("Exportar filtrados (CSV)", [
            {
                "codigo": e.get("codigo"),
                "nome": e.get("nome"),
                "tipo": e.get("tipo"),
                "setor": e.get("setor_nome"),
                "ativo": e.get("ativo"),
                "saude": health_map.get(e["id"], {}).get("faixa"),
                "score": health_map.get(e["id"], {}).get("score"),
            }
            for e in filtrados
        ])
    with colxp2:
        _exportar_csv("Exportar só críticos", [
            {
                "codigo": e.get("codigo"),
                "nome": e.get("nome"),
                "tipo": e.get("tipo"),
                "setor": e.get("setor_nome"),
                "ativo": e.get("ativo"),
                "saude": health_map.get(e["id"], {}).get("faixa"),
                "score": health_map.get(e["id"], {}).get("score"),
            }
            for e in filtrados if health_map.get(e["id"], {}).get("faixa") == "Crítico"
        ])
    with colxp3:
        st.caption(f"{len(filtrados)} equipamento(s) após filtros.")

    if not filtrados:
        st.info("Nenhum equipamento encontrado com os filtros atuais.")
        return

    col_pg1, col_pg2 = st.columns([1, 1])
    with col_pg1:
        por_pagina = st.selectbox("Itens por página", [10, 20, 30, 50], index=1, key="eq_lista_mod_pg")
    total_paginas = max(1, ((len(filtrados) - 1) // int(por_pagina)) + 1)
    with col_pg2:
        pagina = st.number_input("Página", min_value=1, max_value=total_paginas, value=1, step=1, key="eq_lista_mod_pagina")

    inicio = (int(pagina) - 1) * int(por_pagina)
    fim = inicio + int(por_pagina)
    page_items = filtrados[inicio:fim]

    responsaveis, responsavel_labels, label_to_id = _responsavel_data()
    principal_map = _principal_por_equipamento(page_items)
    responsavel_options_map = {"por_equipamento": principal_map}
    editor_df = _build_editor_df(page_items, health_map, responsavel_options_map)

    pode_editar = escopo_service.pode_gerenciar_cadastros()
    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        disabled=not pode_editar,
        column_config={
            "_id": None,
            "Código": st.column_config.TextColumn(disabled=True),
            "Nome": st.column_config.TextColumn(required=True, width="medium"),
            "Tipo": st.column_config.SelectboxColumn(options=TIPOS_EQUIPAMENTO, required=True),
            "Setor": st.column_config.SelectboxColumn(options=[s["nome"] for s in setores], required=True),
            "Ativo": st.column_config.CheckboxColumn(),
            "Responsável principal": st.column_config.SelectboxColumn(options=responsavel_labels),
            "Saúde": st.column_config.TextColumn(disabled=True),
            "Score": st.column_config.NumberColumn(disabled=True, format="%d"),
            "Vencidos": st.column_config.NumberColumn(disabled=True, format="%d"),
            "Próximos": st.column_config.NumberColumn(disabled=True, format="%d"),
            "KM atual": st.column_config.NumberColumn(disabled=True, format="%.0f"),
            "Horas": st.column_config.NumberColumn(disabled=True, format="%.0f"),
        },
        key="equipamentos_inline_editor",
    )

    cards_cols = st.columns(4)
    visiveis = len(page_items)
    cards_cols[0].metric("Página atual", f"{inicio + 1}–{min(fim, len(filtrados))}")
    cards_cols[1].metric("Visíveis na página", visiveis)
    cards_cols[2].metric("Críticos na página", sum(1 for e in page_items if health_map.get(e["id"], {}).get("faixa") == "Crítico"))
    cards_cols[3].metric("Atenção na página", sum(1 for e in page_items if health_map.get(e["id"], {}).get("faixa") == "Atenção"))

    if not pode_editar:
        st.info("Seu perfil está em modo consulta para edição inline.")
        return

    if st.button("Salvar alterações inline", type="primary", use_container_width=True):
        setor_nome_to_id = {s["nome"]: s["id"] for s in setores}
        orig_map = {row["_id"]: row for row in editor_df.to_dict("records")}
        new_map = {row["_id"]: row for row in edited_df.to_dict("records")}
        alterados = 0

        for equipamento_id, novo in new_map.items():
            original = orig_map.get(equipamento_id, {})
            nome = (novo.get("Nome") or "").strip()
            tipo_val = novo.get("Tipo")
            setor_nome = novo.get("Setor")
            ativo = bool(novo.get("Ativo"))
            resp_label = novo.get("Responsável principal", "— sem responsável —")

            if not nome or not tipo_val or setor_nome not in setor_nome_to_id:
                continue

            if (
                nome != original.get("Nome")
                or tipo_val != original.get("Tipo")
                or setor_nome != original.get("Setor")
                or ativo != original.get("Ativo")
            ):
                equipamentos_service.atualizar_inline(
                    equipamento_id,
                    nome=nome,
                    tipo=tipo_val,
                    setor_id=setor_nome_to_id[setor_nome],
                    ativo=ativo,
                )
                alterados += 1

            if resp_label != original.get("Responsável principal"):
                equipamentos_service.definir_responsavel_principal(
                    equipamento_id=equipamento_id,
                    responsavel_id=label_to_id.get(resp_label),
                )
                alterados += 1

        if alterados:
            st.success(f"{alterados} alteração(ões) aplicada(s) com sucesso.")
            st.rerun()
        else:
            st.info("Nenhuma alteração detectada.")


def render():
    _inject_modern_page_css()

    st.markdown(
        f"""
        <div class="eq-hero">
            <div class="eq-hero-title">Equipamentos</div>
            <div class="eq-hero-sub">
                Gestão mais rápida, visual mais limpo e edição inline para operação do dia a dia.
                Escopo atual: <b>{escopo_service.resumo_escopo()}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    equipamentos = equipamentos_service.listar()
    setores = [item for item in setores_service.listar() if item.get("ativo")]
    templates_rev = templates_revisao_service.listar()
    templates_lub = templates_lubrificacao_service.listar()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de equipamentos", len(equipamentos))
    c2.metric("Com setor vinculado", sum(1 for e in equipamentos if e.get("setor_id")))
    c3.metric("Com template revisão", sum(1 for e in equipamentos if e.get("template_revisao_id")))
    c4.metric("Com template lubrificação", sum(1 for e in equipamentos if e.get("template_lubrificacao_id")))

    tab1, tab2, tab3 = st.tabs(["Cadastrar equipamento", "Lista moderna", "Painel 360°"])

    with tab1:
        st.subheader("Novo equipamento")
        pode_cadastrar = escopo_service.pode_gerenciar_cadastros()
        if not pode_cadastrar:
            st.warning("Seu perfil está em modo consulta para cadastro de equipamentos.")
        if not setores:
            st.warning("Cadastre pelo menos um setor antes de criar equipamentos.")
        with st.form("form_equipamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código")
                nome = st.text_input("Nome do equipamento")
                tipo = st.selectbox("Tipo", TIPOS_EQUIPAMENTO)
                setor = st.selectbox("Setor", setores, format_func=lambda x: x["nome"], disabled=not setores) if setores else None
            with col2:
                km_atual = st.number_input("KM atual", min_value=0.0, step=1.0)
                horas_atual = st.number_input("Horas atuais", min_value=0.0, step=1.0)
                template_rev = st.selectbox("Template de revisão", [None] + templates_rev, format_func=lambda t: t["nome"] if t else "— nenhum —")
                template_lub = st.selectbox("Template de lubrificação", [None] + templates_lub, format_func=lambda t: t["nome"] if t else "— nenhum —")
            ativo = st.checkbox("Ativo", value=True)
            submitted = st.form_submit_button("Salvar equipamento", use_container_width=True, disabled=(not setores or not pode_cadastrar))
        if submitted:
            if not codigo.strip() or not nome.strip():
                st.error("Informe código e nome do equipamento.")
            elif not setor:
                st.error("Selecione um setor.")
            else:
                equipamentos_service.criar_completo(
                    codigo=codigo.strip(), nome=nome.strip(), tipo=tipo, setor_id=setor["id"], km_atual=km_atual,
                    horas_atual=horas_atual, template_revisao_id=template_rev["id"] if template_rev else None,
                    template_lubrificacao_id=template_lub["id"] if template_lub else None, ativo=ativo,
                )
                st.success("Equipamento cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if equipamentos:
            _render_lista_moderna(equipamentos, setores)
        else:
            st.info("Nenhum equipamento encontrado.")

    with tab3:
        if not equipamentos:
            st.info("Nenhum equipamento encontrado.")
        else:
            default_id = st.session_state.get("painel_360_equipamento_id")
            opcoes = {f"{e['codigo']} - {e['nome']}": e["id"] for e in equipamentos}
            labels = list(opcoes.keys())
            index_default = 0
            if default_id:
                for i, label in enumerate(labels):
                    if opcoes[label] == default_id:
                        index_default = i
                        break
            selecionado = st.selectbox("Escolha um equipamento", labels, index=index_default)
            st.session_state["painel_360_equipamento_id"] = opcoes[selecionado]
            _mostrar_painel_360(opcoes[selecionado])
