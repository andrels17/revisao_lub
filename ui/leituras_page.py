import pandas as pd
import streamlit as st

from services import equipamentos_service, responsaveis_service, leituras_service
from ui.exportacao import botao_exportar_excel


def _fmt_eqp(e):
    return f"{e['codigo']} — {e['nome']}  (KM: {e['km_atual']:.0f} | H: {e['horas_atual']:.0f})"


def _grafico_evolucao(dados: list, tipo_leitura: str):
    """Gráfico de linha mostrando a evolução de KM ou horas ao longo do tempo."""
    if not dados:
        return

    df = pd.DataFrame(dados)
    df["data_leitura"] = pd.to_datetime(df["data_leitura"])
    df = df.sort_values("data_leitura")

    if tipo_leitura == "horas":
        cols = {"data_leitura": "Data", "horas_valor": "Horas"}
        y_col = "Horas"
    elif tipo_leitura == "km":
        cols = {"data_leitura": "Data", "km_valor": "KM"}
        y_col = "KM"
    else:
        # ambos — mostra KM e Horas
        cols = {"data_leitura": "Data", "km_valor": "KM", "horas_valor": "Horas"}
        y_col = ["KM", "Horas"]

    df_plot = df.rename(columns=cols)[["Data"] + (y_col if isinstance(y_col, list) else [y_col])]
    df_plot = df_plot.set_index("Data")

    # Remove zeros iniciais para não distorcer o gráfico
    df_plot = df_plot[(df_plot > 0).any(axis=1)]
    if df_plot.empty:
        return

    st.line_chart(df_plot, use_container_width=True)


def render():
    st.title("Leituras de KM / Horas")
    st.caption("Atualize os hodômetros e horímetros dos equipamentos. Cada atualização fica registrada no histórico.")

    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    tab1, tab2 = st.tabs(["Registrar leitura", "Histórico e evolução"])

    with tab1:
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp)
        if not eqp:
            return

        with st.form("form_leitura", clear_on_submit=True):
            tipo_leitura = st.selectbox(
                "O que atualizar",
                ["ambos", "horas", "km"],
                format_func=lambda x: {"ambos": "KM e Horas", "km": "Apenas KM", "horas": "Apenas Horas"}[x],
            )
            c1, c2 = st.columns(2)
            with c1:
                km_valor = st.number_input(
                    "KM atual", min_value=0.0,
                    value=float(eqp.get("km_atual") or 0), step=1.0,
                    disabled=(tipo_leitura == "horas"),
                )
                data_leitura = st.date_input("Data da leitura")
            with c2:
                horas_valor = st.number_input(
                    "Horas atuais", min_value=0.0,
                    value=float(eqp.get("horas_atual") or 0), step=1.0,
                    disabled=(tipo_leitura == "km"),
                )
                resp = st.selectbox(
                    "Responsável (opcional)",
                    [None] + responsaveis,
                    format_func=lambda r: r["nome"] if r else "— nenhum —",
                ) if responsaveis else None

            obs    = st.text_input("Observações (opcional)")
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True)

        if salvar:
            leituras_service.registrar(
                equipamento_id=eqp["id"],
                tipo_leitura=tipo_leitura,
                km_valor=km_valor     if tipo_leitura in ("km", "ambos")    else None,
                horas_valor=horas_valor if tipo_leitura in ("horas", "ambos") else None,
                data_leitura=data_leitura,
                responsavel_id=resp["id"] if resp else None,
                observacoes=obs.strip() or None,
            )
            st.success("Leitura registrada e equipamento atualizado.")
            st.rerun()

    with tab2:
        eqp_hist = st.selectbox(
            "Equipamento",
            equipamentos,
            format_func=lambda e: f"{e['codigo']} — {e['nome']}",
            key="leit_hist_eqp",
        )
        if not eqp_hist:
            return

        dados = leituras_service.listar_por_equipamento(eqp_hist["id"], limite=100)

        if not dados:
            st.info("Nenhuma leitura registrada para este equipamento.")
            return

        # Detecta o tipo predominante para o gráfico
        tipos = [d["tipo_leitura"] for d in dados]
        tem_km    = any(t in ("km",    "ambos") for t in tipos)
        tem_horas = any(t in ("horas", "ambos") for t in tipos)
        tipo_graf = "ambos" if (tem_km and tem_horas) else ("horas" if tem_horas else "km")

        st.subheader("Evolução ao longo do tempo")
        _grafico_evolucao(dados, tipo_graf)

        st.subheader(f"Histórico ({len(dados)} leituras)")
        df = pd.DataFrame(dados)

        col_exp = st.columns([5, 1])[1]
        with col_exp:
            botao_exportar_excel(df, f"leituras_{eqp_hist['codigo']}", label="⬇️ Excel", key="exp_leit")

        st.dataframe(df, use_container_width=True, hide_index=True)
