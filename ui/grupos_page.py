from __future__ import annotations

import pandas as pd
import streamlit as st

from services import equipamentos_service, grupos_service, setores_service
from ui.theme import render_page_intro


def _setores_ativos():
    return [s for s in setores_service.listar() if s.get('ativo')]


def _grupo_label(item: dict) -> str:
    dep = item.get('setor_nome') or 'Sem departamento'
    return f"{item.get('nome')} · {dep}"


def render():
    render_page_intro(
        'Grupos operacionais',
        'Cadastre grupos como Caminhões Prancha, Tratores de Apoio e vincule equipamentos em lote por departamento.',
        'Cadastros',
    )

    grupos = grupos_service.listar()
    equipamentos = equipamentos_service.listar()
    setores = _setores_ativos()

    c1, c2, c3 = st.columns(3)
    c1.metric('Total de grupos', len(grupos))
    c2.metric('Grupos ativos', sum(1 for g in grupos if g.get('ativo')))
    c3.metric('Equipamentos com grupo', sum(1 for e in equipamentos if e.get('grupo_id')))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        'Cadastrar grupo',
        'Editar grupo',
        'Ação rápida de vínculo',
        'Lista de grupos',
        'Excluir grupo',
    ])

    with tab1:
        with st.form('form_grupo', clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input('Nome do grupo', placeholder='Ex: Caminhões Prancha')
            with c2:
                ativo = st.checkbox('Ativo', value=True)
            departamento = st.selectbox(
                'Departamento',
                [None] + setores,
                format_func=lambda s: s['nome'] if s else '— sem departamento —',
            )
            submitted = st.form_submit_button('Salvar grupo', type='primary', use_container_width=True)
        if submitted:
            try:
                grupos_service.criar(nome=nome, setor_id=departamento['id'] if departamento else None, ativo=ativo)
                st.success('Grupo cadastrado com sucesso.')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with tab2:
        if not grupos:
            st.info('Nenhum grupo cadastrado.')
        else:
            selecionado = st.selectbox('Grupo para editar', grupos, format_func=_grupo_label)
            opcoes_dep = [None] + [s for s in setores if s.get('id') != selecionado.get('id')]
            dep_atual = next((i for i, s in enumerate(opcoes_dep) if (s or {}).get('id') == selecionado.get('setor_id')), 0)
            with st.form('form_editar_grupo'):
                c1, c2 = st.columns(2)
                with c1:
                    nome_edit = st.text_input('Nome', value=selecionado.get('nome') or '')
                with c2:
                    ativo_edit = st.checkbox('Ativo', value=bool(selecionado.get('ativo', True)))
                dep_edit = st.selectbox('Departamento', opcoes_dep, index=dep_atual, format_func=lambda s: s['nome'] if s else '— sem departamento —')
                submitted = st.form_submit_button('Salvar alterações', type='primary', use_container_width=True)
            if submitted:
                try:
                    grupos_service.editar(
                        grupo_id=selecionado['id'],
                        nome=nome_edit,
                        setor_id=dep_edit['id'] if dep_edit else None,
                        ativo=ativo_edit,
                    )
                    st.success('Grupo atualizado com sucesso.')
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab3:
        if not grupos:
            st.info('Cadastre ao menos um grupo antes de vincular equipamentos.')
        else:
            grupo_destino = st.selectbox('Grupo de destino', grupos, format_func=_grupo_label, key='grupo_vinculo_destino')
            equipamentos_ativos = [e for e in equipamentos if e.get('ativo', True)]
            filtro = st.text_input('Buscar equipamentos por código, nome, tipo, departamento ou grupo atual')
            filtro_norm = (filtro or '').strip().lower()
            if filtro_norm:
                equipamentos_ativos = [
                    e for e in equipamentos_ativos
                    if filtro_norm in ' '.join([
                        str(e.get('codigo', '')),
                        str(e.get('nome', '')),
                        str(e.get('tipo', '')),
                        str(e.get('setor_nome', '')),
                        str(e.get('grupo_nome', '')),
                    ]).lower()
                ]
            opcoes = {f"{e.get('codigo')} · {e.get('nome')} · {e.get('setor_nome') or '-'} · grupo atual: {e.get('grupo_nome') or '—'}": e for e in equipamentos_ativos}
            escolhidos = st.multiselect('Equipamentos', list(opcoes.keys()))
            if st.button('Vincular ao grupo', type='primary', use_container_width=True):
                try:
                    total = grupos_service.vincular_equipamentos(grupo_destino['id'], [opcoes[k]['id'] for k in escolhidos])
                    st.success(f'{total} equipamento(s) vinculado(s) ao grupo.')
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab4:
        if grupos:
            df = pd.DataFrame(grupos).rename(columns={
                'nome': 'Grupo',
                'setor_nome': 'Departamento',
                'ativo': 'Ativo',
                'total_equipamentos': 'Equipamentos',
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('Nenhum grupo cadastrado.')

    with tab5:
        if not grupos:
            st.info('Nenhum grupo cadastrado.')
        else:
            grupo_excluir = st.selectbox('Grupo', grupos, format_func=_grupo_label, key='grupo_excluir')
            desvincular = st.checkbox('Desvincular equipamentos deste grupo antes de excluir', value=True)
            if st.button('Excluir grupo', type='primary', use_container_width=True):
                try:
                    grupos_service.excluir(grupo_excluir['id'], desvincular_equipamentos=desvincular)
                    st.success('Grupo excluído com sucesso.')
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
