import pandas as pd
import streamlit as st
from services import (
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
        .tmpl-note, .tmpl-link-card {
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            background: rgba(15,27,45,.92);
            box-shadow: 0 12px 28px rgba(15,23,42,.04);
            margin-bottom: .85rem;
        }
        .tmpl-link-card h4 {margin:0 0 .2rem 0;color:#ecf3ff;font-size:1rem;font-weight:800;}
        .tmpl-link-card p, .tmpl-note p {margin:.15rem 0 0 0;color:#9db0c7;font-size:.88rem;}
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


def _render_templates_revisao():
    st.markdown("### Templates de revisão")
    st.caption("Use o template como plano/ciclo do equipamento. Exemplo: ciclo de 20.000 km com etapas em 5.000, 10.000, 15.000 e 20.000.")
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
                    unidade = "h" if tipo_controle == "horas" else "km"
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
            unidade = "h" if t["tipo_controle"] == "horas" else "km"
            resumo = ", ".join(f"{int(e['gatilho_valor'])}{unidade}" for e in t["etapas"]) or "sem etapas"
            with st.expander(f"**{t['nome']}** — {resumo}"):
                st.caption(f"Controle: {t['tipo_controle']}")
                if t["etapas"]:
                    df = pd.DataFrame(t["etapas"])[["nome_etapa", "gatilho_valor"]]
                    df.columns = ["Etapa", f"Intervalo ({unidade})"]
                    st.dataframe(df, use_container_width=True, hide_index=True)
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
            unidade = "h" if t["tipo_controle"] == "horas" else "km"
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
        unidade = "h" if analise["tipo_controle"] == "horas" else "km"
        df.columns = ["Etapa de revisão", f"Gatilho ({unidade})", "Aciona lubrificação?", "Itens de lubrificação"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Salvar vínculo entre templates", type="primary", use_container_width=True):
            try:
                templates_integracao_service.salvar_vinculo(revisao["id"], lubrificacao["id"], observacoes.strip() or None)
                st.success("Vínculo salvo. Agora esse par fica documentado para o time.")
                st.rerun()
            except Exception:
                st.error("A tabela de vínculos ainda não existe no banco. Rode o SQL de migração abaixo.")
                st.code(templates_integracao_service.DDL_VINCULOS, language="sql")

    st.markdown("### Sugestões automáticas")
    sugestoes = templates_integracao_service.sugerir_vinculos_automaticos()
    if not sugestoes:
        st.caption("Nenhuma sugestão nova encontrada. Isso pode acontecer quando todos os pares relevantes já foram salvos.")
    else:
        for sug in sugestoes:
            perc = round(float(sug.get("cobertura") or 0) * 100)
            st.markdown(
                f"""
                <div class="tmpl-link-card">
                    <h4>{sug['template_revisao_nome']} → {sug['template_lubrificacao_nome']}</h4>
                    <p>Compatibilidade: {perc}% das etapas da revisão acionam lubrificação · {sug['motivo']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([1, 3])
            with c1:
                if st.button("Salvar sugestão", key=f"save_sug_{sug['template_revisao_id']}_{sug['template_lubrificacao_id']}", use_container_width=True):
                    try:
                        templates_integracao_service.salvar_vinculo(
                            sug["template_revisao_id"],
                            sug["template_lubrificacao_id"],
                            f"Sugestão automática: {sug['motivo']}"
                        )
                        st.success("Sugestão salva com sucesso.")
                        st.rerun()
                    except Exception:
                        st.error("A tabela de vínculos ainda não existe no banco. Rode o SQL de migração abaixo.")
                        st.code(templates_integracao_service.DDL_VINCULOS, language="sql")
            with c2:
                linhas = (sug.get("analise") or {}).get("linhas") or []
                if linhas:
                    with st.expander("Ver detalhe da sugestão"):
                        df_sug = pd.DataFrame(linhas)[["etapa", "gatilho_valor", "dispara_lubrificacao", "itens_acionados"]]
                        unidade_sug = "h" if sug["tipo_controle"] == "horas" else "km"
                        df_sug.columns = ["Etapa de revisão", f"Gatilho ({unidade_sug})", "Aciona lubrificação?", "Itens de lubrificação"]
                        st.dataframe(df_sug, use_container_width=True, hide_index=True)

    st.markdown("### Vínculos salvos")
    if not vinculos:
        st.info("Nenhum vínculo salvo ainda. Você pode começar usando a análise acima.")
        with st.expander("SQL da migração para salvar vínculos"):
            st.code(templates_integracao_service.DDL_VINCULOS, language="sql")
        return

    for vinculo in vinculos:
        st.markdown(
            f"""
            <div class="tmpl-link-card">
                <h4>{vinculo['template_revisao_nome']} ↔ {vinculo['template_lubrificacao_nome']}</h4>
                <p>Controle: {vinculo['tipo_controle']} · Equipamentos usando este par: {vinculo['equipamentos_vinculados']}</p>
                <p>{vinculo['observacoes'] or 'Sem observações.'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render():
    _inject_templates_css()
    render_page_intro(
        "Templates e planos de manutenção",
        "Gerencie os ciclos de revisão e os itens de lubrificação com uma visão mais clara, incluindo a integração entre os dois planos.",
        "Cadastros",
    )
    revisoes = templates_revisao_service.listar_com_etapas()
    lubrificacoes = templates_lubrificacao_service.listar_com_itens()
    vinculos = templates_integracao_service.listar_vinculos()
    c1, c2, c3 = st.columns(3)
    c1.metric("Templates de revisão", len(revisoes))
    c2.metric("Templates de lubrificação", len(lubrificacoes))
    c3.metric("Pares revisão × lubrificação", len(vinculos))

    tab_rev, tab_lub, tab_int = st.tabs(["Revisão", "Lubrificação", "Integração"])
    with tab_rev:
        _render_templates_revisao()
    with tab_lub:
        _render_templates_lubrificacao()
    with tab_int:
        _render_integracao_revisao_lubrificacao()
