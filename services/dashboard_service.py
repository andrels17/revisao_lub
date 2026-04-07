from collections import Counter, defaultdict

from services import equipamentos_service, lubrificacoes_service, revisoes_service


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
PESO_CRITICIDADE = {"VENCIDO": 5, "PROXIMO": 2, "EM DIA": 0, "REALIZADO": -1}


def _iterar_revisoes_por_equipamento(equipamentos):
    """Carrega revisões uma única vez quando possível."""
    listar_controle = getattr(revisoes_service, "listar_controle_revisoes", None)
    if callable(listar_controle):
        try:
            rows = listar_controle()
            agrupado = defaultdict(list)
            for item in rows:
                agrupado[item["equipamento_id"]].append(item)
            for eqp in equipamentos:
                yield eqp, agrupado.get(eqp["id"], [])
            return
        except Exception:
            # cai no fallback por equipamento se a view ainda não existir
            pass

    for eqp in equipamentos:
        calcular = getattr(revisoes_service, "calcular_proximas_revisoes")
        try:
            revisoes = calcular(eqp["id"])
        except Exception:
            revisoes = []
        yield eqp, revisoes


def _normalizar_alerta_revisao(eqp, rev):
    atual = float(
        rev.get("atual", rev.get("leitura_atual", rev.get("km_atual", rev.get("horas_atual", 0)))) or 0
    )
    ultima_execucao = float(rev.get("ultima_execucao", rev.get("ultima_leitura_execucao", 0)) or 0)
    vencimento = float(rev.get("vencimento", 0) or 0)
    falta = float(rev.get("diferenca", rev.get("falta", 0)) or 0)
    return {
        "origem": "Revisão",
        "equipamento_id": eqp["id"],
        "codigo": eqp["codigo"],
        "equipamento": eqp["nome"],
        "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
        "setor": eqp.get("setor_nome") or rev.get("setor_nome") or "-",
        "tipo": rev.get("tipo_controle", eqp.get("tipo") or "-"),
        "item": rev.get("etapa") or rev.get("nome_etapa") or "Revisão",
        "atual": atual,
        "ultima_execucao": ultima_execucao,
        "vencimento": vencimento,
        "falta": falta,
        "status": rev.get("status") or "EM DIA",
        "_ordem": STATUS_ORDEM.get(rev.get("status") or "EM DIA", 99),
    }


def _normalizar_alerta_lubrificacao(eqp, item):
    atual = float(item.get("atual", 0) or 0)
    ultima_execucao = float(item.get("ultima_execucao", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    falta = float(item.get("diferenca", 0) or 0)
    return {
        "origem": "Lubrificação",
        "equipamento_id": eqp["id"],
        "codigo": eqp["codigo"],
        "equipamento": eqp["nome"],
        "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
        "setor": eqp.get("setor_nome") or "-",
        "tipo": item.get("tipo_controle", eqp.get("tipo") or "-"),
        "item": item.get("item") or "Lubrificação",
        "atual": atual,
        "ultima_execucao": ultima_execucao,
        "vencimento": vencimento,
        "falta": falta,
        "status": item.get("status") or "EM DIA",
        "_ordem": STATUS_ORDEM.get(item.get("status") or "EM DIA", 99),
    }


def carregar_alertas():
    equipamentos = equipamentos_service.listar()
    alertas = []

    for eqp, revisoes in _iterar_revisoes_por_equipamento(equipamentos):
        for rev in revisoes:
            alertas.append(_normalizar_alerta_revisao(eqp, rev))

        try:
            lubrificacoes = lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"])
        except Exception:
            lubrificacoes = []
        for item in lubrificacoes:
            alertas.append(_normalizar_alerta_lubrificacao(eqp, item))

    alertas.sort(
        key=lambda item: (
            item["_ordem"],
            0 if item["origem"] == "Revisão" else 1,
            item["falta"],
            item["equipamento_label"],
            item["item"],
        )
    )
    return alertas


def resumo_kpis(alertas):
    contagem = Counter(item["status"] for item in alertas)
    equipamentos = equipamentos_service.listar()
    equipamentos_com_alerta = {item["equipamento_id"] for item in alertas if item["status"] in {"VENCIDO", "PROXIMO"}}
    equipamentos_vencidos = {item["equipamento_id"] for item in alertas if item["status"] == "VENCIDO"}
    equipamentos_proximos = {item["equipamento_id"] for item in alertas if item["status"] == "PROXIMO"}

    return {
        "total_equipamentos": len(equipamentos),
        "total_alertas": len(alertas),
        "vencidos": contagem.get("VENCIDO", 0),
        "proximos": contagem.get("PROXIMO", 0),
        "em_dia": contagem.get("EM DIA", 0),
        "realizados": contagem.get("REALIZADO", 0),
        "equipamentos_com_alerta": len(equipamentos_com_alerta),
        "equipamentos_vencidos": len(equipamentos_vencidos),
        "equipamentos_proximos": len(equipamentos_proximos),
        "itens_revisao": sum(1 for item in alertas if item["origem"] == "Revisão"),
        "itens_lubrificacao": sum(1 for item in alertas if item["origem"] == "Lubrificação"),
    }


def ranking_setores(alertas):
    grupos = defaultdict(list)
    for item in alertas:
        if item["status"] in {"VENCIDO", "PROXIMO"}:
            grupos[item["setor"]].append(item)

    ranking = []
    for setor, itens in grupos.items():
        ranking.append(
            {
                "Setor": setor,
                "Alertas": len(itens),
                "Vencidos": sum(1 for item in itens if item["status"] == "VENCIDO"),
                "Próximos": sum(1 for item in itens if item["status"] == "PROXIMO"),
                "Revisões": sum(1 for item in itens if item["origem"] == "Revisão"),
                "Lubrificações": sum(1 for item in itens if item["origem"] == "Lubrificação"),
            }
        )

    ranking.sort(key=lambda row: (-row["Vencidos"], -row["Próximos"], -row["Alertas"], row["Setor"]))
    return ranking


def ranking_equipamentos(alertas, limite=10):
    grupos = defaultdict(list)
    for item in alertas:
        grupos[item["equipamento_id"]].append(item)

    ranking = []
    for equipamento_id, itens in grupos.items():
        criticidade = sum(PESO_CRITICIDADE.get(item["status"], 0) for item in itens)
        ranking.append(
            {
                "equipamento_id": equipamento_id,
                "Equipamento": itens[0]["equipamento_label"],
                "Setor": itens[0]["setor"],
                "Criticidade": criticidade,
                "Vencidos": sum(1 for item in itens if item["status"] == "VENCIDO"),
                "Próximos": sum(1 for item in itens if item["status"] == "PROXIMO"),
                "Realizados": sum(1 for item in itens if item["status"] == "REALIZADO"),
                "Revisões": sum(1 for item in itens if item["origem"] == "Revisão"),
                "Lubrificações": sum(1 for item in itens if item["origem"] == "Lubrificação"),
            }
        )

    ranking.sort(
        key=lambda row: (-row["Criticidade"], -row["Vencidos"], -row["Próximos"], row["Equipamento"])
    )
    return ranking[:limite]
