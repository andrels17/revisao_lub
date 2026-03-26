import pandas as pd
import streamlit as st
from services import equipamentos_service, responsaveis_service, leituras_service


def _fmt_eqp(e):
    return f"{e['codigo']} - {e['nome']} (KM: {e['km_atual']:.0f} | H: {e['horas_atual']:.0f})"


def render():
    st.title("Leituras de KM / Horas")
    st.caption("Atualize os hodômetros e horímetros dos equipamentos. Cada atualização fica registrada no histórico.")

    equipamentos = equipamentos_service.listar()
    responsaveis = responsaveis_service.listar()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    tab1, tab2 = st.tabs(["Registrar leitura", "Histórico"])

    with tab1:
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp)
        if not eqp:
            return

        with st.form("form_leitura", clear_on_submit=True):
            tipo_leitura = st.selectbox(
                "O que atualizar",
                ["ambos", "horas", "km"],
                format_func=lambda x: {
                    "ambos": "KM e Horas",
                    "km": "Apenas KM",
                    "horas": "Apenas Horas",
                }[x],
            )
            c1, c2 = st.columns(2)
            with c1:
                km_valor = st.number_input(
                    "KM atual",
                    min_value=0.0,
                    value=float(eqp.get("km_atual") or 0),
                    step=1.0,
                    disabled=(tipo_leitura == "horas"),
                )
                data_leitura = st.date_input("Data da leitura")
            with c2:
                horas_valor = st.number_input(
                    "Horas atuais",
                    min_value=0.0,
                    value=float(eqp.get("horas_atual") or 0),
                    step=1.0,
                    disabled=(tipo_leitura == "km"),
                )
                if responsaveis:
                    resp = st.selectbox(
                        "Responsável (opcional)",
                        [None] + responsaveis,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                    )
                else:
                    resp = None

            obs = st.text_input("Observações (opcional)")
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True)

        if salvar:
            leituras_service.registrar(
                equipamento_id=eqp["id"],
                tipo_leitura=tipo_leitura,
                km_valor=km_valor if tipo_leitura in ("km", "ambos") else None,
                horas_valor=horas_valor if tipo_leitura in ("horas", "ambos") else None,
                data_leitura=data_leitura,
                responsavel_id=resp["id"] if resp else None,
                observacoes=obs.strip() or None,
            )
            st.success("Leitura registrada e equipamento atualizado.")
            st.rerun()

    with tab2:
        eqp_hist = st.selectbox(
            "Equipamento", equipamentos,
            format_func=lambda e: f"{e['codigo']} - {e['nome']}",
            key="leit_hist_eqp",
        )
        if eqp_hist:
            dados = leituras_service.listar_por_equipamento(eqp_hist["id"])
            if dados:
                st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma leitura registrada para este equipamento.")
