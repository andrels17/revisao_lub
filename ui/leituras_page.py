import datetime
import html
import io

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

COLUNAS_MODELO = ["COD_EQUIPAMENTO", "LEITURA_ATUAL", "DATA_LEITURA", "OBSERVACAO", "TIPO_HORIMETRO"]
ALIASES = {
    "codigo": ["cod_equipamento", "codigo", "cod", "equipamento", "frota"],
    "leitura": ["leitura_atual", "km_atual", "valor", "medidor_atual", "leitura"],
    "data": ["data_leitura", "data", "dt_leitura"],
    "obs": ["observacao", "observacoes", "obs"],
    "tipo": ["tipo_horimetro", "tipo_controle", "tipo_medidor"],
}


@st.cache_data(ttl=90, show_spinner=False)
def _carregar_base():
    return equipamentos_service.listar(), responsaveis_service.listar()


@st.cache_data(ttl=90, show_spinner=False)
def _carregar_historico(equipamento_id: str, limite: int = 100):
    return leituras_service.listar_por_equipamento(equipamento_id, limite=limite)


def _fmt_eqp(e):
    controle = "KM" if (e.get("tipo_controle") or "km") == "km" else "Horas"
    return f"{e['codigo']} — {e['nome']}  ({controle} | KM: {float(e.get('km_atual') or 0):.0f} | H: {float(e.get('horas_atual') or 0):.0f})"


def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">🧾 Operação</div>
            <h2>Leituras de KM / horas</h2>
            <p>Atualize hodômetros e horímetros manualmente ou por planilha, com histórico pronto para consulta e auditoria.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(equipamentos: list[dict]) -> None:
    total = len(equipamentos)
    km_controlados = sum(1 for e in equipamentos if (e.get("tipo_controle") or "km") == "km")
    horas_controlados = sum(1 for e in equipamentos if (e.get("tipo_controle") or "km") == "horas")
    sem_leitura = sum(
        1
        for e in equipamentos
        if float(e.get("km_atual") or 0) <= 0 and float(e.get("horas_atual") or 0) <= 0
    )

    cards = [
        ("status-info", "🧩 Base monitorada", total, "Equipamentos disponíveis"),
        ("status-info", "🛣️ Controle por KM", km_controlados, "Cadastro oficial"),
        ("status-success", "⏱️ Controle por horas", horas_controlados, "Cadastro oficial"),
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


def _tipo_oficial(equipamento: dict) -> str:
    return "horas" if (equipamento.get("tipo_controle") or "km") == "horas" else "km"


def _coluna_por_alias(df: pd.DataFrame, chave: str) -> str | None:
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for alias in ALIASES[chave]:
        if alias in mapa:
            return mapa[alias]
    return None


def _ler_arquivo(uploaded_file):
    nome = uploaded_file.name.lower()
    if nome.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file, sep=None, engine="python")
        except Exception:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, sep=";")
    return pd.read_excel(uploaded_file)


def _modelo_bytes() -> bytes:
    exemplo = pd.DataFrame(
        [
            {
                "COD_EQUIPAMENTO": "1010",
                "LEITURA_ATUAL": 159861,
                "DATA_LEITURA": datetime.date.today().isoformat(),
                "OBSERVACAO": "Leitura inicial",
                "TIPO_HORIMETRO": "KM",
            }
        ],
        columns=COLUNAS_MODELO,
    )
    return exemplo.to_csv(index=False, sep=";").encode("utf-8-sig")


def _analisar_arquivo(df: pd.DataFrame, equipamentos: list[dict]) -> dict:
    cod_col = _coluna_por_alias(df, "codigo")
    leitura_col = _coluna_por_alias(df, "leitura")
    data_col = _coluna_por_alias(df, "data")
    obs_col = _coluna_por_alias(df, "obs")
    tipo_col = _coluna_por_alias(df, "tipo")

    if not cod_col or not leitura_col:
        faltantes = []
        if not cod_col:
            faltantes.append("COD_EQUIPAMENTO")
        if not leitura_col:
            faltantes.append("LEITURA_ATUAL")
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

    mapa_eq = {str(e.get("codigo", "")).strip(): e for e in equipamentos}
    preview = []
    validos = []
    invalidos = 0
    avisos = 0
    avisos_regressao = 0
    duplicados = 0
    vistos = {}

    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = str(row.get(cod_col, "") or "").strip()
        if not codigo:
            continue
        leitura_bruta = row.get(leitura_col)
        try:
            leitura_atual = float(leitura_bruta)
        except Exception:
            leitura_atual = None

        equipamento = mapa_eq.get(codigo)
        tipo_planilha = str(row.get(tipo_col, "") or "").strip() if tipo_col else ""
        data_leitura = row.get(data_col) if data_col else None
        observacoes = str(row.get(obs_col, "") or "").strip() if obs_col else None

        if codigo in vistos:
            duplicados += 1
        vistos[codigo] = linha

        motivo = []
        status = "Pronto"
        if not equipamento:
            status = "Erro"
            motivo.append("Equipamento não encontrado")
        if leitura_atual is None:
            status = "Erro"
            motivo.append("Leitura inválida")
        elif leitura_atual < 0:
            status = "Erro"
            motivo.append("Leitura negativa")

        tipo_cadastro = _tipo_oficial(equipamento or {}) if equipamento else "-"
        medidor_atual = None
        tipo_leitura = None
        km_valor = None
        horas_valor = None
        if equipamento and leitura_atual is not None and leitura_atual >= 0:
            tipo_leitura = tipo_cadastro
            if tipo_cadastro == "horas":
                medidor_atual = float(equipamento.get("horas_atual") or 0)
                horas_valor = leitura_atual
            else:
                medidor_atual = float(equipamento.get("km_atual") or 0)
                km_valor = leitura_atual
            permitir_regressao_item = False
            if leitura_atual < medidor_atual:
                status = "Atenção"
                motivo.append("Leitura menor que a atual")
                permitir_regressao_item = True
                avisos += 1
                avisos_regressao += 1
            if tipo_planilha:
                tipo_planilha_norm = "horas" if "hora" in tipo_planilha.lower() or "hr" in tipo_planilha.lower() else "km"
                if tipo_planilha_norm != tipo_cadastro:
                    status = "Atenção"
                    motivo.append("Tipo da planilha diverge do cadastro")
                    avisos += 1

        if status == "Erro":
            invalidos += 1
        else:
            validos.append(
                {
                    "linha": linha,
                    "codigo": codigo,
                    "equipamento_id": equipamento["id"],
                    "tipo_leitura": tipo_leitura,
                    "km_valor": km_valor,
                    "horas_valor": horas_valor,
                    "data_leitura": data_leitura,
                    "observacoes": observacoes or None,
                    "permitir_regressao": permitir_regressao_item,
                }
            )

        preview.append(
            {
                "Linha": linha,
                "Código": codigo,
                "Equipamento": equipamento.get("nome") if equipamento else "-",
                "Controle cadastro": tipo_cadastro,
                "Tipo planilha": tipo_planilha or "-",
                "Leitura": leitura_atual if leitura_atual is not None else "-",
                "Atual cadastrado": medidor_atual if medidor_atual is not None else "-",
                "Status": status,
                "Motivo": "; ".join(motivo) if motivo else "OK",
            }
        )

    return {
        "preview": preview,
        "validos": validos,
        "resumo": {
            "linhas": len(preview),
            "prontos": len(validos),
            "erros": invalidos,
            "avisos": avisos,
            "duplicados": duplicados,
            "avisos_regressao": avisos_regressao,
        },
    }


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
        "<div class='section-caption'>Registre medições, importe planilhas e acompanhe a evolução por equipamento sem ambiguidade entre KM e horas.</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando base operacional…"):
        equipamentos, responsaveis = _carregar_base()

    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    _render_kpi_cards(equipamentos)

    tab1, tab2, tab3 = st.tabs(["Registrar leitura", "Importar planilha", "Histórico e evolução"])

    with tab1:
        st.markdown("<div class='filters-shell'><div class='filters-title'>Registro operacional</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="leit_reg_eqp")
        with col2:
            tipo_oficial = _tipo_oficial(eqp) if eqp else "km"
            st.selectbox(
                "Controle oficial",
                [tipo_oficial],
                format_func=lambda x: "KM" if x == "km" else "Horas",
                disabled=True,
            )
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
        c_km.metric("KM atual registrado", format_medida_br(km_atual, "km", 0))
        c_h.metric("Horas atuais registradas", format_medida_br(horas_atual, "h", 0))
        c_u.metric("Última coleta", ultima_data)

        tipo_leitura = _tipo_oficial(eqp)
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
            if tipo_leitura == "km" and km_valor < km_atual:
                avisos.append(
                    f"⚠️ O KM informado **{format_numero_br(km_valor, 0)}** é menor que o atual **{format_numero_br(km_atual, 0)}**."
                )
            if tipo_leitura == "horas" and horas_valor < horas_atual:
                avisos.append(
                    f"⚠️ As horas informadas **{format_numero_br(horas_valor, 0)}** são menores que as atuais **{format_numero_br(horas_atual, 0)}**."
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
                    _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor, data_leitura, resp, obs, permitir_regressao=True)
                    st.session_state.pop(confirmar_key, None)
            else:
                _salvar_leitura(eqp, tipo_leitura, km_valor, horas_valor, data_leitura, resp, obs)

    with tab2:
        st.markdown("<div class='filters-shell'><div class='filters-title'>Importação assistida</div>", unsafe_allow_html=True)
        top_a, top_b = st.columns([2, 1])
        with top_a:
            st.caption("Use o cadastro oficial do equipamento para decidir automaticamente se a leitura vai para KM ou horas.")
        with top_b:
            st.download_button(
                "⬇️ Baixar modelo",
                data=_modelo_bytes(),
                file_name="modelo_importacao_leituras.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        with st.container(border=True):
            col_u, col_r = st.columns([3, 2])
            with col_u:
                arquivo = st.file_uploader(
                    "Planilha de leituras",
                    type=["csv", "xlsx", "xls"],
                    help="Colunas mínimas: COD_EQUIPAMENTO e LEITURA_ATUAL.",
                )
            with col_r:
                resp_import = (
                    st.selectbox(
                        "Responsável para o lote",
                        [None] + responsaveis,
                        format_func=lambda r: r["nome"] if r else "— nenhum —",
                        key="leit_imp_resp",
                    )
                    if responsaveis
                    else None
                )
                permitir_regressao = st.checkbox("Permitir todas as leituras menores que a atual", value=False)
                importar_atencao_automaticamente = st.checkbox(
                    "Importar automaticamente leituras com atenção (possível reset)",
                    value=True,
                    help="Quando marcado, leituras menores que a atual entram como atenção e são importadas sem bloquear o lote.",
                )
            obs_padrao = st.text_input("Observação padrão do lote (opcional)", key="leit_imp_obs")

        if arquivo is not None:
            try:
                df_upload = _ler_arquivo(arquivo)
                analise = _analisar_arquivo(df_upload, equipamentos)
            except Exception as exc:
                st.error(f"Erro ao ler a planilha: {exc}")
                analise = None

            if analise:
                resumo = analise["resumo"]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Linhas lidas", resumo["linhas"])
                c2.metric("Prontas para importar", resumo["prontos"])
                c3.metric("Com erro", resumo["erros"])
                c4.metric("Com atenção", resumo["avisos"])
                if resumo["duplicados"]:
                    st.warning(f"A planilha possui {resumo['duplicados']} código(s) repetido(s). Revise antes de importar.")
                if resumo.get("avisos_regressao"):
                    st.info(
                        f"{resumo['avisos_regressao']} leitura(s) estão menores que o valor atual e podem ser tratadas como possível reset de horímetro/hodômetro."
                    )

                preview_df = pd.DataFrame(analise["preview"])
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

                validos = analise["validos"]
                if validos:
                    if st.button("✅ Importar leituras válidas", type="primary", use_container_width=True):
                        itens_importacao = []
                        for item in validos:
                            item_payload = dict(item)
                            if item_payload.get("permitir_regressao"):
                                item_payload["permitir_regressao"] = importar_atencao_automaticamente or permitir_regressao
                            itens_importacao.append(item_payload)

                        with st.spinner("Importando leituras e atualizando a base operacional…"):
                            resultado = leituras_service.registrar_lote(
                                itens_importacao,
                                responsavel_id=resp_import["id"] if resp_import else None,
                                observacoes_padrao=obs_padrao.strip() or None,
                                permitir_regressao=permitir_regressao,
                            )
                        if resultado["importados"] and resultado["falhas"]:
                            _carregar_base.clear()
                            _carregar_historico.clear()
                            st.warning(
                                f"Importação parcial concluída. {resultado['importados']} leitura(s) gravada(s) e {resultado['falhas']} falha(s)."
                            )
                            erros_df = pd.DataFrame(resultado["erros"])
                            st.dataframe(erros_df, use_container_width=True, hide_index=True)
                        elif resultado["falhas"]:
                            st.error(
                                f"Importação não concluída. {resultado['falhas']} linha(s) falharam e nenhuma leitura foi gravada."
                            )
                            erros_df = pd.DataFrame(resultado["erros"])
                            st.dataframe(erros_df, use_container_width=True, hide_index=True)
                        else:
                            _carregar_base.clear()
                            _carregar_historico.clear()
                            st.success(f"✅ {resultado['importados']} leitura(s) importada(s) com sucesso.")
                            st.rerun()
                else:
                    st.info("Nenhuma linha válida encontrada para importação.")

    with tab3:
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
