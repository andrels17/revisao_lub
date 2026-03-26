import pandas as pd
import streamlit as st
from services import templates_revisao_service, templates_lubrificacao_service

TIPOS_CONTROLE = ["horas", "km"]
TIPOS_PRODUTO = [
    "Óleo motor", "Óleo hidráulico", "Óleo câmbio", "Óleo diferencial",
    "Graxa", "Filtro de óleo", "Filtro de ar", "Filtro de combustível",
    "Filtro hidráulico", "Filtro de cabine", "Outro",
]


def _render_templates_revisao():
    st.subheader("Templates de Revisão")
    st.caption("Cada etapa representa um intervalo a partir da última execução (ex: 250h, 500h, 1000h).")

    templates = templates_revisao_service.listar_com_etapas()
    tab_lista, tab_novo = st.tabs(["Existentes", "Novo template"])

    with tab_novo:
        with st.form("form_tmpl_rev", clear_on_submit=True):
            nome = st.text_input("Nome do template", placeholder="Ex: Revisão 250/500/1000h")
            tipo_controle = st.selectbox("Tipo de controle", TIPOS_CONTROLE)
            etapas_raw = st.text_input(
                "Intervalos separados por vírgula",
                placeholder="Ex: 250, 500, 750, 1000",
                help="Cada número = intervalo desde a última execução.",
            )
            submitted = st.form_submit_button("Salvar template", use_container_width=True)

        if submitted:
            if not nome.strip():
                st.error("Informe o nome do template.")
            elif not etapas_raw.strip():
                st.error("Informe ao menos um intervalo.")
            else:
                try:
                    unidade = "h" if tipo_controle == "horas" else "km"
                    valores = [float(v.strip()) for v in etapas_raw.split(",") if v.strip()]
                    etapas = [
                        {"nome_etapa": f"Revisão {int(v)}{unidade}", "gatilho_valor": v}
                        for v in valores
                    ]
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
            resumo = ", ".join(
                f"{int(e['gatilho_valor'])}{unidade}" for e in t["etapas"]
            ) or "sem etapas"
            with st.expander(f"**{t['nome']}** — {resumo}"):
                st.caption(f"ID: {t['id']} | Controle: {t['tipo_controle']}")
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
    st.subheader("Templates de Lubrificação")
    st.caption("Defina óleos, graxas e filtros com seus intervalos de troca.")

    templates = templates_lubrificacao_service.listar_com_itens()
    tab_lista, tab_novo = st.tabs(["Existentes", "Novo template"])

    with tab_novo:
        with st.form("form_tmpl_lub", clear_on_submit=True):
            nome = st.text_input("Nome do template", placeholder="Ex: Lubrificação Trator Padrão")
            tipo_controle = st.selectbox("Tipo de controle", TIPOS_CONTROLE)
            submitted = st.form_submit_button("Criar template", use_container_width=True)
        if submitted:
            if not nome.strip():
                st.error("Informe o nome.")
            else:
                templates_lubrificacao_service.criar(nome.strip(), tipo_controle)
                st.success("Template criado. Adicione os itens na aba 'Existentes'.")
                st.rerun()

    with tab_lista:
        if not templates:
            st.info("Nenhum template cadastrado.")
            return
        for t in templates:
            unidade = "h" if t["tipo_controle"] == "horas" else "km"
            n = len(t["itens"])
            with st.expander(f"**{t['nome']}** — {n} item(ns) | {t['tipo_controle']}"):
                st.caption(f"ID: {t['id']}")
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
                            templates_lubrificacao_service.adicionar_item(
                                t["id"], ni.strip(), tp or None, iv
                            )
                            st.success("Item adicionado.")
                            st.rerun()
                        else:
                            st.error("Informe o nome.")


def render():
    st.title("Templates de Manutenção")
    tab_rev, tab_lub = st.tabs(["Revisão", "Lubrificação"])
    with tab_rev:
        _render_templates_revisao()
    with tab_lub:
        _render_templates_lubrificacao()
