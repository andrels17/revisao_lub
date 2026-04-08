import streamlit as st
from services import vinculos_service, equipamentos_service, responsaveis_service, setores_service
from ui.theme import render_page_intro

TIPOS_VINCULO_EQP = ["lubrificador", "operador", "encarregado", "mecânico", "outro"]
TIPOS_VINCULO_SETOR = ["gestor", "supervisor", "coordenador", "outro"]


def _fmt_eqp(e):
    return f"{e['codigo']} - {e['nome']}"


def _fmt_resp(r):
    fn = f" ({r['funcao_principal']})" if r.get("funcao_principal") else ""
    return f"{r['nome']}{fn}"


def _render_vinculos_equipamento():
    st.markdown("### Vínculos por equipamento")
    st.caption("Defina lubrificador, operador ou encarregado de cada equipamento para distribuir alertas operacionais.")
    equipamentos = equipamentos_service.listar()
    responsaveis = [r for r in responsaveis_service.listar() if r.get("ativo")]
    if not equipamentos:
        st.info("Cadastre equipamentos primeiro.")
        return
    if not responsaveis:
        st.info("Cadastre responsáveis primeiro.")
        return

    eqp = st.selectbox("Equipamento", equipamentos, format_func=_fmt_eqp, key="veqp_sel")
    vinculos = vinculos_service.listar_por_equipamento(eqp["id"]) if eqp else []
    col_lista, col_form = st.columns([1.5, 1])
    with col_lista:
        st.markdown("**Responsáveis atuais**")
        if vinculos:
            for v in vinculos:
                c1, c2, c3 = st.columns([2, 1.4, .5])
                c1.write(f"{'⭐ ' if v['principal'] else ''}{v['responsavel_nome']}")
                c2.caption(v["tipo_vinculo"])
                if c3.button("✕", key=f"del_ve_{v['id']}"):
                    vinculos_service.remover_vinculo_equipamento(v["id"])
                    st.rerun()
        else:
            st.info("Nenhum vínculo.")
    with col_form:
        st.markdown("**Adicionar vínculo**")
        resp = st.selectbox("Responsável", responsaveis, format_func=_fmt_resp, key="veqp_resp")
        tipo = st.selectbox("Tipo", TIPOS_VINCULO_EQP, key="veqp_tipo")
        principal = st.checkbox("Principal", key="veqp_princ")
        if st.button("Adicionar vínculo", use_container_width=True, key="btn_add_veqp", type="primary"):
            vinculos_service.criar_vinculo_equipamento(eqp["id"], resp["id"], tipo, principal)
            st.success("Vínculo adicionado.")
            st.rerun()


def _render_vinculos_setor():
    st.markdown("### Vínculos por setor")
    st.caption("Defina gestor ou supervisor de cada setor para direcionar alertas gerenciais e cobranças.")
    setores = [s for s in setores_service.listar() if s.get("ativo")]
    responsaveis = [r for r in responsaveis_service.listar() if r.get("ativo")]
    if not setores:
        st.info("Cadastre setores primeiro.")
        return
    if not responsaveis:
        st.info("Cadastre responsáveis primeiro.")
        return

    setor = st.selectbox("Setor", setores, format_func=lambda x: x["nome"], key="vsetor_sel")
    vinculos = vinculos_service.listar_por_setor(setor["id"]) if setor else []
    col_lista, col_form = st.columns([1.5, 1])
    with col_lista:
        st.markdown("**Responsáveis atuais**")
        if vinculos:
            for v in vinculos:
                c1, c2, c3 = st.columns([2, 1.4, .5])
                c1.write(f"{'⭐ ' if v['principal'] else ''}{v['responsavel_nome']}")
                c2.caption(v["tipo_responsabilidade"])
                if c3.button("✕", key=f"del_vs_{v['id']}"):
                    vinculos_service.remover_vinculo_setor(v["id"])
                    st.rerun()
        else:
            st.info("Nenhum vínculo.")
    with col_form:
        st.markdown("**Adicionar vínculo**")
        resp = st.selectbox("Responsável", responsaveis, format_func=_fmt_resp, key="vsetor_resp")
        tipo = st.selectbox("Tipo", TIPOS_VINCULO_SETOR, key="vsetor_tipo")
        principal = st.checkbox("Principal", key="vsetor_princ")
        if st.button("Adicionar vínculo", use_container_width=True, key="btn_add_vsetor", type="primary"):
            vinculos_service.criar_vinculo_setor(setor["id"], resp["id"], tipo, principal)
            st.success("Vínculo adicionado.")
            st.rerun()


def render():
    render_page_intro(
        "Vínculos de responsabilidade",
        "Associe pessoas a equipamentos e setores com uma visualização mais limpa para operação e gestão.",
        "Cadastros",
    )
    tab_eqp, tab_setor = st.tabs(["Por equipamento", "Por setor"])
    with tab_eqp:
        _render_vinculos_equipamento()
    with tab_setor:
        _render_vinculos_setor()
