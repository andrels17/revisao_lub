from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from services import (
    equipamentos_service,
    lubrificacoes_service,
    responsaveis_service,
    revisoes_service,
    setores_service,
)
from ui.constants import STATUS_LABEL, TIPOS_EQUIPAMENTO
from ui.theme import render_page_intro


def _inject_css():
    st.markdown(
        """
        <style>
        /* ── Equipamentos ──────────────────────────────────────────── */

        /* KPI strip */
        .eq-kpi-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap: .6rem;
            margin-bottom: .75rem;
        }
        .eq-kpi {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .75rem .85rem;
            background: #0d1929;
        }
        .eq-kpi .lbl  { font-size: .73rem; color: #8fa4c0; font-weight: 600; margin-bottom: .2rem; }
        .eq-kpi .val  { font-size: 1.55rem; font-weight: 800; line-height: 1; color: #e8f1ff; }
        .eq-kpi .hint { font-size: .68rem; color: #6b84a0; margin-top: .18rem; }

        /* Barra de filtros */
        .eq-filters {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .7rem .85rem .15rem;
            background: #0d1929;
            margin-bottom: .7rem;
        }

        /* Card de equipamento */
        .eq-card {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem .9rem;
            background: #0d1929;
            margin-bottom: .6rem;
        }
        .eq-card-title { font-size: .95rem; font-weight: 700; color: #e8f1ff; margin: 0; }
        .eq-card-meta  { font-size: .78rem; color: #8fa4c0; margin-top: .12rem; }
        .eq-card-badges { margin-top: .38rem; }

        /* Badges */
        .eq-b {
            display: inline-block;
            padding: .15rem .48rem;
            border-radius: 999px;
            font-size: .70rem; font-weight: 700;
            margin-right: .28rem;
        }
        .eq-ok      { background: rgba(34,197,94,.12);  color: #86efac; }
        .eq-warn    { background: rgba(245,158,11,.12); color: #fcd34d; }
        .eq-danger  { background: rgba(239,68,68,.12);  color: #fca5a5; }
        .eq-neutral { background: rgba(148,163,184,.10); color: #c8d8f0; }

        /* Linha de campos inline */
        .eq-fields-row {
            display: grid;
            gap: .55rem;
            margin-top: .65rem;
            padding-top: .65rem;
            border-top: 1px solid rgba(148,163,184,.10);
        }

        /* Painel de detalhe */
        .eq-detalhe {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .85rem .9rem;
            background: #0d1929;
            margin-bottom: .75rem;
        }
        .eq-detalhe-title {
            font-size: .95rem; font-weight: 700; color: #e8f1ff; margin-bottom: .6rem;
        }

        /* Info inline KM/Horas */
        .eq-info-box {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 8px;
            padding: .5rem .7rem;
            background: rgba(255,255,255,.025);
            font-size: .82rem; color: #c8d8f0;
        }
        .eq-info-box strong { display: block; font-size: .68rem; color: #6b84a0; margin-bottom: .12rem; font-weight: 600; }

        @media (max-width: 900px) {
            .eq-kpi-strip { grid-template-columns: repeat(2,minmax(0,1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value, hint: str = ""):
    st.markdown(
        f"""
        <div class="eq-kpi">
            <div class="lbl">{label}</div>
            <div class="val">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _badge(saude: str) -> str:
    css = {
        "Saudável":  "eq-b eq-ok",
        "Atenção":   "eq-b eq-warn",
        "Crítico":   "eq-b eq-danger",
        "Sem plano": "eq-b eq-neutral",
    }.get(saude, "eq-b eq-neutral")
    return f'<span class="{css}">{saude}</span>'


def _build_export_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Código": row.get("codigo"),
        "Equipamento": row.get("nome"),
        "Tipo": row.get("tipo"),
        "Setor": row.get("setor_nome"),
        "Responsável principal": row.get("responsavel_principal_nome"),
        "Saúde": row.get("saude"),
        "Score saúde": row.get("score_saude"),
        "Vencidos": row.get("vencidos"),
        "Próximos": row.get("proximos"),
        "KM atual": row.get("km_atual"),
        "Horas atual": row.get("horas_atual"),
        "Ativo": "Sim" if row.get("ativo") else "Não",
    } for row in rows])


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro):
    termo_norm = (termo or "").strip().lower()
    filtrados = rows
    if termo_norm:
        filtrados = [r for r in filtrados if termo_norm in f'{r.get("codigo","")} {r.get("nome","")} {r.get("setor_nome","")} {r.get("responsavel_principal_nome","")}'.lower()]
    if setores_filtro:
        filtrados = [r for r in filtrados if (r.get("setor_nome") or "-") in setores_filtro]
    if status_filtro != "Todos":
        ativo_bool = status_filtro == "Ativos"
        filtrados = [r for r in filtrados if bool(r.get("ativo")) == ativo_bool]
    if tipo_filtro != "Todos":
        filtrados = [r for r in filtrados if (r.get("tipo") or "-") == tipo_filtro]
    if saude_filtro != "Todas":
        filtrados = [r for r in filtrados if (r.get("saude") or "-") == saude_filtro]
    return filtrados


def _render_summary(rows):
    total    = len(rows)
    ativos   = sum(1 for r in rows if r.get("ativo"))
    criticos = sum(1 for r in rows if r.get("saude") == "Crítico")
    atencao  = sum(1 for r in rows if r.get("saude") == "Atenção")
    sem_plano = sum(1 for r in rows if r.get("saude") == "Sem plano")

    st.markdown('<div class="eq-kpi-strip">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        _kpi("Equipamentos", total, "Base filtrada")
    with c2:
        _kpi("Ativos", ativos, "Disponíveis no sistema")
    with c3:
        _kpi("Críticos / atenção", f"{criticos} / {atencao}", "Prioridade operacional")
    with c4:
        _kpi("Sem plano", sem_plano, "Sem template vinculado")
    st.markdown("</div>", unsafe_allow_html=True)


def _slice(rows, page, page_size):
    start = max(0, (page - 1) * page_size)
    return rows[start:start + page_size]


@st.cache_data(ttl=120, show_spinner=False)
def _responsaveis_ativos():
    try:
        return [r for r in responsaveis_service.listar() if r.get("ativo")]
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def _setores():
    try:
        return setores_service.listar()
    except Exception:
        return []


def _setor_options():
    return {str(s["id"]): s.get("nome", "-") for s in _setores()}


def _responsavel_options():
    return {str(r["id"]): r.get("nome", "-") for r in _responsaveis_ativos()}


def _render_inline_row(row: dict, setor_map: dict, responsavel_map: dict):
    st.markdown('<div class="eq-card">', unsafe_allow_html=True)

    # ── Cabeçalho do card ──────────────────────────────────────────
    h_left, h_right = st.columns([5, 1])
    with h_left:
        venc = int(row.get("vencidos", 0) or 0)
        prox = int(row.get("proximos", 0) or 0)
        score = int(row.get("score_saude", 0) or 0)
        st.markdown(
            f"""
            <div class="eq-card-title">{row.get("codigo", "-")} — {row.get("nome", "-")}</div>
            <div class="eq-card-meta">{row.get("setor_nome", "-")} · {row.get("tipo", "-")} · {row.get("responsavel_principal_nome") or "sem responsável"}</div>
            <div class="eq-card-badges">
                {_badge(row.get("saude", "-"))}
                <span class="eq-b eq-neutral">Score {score}%</span>
                <span class="eq-b {'eq-danger' if venc else 'eq-neutral'}">{venc} vencido(s)</span>
                <span class="eq-b {'eq-warn' if prox else 'eq-neutral'}">{prox} próximo(s)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h_right:
        if st.button("Detalhes", key=f"det_{row['id']}", use_container_width=True):
            st.session_state["eq_detalhe_id"] = row["id"]

    # ── Campos de edição ───────────────────────────────────────────
    st.markdown('<div class="eq-fields-row" style="grid-template-columns:2fr 1.3fr 1.7fr auto auto">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([2.2, 1.3, 1.7, .85, .85])

    with c1:
        nome = st.text_input("Nome", value=row.get("nome", ""), key=f"nome_{row['id']}", label_visibility="collapsed", placeholder="Nome")
    with c2:
        tipo = st.selectbox(
            "Tipo", options=list(TIPOS_EQUIPAMENTO),
            index=max(0, list(TIPOS_EQUIPAMENTO).index(row.get("tipo"))) if row.get("tipo") in TIPOS_EQUIPAMENTO else 0,
            key=f"tipo_{row['id']}", label_visibility="collapsed",
        )

    setor_ids = list(setor_map.keys())
    setor_labels = [setor_map[k] for k in setor_ids]
    setor_atual = str(row.get("setor_id") or "")
    setor_index = setor_ids.index(setor_atual) if setor_atual in setor_ids else 0
    with c3:
        setor_idx = st.selectbox(
            "Setor", options=range(len(setor_ids)), index=setor_index,
            format_func=lambda i: setor_labels[i],
            key=f"setor_{row['id']}", label_visibility="collapsed",
        )
    with c4:
        ativo = st.checkbox("Ativo", value=bool(row.get("ativo")), key=f"ativo_{row['id']}")
    with c5:
        if st.button("Salvar", key=f"salvar_{row['id']}", use_container_width=True, type="primary"):
            equipamentos_service.atualizar_inline(
                row["id"],
                nome=nome.strip() or row.get("nome"),
                tipo=tipo,
                setor_id=setor_ids[setor_idx],
                ativo=ativo,
            )
            st.success(f'{row.get("codigo")} atualizado.')
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Responsável + KM/Horas ─────────────────────────────────────
    resp_ids = [""] + list(responsavel_map.keys())
    resp_labels = ["— sem principal —"] + list(responsavel_map.values())
    resp_atual = str(row.get("responsavel_principal_id") or "")
    resp_index = resp_ids.index(resp_atual) if resp_atual in resp_ids else 0

    r1, r2, r3, r4 = st.columns([2.6, 1, 1, 1.2])
    with r1:
        resp_idx = st.selectbox(
            "Responsável principal",
            options=range(len(resp_ids)), index=resp_index,
            format_func=lambda i: resp_labels[i],
            key=f"resp_{row['id']}",
        )
    with r2:
        st.markdown(
            f'<div class="eq-info-box"><strong>KM atual</strong>{float(row.get("km_atual", 0) or 0):.0f}</div>',
            unsafe_allow_html=True,
        )
    with r3:
        st.markdown(
            f'<div class="eq-info-box"><strong>Horas</strong>{float(row.get("horas_atual", 0) or 0):.0f}</div>',
            unsafe_allow_html=True,
        )
    with r4:
        if st.button("Aplicar responsável", key=f"resp_save_{row['id']}"):
            equipamentos_service.definir_responsavel_principal(row["id"], resp_ids[resp_idx] or None)
            st.success("Responsável atualizado.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_detalhe():
    eq_id = st.session_state.get("eq_detalhe_id")
    if not eq_id:
        return
    equipamento = equipamentos_service.obter(eq_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    st.markdown('<div class="eq-detalhe">', unsafe_allow_html=True)
    d_left, d_right = st.columns([5, 1])
    with d_left:
        st.markdown(
            f'<div class="eq-detalhe-title">Painel rápido · {equipamento.get("codigo")} — {equipamento.get("nome")}</div>',
            unsafe_allow_html=True,
        )
    with d_right:
        if st.button("Fechar", key="eq_detalhe_fechar", use_container_width=True):
            st.session_state.pop("eq_detalhe_id", None)
            st.rerun()

    rev, lub = [], []
    try:
        rev = revisoes_service.listar_controle_revisoes_por_equipamento().get(eq_id, [])
    except Exception:
        pass
    try:
        lub = lubrificacoes_service.calcular_proximas_lubrificacoes_batch([eq_id]).get(eq_id, [])
    except Exception:
        pass

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vencidos", sum(1 for x in rev + lub if x.get("status") == "VENCIDO"))
    m2.metric("Próximos", sum(1 for x in rev + lub if x.get("status") == "PROXIMO"))
    m3.metric("Revisões", len(rev))
    m4.metric("Lubrificações", len(lub))

    tab1, tab2 = st.tabs(["Revisões", "Lubrificações"])
    with tab1:
        if rev:
            df = pd.DataFrame(rev)[["etapa","tipo_controle","atual","proximo_vencimento","diferenca","status"]].rename(columns={
                "etapa": "Etapa", "tipo_controle": "Controle", "atual": "Atual",
                "proximo_vencimento": "Próx. vencimento", "diferenca": "Falta", "status": "Status",
            })
            df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma revisão encontrada.")
    with tab2:
        if lub:
            df = pd.DataFrame(lub)[["item","tipo_controle","atual","vencimento","diferenca","status"]].rename(columns={
                "item": "Item", "tipo_controle": "Controle", "atual": "Atual",
                "vencimento": "Vencimento", "diferenca": "Falta", "status": "Status",
            })
            df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma lubrificação encontrada.")

    st.markdown("</div>", unsafe_allow_html=True)


def render():
    _inject_css()

    # ── Cabeçalho ──────────────────────────────────────────────────
    h_left, h_right = st.columns([5, 1])
    with h_left:
        render_page_intro(
            "Equipamentos",
            "Cadastre, pesquise e gerencie a frota com edição direta.",
            "Cadastros",
        )
    with h_right:
        st.write("")
        if st.button("↺ Atualizar", use_container_width=True):
            equipamentos_service.limpar_cache()
            st.rerun()

    rows = equipamentos_service.carregar_snapshot_equipamentos()

    if not rows:
        st.info("Nenhum equipamento cadastrado.")
        return

    # ── Filtros ─────────────────────────────────────────────────────
    st.markdown('<div class="eq-filters">', unsafe_allow_html=True)
    setores_disp = sorted({r.get("setor_nome") or "-" for r in rows})
    tipos_disp   = ["Todos"] + list(TIPOS_EQUIPAMENTO)

    f1, f2, f3, f4, f5 = st.columns([2.5, 1.5, 1.2, 1.2, 1.1], gap="small")
    with f1:
        termo = st.text_input("Buscar", placeholder="Código, nome, setor ou responsável", label_visibility="collapsed")
    with f2:
        setores_filtro = st.multiselect("Setor", setores_disp, placeholder="Setor")
    with f3:
        status_filtro = st.selectbox("Status", ["Todos", "Ativos", "Inativos"])
    with f4:
        tipo_filtro = st.selectbox("Tipo", tipos_disp)
    with f5:
        saude_filtro = st.selectbox("Saúde", ["Todas", "Crítico", "Atenção", "Saudável", "Sem plano"])
    st.markdown("</div>", unsafe_allow_html=True)

    filtrados = _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro)

    # ── KPIs ────────────────────────────────────────────────────────
    _render_summary(filtrados)

    # ── Barra de paginação / exportação ────────────────────────────
    bar1, bar2, bar3 = st.columns([3, 1.2, 1.2], gap="small")
    with bar1:
        st.caption(f"{len(filtrados)} equipamento(s) após filtros")
    with bar2:
        page_size = st.selectbox("Itens/página", [8, 12, 20, 30], index=1, label_visibility="collapsed")
    with bar3:
        export_df = _build_export_df(filtrados)
        st.download_button(
            "⬇ CSV",
            data=_csv_bytes(export_df),
            file_name="equipamentos_filtrados.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not filtrados:
        st.info("Nenhum equipamento encontrado para os filtros selecionados.")
        return

    total_pages = max(1, math.ceil(len(filtrados) / page_size))
    nav1, nav2, nav3 = st.columns([1, 1, 4], gap="small")
    with nav1:
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
    with nav2:
        criticos = sum(1 for r in filtrados if r.get("saude") == "Crítico")
        st.metric("Críticos", criticos)
    with nav3:
        st.caption("Apenas os itens da página atual são renderizados para manter a tela leve.")

    # ── Lista de equipamentos ────────────────────────────────────────
    setor_map = _setor_options()
    resp_map  = _responsavel_options()

    for row in _slice(filtrados, int(page), int(page_size)):
        _render_inline_row(row, setor_map, resp_map)

    _render_detalhe()
