from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date
from typing import Any

from services import alertas_service, comentarios_service, execucoes_service, leituras_service, lubrificacoes_service


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


def _normalize_dt(value: Any) -> datetime:
    if value is None:
        return datetime.min
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return datetime.min
        candidatos = [raw]
        if raw.endswith("Z"):
            candidatos.append(raw[:-1] + "+00:00")
        if " " in raw and "T" not in raw:
            candidatos.append(raw.replace(" ", "T", 1))
        for candidato in candidatos:
            try:
                dt = datetime.fromisoformat(candidato)
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except Exception:
                pass
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                pass
    return datetime.min


def montar_timeline_equipamento(equipamento_id, limite=50):
    eventos = []

    for leitura in leituras_service.listar_por_equipamento(equipamento_id, limite=limite):
        eventos.append({
            "data": leitura.get("data_leitura"),
            "tipo": "Leitura",
            "titulo": f"Leitura {leitura.get('tipo_leitura', '-')}",
            "detalhe": (
                f"KM {format_int_br(_to_float(leitura.get('km_valor')))} · "
                f"Horas {format_int_br(_to_float(leitura.get('horas_valor')))}"
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
                f"KM {format_int_br(_to_float(lub.get('km')))} · Horas {format_int_br(_to_float(lub.get('horas')))}"
            ),
            "responsavel": lub.get("responsavel") or "-",
            "observacoes": lub.get("observacoes") or "",
            "origem": "execucoes_lubrificacao",
        })

    comentarios = comentarios_service.listar_por_equipamento(equipamento_id, limite=limite)
    for comentario in comentarios:
        eventos.append({
            "data": comentario.get("created_at"),
            "tipo": "Comentário",
            "titulo": f"Comentário de {comentario.get('autor_nome') or 'Usuário'}",
            "detalhe": (comentario.get("comentario") or "")[:180],
            "responsavel": comentario.get("autor_nome") or "-",
            "observacoes": comentario.get("comentario") or "",
            "origem": "comentarios_equipamento",
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
        return _normalize_dt(item.get("data"))

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

    eventos.sort(key=lambda x: _normalize_dt(x.get("data")))
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
            f"Última leitura registrada em {ultima.get('data_leitura')} com KM {format_int_br(_to_float(ultima.get('km_valor')))} e horas {format_int_br(_to_float(ultima.get('horas_valor')))}."
        )
    else:
        insights.append("Nenhuma leitura recente encontrada para este equipamento.")

    return insights[:5]


def agrupar_prioridades_por_setor(alertas: list[dict], limite: int = 5) -> list[dict]:
    acumulado = defaultdict(lambda: {"vencidos": 0, "proximos": 0, "equipamentos": set(), "revisoes": 0, "lubrificacoes": 0})
    for alerta in alertas:
        if alerta.get("status") not in {"VENCIDO", "PROXIMO"}:
            continue
        setor = alerta.get("setor") or "-"
        item = acumulado[setor]
        item["vencidos"] += 1 if alerta.get("status") == "VENCIDO" else 0
        item["proximos"] += 1 if alerta.get("status") == "PROXIMO" else 0
        item["revisoes"] += 1 if alerta.get("origem") == "Revisão" else 0
        item["lubrificacoes"] += 1 if alerta.get("origem") == "Lubrificação" else 0
        item["equipamentos"].add(alerta.get("equipamento_id"))

    ranking = []
    for setor, dados in acumulado.items():
        criticidade = dados["vencidos"] * 3 + dados["proximos"]
        ranking.append({
            "Setor": setor,
            "Vencidos": dados["vencidos"],
            "Próximos": dados["proximos"],
            "Equipamentos impactados": len(dados["equipamentos"]),
            "Revisões": dados["revisoes"],
            "Lubrificações": dados["lubrificacoes"],
            "Criticidade": criticidade,
            "Leitura gerencial": (
                f"{dados['vencidos']} vencido(s), {dados['proximos']} próximo(s) e "
                f"{len(dados['equipamentos'])} equipamento(s) impactado(s)."
            ),
        })
    ranking.sort(key=lambda x: (-x["Criticidade"], -x["Vencidos"], -x["Próximos"], x["Setor"]))
    return ranking[:limite]
