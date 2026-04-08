from collections import Counter, defaultdict

import streamlit as st

from services import equipamentos_service, lubrificacoes_service, revisoes_service

STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
TTL_ALERTAS  = 60   # segundos


@st.cache_data(ttl=TTL_ALERTAS, show_spinner="Carregando alertas…")
def carregar_alertas():
    """
    Carrega todos os alertas em batch:
      - 1 query para todos os equipamentos
      - 1 query batch para todas as revisões   (revisoes_service)
      - 1 query batch para todas as lubrificações (lubrificacoes_service)
    Total: ~3 queries independente de quantos equipamentos existam.
    """
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return []

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}

    # Batch de revisões — já indexado por equipamento_id
    revisoes_idx = revisoes_service.listar_controle_revisoes_por_equipamento()

    # Batch de lubrificações — 1 query para todos
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)

    alertas = []

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]

        for rev in revisoes_idx.get(eqp_id, []):
            alertas.append({
                "origem":           "Revisão",
                "equipamento_id":   eqp_id,
                "codigo":           eqp["codigo"],
                "equipamento":      eqp["nome"],
                "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                "setor":            eqp.get("setor_nome") or "-",
                "tipo":             rev.get("tipo_controle", eqp.get("tipo") or "-"),
                "etapa":            rev["etapa"],
                "atual":            float(rev["atual"]),
                "ultima_execucao":  float(rev.get("ultima_execucao", 0) or 0),
                "vencimento":       float(rev["vencimento"]),
                "falta":            float(rev["diferenca"]),
                "status":           rev["status"],
                "_ordem":           STATUS_ORDEM.get(rev["status"], 99),
            })

        for lub in lub_idx.get(eqp_id, []):
            alertas.append({
                "origem":           "Lubrificação",
                "equipamento_id":   eqp_id,
                "codigo":           eqp["codigo"],
                "equipamento":      eqp["nome"],
                "equipamento_label": f'{eqp["codigo"]} - {eqp["nome"]}',
                "setor":            eqp.get("setor_nome") or "-",
                "tipo":             lub.get("tipo_controle", "-"),
                "etapa":            lub["item"],
                "atual":            float(lub["atual"]),
                "ultima_execucao":  float(lub.get("ultima_execucao", 0) or 0),
                "vencimento":       float(lub["vencimento"]),
                "falta":            float(lub["diferenca"]),
                "status":           lub["status"],
                "_ordem":           STATUS_ORDEM.get(lub["status"], 99),
            })

    alertas.sort(key=lambda x: (x["_ordem"], x["falta"], x["equipamento_label"], x["origem"]))
    return alertas


def resumo_kpis(alertas):
    contagem  = Counter(item["status"] for item in alertas)
    eqp_alerta  = {a["equipamento_id"] for a in alertas if a["status"] in {"VENCIDO", "PROXIMO"}}
    eqp_vencido = {a["equipamento_id"] for a in alertas if a["status"] == "VENCIDO"}
    eqp_proximo = {a["equipamento_id"] for a in alertas if a["status"] == "PROXIMO"}
    total_eqp   = len(equipamentos_service.listar())
    return {
        "total_equipamentos":     total_eqp,
        "total_alertas":          len(alertas),
        "vencidos":               contagem.get("VENCIDO", 0),
        "proximos":               contagem.get("PROXIMO", 0),
        "em_dia":                 contagem.get("EM DIA", 0),
        "equipamentos_com_alerta": len(eqp_alerta),
        "equipamentos_vencidos":  len(eqp_vencido),
        "equipamentos_proximos":  len(eqp_proximo),
    }


def ranking_setores(alertas):
    contagem = Counter(a["setor"] for a in alertas if a["status"] in {"VENCIDO", "PROXIMO"})
    ranking  = []
    for setor, total in contagem.most_common():
        vencidos    = sum(1 for a in alertas if a["setor"] == setor and a["status"] == "VENCIDO")
        proximos    = sum(1 for a in alertas if a["setor"] == setor and a["status"] == "PROXIMO")
        revisoes    = sum(1 for a in alertas if a["setor"] == setor and a["origem"] == "Revisão"     and a["status"] in {"VENCIDO", "PROXIMO"})
        lubrif      = sum(1 for a in alertas if a["setor"] == setor and a["origem"] == "Lubrificação" and a["status"] in {"VENCIDO", "PROXIMO"})
        ranking.append({"Setor": setor, "Alertas": total, "Vencidos": vencidos,
                        "Próximos": proximos, "Revisões": revisoes, "Lubrificações": lubrif})
    return ranking


def ranking_equipamentos_criticos(alertas, limite=10):
    acum = defaultdict(lambda: {"setor": "-", "vencidos": 0, "proximos": 0, "revisoes": 0, "lubrificacoes": 0})
    for a in alertas:
        if a["status"] not in {"VENCIDO", "PROXIMO"}:
            continue
        b = acum[a["equipamento_label"]]
        b["setor"] = a.get("setor") or "-"
        b["vencidos"]      += a["status"] == "VENCIDO"
        b["proximos"]      += a["status"] == "PROXIMO"
        b["revisoes"]      += a["origem"] == "Revisão"
        b["lubrificacoes"] += a["origem"] == "Lubrificação"

    ranking = [
        {
            "Equipamento":   eq,
            "Setor":         d["setor"],
            "Vencidos":      d["vencidos"],
            "Próximos":      d["proximos"],
            "Revisões":      d["revisoes"],
            "Lubrificações": d["lubrificacoes"],
            "Criticidade":   d["vencidos"] * 3 + d["proximos"],
        }
        for eq, d in acum.items()
    ]
    ranking.sort(key=lambda x: (-x["Criticidade"], -x["Vencidos"], -x["Próximos"], x["Equipamento"]))
    return ranking[:limite]
