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


def calcular_health_score(kpis_alertas: dict, mov: dict) -> dict:
    """
    Calcula o índice de saúde da frota (0–100%).
    
    Componentes:
    - 50 pts: % de equipamentos sem alerta
    - 25 pts: penalidade por vencidos (cada vencido = -5 pts, mín 0)
    - 15 pts: penalidade por parados
    - 10 pts: penalidade por anomalias de leitura
    """
    total = max(1, int(kpis_alertas.get("total_equipamentos", 1)))
    com_alerta = int(kpis_alertas.get("equipamentos_com_alerta", 0))
    vencidos = int(kpis_alertas.get("vencidos", 0))
    proximos = int(kpis_alertas.get("proximos", 0))
    
    mov_kpis = mov.get("kpis", {})
    parados = int(mov_kpis.get("equipamentos_parados", 0))
    anom = mov.get("anomalias", {})
    n_anomalias = len(anom.get("travadas", [])) + len(anom.get("saltos", [])) + len(anom.get("inconsistencias", []))
    
    # Componente 1: equipamentos saudáveis (50 pontos)
    pct_saudavel = max(0.0, (total - com_alerta) / total)
    score_saude = pct_saudavel * 50
    
    # Componente 2: penalidade por vencidos (até -25 pts)
    pct_vencidos = vencidos / total
    score_vencidos = max(0.0, 25 - (pct_vencidos * 100))
    
    # Componente 3: penalidade por parados (até -15 pts)
    pct_parados = parados / total
    score_parados = max(0.0, 15 - (pct_parados * 60))
    
    # Componente 4: penalidade por anomalias (até -10 pts)
    pct_anomalias = n_anomalias / total
    score_anomalias = max(0.0, 10 - (pct_anomalias * 30))
    
    score_total = round(score_saude + score_vencidos + score_parados + score_anomalias, 1)
    score_total = max(0.0, min(100.0, score_total))
    
    if score_total >= 85:
        nivel = "Excelente"
        cor = "#22c55e"
    elif score_total >= 70:
        nivel = "Bom"
        cor = "#84cc16"
    elif score_total >= 50:
        nivel = "Regular"
        cor = "#f59e0b"
    elif score_total >= 30:
        nivel = "Crítico"
        cor = "#f97316"
    else:
        nivel = "Grave"
        cor = "#ef4444"
    
    return {
        "score": score_total,
        "nivel": nivel,
        "cor": cor,
        "componentes": {
            "saude": round(score_saude, 1),
            "vencidos": round(score_vencidos, 1),
            "parados": round(score_parados, 1),
            "anomalias": round(score_anomalias, 1),
        },
    }


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
        "health_score": calcular_health_score(kpis_alertas, mov),
    }


def limpar_cache() -> None:
    try:
        carregar_painel_executivo.clear()
    except Exception:
        pass
