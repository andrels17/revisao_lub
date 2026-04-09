import pandas as pd
import streamlit as st
from services import (
    equipamentos_service,
    setores_service,
    templates_integracao_service,
    templates_lubrificacao_service,
    templates_revisao_service,
)
from ui.theme import render_page_intro

TIPOS_CONTROLE = ["horas", "km"]
TIPOS_PRODUTO = [
    "Óleo motor", "Óleo hidráulico", "Óleo câmbio", "Óleo diferencial",
    "Graxa", "Filtro de óleo", "Filtro de ar", "Filtro de combustível",
    "Filtro hidráulico", "Filtro de cabine", "Outro",
]


def _inject_templates_css():
    st.markdown(
        """
        <style>
        .tmpl-note, .tmpl-link-card, .tmpl-distrib-card {
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            background: rgba(15,27,45,.92);
            box-shadow: 0 12px 28px rgba(15,23,42,.04);
            margin-bottom: .85rem;
        }
        .tmpl-link-card h4 {margin:0 0 .2rem 0;color:#ecf3ff;font-size:1rem;font-weight:800;}
        .tmpl-link-card p, .tmpl-note p, .tmpl-distrib-card p {margin:.15rem 0 0 0;color:#9db0c7;font-size:.88rem;}
        .tmpl-chip {
            display:inline-block;
            padding:.2rem .55rem;
            border-radius:999px;
            background: rgba(99,102,241,.14);
            color: #c7d2fe;
            font-size:.74rem;
            font-weight:700;
            margin-right:.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fmt_unidade(tipo_controle: str) -> str:
    return "h" if (tipo_controle or "").lower() == "horas" else "km"


def _render_templates_revisao():
    st.markdown("### Templates de revisão")
    st.caption("Use o template como plano/ciclo do equipamento. Agora você também pode editar etapas e trocar km/horas sem recriar o template.")
    templates = templates_revisao_service.listar_com_etapas()
    tab_lista, tab_novo = st.tabs(["Existentes", "Novo template"])

    with tab_novo:
        with st.form("form_tmpl_rev", clear_on_submit=True):
            nome = st.text_input("Nome do template", placeholder="Ex: Revisão 20.000 km")
            tipo_controle = st.selectbox("Tipo de controle", TIPOS_CONTROLE)
            etapas_raw = st.text_input(
                "Intervalos separados por vírgula",
                placeholder="Ex: 5000, 10000, 15000, 20000",
                help="Cada número representa uma etapa do ciclo do plano.",
            )
            submitted = st.form_submit_button("Salvar template", type="primary", use_container_width=True)

        if submitted:
            if not nome.strip():
                st.error("Informe o nome do template.")
            elif not etapas_raw.strip():
                st.error("Informe ao menos um intervalo.")
            else:
                try:
                    unidade = _fmt_unidade(tipo_controle)
                    valores = sorted({float(v.strip()) for v in etapas_raw.split(",") if v.strip()})
                    etapas = [{"nome_etapa": f"Revisão {int(v)}{unidade}", "gatilho_valor": v} for v in valores]
                    templates_revisao_service.criar(nome.strip(), tipo_controle, etapas)
                    st.success(f"Template criado com {len(etapas)} etapa(s).")
                    st.rerun()
                except ValueError:
                    st.error("Valores inválidos. Use números separados por vírgula.")

    with tab_lista:
        if not templates:
            st.info("Nenhum template cadastrado.")
            return
        for t in templates:
            unidade = _fmt_unidade(t["tipo_controle"])
            resumo = ", ".join(f"{int(e['gatilho_valor'])}{unidade}" for e in t["etapas"]) or "sem etapas"
            with st.expander(f"**{t['nome']}** — {resumo}"):
                with st.form(f"form_edit_tmpl_rev_{t['id']}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        novo_nome = st.text_input("Nome do template", value=t["nome"])
                    with c2:
                        idx_tipo = 0 if t["tipo_controle"] == "horas" else 1
                        novo_tipo = st.selectbox("Tipo de controle", TIPOS_CONTROLE, index=idx_tipo)
                    salvar_cabecalho = st.form_submit_button("Salvar dados do template", type="secondary")
                if salvar_cabecalho:
                    templates_revisao_service.atualizar_template(t["id"], novo_nome.strip(), novo_tipo)
                    st.success("Template atualizado.")
                    st.rerun()

                if t["etapas"]:
                    st.markdown("**Etapas do ciclo**")
                    for etapa in t["etapas"]:
                        with st.form(f"form_edit_etapa_{etapa['id']}"):
                            c1, c2, c3 = st.columns([2, 1, 1])
                            with c1:
                                nome_etapa = st.text_input("Nome da etapa", value=etapa["nome_etapa"], key=f"nome_etapa_{etapa['id']}")
                            with c2:
                                gatilho = st.number_input(
                                    f"Intervalo ({unidade})",
                                    min_value=1.0,
                                    step=50.0,
                                    value=float(etapa["gatilho_valor"]),
                                    key=f"gatilho_{etapa['id']}",
                                )
                            with c3:
                                st.write("")
                                st.write("")
                                salvar = st.form_submit_button("Salvar etapa")
                            if salvar:
                                templates_revisao_service.atualizar_etapa(etapa["id"], nome_etapa.strip(), gatilho)
                                st.success("Etapa atualizada.")
                                st.rerun()
                else:
                    st.info("Este template ainda não possui etapas.")

                st.markdown("**Adicionar etapa**")
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    ne = st.text_input("Nome", key=f"ne_{t['id']}")
                with c2:
                    ve = st.number_input(f"({unidade})", min_value=1.0, step=50.0, key=f"ve_{t['id']}")
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("Adicionar", key=f"add_e_{t['id']}"):
                        if ne.strip():
                            templates_revisao_service.adicionar_etapa(t["id"], ne.strip(), ve)
                            st.success("Etapa adicionada.")
                            st.rerun()
                        else:
                            st.error("Informe o nome.")


def _render_templates_lubrificacao():
    st.markdown("### Templates de lubrificação")
    st.caption("Cadastre itens com os intervalos de troca/coleta. Exemplo: troca e coleta de óleo a cada 10.000 km.")
    templates = templates_lubrificacao_service.listar_com_itens()
    tab_lista, tab_novo = st.tabs(["Existentes", "Novo template"])

    with tab_novo:
        with st.form("form_tmpl_lub", clear_on_submit=True):
            nome = st.text_input("Nome do template", placeholder="Ex: Lubrificação 10.000 km")
            tipo_controle = st.selectbox("Tipo de controle", TIPOS_CONTROLE)
            submitted = st.form_submit_button("Criar template", type="primary", use_container_width=True)
        if submitted:
            if not nome.strip():
                st.error("Informe o nome.")
            else:
                templates_lubrificacao_service.criar(nome.strip(), tipo_controle)
                st.success("Template criado. Adicione os itens na aba de existentes.")
                st.rerun()

    with tab_lista:
        if not templates:
            st.info("Nenhum template cadastrado.")
            return
        for t in templates:
            unidade = _fmt_unidade(t["tipo_controle"])
            n = len(t["itens"])
            with st.expander(f"**{t['nome']}** — {n} item(ns) | {t['tipo_controle']}"):
                if t["itens"]:
                    df = pd.DataFrame(t["itens"])[["nome_item", "tipo_produto", "intervalo_valor"]]
                    df.columns = ["Item", "Produto", f"Intervalo ({unidade})"]
                    st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown("**Adicionar item**")
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                with c1:
                    ni = st.text_input("Nome do item", key=f"ni_{t['id']}", placeholder="Ex: Óleo motor")
                with c2:
                    tp = st.selectbox("Produto", [""] + TIPOS_PRODUTO, key=f"tp_{t['id']}")
                with c3:
                    iv = st.number_input(f"({unidade})", min_value=1.0, step=25.0, key=f"iv_{t['id']}")
                with c4:
                    st.write("")
                    st.write("")
                    if st.button("Adicionar", key=f"add_i_{t['id']}"):
                        if ni.strip():
                            templates_lubrificacao_service.adicionar_item(t["id"], ni.strip(), tp or None, iv)
                            st.success("Item adicionado.")
                            st.rerun()
                        else:
                            st.error("Informe o nome.")


def _render_integracao_revisao_lubrificacao():
    st.markdown("### Integração revisão × lubrificação")
    st.caption("Vincule os planos e visualize em quais etapas da revisão os itens de lubrificação entram juntos.")
    revisoes = templates_revisao_service.listar_com_etapas()
    lubrificacoes = templates_lubrificacao_service.listar_com_itens()
    vinculos = templates_integracao_service.listar_vinculos()

    st.markdown(
        """
        <div class="tmpl-note">
            <span class="tmpl-chip">Exemplo prático</span>
            <p>Se a revisão tem etapas em 5.000 / 10.000 / 15.000 / 20.000 km e a troca/coleta de óleo acontece a cada 10.000 km,
            o sistema mostra que os itens de lubrificação entram nas etapas de 10.000 e 20.000 km, mas não em 5.000 km.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not revisoes or not lubrificacoes:
        st.info("Cadastre ao menos um template de revisão e um de lubrificação para usar a integração.")
        return

    opcoes_rev = {f"{t['nome']} ({t['tipo_controle']})": t for t in revisoes}
    rev_label = st.selectbox("Template de revisão", list(opcoes_rev.keys()))
    revisao = opcoes_rev[rev_label]

    lub_filtradas = [t for t in lubrificacoes if t.get("tipo_controle") == revisao.get("tipo_controle")]
    if not lub_filtradas:
        st.warning("Não há template de lubrificação compatível com o mesmo tipo de controle.")
        return

    opcoes_lub = {f"{t['nome']} ({t['tipo_controle']})": t for t in lub_filtradas}
    lub_label = st.selectbox("Template de lubrificação complementar", list(opcoes_lub.keys()))
    lubrificacao = opcoes_lub[lub_label]
    observacoes = st.text_input(
        "Observação opcional",
        placeholder="Ex: usar este par nos tratores da linha X",
    )

    analise = templates_integracao_service.analisar_compatibilidade(revisao, lubrificacao)
    if not analise.get("ok"):
        st.warning(analise.get("motivo") or "Não foi possível analisar a compatibilidade.")
    else:
        resumo = analise["resumo"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Etapas revisão", resumo["etapas"])
        c2.metric("Itens lubrificação", resumo["itens"])
        c3.metric("Etapas com lubrificação", resumo["etapas_com_lubrificacao"])
        c4.metric("Etapas sem lubrificação", resumo["etapas_sem_lubrificacao"])

        df = pd.DataFrame(analise["linhas"])[["etapa", "gatilho_valor", "dispara_lubrificacao", "itens_acionados"]]
        unidade = _fmt_unidade(analise["tipo_controle"])
        df.columns = ["Etapa de revisão", f"Gatilho ({unidade})", "Aciona lubrificação?", "Itens de lubrificação"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Salvar vínculo revisão × lubrificação", type="primary", use_container_width=True):
            try:
                templates_integracao_service.salvar_vinculo(revisao["id"], lubrificacao["id"], observacoes)
                st.success("Vínculo salvo.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível salvar o vínculo: {exc}")
                st.code(templates_integracao_service.DDL_VINCULOS, language="sql")

    st.divider()
    st.markdown("#### Sugestões automáticas")
    sugestoes = templates_integracao_service.sugerir_vinculos_automaticos()
    if not sugestoes:
        st.info("Nenhuma sugestão automática no momento.")
    else:
        for sug in sugestoes:
            st.markdown(
                f"""
                <div class="tmpl-link-card">
                    <h4>{sug['template_revisao_nome']} → {sug['template_lubrificacao_nome']}</h4>
                    <p>{sug['motivo']} · Cobertura estimada: {sug['cobertura']:.0%}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Salvar sugestão", key=f"save_sug_{sug['template_revisao_id']}_{sug['template_lubrificacao_id']}", use_container_width=True):
                templates_integracao_service.salvar_vinculo(
                    sug["template_revisao_id"],
                    sug["template_lubrificacao_id"],
                    "Vínculo sugerido automaticamente pelo sistema.",
                )
                st.success("Sugestão salva.")
                st.rerun()

    st.divider()
    st.markdown("#### Vínculos salvos")
    if not vinculos:
        st.info("Nenhum vínculo salvo ainda.")
        return

    for vinculo in vinculos:
        titulo = f"{vinculo['template_revisao_nome']} ↔ {vinculo['template_lubrificacao_nome']}"
        with st.expander(titulo):
            c1, c2, c3 = st.columns([1, 1, 1])
            c1.metric("Equipamentos com este par", vinculo.get("equipamentos_vinculados", 0))
            c2.metric("Status", "Ativo" if vinculo.get("ativo", True) else "Inativo")
            c3.metric("Controle", vinculo.get("tipo_controle") or "-")
            st.caption(vinculo.get("observacoes") or "Sem observações.")

            ativo_atual = bool(vinculo.get("ativo", True))
            alvo = st.radio(
                "Aplicar este vínculo na operação?",
                options=[True, False],
                format_func=lambda x: "Sim" if x else "Não",
                index=0 if ativo_atual else 1,
                horizontal=True,
                key=f"ativo_vinc_{vinculo['id']}",
            )
            obs_edit = st.text_input(
                "Observações do vínculo",
                value=vinculo.get("observacoes") or "",
                key=f"obs_vinc_{vinculo['id']}",
            )
            c4, c5 = st.columns(2)
            if c4.button("Salvar vínculo", key=f"save_vinc_{vinculo['id']}", use_container_width=True):
                templates_integracao_service.atualizar_vinculo(vinculo["id"], ativo=alvo, observacoes=obs_edit)
                st.success("Vínculo atualizado.")
                st.rerun()
            if c5.button("Desativar", key=f"disable_vinc_{vinculo['id']}", use_container_width=True):
                templates_integracao_service.atualizar_vinculo(vinculo["id"], ativo=False, observacoes=obs_edit)
                st.success("Vínculo desativado.")
                st.rerun()


def _normalizar_hierarquia_setores(setores: list[dict]) -> dict:
    mapa = {str(s["id"]): s for s in setores}
    hier = {}
    for s in setores:
        atual = s
        caminho = [s.get("nome") or "-"]
        while atual.get("setor_pai_id"):
            pai = mapa.get(str(atual["setor_pai_id"]))
            if not pai:
                break
            caminho.append(pai.get("nome") or "-")
            atual = pai
        caminho = list(reversed(caminho))
        depto = caminho[0] if caminho else (s.get("nome") or "-")
        grupo = caminho[1] if len(caminho) > 1 else "—"
        hier[str(s["id"])] = {"departamento": depto, "grupo": grupo, "setor": s.get("nome") or "-"}
    return hier


def _render_distribuicao_templates():
    st.markdown("### Distribuição de templates")
    st.caption("Popular rapidamente planos de revisão e lubrificação por departamento, grupo e equipamentos, sem precisar entrar item a item.")

    equipamentos = equipamentos_service.listar()
    setores = setores_service.listar()
    templates_rev = templates_revisao_service.listar_com_etapas()
    templates_lub = templates_lubrificacao_service.listar_com_itens()

    if not equipamentos:
        st.info("Nenhum equipamento encontrado para distribuição.")
        return

    hier = _normalizar_hierarquia_setores(setores)
    rows = []
    for eq in equipamentos:
        h = hier.get(str(eq.get("setor_id")), {"departamento": eq.get("setor_nome") or "-", "grupo": "—", "setor": eq.get("setor_nome") or "-"})
        rows.append({
            **eq,
            **h,
            "label": f"{eq.get('codigo') or '-'} · {eq.get('nome') or '-'}",
        })

    departamentos = sorted({r["departamento"] for r in rows if r.get("departamento")})
    dep_sel = st.multiselect("Departamentos", departamentos)
    filtrados = [r for r in rows if not dep_sel or r["departamento"] in dep_sel]

    grupos = sorted({r["grupo"] for r in filtrados if r.get("grupo") and r["grupo"] != "—"})
    grp_sel = st.multiselect("Grupos", grupos)
    filtrados = [r for r in filtrados if not grp_sel or r["grupo"] in grp_sel]

    equipamentos_opcoes = {r["label"]: r for r in filtrados}
    eq_labels = st.multiselect("Equipamentos", list(equipamentos_opcoes.keys()))
    selecionados = [equipamentos_opcoes[l] for l in eq_labels] if eq_labels else filtrados

    c1, c2, c3 = st.columns(3)
    c1.metric("Equipamentos no escopo", len(filtrados))
    c2.metric("Selecionados para atualizar", len(selecionados))
    c3.metric("Com plano atual", sum(1 for r in selecionados if r.get("template_revisao_id") or r.get("template_lubrificacao_id")))

    rev_opcoes = {"— manter como está —": None}
    rev_opcoes.update({f"{t['nome']} ({t['tipo_controle']})": t["id"] for t in templates_rev})
    lub_opcoes = {"— manter como está —": None}
    lub_opcoes.update({f"{t['nome']} ({t['tipo_controle']})": t["id"] for t in templates_lub})

    c4, c5 = st.columns(2)
    rev_label = c4.selectbox("Template de revisão para aplicar", list(rev_opcoes.keys()))
    lub_label = c5.selectbox("Template de lubrificação para aplicar", list(lub_opcoes.keys()))

    st.markdown(
        f"""
        <div class="tmpl-distrib-card">
            <span class="tmpl-chip">Ação em lote</span>
            <p>Você pode aplicar apenas revisão, apenas lubrificação ou os dois de uma vez. O filtro por departamento/grupo ajuda a popular rapidamente o sistema após o cadastro dos planos.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Aplicar templates ao escopo selecionado", type="primary", use_container_width=True):
        if not selecionados:
            st.warning("Selecione ao menos um equipamento.")
        elif rev_opcoes[rev_label] is None and lub_opcoes[lub_label] is None:
            st.warning("Escolha ao menos um template para aplicar.")
        else:
            atualizados = equipamentos_service.aplicar_templates_em_lote(
                [r["id"] for r in selecionados],
                template_revisao_id=rev_opcoes[rev_label],
                template_lubrificacao_id=lub_opcoes[lub_label],
            )
            st.success(f"Templates aplicados em {atualizados} equipamento(s).")
            st.rerun()

    preview = pd.DataFrame(
        [
            {
                "Departamento": r["departamento"],
                "Grupo": r["grupo"],
                "Equipamento": r["label"],
                "Revisão atual": str(r.get("template_revisao_id") or "—"),
                "Lubrificação atual": str(r.get("template_lubrificacao_id") or "—"),
            }
            for r in selecionados[:200]
        ]
    )
    if not preview.empty:
        st.dataframe(preview, use_container_width=True, hide_index=True)


def render():
    _inject_templates_css()
    render_page_intro(
        "Templates",
        "Gerencie os planos/ciclos de revisão e lubrificação, integre os dois mundos e distribua rapidamente para os equipamentos.",
        badge="Cadastros",
    )

    tab_rev, tab_lub, tab_integracao, tab_distrib = st.tabs([
        "Revisões",
        "Lubrificações",
        "Integração",
        "Distribuição",
    ])
    with tab_rev:
        _render_templates_revisao()
    with tab_lub:
        _render_templates_lubrificacao()
    with tab_integracao:
        _render_integracao_revisao_lubrificacao()
    with tab_distrib:
        _render_distribuicao_templates()
