import pandas as pd
import streamlit as st

from services import equipamentos_service, execucoes_service, responsaveis_service, revisoes_service

STATUS_LABEL = {
    "VENCIDO": "🔴 Vencido",
    "PROXIMO": "🟡 Próximo",
    "EM DIA": "🔵 Programado",
}


def render():
    st.title("Controle de Revisões")

    dados = revisoes_service.listar_controle_revisoes()

    if not dados:
        st.info("Nenhuma revisão encontrada.")
        return

    df = pd.DataFrame(dados)

    df["Equipamento"] = df["codigo"] + " - " + df["equipamento_nome"]
    df["Status"] = df["status"].map(lambda x: STATUS_LABEL.get(x, x))

    df_pendencias = df[df["status"].isin(["VENCIDO", "PROXIMO"])]

    st.subheader("Pendências")
    if not df_pendencias.empty:
        st.dataframe(df_pendencias, use_container_width=True)
    else:
        st.info("Nenhuma pendência.")

    st.subheader("Programadas")
    df_prog = df[df["status"] == "EM DIA"]
    if not df_prog.empty:
        st.dataframe(df_prog, use_container_width=True)
    else:
        st.info("Nenhuma programada.")
