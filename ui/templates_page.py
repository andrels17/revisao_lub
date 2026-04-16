from __future__ import annotations

import pandas as pd
import streamlit as st
from utils import numero_input_br

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
        .tmpl-note, .tmpl-link-card, .tmpl-distrib-card, .tmpl-check-row {
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            background: rgba(15,27,45,.92);
            box-shadow: 0 12px 28px rgba(15,23,42,.04);
            margin-bottom: .85rem;
        }
        .tmpl-link-card h4 {margin:0 0 .2rem 0;color:#ecf3ff;font-size:1rem;font-weight:800;}
        .tmpl-link-card p, .tmpl-note p, .tmpl-distrib-card p, .tmpl-check-row p {margin:.15rem 0 0 0;color:#9db0c7;font-size:.88rem;}
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
        .tmpl-mini-muted {color:#94a3b8;font-size:.83rem;}
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
                                gatilho = numero_input_br(
                                    f"Intervalo ({unidade})",
                                    value=float(etapa["gatilho_valor"]),
                                    key=f"gatilho_{etapa['id']}",
                                    placeholder="Ex.: 1.234,56",
                                    casas_preview=0 if unidade == "km" else 1,
                                )
                            with c3:
                                st.write("")
                                st.write("")
                                salvar = st.form_submit_button("Salvar etapa")
                            if salvar:
                                if gatilho is None:
                                    st.error("Informe um intervalo válido.")
                                else:
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
                    ve = numero_input_br(f"({unidade})", value=0, key=f"ve_{t['id']}", placeholder="Ex.: 1.234,56", casas_preview=0 if unidade == "km" else 1)
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("Adicionar", key=f"add_e_{t['id']}"):
                        if not ne.strip():
                            st.error("Informe o nome.")
                        elif ve is None:
                            st.error("Informe um intervalo válido.")
                        else:
                            templates_revisao_service.adicionar_etapa(t["id"], ne.strip(), ve)
                            st.success("Etapa adicionada.")
                            st.rerun()



def _render_templates_lubrificacao():
    st.markdown("### Templates de lubrificação")
    st.caption("Agora a lubrificação também pode ser editada como a revisão: cabeçalho do template e itens sem precisar recriar tudo.")
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
                with st.form(f"form_edit_tmpl_lub_{t['id']}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        novo_nome = st.text_input("Nome do template", value=t["nome"], key=f"tmpl_lub_nome_{t['id']}")
                    with c2:
                        idx_tipo = 0 if t["tipo_controle"] == "horas" else 1
                        novo_tipo = st.selectbox("Tipo de controle", TIPOS_CONTROLE, index=idx_tipo, key=f"tmpl_lub_tipo_{t['id']}")
                    salvar_cabecalho = st.form_submit_button("Salvar dados do template", type="secondary")
                if salvar_cabecalho:
                    templates_lubrificacao_service.atualizar_template(t["id"], novo_nome.strip(), novo_tipo)
                    st.success("Template atualizado.")
                    st.rerun()

                if t["itens"]:
                    st.markdown("**Itens do plano**")
                    for item in t["itens"]:
                        with st.form(f"form_edit_item_lub_{item['id']}"):
                            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                            with c1:
                                nome_item = st.text_input("Nome do item", value=item["nome_item"], key=f"item_nome_{item['id']}")
                            with c2:
                                produto = st.selectbox(
                                    "Produto",
                                    [""] + TIPOS_PRODUTO,
                                    index=([""] + TIPOS_PRODUTO).index(item["tipo_produto"]) if item["tipo_produto"] in TIPOS_PRODUTO else 0,
                                    key=f"item_prod_{item['id']}",
                                )
                            with c3:
                                intervalo = numero_input_br(
                                    f"Intervalo ({unidade})",
                                    value=float(item["intervalo_valor"]),
                                    key=f"item_int_{item['id']}",
                                    placeholder="Ex.: 1.234,56",
                                    casas_preview=0 if unidade == "km" else 1,
                                )
                            with c4:
                                st.write("")
                                st.write("")
                                salvar = st.form_submit_button("Salvar item")
                            if salvar:
                                if intervalo is None:
                                    st.error("Informe um intervalo válido.")
                                else:
                                    templates_lubrificacao_service.atualizar_item(item["id"], nome_item.strip(), produto or None, intervalo)
                                    st.success("Item atualizado.")
                                    st.rerun()
                else:
                    st.info("Este template ainda não possui itens.")

                st.markdown("**Adicionar item**")
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                with c1:
                    ni = st.text_input("Nome do item", key=f"ni_{t['id']}", placeholder="Ex: Óleo motor")
                with c2:
                    tp = st.selectbox("Produto", [""] + TIPOS_PRODUTO, key=f"tp_{t['id']}")
                with c3:
                    iv = numero_input_br(f"({unidade})", value=0, key=f"iv_{t['id']}", placeholder="Ex.: 1.234,56", casas_preview=0 if unidade == "km" else 1)
                with c4:
                    st.write("")
                    st.write("")
                    if st.button("Adicionar", key=f"add_i_{t['id']}"):
                        if not ni.strip():
                            st.error("Informe o nome.")
                        elif iv is None:
                            st.error("Informe um intervalo válido.")
                        else:
                            templates_lubrificacao_service.adicionar_item(t["id"], ni.strip(), tp or None, iv)
                            st.success("Item adicionado.")
                            st.rerun()



def _render_integracao_revisao_lubrificacao():
    st.markdown("### Integração revisão × lubrificação")
    st.caption("Agora cada etapa pode ser ligada ou desligada com checkbox. Isso resolve cenários como 5 mil sem óleo e 10 mil com óleo.")
    revisoes = templates_revisao_service.listar_com_etapas()
    lubrificacoes = templates_lubrificacao_service.listar_com_itens()
    vinculos = templates_integracao_service.listar_vinculos()

    st.markdown(
        """
        <div class="tmpl-note">
            <span class="tmpl-chip">Exemplo prático</span>
            <p>Se a revisão tem etapas em 5.000 / 10.000 / 15.000 / 20.000 km e a troca/coleta de óleo ocorre a cada 10.000 km, você pode deixar marcado apenas nas etapas de 10k e 20k.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not revisoes or not lubrificacoes:
        st.info("Cadastre ao menos um template de revisão e um de lubrificação para integrar.")
        return

    mapa_rev = {f"{t['nome']} ({t['tipo_controle']})": t for t in revisoes}
    mapa_lub = {f"{t['nome']} ({t['tipo_controle']})": t for t in lubrificacoes}

    revisao = mapa_rev[st.selectbox("Template de revisão", list(mapa_rev.keys()))]
    lubrificacao = mapa_lub[st.selectbox("Template de lubrificação complementar", list(mapa_lub.keys()))]
    observacoes = st.text_input(
        "Observação opcional",
        placeholder="Ex: usar este par nos tratores da linha X",
    )

    vinculo_existente = templates_integracao_service.obter_vinculo_por_par(revisao["id"], lubrificacao["id"])
    overrides_salvos = templates_integracao_service.listar_overrides_etapas(vinculo_existente["id"]) if vinculo_existente else {}
    analise = templates_integracao_service.analisar_compatibilidade(revisao, lubrificacao, etapa_overrides=overrides_salvos)

    if not analise.get("ok"):
        st.warning(analise.get("motivo") or "Não foi possível analisar a compatibilidade.")
    else:
        resumo = analise["resumo"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Etapas revisão", resumo["etapas"])
        c2.metric("Itens lubrificação", resumo["itens"])
        c3.metric("Etapas com lubrificação", resumo["etapas_com_lubrificacao"])
        c4.metric("Etapas sem lubrificação", resumo["etapas_sem_lubrificacao"])

        st.markdown("#### Ajuste fino por etapa")
        st.caption("Marque apenas as etapas que devem puxar a lubrificação. O valor padrão vem do cálculo automático, mas você pode sobrescrever.")
        etapa_flags = {}
        for linha in analise["linhas"]:
            etapa_id = linha["etapa_id"]
            c1, c2, c3, c4 = st.columns([1.1, 2.2, 1.2, 3.2])
            with c1:
                etapa_flags[etapa_id] = st.checkbox(
                    "Aplicar",
                    value=bool(linha["aplicar_lubrificacao"]),
                    key=f"chk_vinc_{revisao['id']}_{lubrificacao['id']}_{etapa_id}",
                )
            with c2:
                st.markdown(f"**{linha['etapa']}**")
                st.caption(f"Gatilho: {int(linha['gatilho_valor']) if float(linha['gatilho_valor']).is_integer() else linha['gatilho_valor']} {_fmt_unidade(analise['tipo_controle'])}")
            with c3:
                st.markdown("<div class='tmpl-mini-muted'>Sugestão automática</div>", unsafe_allow_html=True)
                st.write("Sim" if linha["aplica_automatico"] else "Não")
            with c4:
                st.markdown("<div class='tmpl-mini-muted'>Itens que entram se marcado</div>", unsafe_allow_html=True)
                st.write(linha["itens_acionados"])

        if st.button("Salvar vínculo revisão × lubrificação", type="primary", use_container_width=True):
            try:
                vinculo_id = templates_integracao_service.salvar_vinculo(revisao["id"], lubrificacao["id"], observacoes)
                templates_integracao_service.salvar_overrides_etapas(vinculo_id, etapa_flags)
                st.success("Vínculo salvo com as marcações por etapa.")
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

            ativo = st.checkbox(
                "Aplicar este vínculo na operação?",
                value=bool(vinculo.get("ativo", True)),
                key=f"ativo_vinc_{vinculo['id']}",
            )
            obs_edit = st.text_input(
                "Observações do vínculo",
                value=vinculo.get("observacoes") or "",
                key=f"obs_vinc_{vinculo['id']}",
            )
            if st.button("Salvar vínculo", key=f"save_vinc_{vinculo['id']}", use_container_width=True):
                templates_integracao_service.atualizar_vinculo(vinculo["id"], ativo=ativo, observacoes=obs_edit)
                st.success("Vínculo atualizado.")
                st.rerun()



def _render_distribuicao_templates():
    st.markdown("### Distribuição de templates")
    st.caption("Popular rapidamente planos de revisão e lubrificação por departamento, grupo e equipamentos, sem precisar entrar item a item.")

    equipamentos = equipamentos_service.listar()
    templates_rev = templates_revisao_service.listar_com_etapas()
    templates_lub = templates_lubrificacao_service.listar_com_itens()

    if not equipamentos:
        st.info("Nenhum equipamento encontrado para distribuição.")
        return

    rows = []
    for eq in equipamentos:
        rows.append({
            **eq,
            "departamento": eq.get("setor_nome") or "-",
            "grupo": eq.get("grupo_nome") or "—",
            "label": f"{eq.get('codigo') or '-'} · {eq.get('nome') or '-'}",
        })

    departamentos = sorted({r["departamento"] for r in rows if r.get("departamento") and r["departamento"] != "-"})
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
        """
        <div class="tmpl-distrib-card">
            <span class="tmpl-chip">Ação em lote</span>
            <p>Agora a distribuição usa o departamento do equipamento e o grupo operacional real, sem depender da hierarquia de setores.</p>
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
