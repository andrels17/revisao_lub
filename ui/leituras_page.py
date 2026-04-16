import datetime
import html

import pandas as pd
import streamlit as st

from services import equipamentos_service, leituras_service, responsaveis_service
from ui.exportacao import botao_exportar_excel


PLOTLY_COLORS = {
    "km": "#4f8cff",
    "horas": "#22c55e",
    "axis": "rgba(157,176,199,.36)",
    "grid": "rgba(157,176,199,.12)",
    "font": "#dbe9ff",
    "muted": "#9db0c7",
}


@st.cache_data(ttl=90, show_spinner=False)
def _carregar_base():
    return equipamentos_service.listar(), responsaveis_service.listar()


@st.cache_data(ttl=90, show_spinner=False)
def _carregar_historico(equipamento_id: str, limite: int = 100):
    return leituras_service.listar_por_equipamento(equipamento_id, limite=limite)


def _fmt_eqp(e):
    controle = 'KM' if (e.get('tipo_controle') or 'km') == 'km' else 'Horas'
    return f"{e['codigo']} — {e['nome']}  ({controle} | KM: {float(e.get('km_atual') or 0):.0f} | H: {float(e.get('horas_atual') or 0):.0f})"


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">🧾 Operação</div>
            <h2>Leituras de KM / horas</h2>
            <p>Atualize hodômetros e horímetros com um fluxo mais direto, visual mais limpo e histórico pronto para consulta e auditoria.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(equipamentos: list[dict]) -> None:
    total = len(equipamentos)
    com_km = sum(1 for e in equipamentos if float(e.get("km_atual") or 0) > 0)
    com_horas = sum(1 for e in equipamentos if float(e.get("horas_atual") or 0) > 0)
    sem_leitura = sum(
        1
        for e in equipamentos
        if float(e.get("km_atual") or 0) <= 0 and float(e.get("horas_atual") or 0) <= 0
    )

    cards = [
        ("status-info", "🧩 Base monitorada", total, "Equipamentos disponíveis"),
        ("status-info", "🛣️ Com KM ativo", com_km, "Hodômetro preenchido"),
        ("status-success", "⏱️ Com horas ativas", com_horas, "Horímetro preenchido"),
        ("status-warning", "📝 Sem leitura inicial", sem_leitura, "Requer primeira coleta"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{html.escape(str(label))}</div><div class='value'>{int(value)}</div><div class='sub'>{html.escape(str(sub))}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def _apply_plotly_theme(fig, height: int):
    fig.update_layout(
        height=height,
        margin=dict(t=16, b=10, l=8, r=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PLOTLY_COLORS["font"], size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOTLY_COLORS["muted"]),
        ),
        xaxis=dict(
            showgrid=False,
            linecolor=PLOTLY_COLORS["axis"],
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=PLOTLY_COLORS["grid"],
            zeroline=False,
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        hoverlabel=dict(bgcolor="#0f1b2d", font_color="#eef5ff", bordercolor="#1f3350"),
    )
    return fig


def _grafico_evolucao(dados: list, tipo_leitura: str):
    if not dados:
        st.info("Nenhuma leitura registrada para exibir no gráfico.")
        return

    df = pd.DataFrame(dados).copy()
    df["data_leitura"] = pd.to_datetime(df["data_leitura"])
    df = df.sort_values("data_leitura")

    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        if tipo_leitura in ("km", "ambos"):
            km_df = df[df["km_valor"].fillna(0) > 0]
            if not km_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=km_df["data_leitura"],
                        y=km_df["km_valor"],
                        mode="lines+markers",
                        name="KM",
                        line=dict(color=PLOTLY_COLORS["km"], width=3),
                        marker=dict(size=7, color=PLOTLY_COLORS["km"]),
                        hovertemplate="%{x|%d/%m/%Y}<br>KM: %{y:.0f}<extra></extra>",
                    )
                )
        if tipo_leitura in ("horas", "ambos"):
            horas_df = df[df["horas_valor"].fillna(0) > 0]
            if not horas_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=horas_df["data_leitura"],
                        y=horas_df["horas_valor"],
                        mode="lines+markers",
                        name="Horas",
                        line=dict(color=PLOTLY_COLORS["horas"], width=3),
                        marker=dict(size=7, color=PLOTLY_COLORS["horas"]),
                        hovertemplate="%{x|%d/%m/%Y}<br>Horas: %{y:.0f}<extra></extra>",
                    )
                )

        if not fig.data:
            st.info("Sem valores positivos suficientes para montar a evolução.")
            return

        _apply_plotly_theme(fig, 360)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        cols = {"data_leitura": "Data", "km_valor": "KM", "horas_valor": "Horas"}
        df = df.rename(columns=cols)
        series = ["Data"]
        if tipo_leitura in ("km", "ambos"):
            series.append("KM")
        if tipo_leitura in ("horas", "ambos"):
            series.append("Horas")
        st.line_chart(df[series].set_index("Data"), use_container_width=True)


def _determinar_tipo_grafico(dados: list, escolha: str):
    if escolha != "automatico":
        return escolha
    tipos = [d.get("tipo_leitura") for d in dados]
    tem_km = any(t in ("km", "ambos") for t in tipos)
    tem_horas = any(t in ("horas", "ambos") for t in tipos)
    if tem_km and tem_horas:
        return "ambos"
    if tem_horas:
        return "horas"
    return "km"


def _resumo_historico(dados: list[dict]) -> None:
    ultima = dados[0] if dados else None
    ultimo_resp = ultima.get("responsavel") if ultima else "-"
    ultima_data = (
        pd.to_datetime(ultima.get("data_leitura")).strftime("%d/%m/%Y")
        if ultima and ultima.get("data_leitura")
        else "-"
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Leituras registradas", len(dados))
    col2.metric("Última coleta", ultima_data)
    col3.metric("Responsável mais recente", ultimo_resp)


def render():
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True):
            _carregar_base.clear()
            _carregar_historico.clear()
            st.rerun()

    st.markdown(
        "<div class='section-caption'>Registre medições, acompanhe a evolução por equipamento e mantenha a operação com menos ruído visual.</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando base operacional…"):
        equipamentos, responsaveis = _carregar_base()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    _render_kpi_cards(equipamentos)

    tab1, tab2 = st.tabs(["Registrar leitura", "Histórico e evolução"])

    with tab1:
        st.markdown("<div class='filters-shell'><div class='filters-title'>Registro operacional</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="leit_reg_eqp")
        with col2:
            controle_eq = (eqp.get('tipo_controle') or 'km').lower()
            opcoes_leitura = ['km'] if controle_eq == 'km' else ['horas']
            tipo_leitura = st.selectbox(
                "O que atualizar",
                opcoes_leitura,
                format_func=lambda x: {"ambos": "KM e Horas", "km": "Apenas KM", "horas": "Apenas Horas"}[x],
            )
            st.caption(f"Controle oficial do equipamento: {'KM / hodômetro' if controle_eq == 'km' else 'Horas / horímetro'}")
        st.markdown("</div>", unsafe_allow_html=True)

        if not eqp:
            return

        km_atual = float(eqp.get("km_atual") or 0)
        horas_atual = float(eqp.get("horas_atual") or 0)
        hist_preview = _carregar_historico(eqp["id"], limite=1)
        ultima_data = (
            pd.to_datetime(hist_preview[0]["data_leitura"]).strftime("%d/%m/%Y") if hist_preview else "-"
        )

        c_km, c_h, c_u = st.columns(3)
        c_km.metric("KM atual registrado", f"{km_atual:.0f} km")
        c_h.metric("Horas atuais registradas", f"{horas_atual:.0f} h")
        c_u.metric("Última coleta", ultima_data)

        with st.form("form_leitura", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                km_valor = st.number_input(
                    "Novo KM",
                    min_value=0.0,
                    value=km_atual,
                    step=1.0,
                    disabled=(tipo_leitura == "horas"),
                )
                data_leitura = st.date_input("Data da leitura", value=datetime.date.today())
            with c2:
                horas_valor = st.number_input(
                    "Novas Horas",
                    min_value=0.0,
                    value=horas_atual,
                    step=1.0,
                    disabled=(tipo_leitura == "km"),
                )
                resp = (
                    st.selectbox(
                        "Responsável (opcional)",
                        [None] + responsaveis,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                    )
                    if responsaveis
                    else None
                )

            obs = st.text_input("Observações (opcional)")
            salvar = st.form_submit_button("Salvar leitura", use_container_width=True, type="primary")

        if salvar:
            avisos = []
            if tipo_leitura in ("km", "ambos") and km_valor < km_atual:
                avisos.append(
                    f"⚠️ O KM informado **{km_valor:.0f}** é menor que o atual **{km_atual:.0f}**. Isso pode indicar um erro de digitação."
                )
            if tipo_leitura in ("horas", "ambos") and horas_valor < horas_atual:
                avisos.append(
                    f"⚠️ As horas informadas **{horas_valor:.0f}** são menores que as atuais **{horas_atual:.0f}**. Isso pode indicar um erro de digitação."
                )

            if avisos:
                for aviso in avisos:
                    st.warning(aviso)

                confirmar_key = f"confirmar_leit_{eqp['id']}"
                if confirmar_key not in st.session_state:
                    st.session_state[confirmar_key] = False

                col_sim, col_nao, _ = st.columns([1, 1, 3])
                with col_sim:
                    if st.button("✅ Confirmar mesmo assim", key=f"btn_sim_{eqp['id']}", type="primary"):
                        st.session_state[confirmar_key] = True
                with col_nao:
                    if st.button("❌ Cancelar", key=f"btn_nao_{eqp['id']}"):
                        st.session_state.pop(confirmar_key, None)
                        st.info("Leitura cancelada.")

                if st.session_state.get(confirmar_key):
                    _salvar_leitura(
                        eqp,
                        tipo_leitura,
                        km_valor,
                        horas_valor,
                        data_leitura,
                        resp,
                        obs,
                        permitir_regressao=True,
                    )
                    st.session_state.pop(confirmar_key, None)
            else:
                _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor, data_leitura, resp, obs)

    with tab2:
        st.markdown("<div class='filters-shell'><div class='filters-title'>Análise e histórico</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            eqp_hist = st.selectbox(
                "Equipamento",
                equipamentos,
                format_func=lambda e: f"{e['codigo']} — {e['nome']}",
                key="leit_hist_eqp",
            )
        with col2:
            modo = st.selectbox(
                "Visualização",
                ["automatico", "ambos", "km", "horas"],
                format_func=lambda x: {
                    "automatico": "Automático",
                    "ambos": "KM e Horas",
                    "km": "Apenas KM",
                    "horas": "Apenas Horas",
                }[x],
            )
        st.markdown("</div>", unsafe_allow_html=True)

        if not eqp_hist:
            return

        with st.spinner("Carregando histórico…"):
            dados = _carregar_historico(eqp_hist["id"], limite=100)

        if not dados:
            st.info("Nenhuma leitura registrada para este equipamento.")
            return

        tipo_graf = _determinar_tipo_grafico(dados, modo)
        _resumo_historico(dados)

        st.subheader("Evolução ao longo do tempo")
        _grafico_evolucao(dados, tipo_graf)

        st.subheader(f"Histórico ({len(dados)} leituras)")
        df = pd.DataFrame(dados).rename(
            columns={
                "data_leitura": "Data",
                "tipo_leitura": "Tipo",
                "km_valor": "KM",
                "horas_valor": "Horas",
                "responsavel": "Responsável",
                "observacoes": "Observações",
            }
        )
        col_exp = st.columns([5, 1])[1]
        with col_exp:
            botao_exportar_excel(df, f"leituras_{eqp_hist['codigo']}", label="⬇️ Excel", key="exp_leit")
        st.dataframe(df, use_container_width=True, hide_index=True)


def _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor, data_leitura, resp, obs, permitir_regressao=False):
    try:
        leituras_service.registrar(
            equipamento_id=eqp["id"],
            tipo_leitura=tipo_leitura,
            km_valor=km_valor if tipo_leitura in ("km", "ambos") else None,
            horas_valor=horas_valor if tipo_leitura in ("horas", "ambos") else None,
            data_leitura=data_leitura,
            responsavel_id=resp["id"] if resp else None,
            observacoes=obs.strip() or None,
            permitir_regressao=permitir_regressao,
        )
        _carregar_base.clear()
        _carregar_historico.clear()
        st.success(f"✅ Leitura registrada com sucesso para **{eqp['codigo']} — {eqp['nome']}**.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar leitura: {e}")
