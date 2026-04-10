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
        .eq-kpi-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap: .55rem;
            margin-bottom: 1rem;
        }
        .eq-kpi {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 10px;
            padding: .65rem .85rem;
            background: #0d1929;
        }
        .eq-kpi .lbl  { font-size: .70rem; color: #6b84a0; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: .22rem; }
        .eq-kpi .val  { font-size: 1.45rem; font-weight: 700; line-height: 1; color: #e8f1ff; }
        .eq-kpi .val.ok     { color: #86efac; }
        .eq-kpi .val.warn   { color: #fcd34d; }
        .eq-kpi .val.danger { color: #fca5a5; }

        .eq-card {
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px;
            padding: .8rem 1rem;
            background: #0d1929;
            margin-bottom: .5rem;
            transition: border-color .15s;
        }
        .eq-card:hover { border-color: rgba(148,163,184,.24); }
        .eq-card-code  { font-size: .70rem; color: #6b84a0; font-weight: 600; letter-spacing: .04em; margin-bottom: .08rem; }
        .eq-card-title { font-size: .95rem; font-weight: 700; color: #e8f1ff; }
        .eq-card-meta  { font-size: .78rem; color: #8fa4c0; margin-top: .14rem; }
        .eq-card-badges { margin-top: .42rem; display: flex; flex-wrap: wrap; gap: .3rem; }

        .eq-score-wrap {
            position: relative; width: 44px; height: 44px; flex-shrink: 0;
        }
        .eq-score-num {
            position: absolute; inset: 0;
            display: flex; align-items: center; justify-content: center;
            font-size: .65rem; font-weight: 700;
        }

        .eq-b {
            display: inline-block;
            padding: .14rem .45rem;
            border-radius: 999px;
            font-size: .69rem; font-weight: 700;
        }
        .eq-ok      { background: rgba(34,197,94,.10);  color: #86efac; }
        .eq-warn    { background: rgba(245,158,11,.10); color: #fcd34d; }
        .eq-danger  { background: rgba(239,68,68,.10);  color: #fca5a5; }
        .eq-neutral { background: rgba(148,163,184,.09); color: #94a8c4; }

        .eq-detalhe {
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 12px;
            padding: .9rem 1rem;
            background: #0d1929;
            margin-bottom: .75rem;
        }
        .eq-detalhe-title { font-size: .95rem; font-weight: 700; color: #e8f1ff; margin-bottom: .65rem; }

        .eq-info-box {
            border: 1px solid rgba(148,163,184,.10);
            border-radius: 8px;
            padding: .45rem .65rem;
            background: rgba(255,255,255,.02);
            font-size: .82rem; color: #c8d8f0;
        }
        .eq-info-box strong { display: block; font-size: .67rem; color: #6b84a0; margin-bottom: .1rem; font-weight: 600; }

        @media (max-width: 900px) {
            .eq-kpi-strip { grid-template-columns: repeat(2,minmax(0,1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value, css_class: str = ""):
    st.markdown(
        f'<div class="eq-kpi"><div class="lbl">{label}</div><div class="val {css_class}">{value}</div></div>',
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


def _score_ring(score: int) -> str:
    radius = 18
    circumference = 2 * 3.14159 * radius
    dash = circumference * score / 100
    color = "#22c55e" if score >= 80 else ("#f59e0b" if score >= 50 else "#ef4444")
    return (
        f'<div class="eq-score-wrap">'
        f'<svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;width:44px;height:44px">'
        f'<circle cx="22" cy="22" r="{radius}" fill="none" stroke="rgba(148,163,184,.15)" stroke-width="3.5"/>'
        f'<circle cx="22" cy="22" r="{radius}" fill="none" stroke="{color}" stroke-width="3.5" '
        f'stroke-dasharray="{dash:.1f} {circumference:.1f}" stroke-linecap="round" transform="rotate(-90 22 22)"/>'
        f'</svg>'
        f'<div class="eq-score-num" style="color:{color}">{score}%</div>'
        f'</div>'
    )


def _build_export_df(rows):
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
        "KM base plano": row.get("km_base_plano"),
        "Horas base plano": row.get("horas_base_plano"),
        "Ativo": "Sim" if row.get("ativo") else "Não",
    } for row in rows])


def _csv_bytes(df):
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
    total     = len(rows)
    ativos    = sum(1 for r in rows if r.get("ativo"))
    criticos  = sum(1 for r in rows if r.get("saude") == "Crítico")
    sem_plano = sum(1 for r in rows if r.get("saude") == "Sem plano")

    st.markdown('<div class="eq-kpi-strip">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: _kpi("Total", total)
    with c2: _kpi("Ativos", ativos, "ok")
    with c3: _kpi("Críticos", criticos, "danger" if criticos else "")
    with c4: _kpi("Sem plano", sem_plano, "warn" if sem_plano else "")
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


def _render_card(row: dict):
    venc  = int(row.get("vencidos", 0) or 0)
    prox  = int(row.get("proximos", 0) or 0)
    score = int(row.get("score_saude", 0) or 0)
    ativo = row.get("ativo")

    km  = float(row.get("km_atual") or 0)
    hrs = float(row.get("horas_atual") or 0)
    medidor = f"{km:,.0f} km" if km else (f"{hrs:,.0f} h" if hrs else "—")

    badge_saude  = _badge(row.get("saude", "-"))
    badge_venc   = f'<span class="eq-b {"eq-danger" if venc else "eq-neutral"}">{venc} vencida{"s" if venc != 1 else ""}</span>'
    badge_prox   = f'<span class="eq-b {"eq-warn" if prox else "eq-neutral"}">{prox} próxima{"s" if prox != 1 else ""}</span>'
    badge_status = f'<span class="eq-b {"eq-ok" if ativo else "eq-neutral"}">{"Ativo" if ativo else "Inativo"}</span>'

    col_info, col_score, col_btn = st.columns([6, 1, 1], gap="small")
    with col_info:
        st.markdown(
            f'<div class="eq-card-code">{row.get("codigo", "-")}</div>'
            f'<div class="eq-card-title">{row.get("nome", "-")}</div>'
            f'<div class="eq-card-meta">{row.get("setor_nome", "-")} · {row.get("tipo", "-")} · {medidor}</div>'
            f'<div class="eq-card-badges">{badge_saude}{badge_venc}{badge_prox}{badge_status}</div>',
            unsafe_allow_html=True,
        )
    with col_score:
        st.markdown(_score_ring(score), unsafe_allow_html=True)
    with col_btn:
        if st.button("Detalhes", key=f"det_{row['id']}", use_container_width=True):
            st.session_state["eq_detalhe_id"] = row["id"]


def _render_detalhe(setor_map: dict, responsavel_map: dict):
    eq_id = st.session_state.get("eq_detalhe_id")
    if not eq_id:
        return

    equipamento = equipamentos_service.obter(eq_id)
    if not equipamento:
        st.warning("Equipamento não encontrado.")
        return

    st.markdown('<div class="eq-detalhe">', unsafe_allow_html=True)

    hdr_l, hdr_r = st.columns([5, 1])
    with hdr_l:
        st.markdown(
            f'<div class="eq-detalhe-title">{equipamento.get("codigo")} — {equipamento.get("nome")}</div>',
            unsafe_allow_html=True,
        )
    with hdr_r:
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
    m1.metric("Vencidos",      sum(1 for x in rev + lub if x.get("status") == "VENCIDO"))
    m2.metric("Próximos",      sum(1 for x in rev + lub if x.get("status") == "PROXIMO"))
    m3.metric("Revisões",      len(rev))
    m4.metric("Lubrificações", len(lub))

    tab1, tab2, tab3 = st.tabs(["Revisões", "Lubrificações", "Editar"])

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

    with tab3:
        e1, e2, e3 = st.columns([2.5, 1.5, 1])
        with e1:
            nome_edit = st.text_input("Nome", value=equipamento.get("nome", ""), key=f"edit_nome_{eq_id}")
        with e2:
            tipos_list = list(TIPOS_EQUIPAMENTO)
            tipo_edit = st.selectbox(
                "Tipo", options=tipos_list,
                index=max(0, tipos_list.index(equipamento.get("tipo"))) if equipamento.get("tipo") in tipos_list else 0,
                key=f"edit_tipo_{eq_id}",
            )
        with e3:
            ativo_edit = st.checkbox("Ativo", value=bool(equipamento.get("ativo")), key=f"edit_ativo_{eq_id}")

        setor_ids    = list(setor_map.keys())
        setor_labels = [setor_map[k] for k in setor_ids]
        setor_atual  = str(equipamento.get("setor_id") or "")
        setor_index  = setor_ids.index(setor_atual) if setor_atual in setor_ids else 0

        e4, e5 = st.columns([3, 1])
        with e4:
            setor_idx = st.selectbox(
                "Setor", options=range(len(setor_ids)), index=setor_index,
                format_func=lambda i: setor_labels[i],
                key=f"edit_setor_{eq_id}",
            )

        km_base_atual = float(equipamento.get("km_base_plano") or equipamento.get("km_atual") or 0)
        horas_base_atual = float(equipamento.get("horas_base_plano") or equipamento.get("horas_atual") or 0)

        b1, b2 = st.columns(2)
        with b1:
            km_base_edit = st.number_input("KM inicial do plano", min_value=0.0, value=km_base_atual, step=1.0, key=f"edit_km_base_{eq_id}")
        with b2:
            horas_base_edit = st.number_input("Horas iniciais do plano", min_value=0.0, value=horas_base_atual, step=1.0, key=f"edit_horas_base_{eq_id}")

        st.caption("Esses campos ancoram os ciclos de revisão e lubrificação. Ex.: base 3.200 + etapas 5/10/15/20 mil = 8.200 / 13.200 / 18.200 / 23.200.")

        with e5:
            st.write("")
            if st.button("Salvar alterações", key=f"edit_salvar_{eq_id}", use_container_width=True, type="primary"):
                equipamentos_service.atualizar_inline(
                    eq_id,
                    nome=nome_edit.strip() or equipamento.get("nome"),
                    tipo=tipo_edit,
                    setor_id=setor_ids[setor_idx],
                    ativo=ativo_edit,
                    km_base_plano=km_base_edit,
                    horas_base_plano=horas_base_edit,
                )
                st.success("Equipamento atualizado.")
                st.rerun()

        resp_ids    = [""] + list(responsavel_map.keys())
        resp_labels = ["— sem principal —"] + list(responsavel_map.values())
        resp_atual  = str(equipamento.get("responsavel_principal_id") or "")
        resp_index  = resp_ids.index(resp_atual) if resp_atual in resp_ids else 0

        r1, r2, r3, r4 = st.columns([3, 1, 1, 1.2])
        with r1:
            resp_idx = st.selectbox(
                "Responsável principal",
                options=range(len(resp_ids)), index=resp_index,
                format_func=lambda i: resp_labels[i],
                key=f"edit_resp_{eq_id}",
            )
        with r2:
            st.markdown(
                f'<div class="eq-info-box"><strong>KM atual</strong>{float(equipamento.get("km_atual", 0) or 0):.0f}<br><small>Base: {float(equipamento.get("km_base_plano", equipamento.get("km_atual", 0)) or 0):.0f}</small></div>',
                unsafe_allow_html=True,
            )
        with r3:
            st.markdown(
                f'<div class="eq-info-box"><strong>Horas</strong>{float(equipamento.get("horas_atual", 0) or 0):.0f}<br><small>Base: {float(equipamento.get("horas_base_plano", equipamento.get("horas_atual", 0)) or 0):.0f}</small></div>',
                unsafe_allow_html=True,
            )
        with r4:
            st.write("")
            if st.button("Aplicar responsável", key=f"edit_resp_save_{eq_id}"):
                equipamentos_service.definir_responsavel_principal(eq_id, resp_ids[resp_idx] or None)
                st.success("Responsável atualizado.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render():
    _inject_css()

    h_left, h_right = st.columns([5, 1])
    with h_left:
        render_page_intro(
            "Equipamentos",
            "Cadastre, pesquise e gerencie a frota.",
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

    # ── Filtros ──────────────────────────────────────────────────────
    setores_disp = sorted({r.get("setor_nome") or "-" for r in rows})
    tipos_disp   = ["Todos"] + list(TIPOS_EQUIPAMENTO)

    f1, f2, f3, f4, f5 = st.columns([2.5, 1.5, 1.2, 1.2, 1.1], gap="small")
    with f1:
        termo = st.text_input("Buscar", placeholder="Código, nome, setor ou responsável", label_visibility="collapsed")
    with f2:
        setores_filtro = st.multiselect("Setor", setores_disp, placeholder="Setor", label_visibility="collapsed")
    with f3:
        status_filtro = st.selectbox("Status", ["Todos", "Ativos", "Inativos"], label_visibility="collapsed")
    with f4:
        tipo_filtro = st.selectbox("Tipo", tipos_disp, label_visibility="collapsed")
    with f5:
        saude_filtro = st.selectbox("Saúde", ["Todas", "Crítico", "Atenção", "Saudável", "Sem plano"], label_visibility="collapsed")

    filtrados = _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro)

    # ── KPIs ─────────────────────────────────────────────────────────
    _render_summary(filtrados)

    # ── Barra de paginação / exportação ─────────────────────────────
    bar1, bar2, bar3 = st.columns([3, 1, 1.2], gap="small")
    with bar1:
        st.caption(f"{len(filtrados)} equipamento(s)")
    with bar2:
        page_size = st.selectbox("Itens/pág", [8, 12, 20, 30], index=1, label_visibility="collapsed")
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
    if total_pages > 1:
        nav1, _ = st.columns([1, 5])
        with nav1:
            page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
    else:
        page = 1

    setor_map = _setor_options()
    resp_map  = _responsavel_options()

    for row in _slice(filtrados, int(page), int(page_size)):
        st.markdown('<div class="eq-card">', unsafe_allow_html=True)
        _render_card(row)
        st.markdown("</div>", unsafe_allow_html=True)

    _render_detalhe(setor_map, resp_map)
