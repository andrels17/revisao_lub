from __future__ import annotations


"""Invalidação centralizada dos caches mais usados do app.

Evita st.cache_data.clear() global, que força recarga desnecessária do app inteiro.
"""


def _clear_attr(obj, attr: str) -> None:
    fn = getattr(obj, attr, None)
    if fn is None:
        return
    try:
        fn.clear()
    except Exception:
        pass


def invalidate_planejamento() -> None:
    """Caches de leitura pesada usados em dashboard, alertas e páginas operacionais."""
    from services import dashboard_service, equipamentos_service, lubrificacoes_service, revisoes_service

    _clear_attr(equipamentos_service, "listar")
    _clear_attr(equipamentos_service, "listar_responsaveis_principais")
    _clear_attr(equipamentos_service, "carregar_snapshot_equipamentos")

    _clear_attr(revisoes_service, "listar_controle_revisoes")
    _clear_attr(revisoes_service, "listar_controle_revisoes_por_equipamento")
    _clear_attr(revisoes_service, "listar_controle_revisoes_painel")

    _clear_attr(lubrificacoes_service, "calcular_proximas_lubrificacoes_batch")
    _clear_attr(lubrificacoes_service, "listar_por_equipamento")
    _clear_attr(lubrificacoes_service, "listar_todos")

    _clear_attr(dashboard_service, "carregar_alertas")



def invalidate_execucoes() -> None:
    from services import execucoes_service

    _clear_attr(execucoes_service, "listar_itens_execucao")
    _clear_attr(execucoes_service, "listar_revisoes_por_equipamento")
    _clear_attr(execucoes_service, "resumo_revisoes_por_equipamento")



def invalidate_configuracoes() -> None:
    from services import configuracoes_service

    _clear_attr(configuracoes_service, "carregar_todas")
