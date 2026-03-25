import pandas as pd
import streamlit as st
from services import equipamentos_service, setores_service


TIPOS_EQUIPAMENTO = [
    "Caminhão",
    "Trator",
    "Colheitadeira",
    "Pulverizador",
    "Implemento",
    "Máquina",
    "Outro",
]


def render():
    st.title("Equipamentos")
    equipamentos = equipamentos_service.listar()
    setores = [item for item in setores_service.listar() if item.get("ativo")]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de equipamentos", len(equipamentos))
    c2.metric("Com setor vinculado", sum(1 for item in equipamentos if item.get("setor_id")))
    c3.metric("Com template", sum(1 for item in equipamentos if item.get("template_revisao_id")))

    tab1, tab2 = st.tabs(["Cadastrar equipamento", "Lista de equipamentos"])

    with tab1:
        st.subheader("Novo equipamento")
        if not setores:
            st.warning("Cadastre pelo menos um setor antes de criar equipamentos.")
        with st.form("form_equipamento", clear_on_submit=True):
            codigo = st.text_input("Código")
            nome = st.text_input("Nome do equipamento")
            tipo = st.selectbox("Tipo", TIPOS_EQUIPAMENTO)
            setor = st.selectbox(
                "Setor",
                setores,
                format_func=lambda x: x["nome"],
                disabled=not setores,
            ) if setores else None
            col1, col2 = st.columns(2)
            with col1:
                km_atual = st.number_input("KM atual", min_value=0.0, step=1.0)
            with col2:
                horas_atual = st.number_input("Horas atuais", min_value=0.0, step=1.0)
            template_raw = st.text_input("ID do template de revisão (opcional)")
            ativo = st.checkbox("Ativo", value=True)
            submitted = st.form_submit_button("Salvar equipamento", use_container_width=True, disabled=not setores)

        if submitted:
            if not codigo.strip() or not nome.strip():
                st.error("Informe código e nome do equipamento.")
            elif not setor:
                st.error("Selecione um setor.")
            else:
                template_revisao_id = int(template_raw) if template_raw.strip() else None
                equipamentos_service.criar(
                    codigo=codigo.strip(),
                    nome=nome.strip(),
                    tipo=tipo,
                    setor_id=setor["id"],
                    km_atual=km_atual,
                    horas_atual=horas_atual,
                    template_revisao_id=template_revisao_id,
                    ativo=ativo,
                )
                st.success("Equipamento cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if equipamentos:
            df = pd.DataFrame(equipamentos)
            df = df.rename(
                columns={
                    "codigo": "Código",
                    "nome": "Nome",
                    "tipo": "Tipo",
                    "km_atual": "KM atual",
                    "horas_atual": "Horas atuais",
                    "template_revisao_id": "Template",
                    "setor_nome": "Setor",
                }
            )
            colunas = [
                "Código",
                "Nome",
                "Tipo",
                "Setor",
                "KM atual",
                "Horas atuais",
                "Template",
            ]
            st.dataframe(df[colunas], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento encontrado.")
