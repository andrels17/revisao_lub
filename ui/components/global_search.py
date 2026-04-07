import streamlit as st
from services import equipamentos_service


STATUS_LABELS = {
    'VENCIDO': '🔴 Vencido',
    'PROXIMO': '🟡 Próximo',
    'EM DIA': '🟢 Em dia',
    'REALIZADO': '✅ Realizado',
    'REALIZADO NO CICLO': '✅ Realizado',
}


def _format_resultado(item: dict) -> str:
    base = f"{item.get('codigo', '-') } - {item.get('nome', '-') }"
    meta = []
    if item.get('setor_nome'):
        meta.append(item['setor_nome'])
    if item.get('tipo'):
        meta.append(item['tipo'])
    status = item.get('status_resumo')
    if status:
        meta.append(STATUS_LABELS.get(status, status.title()))
    return f"{base} | {' • '.join(meta)}" if meta else base


def render():
    st.markdown('### 🔎 Busca global de equipamentos')
    termo = st.text_input(
        'Buscar por código, nome, setor ou tipo',
        key='global_equipment_search_term',
        placeholder='Ex.: TR-204, colheitadeira, oficina, pulverizador...',
    )

    if not termo or len(termo.strip()) < 2:
        st.caption('Digite pelo menos 2 caracteres para buscar.')
        return

    resultados = equipamentos_service.buscar_rapida(termo.strip(), limite=12)
    if not resultados:
        st.info('Nenhum equipamento encontrado para esse termo.')
        return

    opcoes = { _format_resultado(item): item for item in resultados }
    escolha = st.selectbox('Resultados', list(opcoes.keys()), key='global_search_result')
    selecionado = opcoes[escolha]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('KM atual', f"{float(selecionado.get('km_atual', 0) or 0):,.0f}".replace(',', '.'))
    c2.metric('Horas atuais', f"{float(selecionado.get('horas_atual', 0) or 0):,.0f}".replace(',', '.'))
    c3.metric('Setor', selecionado.get('setor_nome') or '-')
    c4.metric('Status', STATUS_LABELS.get(selecionado.get('status_resumo'), '—'))

    if st.button('Abrir acesso rápido do equipamento', use_container_width=True):
        st.session_state['main_menu'] = '🚜 Equipamentos'
        st.session_state['quick_equipment_id'] = selecionado['id']
        st.rerun()
