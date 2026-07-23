"""Navegação programática entre páginas (usada por botões tipo "Abrir
revisões", vindos de outra página, ex.: Prioridades -> Controle de Revisões).

Compatível com o roteamento nativo `st.navigation`/`st.Page` do main.py:
o próprio main.py registra os objetos `st.Page` aqui em `registrar_paginas()`,
e qualquer página pode chamar `ir_para(nome_pagina)` usando o mesmo rótulo
com emoji que aparece em `SECOES` (ex.: "🔧 Controle de Revisões").
"""

from __future__ import annotations

import streamlit as st

_REGISTRY_KEY = "_nav_pages_registry"


def registrar_paginas(paginas: dict[str, "st.Page"]) -> None:
    """Chamado uma vez pelo main.py com {nome_pagina: st.Page}."""
    st.session_state[_REGISTRY_KEY] = paginas


def ir_para(nome_pagina: str, **parametros_sessao) -> None:
    """Navega para outra página pelo nome usado em SECOES (ex.: '🚜 Equipamentos').

    `parametros_sessao` são valores opcionais a gravar em session_state antes
    de trocar de página (ex.: filtros pré-selecionados).
    """
    for chave, valor in parametros_sessao.items():
        st.session_state[chave] = valor

    registro = st.session_state.get(_REGISTRY_KEY) or {}
    pagina = registro.get(nome_pagina)
    if pagina is not None:
        st.switch_page(pagina)
    else:
        # Fallback defensivo: se o registro não foi populado por algum motivo,
        # evita quebrar a página atual — apenas atualiza sem navegar.
        st.rerun()
