from collections import Counter

from services import equipamentos_service, lubrificacoes_service, revisoes_service


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}


def _alerta_revisao(eqp, rev):
    return {
        "equipamento_id": eqp["id"],
        "codigo": eqp["codigo"],
        "equipamento": eqp["nome"],
        "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
        "setor": eqp.get("setor_nome") or "-",
        "origem": "revisao",
        "tipo": rev.get("tipo_controle", eqp.get("tipo") or "-"),
        "etapa": rev["etapa"],
        "atual": float(rev["atual"]),
        "ultima_execucao": float(rev.get("ultima_execucao", 0) or 0),
        "vencimento": float(rev["vencimento"]),
        "falta": float(rev["diferenca"]),
        "status": rev["status"],
        "_ordem": STATUS_ORDEM.get(rev["status"], 99),
    }



def _alerta_lubrificacao(eqp, item):
    return {
        "equipamento_id": eqp["id"],
        "codigo": eqp["codigo"],
        "equipamento": eqp["nome"],
        "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
        "setor": eqp.get("setor_nome") or "-",
        "origem": "lubrificacao",
        "tipo": item.get("tipo_controle", eqp.get("tipo") or "-"),
        "etapa": item["item"],
        "atual": float(item["atual"]),
        "ultima_execucao": float(item.get("ultima_execucao", 0) or 0),
        "vencimento": float(item["vencimento"]),
        "falta": float(item["diferenca"]),
        "status": item["status"],
        "_ordem": STATUS_ORDEM.get(item["status"], 99),
    }



def carregar_alertas():
    equipamentos = equipamentos_service.listar()
    alertas = []
    revisoes_por_equipamento = revisoes_service.listar_controle_revisoes_por_equipamento()

    for eqp in equipamentos:
        for rev in revisoes_por_equipamento.get(eqp["id"], []):
            alertas.append(_alerta_revisao(eqp, rev))

        for item in lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"]):
            alertas.append(_alerta_lubrificacao(eqp, item))

    alertas.sort(key=lambda item: (item["_ordem"], item["falta"], item["equipamento_label"], item["etapa"]))
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
        "equipamentos_com_alerta": len(equipamentos_com_alerta),
        "equipamentos_vencidos": len(equipamentos_vencidos),
        "equipamentos_proximos": len(equipamentos_proximos),
    }



def ranking_setores(alertas):
    contagem = Counter(item["setor"] for item in alertas if item["status"] in {"VENCIDO", "PROXIMO"})
    ranking = []
    for setor, total in contagem.most_common():
        vencidos = sum(1 for item in alertas if item["setor"] == setor and item["status"] == "VENCIDO")
        proximos = sum(1 for item in alertas if item["setor"] == setor and item["status"] == "PROXIMO")
        ranking.append(
            {
                "Setor": setor,
                "Alertas": total,
                "Vencidos": vencidos,
                "Próximos": proximos,
            }
        )
    return ranking
