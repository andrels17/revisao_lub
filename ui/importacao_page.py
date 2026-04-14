import streamlit as st

from services import escopo_service, importacao_service
from ui.theme import render_page_intro

MODO_LABELS = {
    importacao_service.MODO_IGNORAR: "Ignorar duplicados",
    importacao_service.MODO_ATUALIZAR: "Atualizar cadastro existente",
    importacao_service.MODO_PREENCHER_VAZIOS: "Preencher apenas campos vazios + consolidar KM/Horas",
}


def _render_resumo(resultado: dict):
    resumo = resultado.get("resumo", {})
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Linhas do arquivo", resumo.get("total_linhas", 0))
    c2.metric("Novas", resumo.get("novas", 0))
    c3.metric("Duplicadas", resumo.get("duplicadas_sistema", 0))
    c4.metric("Com aviso", resumo.get("com_aviso", 0))
    c5.metric("Com erro", resumo.get("com_erro", 0))
    c6.metric("Setores a criar", resumo.get("setores_novos", 0))


def _render_preview_setores(resultado: dict):
    preview = resultado.get("preview_full")
    if preview is None or preview.empty:
        return

    cols_prioridade = [
        "codigo",
        "nome",
        "setor",
        "setor_resolvido",
        "ação_setor",
        "ação",
        "status",
        "km_atual",
        "horas_atual",
        "placa",
        "serie",
    ]
    cols = [c for c in cols_prioridade if c in preview.columns] + [c for c in preview.columns if c not in cols_prioridade]
    st.markdown("### Pré-validação da importação")
    st.dataframe(preview[cols], use_container_width=True, hide_index=True)

    setores_criar = resultado.get("setores_a_criar") or []
    if setores_criar:
        with st.expander(f"Setores que serão criados automaticamente ({len(setores_criar)})"):
            for item in setores_criar:
                caminho = item.get("caminho_original") or item.get("nome")
                st.write(f"- {caminho}")


def render():
    render_page_intro(
        "Importação em lote de equipamentos",
        "Faça carga inicial ou atualização em massa com criação automática de setores, pré-validação e confirmação.",
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
        st.markdown(
            """
- `codigo` *(obrigatório)* — código único
- `nome` *(obrigatório)* — nome do equipamento
- `tipo` — Trator, Caminhão, Máquina, etc.
- `setor` — aceita nome simples ou hierarquia, por exemplo: `Operação > Caminhões`
- `km_atual` — hodômetro atual
- `horas_atual` — horímetro atual
- `placa` — placa do veículo
- `serie` — número de série
"""
        )
        st.info("Quando um setor não existir, ele será criado automaticamente durante a importação.")

    with tab_import:
        st.caption("Sem setor padrão: o sistema usa o setor da planilha. Se não existir, cria automaticamente.")
        arquivo = st.file_uploader("Selecione o arquivo CSV ou Excel", type=["csv", "xlsx", "xls"])

        if not arquivo:
            return

        file_bytes = arquivo.read()
        resultado = importacao_service.processar_arquivo(file_bytes, arquivo.name)
        if "erro" in resultado:
            st.error(resultado["erro"])
            if resultado.get("detalhe"):
                st.caption(f"Mapeamentos aceitos: {resultado['detalhe']}")
            return

        if resultado.get("colunas_reconhecidas"):
            reconhecidas = ", ".join(
                [f"{destino} ← {origem}" for destino, origem in resultado["colunas_reconhecidas"].items()]
            )
            st.caption(f"Colunas reconhecidas automaticamente: {reconhecidas}")

        _render_resumo(resultado)

        st.success(
            f"Arquivo lido: **{resultado['linhas_ok']}** linha(s) válida(s)"
            + (f" | {resultado['linhas_erro']} com erro" if resultado["linhas_erro"] else "")
        )

        if resultado.get("erros"):
            with st.expander("Ver erros de validação"):
                for e in resultado["erros"]:
                    st.warning(e)

        if resultado.get("avisos"):
            with st.expander("Ver avisos e conflitos detectados"):
                for a in resultado["avisos"]:
                    st.info(a)

        _render_preview_setores(resultado)

        if resultado["linhas_ok"] <= 0:
            return

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
                setor_padrao_id=None,
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
            if res.get("setores_criados"):
                msg += f" | **{res['setores_criados']}** setor(es) criado(s)"
            if res.get("duplicados"):
                msg += f" | {res['duplicados']} duplicado(s) ignorado(s)"
            st.success(msg)

            if res.get("erros"):
                for e in res["erros"]:
                    st.error(e)
