import datetime

import pandas as pd
import streamlit as st

from services import equipamentos_service, responsaveis_service, leituras_service
from ui.exportacao import botao_exportar_excel


def _fmt_eqp(e):
    return f"{e['codigo']} — {e['nome']}  (KM: {e['km_atual']:.0f} | H: {e['horas_atual']:.0f})"


def _grafico_evolucao(dados: list, tipo_leitura: str):
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
        cols  = {"data_leitura": "Data", "km_valor": "KM", "horas_valor": "Horas"}
        y_col = ["KM", "Horas"]

    df_plot = df.rename(columns=cols)[["Data"] + (y_col if isinstance(y_col, list) else [y_col])]
    df_plot = df_plot.set_index("Data")
    df_plot = df_plot[(df_plot > 0).any(axis=1)]
    if not df_plot.empty:
        st.line_chart(df_plot, use_container_width=True)


def render():
    render_page_intro("Leituras de KM e horas", "Registre medições com foco operacional e uma experiência visual mais limpa para o dia a dia.", "Operação")
    st.caption("Atualize os hodômetros e horímetros dos equipamentos.")

    with st.spinner("Carregando equipamentos…"):
        equipamentos = equipamentos_service.listar()
        responsaveis = responsaveis_service.listar()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    tab1, tab2 = st.tabs(["Registrar leitura", "Histórico e evolução"])

    # ── Aba 1: registro com validação ─────────────────────────────────────────
    with tab1:
        eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp)
        if not eqp:
            return

        km_atual    = float(eqp.get("km_atual")    or 0)
        horas_atual = float(eqp.get("horas_atual") or 0)

        # Leituras atuais visíveis antes do form
        c_km, c_h = st.columns(2)
        c_km.metric("KM atual registrado",    f"{km_atual:.0f} km")
        c_h.metric("Horas atuais registradas", f"{horas_atual:.0f} h")

        st.divider()

        tipo_leitura = st.selectbox(
            "O que atualizar",
            ["ambos", "horas", "km"],
            format_func=lambda x: {"ambos": "KM e Horas", "km": "Apenas KM", "horas": "Apenas Horas"}[x],
        )

        with st.form("form_leitura", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                km_valor = st.number_input(
                    "Novo KM", min_value=0.0,
                    value=km_atual, step=1.0,
                    disabled=(tipo_leitura == "horas"),
                )
                data_leitura = st.date_input("Data da leitura", value=datetime.date.today())
            with c2:
                horas_valor = st.number_input(
                    "Novas Horas", min_value=0.0,
                    value=horas_atual, step=1.0,
                    disabled=(tipo_leitura == "km"),
                )
                resp = st.selectbox(
                    "Responsável (opcional)",
                    [None] + responsaveis,
                    format_func=lambda r: r["nome"] if r else "— nenhum —",
                ) if responsaveis else None

            obs    = st.text_input("Observações (opcional)")
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True)

        # Validação e confirmação FORA do form (Streamlit não permite widgets dentro de form após submit)
        if salvar:
            avisos = []

            if tipo_leitura in ("km", "ambos") and km_valor < km_atual:
                avisos.append(
                    f"⚠️ O KM informado **{km_valor:.0f}** é menor que o atual **{km_atual:.0f}**. "
                    "Isso pode indicar um erro de digitação."
                )
            if tipo_leitura in ("horas", "ambos") and horas_valor < horas_atual:
                avisos.append(
                    f"⚠️ As horas informadas **{horas_valor:.0f}** são menores que as atuais **{horas_atual:.0f}**. "
                    "Isso pode indicar um erro de digitação."
                )

            if avisos:
                for aviso in avisos:
                    st.warning(aviso)

                confirmar_key = f"confirmar_leit_{eqp['id']}"
                if confirmar_key not in st.session_state:
                    st.session_state[confirmar_key] = False

                col_sim, col_nao, _ = st.columns([1, 1, 3])
                with col_sim:
                    if st.button("✅ Confirmar mesmo assim", key=f"btn_sim_{eqp['id']}",
                                 type="primary"):
                        st.session_state[confirmar_key] = True
                with col_nao:
                    if st.button("❌ Cancelar", key=f"btn_nao_{eqp['id']}"):
                        st.session_state.pop(confirmar_key, None)
                        st.info("Leitura cancelada.")

                if st.session_state.get(confirmar_key):
                    _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor,
                                    data_leitura, resp, obs, permitir_regressao=True)
                    st.session_state.pop(confirmar_key, None)
            else:
                _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor,
                                data_leitura, resp, obs)

    # ── Aba 2: histórico ──────────────────────────────────────────────────────
    with tab2:
        eqp_hist = st.selectbox(
            "Equipamento",
            equipamentos,
            format_func=lambda e: f"{e['codigo']} — {e['nome']}",
            key="leit_hist_eqp",
        )
        if not eqp_hist:
            return

        with st.spinner("Carregando histórico…"):
            dados = leituras_service.listar_por_equipamento(eqp_hist["id"], limite=100)

        if not dados:
            st.info("Nenhuma leitura registrada para este equipamento.")
            return

        tipos     = [d["tipo_leitura"] for d in dados]
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


def _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor, data_leitura, resp, obs, permitir_regressao=False):
    try:
        leituras_service.registrar(
            equipamento_id=eqp["id"],
            tipo_leitura=tipo_leitura,
            km_valor=km_valor      if tipo_leitura in ("km",    "ambos") else None,
            horas_valor=horas_valor if tipo_leitura in ("horas", "ambos") else None,
            data_leitura=data_leitura,
            responsavel_id=resp["id"] if resp else None,
            observacoes=obs.strip() or None,
            permitir_regressao=permitir_regressao,
        )
        st.success(f"✅ Leitura registrada com sucesso para **{eqp['codigo']} — {eqp['nome']}**.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar leitura: {e}")
