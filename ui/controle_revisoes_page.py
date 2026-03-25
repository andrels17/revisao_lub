import streamlit as st
import pandas as pd
from services import revisoes_service

STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}
STATUS_LABEL = {"VENCIDO": "🔴 Vencido", "PROXIMO": "🟡 Próximo", "EM DIA": "🟢 Em dia"}


def _carregar_pendencias():
    dados = revisoes_service.listar_controle_revisoes()
    if not dados:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "equipamento_id": item["equipamento_id"],
                "setor": item["setor_nome"] or "-",
                "Equipamento": f'{item["codigo"]} - {item["equipamento_nome"]}',
                "Etapa": item["etapa"],
                "Controle": item["tipo_controle"] or "-",
                "Atual": float(item["leitura_atual"] or 0),
                "Última execução": float(item["ultima_execucao"] or 0),
                "Vencimento": float(item["vencimento"] or 0),
                "Status": item["status"],
                "Falta": float(item["falta"] or 0),
                "_ordem": STATUS_ORDEM.get(item["status"], 99),
            }
            for item in dados
        ]
    )

    return df.sort_values(by=["_ordem", "Falta", "Equipamento"]).drop(columns=["_ordem"])


def render():
    st.title("Controle de Revisões")

    pendencias_df = _carregar_pendencias()

    if pendencias_df.empty:
        st.info("Nenhuma revisão encontrada.")
        return

    df = pendencias_df.copy()

    setores = sorted(df["setor"].dropna().unique().tolist())

    col1, col2 = st.columns([2, 1])
    with col1:
        setores_selecionados = st.multiselect("Filtrar por setor", setores)
    with col2:
        status_filtro = st.selectbox(
            "Filtrar por status",
            ["Todos", "VENCIDO", "PROXIMO", "EM DIA"],
        )

    if setores_selecionados:
        df = df[df["setor"].isin(setores_selecionados)]

    if status_filtro != "Todos":
        df = df[df["Status"] == status_filtro]

    if df.empty:
        st.info("Nenhum resultado para os filtros.")
        return

    df_view = df.copy()
    df_view["Status"] = df_view["Status"].map(lambda x: STATUS_LABEL.get(x, x))

    st.dataframe(df_view, use_container_width=True, hide_index=True)
