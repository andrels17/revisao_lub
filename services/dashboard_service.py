from __future__ import annotations

from collections import Counter, defaultdict

from services import equipamentos_service

try:
    from services import lubrificacoes_service
except Exception:  # pragma: no cover
    lubrificacoes_service = None

try:
    from services import revisoes_service
except Exception:  # pragma: no cover
    revisoes_service = None


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
STATUS_PESO = {"VENCIDO": 5, "PROXIMO": 2, "EM DIA": 0, "REALIZADO": -1}


def _float(value, default=0.0):
    try:
        return float(value or default)
    except Exception:
        return float(default)


def _equipamentos_map():
    equipamentos = equipamentos_service.listar()
    return equipamentos, {eq["id"]: eq for eq in equipamentos}


def _carregar_revisoes(eq_map):
    if revisoes_service is None:
        return []

    alertas = []
    try:
        dados_indexados = revisoes_service.listar_controle_revisoes_por_equipamento()
    except Exception:
        dados_indexados = None

    for equipamento_id, eq in eq_map.items():
        try:
            if dados_indexados is not None:
                itens = revisoes_service.calcular_proximas_revisoes(equipamento_id, dados_indexados=dados_indexados)
            else:
                itens = revisoes_service.calcular_proximas_revisoes(equipamento_id)
        except TypeError:
            itens = revisoes_service.calcular_proximas_revisoes(equipamento_id)
        except Exception:
            itens = []

        for item in itens or []:
            atual = _float(item.get("atual", item.get("leitura_atual", 0)))
            ultima = _float(item.get("ultima_execucao", item.get("ultima_leitura_execucao", 0)))
            vencimento = _float(item.get("vencimento", 0))
            falta = _float(item.get("diferenca", item.get("falta", 0)))
            status = (item.get("status") or "EM DIA").upper()
            alertas.append(
                {
                    "origem": "Revisão",
                    "equipamento_id": eq["id"],
                    "codigo": eq.get("codigo") or "-",
                    "equipamento": eq.get("nome") or "-",
                    "equipamento_label": f'{eq.get("codigo") or "-"} - {eq.get("nome") or "-"}',
                    "setor": eq.get("setor_nome") or "-",
                    "controle": item.get("tipo_controle") or item.get("tipo") or eq.get("tipo") or "-",
                    "item": item.get("etapa") or item.get("nome_etapa") or "-",
                    "atual": atual,
                    "referencia_ciclo": _float(item.get("referencia_ciclo", 0)),
                    "executado_em": ultima,
                    "proximo_vencimento": vencimento,
                    "falta": falta,
                    "status": status,
                    "_ordem": STATUS_ORDEM.get(status, 99),
                }
            )
    return alertas


def _carregar_lubrificacoes(eq_map):
    if lubrificacoes_service is None:
        return []

    alertas = []
    for equipamento_id, eq in eq_map.items():
        try:
            itens = lubrificacoes_service.calcular_proximas_lubrificacoes(equipamento_id)
        except Exception:
            itens = []
        for item in itens or []:
            atual = _float(item.get("atual", 0))
            ultima = _float(item.get("ultima_execucao", 0))
            vencimento = _float(item.get("vencimento", 0))
            falta = _float(item.get("diferenca", item.get("falta", 0)))
            status = (item.get("status") or "EM DIA").upper()
            alertas.append(
                {
                    "origem": "Lubrificação",
                    "equipamento_id": eq["id"],
                    "codigo": eq.get("codigo") or "-",
                    "equipamento": eq.get("nome") or "-",
                    "equipamento_label": f'{eq.get("codigo") or "-"} - {eq.get("nome") or "-"}',
                    "setor": eq.get("setor_nome") or "-",
                    "controle": item.get("tipo_controle") or eq.get("tipo") or "-",
                    "item": item.get("item") or item.get("nome_item") or "-",
                    "atual": atual,
                    "referencia_ciclo": _float(item.get("referencia_ciclo", 0)),
                    "executado_em": ultima,
                    "proximo_vencimento": vencimento,
                    "falta": falta,
                    "status": status,
                    "_ordem": STATUS_ORDEM.get(status, 99),
                }
            )
    return alertas


def carregar_alertas():
    equipamentos, eq_map = _equipamentos_map()
    alertas = []
    alertas.extend(_carregar_revisoes(eq_map))
    alertas.extend(_carregar_lubrificacoes(eq_map))
    alertas.sort(key=lambda item: (item["_ordem"], item["falta"], item["equipamento_label"], item["origem"], item["item"]))
    return alertas


def resumo_kpis(alertas):
    equipamentos = equipamentos_service.listar()
    contagem = Counter(item["status"] for item in alertas)
    equipamentos_com_alerta = {item["equipamento_id"] for item in alertas if item["status"] in {"VENCIDO", "PROXIMO"}}
    equipamentos_vencidos = {item["equipamento_id"] for item in alertas if item["status"] == "VENCIDO"}
    equipamentos_proximos = {item["equipamento_id"] for item in alertas if item["status"] == "PROXIMO"}
    equipamentos_realizados = {item["equipamento_id"] for item in alertas if item["status"] == "REALIZADO"}
    return {
        "total_equipamentos": len(equipamentos),
        "vencidos": contagem.get("VENCIDO", 0),
        "proximos": contagem.get("PROXIMO", 0),
        "em_dia": contagem.get("EM DIA", 0),
        "realizados": contagem.get("REALIZADO", 0),
        "equipamentos_com_alerta": len(equipamentos_com_alerta),
        "equipamentos_vencidos": len(equipamentos_vencidos),
        "equipamentos_proximos": len(equipamentos_proximos),
        "equipamentos_realizados": len(equipamentos_realizados),
    }


def ranking_setores(alertas):
    grupos = defaultdict(lambda: {"alertas": 0, "vencidos": 0, "proximos": 0, "realizados": 0, "revisoes": 0, "lubrificacoes": 0})
    for item in alertas:
        setor = item.get("setor") or "-"
        g = grupos[setor]
        if item["status"] in {"VENCIDO", "PROXIMO"}:
            g["alertas"] += 1
        if item["status"] == "VENCIDO":
            g["vencidos"] += 1
        elif item["status"] == "PROXIMO":
            g["proximos"] += 1
        elif item["status"] == "REALIZADO":
            g["realizados"] += 1
        if item.get("origem") == "Revisão":
            g["revisoes"] += 1
        elif item.get("origem") == "Lubrificação":
            g["lubrificacoes"] += 1

    ranking = []
    for setor, info in grupos.items():
        ranking.append(
            {
                "Setor": setor,
                "Alertas": info["alertas"],
                "Vencidos": info["vencidos"],
                "Próximos": info["proximos"],
                "Realizados": info["realizados"],
                "Revisões": info["revisoes"],
                "Lubrificações": info["lubrificacoes"],
            }
        )
    ranking.sort(key=lambda x: (-x["Alertas"], -x["Vencidos"], x["Setor"]))
    return ranking


def top_equipamentos_criticos(alertas, limite=10):
    grupos = defaultdict(lambda: {"score": 0, "vencidos": 0, "proximos": 0, "realizados": 0, "origens": set(), "setor": "-"})
    for item in alertas:
        chave = (item["equipamento_id"], item["equipamento_label"])
        g = grupos[chave]
        g["score"] += STATUS_PESO.get(item["status"], 0)
        g["setor"] = item.get("setor") or "-"
        g["origens"].add(item.get("origem") or "-")
        if item["status"] == "VENCIDO":
            g["vencidos"] += 1
        elif item["status"] == "PROXIMO":
            g["proximos"] += 1
        elif item["status"] == "REALIZADO":
            g["realizados"] += 1

    linhas = []
    for (_, equipamento_label), info in grupos.items():
        linhas.append(
            {
                "Equipamento": equipamento_label,
                "Setor": info["setor"],
                "Score": info["score"],
                "Vencidos": info["vencidos"],
                "Próximos": info["proximos"],
                "Realizados": info["realizados"],
                "Origem": ", ".join(sorted(info["origens"])) if info["origens"] else "-",
            }
        )
    linhas.sort(key=lambda x: (-x["Score"], -x["Vencidos"], -x["Próximos"], x["Equipamento"]))
    return linhas[:limite]
