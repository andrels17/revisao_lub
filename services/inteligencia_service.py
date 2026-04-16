from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

from services import dashboard_service, prioridades_service

TTL_EXEC = 90


def _criticidade(item: dict[str, Any]) -> tuple[str, int]:
    status = str(item.get("status") or "").upper()
    atraso = float(item.get("atraso", 0) or 0)
    dias = float(item.get("dias_sem_leitura", 0) or 0)
    if status == "VENCIDO":
        if atraso >= 30:
            return "Crítica", 100
        return "Alta", 85
    if status in {"SEM_LEITURA", "PARADO"}:
        if dias >= 7:
            return "Crítica", 95
        return "Alta", 80
    if status == "PROXIMO":
        return "Média", 60
    return "Baixa", 30


def _acao_sugerida(item: dict[str, Any]) -> str:
    origem = str(item.get("origem") or "")
    status = str(item.get("status") or "")
    if origem == "Revisão" and status == "VENCIDO":
        return "Programar revisão imediata"
    if origem == "Lubrificação" and status == "VENCIDO":
        return "Executar lubrificação prioritária"
    if status in {"SEM_LEITURA", "PARADO"}:
        return "Validar operação e última leitura"
    if origem == "Leitura":
        return "Conferir leitura e operador responsável"
    return "Acompanhar e reavaliar na rotina diária"


def _resumo_categorias(kpis_alertas: dict[str, Any], mov: dict[str, Any]) -> list[dict[str, Any]]:
    anom = mov.get("anomalias") or {}
    return [
        {"Categoria": "Revisões/lubrificações vencidas", "Qtd": int(kpis_alertas.get("vencidos", 0))},
        {"Categoria": "Itens próximos do vencimento", "Qtd": int(kpis_alertas.get("proximos", 0))},
        {"Categoria": "Equipamentos parados", "Qtd": int(mov.get("kpis", {}).get("equipamentos_parados", 0))},
        {"Categoria": "Leituras travadas", "Qtd": len(anom.get("travadas", []))},
        {"Categoria": "Saltos anormais", "Qtd": len(anom.get("saltos", []))},
        {"Categoria": "Inconsistências KM/H", "Qtd": len(anom.get("inconsistencias", []))},
    ]


def _exposicao_setores(ranking_setores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saida = []
    for item in ranking_setores[:8]:
        total = int(item.get("Alertas", 0) or item.get("total", 0) or 0)
        vencidos = int(item.get("Vencidos", 0) or 0)
        proximos = int(item.get("Próximos", 0) or item.get("proximos", 0) or 0)
        score = vencidos * 3 + proximos
        saida.append({
            "Setor": item.get("Setor") or item.get("setor_nome") or "-",
            "Alertas": total,
            "Vencidos": vencidos,
            "Próximos": proximos,
            "Score": score,
        })
    saida.sort(key=lambda x: (-x["Score"], -x["Alertas"], x["Setor"]))
    return saida


def _construir_top_alertas(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saida = []
    for item in itens[:10]:
        criticidade, score = _criticidade(item)
        saida.append({
            "Equipamento": item.get("equipamento_label") or item.get("titulo") or "-",
            "Setor": item.get("setor_nome") or "-",
            "Origem": item.get("origem") or "-",
            "Status": item.get("status") or "-",
            "Criticidade": criticidade,
            "Score": score,
            "Ação sugerida": _acao_sugerida(item),
            "Resumo": item.get("descricao") or "-",
        })
    saida.sort(key=lambda x: (-x["Score"], x["Equipamento"]))
    return saida


def _plano_acao(top_alertas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    acoes = []
    for item in top_alertas[:5]:
        acoes.append({
            "Frente": item["Origem"],
            "Equipamento": item["Equipamento"],
            "Criticidade": item["Criticidade"],
            "Ação": item["Ação sugerida"],
        })
    return acoes


@st.cache_data(ttl=TTL_EXEC, show_spinner=False)
def carregar_painel_executivo() -> dict[str, Any]:
    alertas, total_equipamentos = dashboard_service.carregar_alertas()
    kpis_alertas = dashboard_service.resumo_kpis(alertas, total_equipamentos)
    mov = dashboard_service.carregar_movimentacao()
    prioridades = prioridades_service.carregar_prioridades()

    itens = prioridades.get("itens") or []
    top_alertas = _construir_top_alertas(itens)
    exposicao = _exposicao_setores(dashboard_service.ranking_setores(alertas))
    categorias = _resumo_categorias(kpis_alertas, mov)

    criticos = sum(1 for item in top_alertas if item["Criticidade"] == "Crítica")
    altos = sum(1 for item in top_alertas if item["Criticidade"] == "Alta")
    cobertura = 0.0
    if total_equipamentos:
        cobertura = ((total_equipamentos - kpis_alertas.get("equipamentos_com_alerta", 0)) / total_equipamentos) * 100

    ranking_mov = pd.DataFrame(mov.get("ranking_rodados") or [])
    if not ranking_mov.empty:
        ranking_mov = ranking_mov.head(8).to_dict("records")
    else:
        ranking_mov = []

    parados = pd.DataFrame(mov.get("alertas_parados") or [])
    if not parados.empty:
        parados = parados.head(8).to_dict("records")
    else:
        parados = []

    return {
        "kpis": {
            "criticos": criticos,
            "altos": altos,
            "parados": int(mov.get("kpis", {}).get("equipamentos_parados", 0)),
            "cobertura": cobertura,
            "total_equipamentos": total_equipamentos,
            "equipamentos_com_alerta": int(kpis_alertas.get("equipamentos_com_alerta", 0)),
        },
        "top_alertas": top_alertas,
        "exposicao_setores": exposicao,
        "categorias": categorias,
        "ranking_movimentacao": ranking_mov,
        "parados": parados,
        "plano_acao": _plano_acao(top_alertas),
        "movimentacao": mov,
    }


def limpar_cache() -> None:
    try:
        carregar_painel_executivo.clear()
    except Exception:
        pass
