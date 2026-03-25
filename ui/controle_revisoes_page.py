import streamlit as st
import pandas as pd

from services import equipamentos_service
from services import revisoes_service

def render():
    st.title("Controle de Revisões")

    equipamentos = equipamentos_service.listar()

    dados = []

    for eqp in equipamentos:
        revisoes = revisoes_service.calcular_proximas_revisoes(eqp["id"])

        if revisoes:
            prox = revisoes[0]

            dados.append({
                "Equipamento": f"{eqp['codigo']} - {eqp['nome']}",
                "Etapa": prox["etapa"],
                "Atual": prox["atual"],
                "Vencimento": prox["vencimento"],
                "Status": prox["status"],
                "Falta": prox["diferenca"]
            })

    if dados:
        st.dataframe(pd.DataFrame(dados), use_container_width=True)
    else:
        st.info("Nenhum dado encontrado.")
