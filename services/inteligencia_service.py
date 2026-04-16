from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import streamlit as st

from services import dashboard_service


SEVERIDADE_ORDEM = {"critico": 0, "alto": 1, "medio": 2, "baixo": 3}
SEVERIDADE_LABEL = {
    "critico": "Crítico",
    "alto": "Alto",
    "medio": "Médio",
    "baixo": "Baixo",
}
SEVERIDADE_SCORE = {
    "critico": 100,
    "alto": 80,
    "medio": 55,
    "baixo": 30,
}

ACAO_PADRAO = {
    "revisao_vencida": "Programar execução imediata da revisão e verificar backlog do setor.",
    "lubrificacao_vencida": "Programar lubrificação imediata e revisar rotina preventiva.",
    "revisao_proxima": "Planejar execução preventiva antes do vencimento do próximo ciclo.",
    "lubrificacao_proxima": "Antecipar lubrificação e alinhar parada com a operação.",
    "equipamento_parado": "Validar se o equipamento está realmente parado ou sem apontamento de leitura.",
    "leitura_travada": "Conferir horímetro/odômetro e validar se houve falha de apontamento.",
    "salto_anormal": "Auditar leitura lançada e confirmar possível erro operacional ou troca de medidor.",
    "inconsistencia_km_h": "Conferir coerência entre KM e horas antes de usar o dado em planejamento.",
}


def _status_to_tipo(status: str, origem: str) -> str:
    origem_norm = (origem or "").strip().lower()
    if status == "VENCIDO":
        return "revisao_vencida" if origem_norm == "revisão" else "lubrificacao_vencida"
    return "revisao_proxima" if origem_norm == "revisão" else "lubrificacao_proxima"


def _severidade_alerta(status: str, origem: str) -> str:
    if status == "VENCIDO":
        return "critico"
    if status == "PROXIMO":
        return "alto" if (origem or "").strip().lower() == "revisão" else "medio"
    return "baixo"


def _categoria(tipo: str) -> str:
    return {
        "revisao_vencida": "Manutenção",
        "lubrificacao_vencida": "Manutenção",
        "revisao_proxima": "Planejamento",
        "lubrificacao_proxima": "Planejamento",
        "equipamento_parado": "Movimentação",
        "leitura_travada": "Leituras",
        "salto_anormal": "Leituras",
        "inconsistencia_km_h": "Leituras",
    }.get(tipo, "Operação")


def _top_setor(itens: list[dict[str, Any]]) -> str:
    cont = Counter((i.get("setor") or "-") for i in itens)
    return cont.most_common(1)[0][0] if cont else "-"


@st.cache_data(ttl=90, show_spinner=False)
def gerar_alertas_inteligentes(limite: int = 50) -> dict[str, Any]:
    alertas_base, total_equipamentos = dashboard_service.carregar_alertas()
    movimentacao = dashboard_service.carregar_movimentacao()

    itens: list[dict[str, Any]] = []

    for a in alertas_base:
        if a.get("status") not in {"VENCIDO", "PROXIMO"}:
            continue
        tipo = _status_to_tipo(a.get("status") or "", a.get("origem") or "")
        severidade = _severidade_alerta(a.get("status") or "", a.get("origem") or "")
        itens.append({
            "tipo": tipo,
            "titulo": f"{a.get('origem') or 'Item'} {str(a.get('status') or '').title()}",
            "descricao": f"{a.get('equipamento_label') or '-'} · {a.get('etapa') or '-'}",
            "equipamento": a.get("equipamento_label") or "-",
            "setor": a.get("setor") or "-",
            "origem": a.get("origem") or "-",
            "status": a.get("status") or "-",
            "severidade": severidade,
            "criticidade": SEVERIDADE_SCORE[severidade] + (8 if a.get("status") == "VENCIDO" else 0),
            "acao": ACAO_PADRAO.get(tipo, "Avaliar item e definir ação corretiva."),
            "contexto": {
                "atual": a.get("atual"),
                "vencimento": a.get("vencimento"),
                "falta": a.get("falta"),
                "etapa": a.get("etapa"),
            },
        })

    for p in movimentacao.get("alertas_parados") or []:
        dias = int(p.get("Dias parado") or 0)
        severidade = "critico" if dias >= 14 else "alto" if dias >= 7 else "medio"
        itens.append({
            "tipo": "equipamento_parado",
            "titulo": "Equipamento sem movimentação",
            "descricao": f"{p.get('Equipamento') or '-'} · {dias} dia(s) sem leitura",
            "equipamento": p.get("Equipamento") or "-",
            "setor": p.get("Setor") or "-",
            "origem": "Movimentação",
            "status": "PARADO",
            "severidade": severidade,
            "criticidade": SEVERIDADE_SCORE[severidade] + min(dias, 20),
            "acao": ACAO_PADRAO["equipamento_parado"],
            "contexto": {"dias_parado": dias, "controle": p.get("Controle")},
        })

    for row in (movimentacao.get("anomalias") or {}).get("travadas") or []:
        itens.append({
            "tipo": "leitura_travada",
            "titulo": "Leitura travada detectada",
            "descricao": f"{row.get('Equipamento') or '-'} · valor repetido {row.get('Valor repetido')}",
            "equipamento": row.get("Equipamento") or "-",
            "setor": row.get("Setor") or "-",
            "origem": "Leituras",
            "status": "TRAVADA",
            "severidade": "alto",
            "criticidade": 76,
            "acao": ACAO_PADRAO["leitura_travada"],
            "contexto": row,
        })

    for row in (movimentacao.get("anomalias") or {}).get("saltos") or []:
        itens.append({
            "tipo": "salto_anormal",
            "titulo": "Salto anormal de leitura",
            "descricao": f"{row.get('Equipamento') or '-'} · salto {row.get('Salto')}",
            "equipamento": row.get("Equipamento") or "-",
            "setor": row.get("Setor") or "-",
            "origem": "Leituras",
            "status": "SALTO",
            "severidade": "alto",
            "criticidade": 74,
            "acao": ACAO_PADRAO["salto_anormal"],
            "contexto": row,
        })

    for row in (movimentacao.get("anomalias") or {}).get("inconsistencias") or []:
        itens.append({
            "tipo": "inconsistencia_km_h",
            "titulo": "Inconsistência entre KM e horas",
            "descricao": f"{row.get('Equipamento') or '-'} · relação {row.get('Relação KM/H')}",
            "equipamento": row.get("Equipamento") or "-",
            "setor": row.get("Setor") or "-",
            "origem": "Leituras",
            "status": "INCONSISTÊNCIA",
            "severidade": "medio",
            "criticidade": 58,
            "acao": ACAO_PADRAO["inconsistencia_km_h"],
            "contexto": row,
        })

    itens.sort(key=lambda x: (-int(x.get("criticidade") or 0), SEVERIDADE_ORDEM.get(x.get("severidade") or "baixo", 99), x.get("setor") or "", x.get("equipamento") or ""))
    itens = itens[:limite]

    resumo = {
        "total_equipamentos": total_equipamentos,
        "total_alertas": len(itens),
        "criticos": sum(1 for i in itens if i.get("severidade") == "critico"),
        "altos": sum(1 for i in itens if i.get("severidade") == "alto"),
        "medios": sum(1 for i in itens if i.get("severidade") == "medio"),
        "baixo": sum(1 for i in itens if i.get("severidade") == "baixo"),
        "setor_mais_exposto": _top_setor(itens),
        "equipamentos_parados": sum(1 for i in itens if i.get("tipo") == "equipamento_parado"),
    }

    por_categoria = defaultdict(int)
    por_setor = defaultdict(lambda: {"Total": 0, "Críticos": 0, "Altos": 0, "Médios": 0})
    acoes = Counter()
    for item in itens:
        por_categoria[_categoria(item.get("tipo") or "")] += 1
        setor = item.get("setor") or "-"
        por_setor[setor]["Total"] += 1
        if item.get("severidade") == "critico":
            por_setor[setor]["Críticos"] += 1
        elif item.get("severidade") == "alto":
            por_setor[setor]["Altos"] += 1
        elif item.get("severidade") == "medio":
            por_setor[setor]["Médios"] += 1
        acoes[item.get("acao") or "-"] += 1

    setores = [{"Setor": s, **dados} for s, dados in por_setor.items()]
    setores.sort(key=lambda x: (-x["Críticos"], -x["Altos"], -x["Total"], x["Setor"]))

    recomendacoes = [
        {"Ação recomendada": acao, "Ocorrências": qtd}
        for acao, qtd in acoes.most_common(5)
    ]

    return {
        "resumo": resumo,
        "itens": itens,
        "categorias": [{"Categoria": k, "Alertas": v} for k, v in sorted(por_categoria.items(), key=lambda kv: (-kv[1], kv[0]))],
        "setores": setores,
        "recomendacoes": recomendacoes,
        "movimentacao": movimentacao,
    }
