import pandas as pd
import streamlit as st
from services import equipamentos_service, setores_service
from ui.theme import render_page_intro

TIPOS_NIVEL = ["empresa", "unidade", "departamento", "setor", "subsetor"]


def _rotulo_setor(item: dict) -> str:
    total = int(item.get("total_equipamentos") or 0)
    return f"{item.get('nome', '-')} · {total} equipamento(s)"


def render():
    setores = setores_service.listar()
    equipamentos = equipamentos_service.listar()

    render_page_intro(
        "Estrutura organizacional",
        "Cadastre, organize e agora também mova rapidamente equipamentos entre setores.",
        "Cadastros",
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    c1.metric("Total de setores", len(setores))
    c2.metric("Setores ativos", sum(1 for item in setores if item.get("ativo")))
    c3.metric("Equipamentos vinculados", sum(int(item.get("total_equipamentos") or 0) for item in setores))

    tab1, tab2, tab3, tab4 = st.tabs([
        "Cadastrar setor",
        "Lista de setores",
        "Ação rápida de vínculo",
        "Excluir setor",
    ])

    with tab1:
        st.markdown("### Novo setor")
        st.caption("Use nomes claros e mantenha a hierarquia sempre que existir setor pai.")
        pais = [item for item in setores if item.get("ativo")]
        with st.form("form_setor", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome do setor", placeholder="Ex: Oficina Central")
                tipo_nivel = st.selectbox("Tipo/Nível", TIPOS_NIVEL, index=3)
            with c2:
                ativo = st.checkbox("Ativo", value=True)
                usar_pai = st.checkbox("Vincular a um setor pai")

            setor_pai = None
            if usar_pai:
                if pais:
                    setor_pai = st.selectbox("Setor pai", pais, format_func=lambda x: x["nome"])
                else:
                    st.info("Cadastre um setor base antes de vincular um setor pai.")

            submitted = st.form_submit_button("Salvar setor", type="primary", use_container_width=True)

        if submitted:
            if not nome.strip():
                st.error("Informe o nome do setor.")
            else:
                setores_service.criar(
                    nome=nome.strip(),
                    tipo_nivel=tipo_nivel,
                    setor_pai_id=setor_pai["id"] if setor_pai else None,
                    ativo=ativo,
                )
                st.success("Setor cadastrado com sucesso.")
                st.rerun()

    with tab2:
        if setores:
            df = pd.DataFrame(setores).rename(columns={
                "nome": "Nome",
                "tipo_nivel": "Nível",
                "setor_pai_nome": "Setor pai",
                "ativo": "Ativo",
                "total_equipamentos": "Equipamentos",
            })
            cols = [c for c in ["id", "Nome", "Nível", "Setor pai", "Equipamentos", "Ativo"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum setor encontrado.")

    with tab3:
        st.markdown("### Vincular equipamentos rapidamente")
        st.caption("Selecione um setor de destino e mova vários equipamentos de uma vez.")
        setores_ativos = [s for s in setores if s.get("ativo")]
        if not setores_ativos:
            st.info("Cadastre ao menos um setor ativo para usar essa ação rápida.")
        elif not equipamentos:
            st.info("Nenhum equipamento encontrado para vincular.")
        else:
            setor_destino = st.selectbox(
                "Setor de destino",
                setores_ativos,
                format_func=_rotulo_setor,
                key="setor_vinculo_rapido",
            )
            termo = st.text_input(
                "Buscar equipamentos",
                placeholder="Digite código, nome, tipo ou setor atual",
                key="busca_eq_setor_rapido",
            ).strip().lower()

            elegiveis = []
            for eq in equipamentos:
                alvo = " ".join([
                    str(eq.get("codigo", "")),
                    str(eq.get("nome", "")),
                    str(eq.get("tipo", "")),
                    str(eq.get("setor_nome", "")),
                ]).lower()
                if termo and termo not in alvo:
                    continue
                if str(eq.get("setor_id") or "") == str(setor_destino.get("id")):
                    continue
                elegiveis.append(eq)

            if not elegiveis:
                st.info("Nenhum equipamento elegível para o filtro informado.")
            else:
                selecionados = st.multiselect(
                    "Equipamentos",
                    options=[str(eq.get("id")) for eq in elegiveis],
                    format_func=lambda eid: next(
                        f"{eq.get('codigo')} · {eq.get('nome')} · atual: {eq.get('setor_nome') or '-'}"
                        for eq in elegiveis if str(eq.get("id")) == str(eid)
                    ),
                    key="equipamentos_vinculo_rapido",
                )
                if st.button("Vincular equipamentos selecionados", type="primary", use_container_width=True):
                    if not selecionados:
                        st.warning("Selecione ao menos um equipamento.")
                    else:
                        total = setores_service.vincular_equipamentos(
                            setor_id=setor_destino["id"],
                            equipamento_ids=[int(x) for x in selecionados],
                        )
                        equipamentos_service.limpar_cache()
                        st.success(f"{total} equipamento(s) vinculado(s) ao setor {setor_destino['nome']}.")
                        st.rerun()

    with tab4:
        st.markdown("### Excluir setor")
        st.caption("Se houver equipamentos ou setores filhos, escolha um setor de destino para reaproveitar os vínculos antes da exclusão.")
        if not setores:
            st.info("Nenhum setor encontrado.")
        else:
            setor_excluir = st.selectbox(
                "Setor a excluir",
                setores,
                format_func=_rotulo_setor,
                key="setor_excluir_sel",
            )
            destinos = [s for s in setores if str(s.get("id")) != str(setor_excluir.get("id"))]
            usar_destino = st.checkbox("Mover equipamentos e subníveis para outro setor antes de excluir", value=True)
            destino = None
            if usar_destino and destinos:
                destino = st.selectbox(
                    "Setor de destino",
                    destinos,
                    format_func=lambda x: x.get("nome", "-"),
                    key="setor_excluir_destino",
                )
            elif usar_destino and not destinos:
                st.warning("Não há outro setor disponível como destino.")

            st.write(
                f"Equipamentos neste setor: **{int(setor_excluir.get('total_equipamentos') or 0)}**"
            )
            if st.button("Excluir setor selecionado", use_container_width=True):
                try:
                    setores_service.excluir(
                        setor_id=setor_excluir["id"],
                        destino_setor_id=(destino["id"] if destino and usar_destino else None),
                    )
                    equipamentos_service.limpar_cache()
                    st.success("Setor excluído com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
