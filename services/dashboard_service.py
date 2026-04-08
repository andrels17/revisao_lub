from collections import Counter, defaultdict

import streamlit as st

from services import equipamentos_service, lubrificacoes_service, revisoes_service


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}

TTL_ALERTAS = 60  # segundos — ajuste conforme necessidade


@st.cache_data(ttl=TTL_ALERTAS, show_spinner="Carregando alertas…")
def carregar_alertas():
    equipamentos = equipamentos_service.listar()
    revisoes_indexadas = revisoes_service.listar_controle_revisoes_por_equipamento()
    alertas = []

    for eqp in equipamentos:
        for rev in revisoes_service.calcular_proximas_revisoes(eqp["id"], revisoes_indexadas):
            alertas.append(
                {
                    "origem": "Revisão",
                    "equipamento_id": eqp["id"],
                    "codigo": eqp["codigo"],
                    "equipamento": eqp["nome"],
                    "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                    "setor": eqp.get("setor_nome") or "-",
                    "tipo": rev.get("tipo_controle", eqp.get("tipo") or "-"),
                    "etapa": rev["etapa"],
                    "atual": float(rev["atual"]),
                    "ultima_execucao": float(rev.get("ultima_execucao", 0) or 0),
                    "vencimento": float(rev["vencimento"]),
                    "falta": float(rev["diferenca"]),
                    "status": rev["status"],
                    "_ordem": STATUS_ORDEM.get(rev["status"], 99),
                }
            )

        for lub in lubrificacoes_service.calcular_proximas_lubrificacoes(eqp["id"]):
            alertas.append(
                {
                    "origem": "Lubrificação",
                    "equipamento_id": eqp["id"],
                    "codigo": eqp["codigo"],
                    "equipamento": eqp["nome"],
                    "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                    "setor": eqp.get("setor_nome") or "-",
                    "tipo": lub.get("tipo_controle", "-"),
                    "etapa": lub["item"],
                    "atual": float(lub["atual"]),
                    "ultima_execucao": float(lub.get("ultima_execucao", 0) or 0),
                    "vencimento": float(lub["vencimento"]),
                    "falta": float(lub["diferenca"]),
                    "status": lub["status"],
                    "_ordem": STATUS_ORDEM.get(lub["status"], 99),
                }
            )

    alertas.sort(key=lambda item: (item["_ordem"], item["falta"], item["equipamento_label"], item["origem"]))
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
        revisoes = sum(1 for item in alertas if item["setor"] == setor and item["origem"] == "Revisão" and item["status"] in {"VENCIDO", "PROXIMO"})
        lubrificacoes = sum(1 for item in alertas if item["setor"] == setor and item["origem"] == "Lubrificação" and item["status"] in {"VENCIDO", "PROXIMO"})
        ranking.append(
            {
                "Setor": setor,
                "Alertas": total,
                "Vencidos": vencidos,
                "Próximos": proximos,
                "Revisões": revisoes,
                "Lubrificações": lubrificacoes,
            }
        )
    return ranking



def ranking_equipamentos_criticos(alertas, limite=10):
    acumulado = defaultdict(lambda: {"setor": "-", "vencidos": 0, "proximos": 0, "revisoes": 0, "lubrificacoes": 0})
    for item in alertas:
        if item["status"] not in {"VENCIDO", "PROXIMO"}:
            continue
        bucket = acumulado[item["equipamento_label"]]
        bucket["setor"] = item.get("setor") or "-"
        if item["status"] == "VENCIDO":
            bucket["vencidos"] += 1
        if item["status"] == "PROXIMO":
            bucket["proximos"] += 1
        if item["origem"] == "Revisão":
            bucket["revisoes"] += 1
        else:
            bucket["lubrificacoes"] += 1

    ranking = []
    for equipamento, dados in acumulado.items():
        criticidade = (dados["vencidos"] * 3) + dados["proximos"]
        ranking.append(
            {
                "Equipamento": equipamento,
                "Setor": dados["setor"],
                "Vencidos": dados["vencidos"],
                "Próximos": dados["proximos"],
                "Revisões": dados["revisoes"],
                "Lubrificações": dados["lubrificacoes"],
                "Criticidade": criticidade,
            }
        )

    ranking.sort(key=lambda x: (-x["Criticidade"], -x["Vencidos"], -x["Próximos"], x["Equipamento"]))
    return ranking[:limite]
