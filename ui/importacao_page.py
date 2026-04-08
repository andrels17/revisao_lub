import streamlit as st
from services import importacao_service, setores_service


def render():
    st.title("Importação de Equipamentos")
    st.caption("Importe múltiplos equipamentos de uma vez via planilha CSV ou Excel.")

    tab_import, tab_template = st.tabs(["Importar arquivo", "Baixar modelo"])

    with tab_template:
        st.markdown("**Modelo de planilha para importação**")
        st.write("Baixe o modelo, preencha e importe:")
        csv_bytes = importacao_service.get_template_csv()
        st.download_button(
            "⬇️ Baixar modelo CSV",
            data=csv_bytes,
            file_name="modelo_equipamentos.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.markdown("**Colunas:**")
        st.markdown(
            "- `codigo` *(obrigatório)* — código único\n"
            "- `nome` *(obrigatório)* — nome do equipamento\n"
            "- `tipo` — Trator, Caminhão, Máquina, etc.\n"
            "- `setor` — nome exato do setor cadastrado\n"
            "- `km_atual` — hodômetro atual\n"
            "- `horas_atual` — horímetro atual\n"
            "- `placa` — placa do veículo\n"
            "- `serie` — número de série"
        )

    with tab_import:
        setores = setores_service.listar()
        setor_padrao = None
        if setores:
            setor_padrao_obj = st.selectbox(
                "Setor padrão (usado quando a coluna 'setor' não bater com nenhum setor cadastrado)",
                [None] + [s for s in setores if s.get("ativo")],
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

            st.success(
                f"Arquivo lido: **{resultado['linhas_ok']}** linha(s) válida(s)"
                + (f" | {resultado['linhas_erro']} com erro" if resultado["linhas_erro"] else "")
            )

            if resultado["erros"]:
                with st.expander("Ver erros de validação"):
                    for e in resultado["erros"]:
                        st.warning(e)

            st.markdown("**Preview (primeiras 10 linhas)**")
            st.dataframe(resultado["preview"], use_container_width=True, hide_index=True)

            if resultado["linhas_ok"] > 0:
                atualizar = st.checkbox(
                    "Atualizar equipamentos já existentes (pelo código)",
                    value=False,
                    help="Se marcado, equipamentos com código duplicado terão nome, tipo, setor e leituras atualizados. Se desmarcado, duplicados são ignorados.",
                )
                if st.button("✅ Confirmar importação", use_container_width=True, type="primary"):
                    res = importacao_service.importar(
                        resultado["df"],
                        setor_padrao_id=setor_padrao,
                        atualizar_duplicados=atualizar,
                    )
                    msg = f"Importação concluída: **{res['importados']}** importado(s)"
                    if res.get("atualizados"):
                        msg += f" | **{res['atualizados']}** atualizado(s)"
                    if res["duplicados"]:
                        msg += f" | {res['duplicados']} duplicado(s) ignorado(s)"
                    st.success(msg)
                    if res["erros"]:
                        for e in res["erros"]:
                            st.error(e)
