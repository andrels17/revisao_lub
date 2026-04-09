from collections import Counter, defaultdict

import streamlit as st

from services import equipamentos_service, lubrificacoes_service, revisoes_service

STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
TTL_ALERTAS = 120  # segundos


@st.cache_data(ttl=TTL_ALERTAS, show_spinner="Carregando alertas…")
def carregar_alertas():
    """
    Carrega todos os alertas em batch:
      - 1 query para todos os equipamentos
      - 1 query batch para todas as revisões
      - 1 query batch para todas as lubrificações
    """
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return [], 0

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    revisoes_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)

    alertas = []
    for eqp_id in ids:
        eqp = eqp_map[eqp_id]

        for rev in revisoes_idx.get(eqp_id, []):
            alertas.append({
                "origem": "Revisão",
                "equipamento_id": eqp_id,
                "codigo": eqp["codigo"],
                "equipamento": eqp["nome"],
                "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                "setor": eqp.get("setor_nome") or "-",
                "tipo": rev.get("tipo_controle", eqp.get("tipo") or "-"),
                "etapa": rev["etapa"],
                "atual": float(rev.get("atual", 0) or 0),
                "ultima_execucao": float(rev.get("ultima_execucao", 0) or 0),
                "vencimento": float(rev.get("vencimento", 0) or 0),
                "falta": float(rev.get("diferenca", 0) or 0),
                "status": rev["status"],
                "_ordem": STATUS_ORDEM.get(rev["status"], 99),
            })

        for lub in lub_idx.get(eqp_id, []):
            alertas.append({
                "origem": "Lubrificação",
                "equipamento_id": eqp_id,
                "codigo": eqp["codigo"],
                "equipamento": eqp["nome"],
                "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                "setor": eqp.get("setor_nome") or "-",
                "tipo": lub.get("tipo_controle", "-"),
                "etapa": lub["item"],
                "atual": float(lub.get("atual", 0) or 0),
                "ultima_execucao": float(lub.get("ultima_execucao", 0) or 0),
                "vencimento": float(lub.get("vencimento", 0) or 0),
                "falta": float(lub.get("diferenca", 0) or 0),
                "status": lub["status"],
                "_ordem": STATUS_ORDEM.get(lub["status"], 99),
            })

    alertas.sort(key=lambda x: (x["_ordem"], x["falta"], x["equipamento_label"], x["origem"]))
    return alertas, len(equipamentos)


def resumo_kpis(alertas, total_equipamentos: int):
    contagem = Counter(item["status"] for item in alertas)
    eqp_alerta = {a["equipamento_id"] for a in alertas if a["status"] in {"VENCIDO", "PROXIMO"}}
    eqp_vencido = {a["equipamento_id"] for a in alertas if a["status"] == "VENCIDO"}
    eqp_proximo = {a["equipamento_id"] for a in alertas if a["status"] == "PROXIMO"}

    return {
        "total_equipamentos": total_equipamentos,
        "total_alertas": len(alertas),
        "vencidos": contagem.get("VENCIDO", 0),
        "proximos": contagem.get("PROXIMO", 0),
        "em_dia": contagem.get("EM DIA", 0),
        "equipamentos_com_alerta": len(eqp_alerta),
        "equipamentos_vencidos": len(eqp_vencido),
        "equipamentos_proximos": len(eqp_proximo),
    }


def ranking_setores(alertas):
    acum = defaultdict(lambda: {"Alertas": 0, "Vencidos": 0, "Próximos": 0, "Revisões": 0, "Lubrificações": 0})

    for a in alertas:
        if a["status"] not in {"VENCIDO", "PROXIMO"}:
            continue
        setor = a.get("setor") or "-"
        bucket = acum[setor]
        bucket["Alertas"] += 1
        if a["status"] == "VENCIDO":
            bucket["Vencidos"] += 1
        if a["status"] == "PROXIMO":
            bucket["Próximos"] += 1
        if a["origem"] == "Revisão":
            bucket["Revisões"] += 1
        if a["origem"] == "Lubrificação":
            bucket["Lubrificações"] += 1

    ranking = [{"Setor": setor, **dados} for setor, dados in acum.items()]
    ranking.sort(key=lambda x: (-x["Alertas"], -x["Vencidos"], x["Setor"]))
    return ranking


def ranking_equipamentos_criticos(alertas, limite=10):
    acum = defaultdict(lambda: {"setor": "-", "vencidos": 0, "proximos": 0, "revisoes": 0, "lubrificacoes": 0})

    for a in alertas:
        if a["status"] not in {"VENCIDO", "PROXIMO"}:
            continue
        bucket = acum[a["equipamento_label"]]
        bucket["setor"] = a.get("setor") or "-"
        if a["status"] == "VENCIDO":
            bucket["vencidos"] += 1
        if a["status"] == "PROXIMO":
            bucket["proximos"] += 1
        if a["origem"] == "Revisão":
            bucket["revisoes"] += 1
        if a["origem"] == "Lubrificação":
            bucket["lubrificacoes"] += 1

    ranking = [
        {
            "Equipamento": eq,
            "Setor": dados["setor"],
            "Vencidos": dados["vencidos"],
            "Próximos": dados["proximos"],
            "Revisões": dados["revisoes"],
            "Lubrificações": dados["lubrificacoes"],
            "Criticidade": dados["vencidos"] * 3 + dados["proximos"],
        }
        for eq, dados in acum.items()
    ]
    ranking.sort(key=lambda x: (-x["Criticidade"], -x["Vencidos"], -x["Próximos"], x["Equipamento"]))
    return ranking[:limite]
