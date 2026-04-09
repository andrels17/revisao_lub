from __future__ import annotations

import datetime as dt
import html

import pandas as pd
import streamlit as st

from services import auth_service, ciclos_service


def _render_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">🔄 Operação</div>
            <h2>Ciclos operacionais</h2>
            <p>Abra, acompanhe e feche ciclos formais de revisão e lubrificação com rastreabilidade e histórico confiável.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis(resumo: dict) -> None:
    cards = [
        ('status-info', 'Execuções no ciclo', resumo.get('total_execucoes', 0), 'Registros vinculados'),
        ('status-danger', 'Pendências vencidas', resumo.get('total_vencidos', 0), 'Situação atual consolidada'),
        ('status-warning', 'Próximas do limite', resumo.get('total_proximos', 0), 'Janela de atenção'),
        ('status-success', 'Leituras no ciclo', resumo.get('total_leituras', 0), 'Coletas registradas'),
    ]
    html_cards = ''.join(
        f"<div class='status-kpi {css}'><div class='label'>{html.escape(label)}</div><div class='value'>{int(value)}</div><div class='sub'>{html.escape(sub)}</div></div>"
        for css, label, value, sub in cards
    )
    st.markdown(f"<div class='status-kpi-grid'>{html_cards}</div>", unsafe_allow_html=True)


def _render_schema_alert(diag: dict) -> None:
    faltas = []
    if not diag.get('tem_ciclos'):
        faltas.append('tabela public.ciclos_operacionais')
    if diag.get('tem_execucoes_manutencao') and not diag.get('tem_ciclo_exec_manut'):
        faltas.append('coluna ciclo_id em execucoes_manutencao')
    if diag.get('tem_execucoes_lubrificacao') and not diag.get('tem_ciclo_exec_lub'):
        faltas.append('coluna ciclo_id em execucoes_lubrificacao')
    if diag.get('tem_leituras') and not diag.get('tem_ciclo_leituras'):
        faltas.append('coluna ciclo_id em leituras')

    st.warning('A estrutura de ciclos ainda não está aplicada no banco.')
    if faltas:
        st.caption('Pendências detectadas: ' + ', '.join(faltas))
    with st.expander('Mostrar SQL de migração'):
        st.code(ciclos_service.sql_migracao(), language='sql')
        st.caption('Arquivo no projeto: database/ciclos_operacionais.sql')


def _render_form_abertura(usuario: dict) -> None:
    inicio_sug, fim_sug = ciclos_service.intervalo_semana_sugerido()
    with st.form('form_abrir_ciclo', clear_on_submit=False):
        st.markdown("<div class='filters-shell'><div class='filters-title'>Abrir novo ciclo</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            tipo = st.selectbox('Tipo', ['geral', 'revisao', 'lubrificacao'], format_func=lambda x: ciclos_service.TIPOS_CICLO.get(x, x.title()))
        with c2:
            data_inicio = st.date_input('Início', value=inicio_sug)
        with c3:
            data_fim = st.date_input('Fim', value=fim_sug)
        titulo = st.text_input('Título', value=ciclos_service.titulo_padrao('geral', inicio_sug, fim_sug))
        observacoes = st.text_area('Observações', height=90, placeholder='Opcional')
        st.markdown('</div>', unsafe_allow_html=True)
        salvar = st.form_submit_button('🟢 Abrir ciclo', type='primary', use_container_width=True)
        if salvar:
            ok, msg, _ = ciclos_service.abrir_ciclo(
                tipo=tipo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                criado_por=usuario.get('id'),
                titulo=titulo.strip() or None,
                observacoes=observacoes.strip() or None,
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def _render_resumo_ciclo(ciclo: dict, usuario: dict) -> None:
    resumo = ciclos_service.resumo_ciclo(ciclo['id'])
    st.markdown(
        f"""
        <div class="section-card">
            <h3>{html.escape(ciclo.get('titulo') or 'Ciclo aberto')}</h3>
            <p>Tipo: {html.escape(ciclos_service.TIPOS_CICLO.get(ciclo.get('tipo'), ciclo.get('tipo', '-')))} · Período: {ciclo.get('data_inicio').strftime('%d/%m/%Y')} a {ciclo.get('data_fim').strftime('%d/%m/%Y')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_kpis(resumo)

    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        detalhes = {
            'Revisões no ciclo': resumo.get('total_revisoes', 0),
            'Lubrificações no ciclo': resumo.get('total_lubrificacoes', 0),
            'Leituras no ciclo': resumo.get('total_leituras', 0),
            'Itens em dia agora': resumo.get('total_em_dia', 0),
            'Itens realizados agora': resumo.get('total_realizados', 0),
        }
        st.dataframe(pd.DataFrame([{'Indicador': k, 'Valor': int(v)} for k, v in detalhes.items()]), hide_index=True, use_container_width=True)
    with col_b:
        pode_gerir = auth_service.role_atual() in {'admin', 'gestor'}
        st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
        st.markdown('**Ações do ciclo**')
        st.caption('Fechar congela o período e registra um snapshot quando a tabela de snapshot existir.')
        confirmar = st.checkbox('Confirmo que o ciclo pode ser encerrado.', key='confirmar_fechar_ciclo') if pode_gerir else False
        if pode_gerir:
            if st.button('🔒 Fechar ciclo atual', type='primary', use_container_width=True, disabled=not confirmar):
                ok, msg = ciclos_service.fechar_ciclo(ciclo['id'], fechado_por=usuario.get('id'))
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info('Somente gestor ou administrador pode abrir/fechar ciclos.')
        st.markdown('</div>', unsafe_allow_html=True)


def _render_historico(usuario: dict) -> None:
    ciclos = ciclos_service.listar_ciclos(80)
    if not ciclos:
        st.info('Nenhum ciclo cadastrado ainda.')
        return
    df = pd.DataFrame(ciclos)
    if 'tipo' in df.columns:
        df['tipo'] = df['tipo'].map(lambda x: ciclos_service.TIPOS_CICLO.get(x, x))
    for col in ('data_inicio', 'data_fim', 'criado_em', 'fechado_em'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    view = df[['titulo', 'tipo', 'data_inicio', 'data_fim', 'status', 'criado_em', 'fechado_em']].rename(columns={
        'titulo': 'Título', 'tipo': 'Tipo', 'data_inicio': 'Início', 'data_fim': 'Fim', 'status': 'Status', 'criado_em': 'Criado em', 'fechado_em': 'Fechado em'
    })
    st.dataframe(view, hide_index=True, use_container_width=True)

    fechados = [c for c in ciclos if c.get('status') == 'fechado']
    pode_reabrir = auth_service.role_atual() == 'admin'
    if pode_reabrir and fechados:
        with st.expander('Reabrir ciclo fechado'):
            alvo = st.selectbox(
                'Selecione o ciclo',
                fechados,
                format_func=lambda c: f"{c.get('titulo') or c.get('id')} · {pd.to_datetime(c.get('data_inicio')).strftime('%d/%m/%Y') if c.get('data_inicio') else '-'}",
                key='ciclo_reabrir',
            )
            if st.button('↩️ Reabrir ciclo selecionado', use_container_width=True):
                ok, msg = ciclos_service.reabrir_ciclo(alvo['id'], usuario_id=usuario.get('id'))
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


def render():
    usuario = auth_service.usuario_logado() or {}

    head_l, head_r = st.columns([6, 1], vertical_alignment='center')
    with head_l:
        _render_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button('🔄 Atualizar', use_container_width=True):
            ciclos_service.limpar_cache()
            st.rerun()

    st.markdown("<div class='section-caption'>Formalize períodos de operação sem mexer na lógica dinâmica de revisão e lubrificação.</div>", unsafe_allow_html=True)

    diag = ciclos_service.diagnostico_schema()
    if not diag.get('tem_ciclos') or (diag.get('tem_execucoes_manutencao') and not diag.get('tem_ciclo_exec_manut')):
        _render_schema_alert(diag)

    aberto = ciclos_service.obter_ciclo_aberto() or ciclos_service.obter_ciclo_aberto('geral')
    pode_gerir = auth_service.role_atual() in {'admin', 'gestor'}

    if aberto:
        _render_resumo_ciclo(aberto, usuario)
    elif pode_gerir:
        _render_form_abertura(usuario)
    else:
        st.info('Nenhum ciclo aberto no momento.')

    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)
    st.subheader('Histórico de ciclos')
    _render_historico(usuario)
