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
    from services import dashboard_service, equipamentos_service, lubrificacoes_service, prioridades_service, revisoes_service

    _clear_attr(equipamentos_service, "listar")
    _clear_attr(equipamentos_service, "obter")
    _clear_attr(equipamentos_service, "listar_responsaveis_principais")
    _clear_attr(equipamentos_service, "carregar_snapshot_equipamentos")

    _clear_attr(revisoes_service, "listar_controle_revisoes")
    _clear_attr(revisoes_service, "listar_controle_revisoes_por_equipamento")
    _clear_attr(revisoes_service, "listar_controle_revisoes_painel")

    _clear_attr(lubrificacoes_service, "calcular_proximas_lubrificacoes_batch")
    _clear_attr(lubrificacoes_service, "listar_por_equipamento")
    _clear_attr(lubrificacoes_service, "listar_todos")

    _clear_attr(dashboard_service, "carregar_alertas")
    _clear_attr(dashboard_service, "carregar_movimentacao")

    try:
        prioridades_service.limpar_cache()
    except Exception:
        pass



def invalidate_execucoes() -> None:
    from services import execucoes_service

    _clear_attr(execucoes_service, "listar_itens_execucao")
    _clear_attr(execucoes_service, "listar_revisoes_por_equipamento")
    _clear_attr(execucoes_service, "resumo_revisoes_por_equipamento")



def invalidate_configuracoes() -> None:
    from services import configuracoes_service

    _clear_attr(configuracoes_service, "carregar_todas")



def invalidate_templates() -> None:
    from services import templates_integracao_service, templates_lubrificacao_service, templates_revisao_service

    _clear_attr(templates_revisao_service, "listar")
    _clear_attr(templates_revisao_service, "listar_com_etapas")

    _clear_attr(templates_lubrificacao_service, "listar")
    _clear_attr(templates_lubrificacao_service, "listar_com_itens")
    _clear_attr(templates_lubrificacao_service, "_get_table_columns_cached")

    _clear_attr(templates_integracao_service, "listar_vinculos")
    _clear_attr(templates_integracao_service, "listar_overrides_etapas")
    _clear_attr(templates_integracao_service, "obter_mapa_vinculos_por_template_revisao")
    _clear_attr(templates_integracao_service, "sugerir_vinculos_automaticos")


def invalidate_vinculos() -> None:
    from services import equipamentos_service, vinculos_service

    _clear_attr(vinculos_service, "listar_por_equipamento")
    _clear_attr(vinculos_service, "listar_por_setor")
    _clear_attr(vinculos_service, "responsavel_gestao_setor")
    _clear_attr(vinculos_service, "mapa_responsaveis_operacionais")
    _clear_attr(vinculos_service, "mapa_responsaveis_gestao")

    _clear_attr(equipamentos_service, "listar_responsaveis_principais")
    _clear_attr(equipamentos_service, "carregar_snapshot_equipamentos")
