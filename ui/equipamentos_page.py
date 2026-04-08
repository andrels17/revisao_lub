from __future__ import annotations

import io
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
        .eq-shell {
            background: linear-gradient(180deg, rgba(10,19,34,.92), rgba(15,27,45,.96));
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 24px;
            padding: 1.05rem 1.1rem;
            box-shadow: 0 18px 48px rgba(15,23,42,.06);
            margin-bottom: .9rem;
        }
        .eq-hero {
            padding: 1.15rem 1.2rem;
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(15,23,42,.97), rgba(30,41,59,.95));
            color: #f8fbff;
            border: 1px solid rgba(148,163,184,.16);
            box-shadow: 0 20px 60px rgba(2,6,23,.16);
            margin-bottom: .95rem;
        }
        .eq-hero h2{margin:0;font-size:1.38rem;font-weight:800;}
        .eq-hero p{margin:.38rem 0 0 0;color:#c0d0e6;font-size:.93rem;}
        .eq-pill{
            display:inline-block;
            padding:.18rem .55rem;
            border-radius:999px;
            background:rgba(255,255,255,.08);
            border:1px solid rgba(255,255,255,.12);
            color:#e2e8f0;
            font-size:.72rem;
            font-weight:700;
            margin-right:.35rem;
        }
        .eq-kpi{
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 20px;
            padding: 1rem 1rem .9rem 1rem;
            background: rgba(15,27,45,.98);
            box-shadow: 0 10px 28px rgba(15,23,42,.05);
            min-height: 110px;
        }
        .eq-kpi .label{font-size:.80rem;color:#9db0c7;margin-bottom:.35rem;}
        .eq-kpi .value{font-size:1.9rem;font-weight:800;color:#ecf3ff;line-height:1.1;}
        .eq-kpi .hint{font-size:.78rem;color:#7f93ad;margin-top:.35rem;}
        .eq-toolbar{
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 20px;
            padding: .9rem 1rem;
            background: rgba(15,27,45,.98);
            box-shadow: 0 10px 25px rgba(15,23,42,.05);
            margin-bottom: .85rem;
        }
        .eq-row{
            border: 1px solid rgba(148,163,184,.18);
            border-radius: 20px;
            padding: .95rem 1rem;
            background: rgba(15,27,45,.98);
            box-shadow: 0 10px 25px rgba(15,23,42,.04);
            margin-bottom: .75rem;
        }
        .eq-row-title{font-size:1rem;font-weight:800;color:#ecf3ff;margin:0;}
        .eq-row-sub{font-size:.82rem;color:#9db0c7;margin-top:.18rem;}
        .eq-badge{
            display:inline-block;
            padding:.22rem .58rem;
            border-radius:999px;
            font-size:.74rem;
            font-weight:800;
            margin-right:.34rem;
            border:1px solid transparent;
        }
        .eq-ok{background:rgba(34,197,94,.16);color:#86efac;}
        .eq-warn{background:rgba(245,158,11,.16);color:#fcd34d;}
        .eq-danger{background:rgba(239,68,68,.16);color:#fca5a5;}
        .eq-neutral{background:rgba(148,163,184,.14);color:#dbe9ff;}
        .eq-soft{
            border: 1px solid rgba(148,163,184,.16);
            border-radius: 16px;
            padding: .75rem .85rem;
            background: rgba(10,19,34,.78);
        }
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
            border-radius: 14px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi_card(label: str, value, hint: str = ""):
    st.markdown(
        f"""
        <div class="eq-kpi">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_badge(saude: str) -> str:
    css = {
        "Saudável": "eq-badge eq-ok",
        "Atenção": "eq-badge eq-warn",
        "Crítico": "eq-badge eq-danger",
        "Sem plano": "eq-badge eq-neutral",
    }.get(saude, "eq-badge eq-neutral")
    return f'<span class="{css}">{saude}</span>'


def _build_export_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
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
            }
            for row in rows
        ]
    )


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _filtrar(rows: list[dict], termo: str, setores_filtro: list[str], status_filtro: str, tipo_filtro: str, saude_filtro: str) -> list[dict]:
    termo_norm = (termo or "").strip().lower()
    filtrados = rows
    if termo_norm:
        filtrados = [
            row for row in filtrados
            if termo_norm in f'{row.get("codigo","")} {row.get("nome","")} {row.get("setor_nome","")} {row.get("responsavel_principal_nome","")}'.lower()
        ]
    if setores_filtro:
        filtrados = [row for row in filtrados if (row.get("setor_nome") or "-") in setores_filtro]
    if status_filtro != "Todos":
        ativo_bool = status_filtro == "Ativos"
        filtrados = [row for row in filtrados if bool(row.get("ativo")) == ativo_bool]
    if tipo_filtro != "Todos":
        filtrados = [row for row in filtrados if (row.get("tipo") or "-") == tipo_filtro]
    if saude_filtro != "Todas":
        filtrados = [row for row in filtrados if (row.get("saude") or "-") == saude_filtro]
    return filtrados


def _render_summary(rows: list[dict]):
    total = len(rows)
    ativos = sum(1 for row in rows if row.get("ativo"))
    criticos = sum(1 for row in rows if row.get("saude") == "Crítico")
    atencao = sum(1 for row in rows if row.get("saude") == "Atenção")
    sem_plano = sum(1 for row in rows if row.get("saude") == "Sem plano")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi_card("Equipamentos", total, "Base filtrada")
    with c2:
        _kpi_card("Ativos", ativos, "Disponíveis no sistema")
    with c3:
        _kpi_card("Críticos / atenção", f"{criticos} / {atencao}", "Prioridade operacional")
    with c4:
        _kpi_card("Sem plano", sem_plano, "Sem template vinculado")


def _slice(rows: list[dict], page: int, page_size: int) -> list[dict]:
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
    setores = _setores()
    return {str(item["id"]): item.get("nome", "-") for item in setores}


def _responsavel_options():
    responsaveis = _responsaveis_ativos()
    return {str(item["id"]): item.get("nome", "-") for item in responsaveis}


def _render_inline_row(row: dict, setor_map: dict[str, str], responsavel_map: dict[str, str]):
    st.markdown('<div class="eq-row">', unsafe_allow_html=True)
    top_left, top_right = st.columns([4.5, 1.2])

    with top_left:
        st.markdown(
            f"""
            <div class="eq-row-title">{row.get("codigo", "-")} · {row.get("nome", "-")}</div>
            <div class="eq-row-sub">{row.get("setor_nome", "-")} • {row.get("tipo", "-")} • {row.get("responsavel_principal_nome", "-")}</div>
            <div style="margin-top:.35rem;">{_status_badge(row.get("saude", "-"))}<span class="eq-badge eq-neutral">Score {int(row.get("score_saude", 0) or 0)}%</span><span class="eq-badge eq-neutral">{int(row.get("vencidos", 0) or 0)} vencido(s)</span><span class="eq-badge eq-neutral">{int(row.get("proximos", 0) or 0)} próximo(s)</span></div>
            """,
            unsafe_allow_html=True,
        )

    with top_right:
        if st.button("🔎 Detalhes", key=f"detalhes_{row['id']}", use_container_width=True):
            st.session_state["eq_detalhe_id"] = row["id"]

    col1, col2, col3, col4, col5 = st.columns([2.2, 1.3, 1.6, .9, .9])
    with col1:
        nome = st.text_input("Nome", value=row.get("nome", ""), key=f"nome_{row['id']}", label_visibility="collapsed", placeholder="Nome")
    with col2:
        tipo = st.selectbox(
            "Tipo",
            options=list(TIPOS_EQUIPAMENTO),
            index=max(0, list(TIPOS_EQUIPAMENTO).index(row.get("tipo"))) if row.get("tipo") in TIPOS_EQUIPAMENTO else 0,
            key=f"tipo_{row['id']}",
            label_visibility="collapsed",
        )
    setor_ids = list(setor_map.keys())
    setor_labels = [setor_map[k] for k in setor_ids]
    setor_atual = str(row.get("setor_id") or "")
    setor_index = setor_ids.index(setor_atual) if setor_atual in setor_ids else 0
    with col3:
        setor_escolhido_idx = st.selectbox(
            "Setor",
            options=range(len(setor_ids)),
            index=setor_index,
            format_func=lambda idx: setor_labels[idx],
            key=f"setor_{row['id']}",
            label_visibility="collapsed",
        )
    with col4:
        ativo = st.checkbox("Ativo", value=bool(row.get("ativo")), key=f"ativo_{row['id']}")
    with col5:
        if st.button("💾 Salvar", key=f"salvar_{row['id']}", use_container_width=True):
            equipamentos_service.atualizar_inline(
                row["id"],
                nome=nome.strip() or row.get("nome"),
                tipo=tipo,
                setor_id=setor_ids[setor_escolhido_idx],
                ativo=ativo,
            )
            st.success(f'{row.get("codigo")} atualizado.')
            st.rerun()

    resp_ids = [""] + list(responsavel_map.keys())
    resp_labels = ["— sem principal —"] + [responsavel_map[k] for k in responsavel_map.keys()]
    resp_atual = str(row.get("responsavel_principal_id") or "")
    resp_index = resp_ids.index(resp_atual) if resp_atual in resp_ids else 0

    sub1, sub2, sub3 = st.columns([2.4, 1.1, 1.2])
    with sub1:
        resp_idx = st.selectbox(
            "Responsável principal",
            options=range(len(resp_ids)),
            index=resp_index,
            format_func=lambda idx: resp_labels[idx],
            key=f"resp_{row['id']}",
        )
    with sub2:
        st.markdown(f'<div class="eq-soft"><strong>KM</strong><br>{float(row.get("km_atual", 0) or 0):.0f}</div>', unsafe_allow_html=True)
    with sub3:
        st.markdown(f'<div class="eq-soft"><strong>Horas</strong><br>{float(row.get("horas_atual", 0) or 0):.0f}</div>', unsafe_allow_html=True)

    if st.button("👤 Aplicar responsável", key=f"resp_save_{row['id']}", use_container_width=False):
        equipamentos_service.definir_responsavel_principal(row["id"], resp_ids[resp_idx] or None)
        st.success("Responsável principal atualizado.")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_detalhe():
    eq_id = st.session_state.get("eq_detalhe_id")
    if not eq_id:
        return
    equipamento = equipamentos_service.obter(eq_id)
    if not equipamento:
        st.warning("Equipamento não encontrado para detalhamento.")
        return

    with st.container(border=False):
        st.markdown('<div class="eq-shell">', unsafe_allow_html=True)
        top1, top2 = st.columns([4, 1])
        with top1:
            st.subheader(f'Painel rápido · {equipamento.get("codigo")} - {equipamento.get("nome")}')
        with top2:
            if st.button("Fechar", key="eq_detalhe_fechar", use_container_width=True):
                st.session_state.pop("eq_detalhe_id", None)
                st.rerun()

        rev = []
        lub = []
        try:
            rev = revisoes_service.listar_controle_revisoes_por_equipamento().get(eq_id, [])
        except Exception:
            pass
        try:
            lub = lubrificacoes_service.calcular_proximas_lubrificacoes_batch([eq_id]).get(eq_id, [])
        except Exception:
            pass

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Vencidos", sum(1 for x in rev + lub if x.get("status") == "VENCIDO"))
        c2.metric("Próximos", sum(1 for x in rev + lub if x.get("status") == "PROXIMO"))
        c3.metric("Revisões", len(rev))
        c4.metric("Lubrificações", len(lub))

        tab1, tab2 = st.tabs(["Revisões", "Lubrificações"])
        with tab1:
            if rev:
                df = pd.DataFrame(rev)[["etapa", "tipo_controle", "atual", "proximo_vencimento", "diferenca", "status"]].rename(
                    columns={
                        "etapa": "Etapa",
                        "tipo_controle": "Controle",
                        "atual": "Atual",
                        "proximo_vencimento": "Próximo vencimento",
                        "diferenca": "Falta",
                        "status": "Status",
                    }
                )
                df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma revisão encontrada.")
        with tab2:
            if lub:
                df = pd.DataFrame(lub)[["item", "tipo_controle", "atual", "vencimento", "diferenca", "status"]].rename(
                    columns={
                        "item": "Item",
                        "tipo_controle": "Controle",
                        "atual": "Atual",
                        "vencimento": "Vencimento",
                        "diferenca": "Falta",
                        "status": "Status",
                    }
                )
                df["Status"] = df["Status"].map(lambda x: STATUS_LABEL.get(x, x))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma lubrificação encontrada.")
        st.markdown("</div>", unsafe_allow_html=True)


def render():
    _inject_css()

    top_left, top_right = st.columns([5, 1])
    with top_left:
        render_page_intro("Equipamentos", "Cadastre, pesquise e gerencie a frota em uma tela mais limpa, escura e consistente com o restante do sistema.", "Cadastros")
    with top_right:
        st.write("")
        if st.button("🔄 Atualizar", use_container_width=True):
            equipamentos_service.limpar_cache()
            st.rerun()

    rows = equipamentos_service.carregar_snapshot_equipamentos()
    st.markdown(
        f"""
        <div class="eq-hero">
            <span class="eq-pill">Edição inline</span>
            <span class="eq-pill">Mais leve</span>
            <h2>Gestão rápida de equipamentos</h2>
            <p>Lista otimizada com filtros, paginação e edição direta apenas nos itens visíveis. Base atual: <strong>{len(rows)}</strong> equipamento(s).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not rows:
        st.info("Nenhum equipamento cadastrado.")
        return

    st.markdown('<div class="eq-toolbar">', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns([2.4, 1.5, 1.2, 1.2, 1.1])
    setores_disp = sorted({row.get("setor_nome") or "-" for row in rows})
    tipos_disp = ["Todos"] + [t for t in TIPOS_EQUIPAMENTO]
    with f1:
        termo = st.text_input("Buscar", placeholder="Código, nome, setor ou responsável")
    with f2:
        setores_filtro = st.multiselect("Setor", setores_disp)
    with f3:
        status_filtro = st.selectbox("Status", ["Todos", "Ativos", "Inativos"])
    with f4:
        tipo_filtro = st.selectbox("Tipo", tipos_disp)
    with f5:
        saude_filtro = st.selectbox("Saúde", ["Todas", "Crítico", "Atenção", "Saudável", "Sem plano"])
    st.markdown("</div>", unsafe_allow_html=True)

    filtrados = _filtrar(rows, termo, setores_filtro, status_filtro, tipo_filtro, saude_filtro)
    _render_summary(filtrados)

    export_df = _build_export_df(filtrados)
    bar1, bar2, bar3 = st.columns([3, 1.2, 1.2])
    with bar1:
        st.caption(f"{len(filtrados)} equipamento(s) após filtros")
    with bar2:
        page_size = st.selectbox("Itens por página", [8, 12, 20, 30], index=1)
    with bar3:
        st.download_button(
            "⬇️ CSV filtrado",
            data=_csv_bytes(export_df),
            file_name="equipamentos_filtrados.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not filtrados:
        st.info("Nenhum equipamento encontrado para os filtros selecionados.")
        return

    total_pages = max(1, math.ceil(len(filtrados) / page_size))
    nav1, nav2, nav3 = st.columns([1.1, 1.1, 4])
    with nav1:
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
    with nav2:
        criticos = sum(1 for row in filtrados if row.get("saude") == "Crítico")
        st.metric("Críticos", criticos)
    with nav3:
        st.caption("A tela renderiza apenas os itens da página atual para reduzir peso e travamento.")

    setor_map = _setor_options()
    responsavel_map = _responsavel_options()

    for row in _slice(filtrados, int(page), int(page_size)):
        _render_inline_row(row, setor_map, responsavel_map)

    _render_detalhe()
