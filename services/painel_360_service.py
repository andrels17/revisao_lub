from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from services import alertas_service, execucoes_service, leituras_service, lubrificacoes_service


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _tipo_medicao(item: dict) -> str:
    tipo = (item.get("tipo_controle") or "").lower()
    if tipo == "horas":
        return "horas"
    return "km"


def montar_timeline_equipamento(equipamento_id, limite=50):
    eventos = []

    for leitura in leituras_service.listar_por_equipamento(equipamento_id, limite=limite):
        eventos.append({
            "data": leitura.get("data_leitura"),
            "tipo": "Leitura",
            "titulo": f"Leitura {leitura.get('tipo_leitura', '-')}",
            "detalhe": (
                f"KM { _to_float(leitura.get('km_valor')):.0f} · "
                f"Horas { _to_float(leitura.get('horas_valor')):.0f}"
            ),
            "responsavel": leitura.get("responsavel") or "-",
            "observacoes": leitura.get("observacoes") or "",
            "origem": "leituras",
        })

    for revisao in execucoes_service.listar_revisoes_por_equipamento(equipamento_id, limite=limite):
        eventos.append({
            "data": revisao.get("data"),
            "tipo": "Revisão",
            "titulo": revisao.get("etapa_referencia") or "Execução de revisão",
            "detalhe": revisao.get("resultado") or "Revisão registrada",
            "responsavel": revisao.get("responsavel") or "-",
            "observacoes": revisao.get("observacoes") or "",
            "origem": "execucoes_manutencao",
        })

    for lub in lubrificacoes_service.listar_por_equipamento(equipamento_id)[:limite]:
        eventos.append({
            "data": lub.get("data"),
            "tipo": "Lubrificação",
            "titulo": lub.get("item") or "Execução de lubrificação",
            "detalhe": (
                f"Produto {lub.get('produto') or '-'} · "
                f"KM { _to_float(lub.get('km')):.0f} · Horas { _to_float(lub.get('horas')):.0f}"
            ),
            "responsavel": lub.get("responsavel") or "-",
            "observacoes": lub.get("observacoes") or "",
            "origem": "execucoes_lubrificacao",
        })

    historico_alertas = alertas_service.listar_historico_por_equipamento(equipamento_id, limite=limite)
    for alerta in historico_alertas:
        eventos.append({
            "data": alerta.get("enviado_em"),
            "tipo": "Alerta",
            "titulo": f"Alerta {alerta.get('tipo')}",
            "detalhe": f"Perfil {alerta.get('perfil')}",
            "responsavel": alerta.get("responsavel") or "-",
            "observacoes": alerta.get("mensagem") or "",
            "origem": "alertas_enviados",
        })

    def _sort_key(item):
        data = item.get("data")
        if isinstance(data, datetime):
            return data
        return datetime.min

    eventos.sort(key=_sort_key, reverse=True)
    return eventos[:limite]


def serie_evolucao_semanal(equipamento: dict, leituras: list[dict], limite=8):
    eventos = []
    for leitura in leituras:
        data = leitura.get("data_leitura")
        if not data:
            continue
        eventos.append({
            "data": data,
            "km": _to_float(leitura.get("km_valor")),
            "horas": _to_float(leitura.get("horas_valor")),
            "tipo": leitura.get("tipo_leitura") or "-",
        })

    eventos.sort(key=lambda x: x["data"])
    if not eventos:
        eventos = [{"data": None, "km": _to_float(equipamento.get("km_atual")), "horas": _to_float(equipamento.get("horas_atual")), "tipo": "atual"}]

    return eventos[-limite:]


def resumir_pendencias(revisoes: list[dict], lubrificacoes: list[dict]) -> list[dict]:
    linhas = []
    for item in revisoes:
        if item.get("status") in {"VENCIDO", "PROXIMO"}:
            linhas.append({
                "origem": "Revisão",
                "item": item.get("etapa"),
                "controle": _tipo_medicao(item),
                "status": item.get("status"),
                "referencia": _to_float(item.get("proximo_vencimento") or item.get("vencimento") or 0),
                "atual": _to_float(item.get("atual")),
                "falta": _to_float(item.get("diferenca")),
            })
    for item in lubrificacoes:
        if item.get("status") in {"VENCIDO", "PROXIMO"}:
            linhas.append({
                "origem": "Lubrificação",
                "item": item.get("item"),
                "controle": _tipo_medicao(item),
                "status": item.get("status"),
                "referencia": _to_float(item.get("vencimento") or 0),
                "atual": _to_float(item.get("atual")),
                "falta": _to_float(item.get("diferenca")),
            })
    ordem = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
    linhas.sort(key=lambda x: (ordem.get(x["status"], 99), x["falta"], x["origem"], str(x["item"])))
    return linhas


def gerar_insights(equipamento: dict, revisoes: list[dict], lubrificacoes: list[dict], leituras: list[dict], vinculos: list[dict]) -> list[str]:
    insights = []
    pendencias = resumir_pendencias(revisoes, lubrificacoes)
    vencidos = [p for p in pendencias if p["status"] == "VENCIDO"]
    proximos = [p for p in pendencias if p["status"] == "PROXIMO"]

    if vencidos:
        insights.append(f"Há {len(vencidos)} pendência(s) vencida(s) exigindo ação imediata.")
    elif proximos:
        insights.append(f"Há {len(proximos)} item(ns) próximo(s) do vencimento; vale programar a execução.")
    else:
        insights.append("Nenhuma pendência crítica encontrada no momento.")

    if not vinculos:
        insights.append("Equipamento sem responsável operacional vinculado; isso enfraquece o fluxo de cobrança.")

    if not equipamento.get("template_revisao_id"):
        insights.append("Equipamento sem template de revisão vinculado.")
    if not equipamento.get("template_lubrificacao_id"):
        insights.append("Equipamento sem template de lubrificação vinculado.")

    if leituras:
        ultima = leituras[0]
        insights.append(
            f"Última leitura registrada em {ultima.get('data_leitura')} com KM {_to_float(ultima.get('km_valor')):.0f} e horas {_to_float(ultima.get('horas_valor')):.0f}."
        )
    else:
        insights.append("Nenhuma leitura recente encontrada para este equipamento.")

    return insights[:5]
