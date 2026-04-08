import streamlit as st

from services import escopo_service, importacao_service, setores_service
from ui.theme import render_page_intro

MODO_LABELS = {
    importacao_service.MODO_IGNORAR: "Ignorar duplicados",
    importacao_service.MODO_ATUALIZAR: "Atualizar cadastro existente",
    importacao_service.MODO_PREENCHER_VAZIOS: "Preencher apenas campos vazios + consolidar KM/Horas",
}


def render():
    render_page_intro(
        "Importação em lote de equipamentos",
        "Faça carga inicial ou atualização em massa com uma área mais limpa para arquivo, validação e confirmação.",
        "Ferramentas",
    )
    st.info(f"Escopo atual: {escopo_service.resumo_escopo()}")

    if not escopo_service.pode_importar():
        st.warning("Somente administradores podem importar equipamentos nesta fase.")
        return

    tab_import, tab_template = st.tabs(["Importar arquivo", "Baixar modelo"])

    with tab_template:
        st.markdown("### Modelo de planilha")
        st.write("Baixe o modelo, preencha e importe:")
        csv_bytes = importacao_service.get_template_csv()
        st.download_button(
            "Baixar modelo CSV",
            data=csv_bytes,
            file_name="modelo_equipamentos.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.markdown("""
- `codigo` *(obrigatório)* — código único
- `nome` *(obrigatório)* — nome do equipamento
- `tipo` — Trator, Caminhão, Máquina, etc.
- `setor` — nome exato do setor cadastrado
- `km_atual` — hodômetro atual
- `horas_atual` — horímetro atual
- `placa` — placa do veículo
- `serie` — número de série
""")

    with tab_import:
        setores = [s for s in setores_service.listar() if s.get("ativo")]
        setor_padrao = None
        if setores:
            setor_padrao_obj = st.selectbox(
                "Setor padrão (usado quando a coluna 'setor' não bater com nenhum setor cadastrado)",
                [None] + setores,
                format_func=lambda s: s["nome"] if s else "— nenhum —",
            )
            setor_padrao = setor_padrao_obj["id"] if setor_padrao_obj else None

        arquivo = st.file_uploader("Selecione o arquivo CSV ou Excel", type=["csv", "xlsx", "xls"])

        if arquivo:
            file_bytes = arquivo.read()
            resultado = importacao_service.processar_arquivo(file_bytes, arquivo.name)
            if "erro" in resultado:
                st.error(resultado["erro"])
                return

            resumo = resultado.get("resumo", {})
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Linhas do arquivo", resumo.get("total_linhas", 0))
            c2.metric("Novas", resumo.get("novas", 0))
            c3.metric("Duplicadas", resumo.get("duplicadas_sistema", 0))
            c4.metric("Com aviso", resumo.get("com_aviso", 0))
            c5.metric("Com erro", resumo.get("com_erro", 0))

            st.success(
                f"Arquivo lido: **{resultado['linhas_ok']}** linha(s) válida(s)"
                + (f" | {resultado['linhas_erro']} com erro" if resultado["linhas_erro"] else "")
            )

            if resultado["erros"]:
                with st.expander("Ver erros de validação"):
                    for e in resultado["erros"]:
                        st.warning(e)

            if resultado.get("avisos"):
                with st.expander("Ver avisos e conflitos detectados"):
                    for a in resultado["avisos"]:
                        st.info(a)

            st.markdown("### Pré-validação da importação")
            st.dataframe(resultado["preview_full"], use_container_width=True, hide_index=True)

            if resultado["linhas_ok"] > 0:
                modo = st.radio(
                    "Tratamento de códigos já existentes",
                    options=list(MODO_LABELS.keys()),
                    format_func=lambda item: MODO_LABELS[item],
                    horizontal=False,
                )
                st.caption("Use a opção de preencher vazios para enriquecer o cadastro sem sobrescrever dados principais já consolidados.")

                if st.button("Confirmar importação", use_container_width=True, type="primary"):
                    barra = st.progress(0, text="Iniciando importação…")
                    status_txt = st.empty()

                    def _progresso(atual, total, codigo):
                        pct = int(atual / total * 100) if total else 100
                        barra.progress(pct, text=f"Processando {atual}/{total} — {codigo}")
                        status_txt.caption(f"{atual} de {total} linhas processadas")

                    res = importacao_service.importar(
                        resultado["df"],
                        setor_padrao_id=setor_padrao,
                        modo_duplicados=modo,
                        progress_callback=_progresso,
                    )

                    barra.progress(100, text="Concluído!")
                    status_txt.empty()

                    msg = f"Importação concluída: **{res['importados']}** importado(s)"
                    if res.get("atualizados"):
                        msg += f" | **{res['atualizados']}** atualizado(s)"
                    if res.get("preenchidos_vazios"):
                        msg += f" | **{res['preenchidos_vazios']}** enriquecido(s)"
                    if res["duplicados"]:
                        msg += f" | {res['duplicados']} duplicado(s) ignorado(s)"
                    st.success(msg)
                    if res["erros"]:
                        for e in res["erros"]:
                            st.error(e)
