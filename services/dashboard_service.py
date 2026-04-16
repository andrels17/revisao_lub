from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any

import streamlit as st

from database.connection import get_conn, release_conn
from services import configuracoes_service, equipamentos_service, lubrificacoes_service, revisoes_service

STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
TTL_ALERTAS = 120  # segundos


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _listar_colunas(cur, tabela: str) -> set[str]:
    cur.execute(
        """
        select column_name
          from information_schema.columns
         where table_schema = 'public'
           and table_name = %s
        """,
        (tabela,),
    )
    return {str(r[0]) for r in cur.fetchall()}


def _nome_coluna(colunas: set[str], *candidatos: str) -> str | None:
    for nome in candidatos:
        if nome in colunas:
            return nome
    return None


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


def _medida_principal(equipamento: dict[str, Any], row: dict[str, Any]) -> tuple[str, float]:
    tipo = str(equipamento.get("tipo_controle") or "km").lower()
    if tipo == "horas":
        return "Horas", _safe_float(row.get("horas_valor"))
    return "KM", _safe_float(row.get("km_valor"))


def _delta_principal(equipamento: dict[str, Any], atual: dict[str, Any], anterior: dict[str, Any] | None) -> tuple[str, float]:
    label, valor_atual = _medida_principal(equipamento, atual)
    _, valor_anterior = _medida_principal(equipamento, anterior or {})
    return label, max(0.0, valor_atual - valor_anterior)


@st.cache_data(ttl=90, show_spinner=False)
def carregar_movimentacao(janela_dias: int = 30) -> dict[str, Any]:
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return {
            "kpis": {
                "equipamentos_com_leitura": 0,
                "equipamentos_sem_leitura": 0,
                "equipamentos_parados": 0,
                "leituras_na_janela": 0,
            },
            "ranking_rodados": [],
            "alertas_parados": [],
            "anomalias": {"travadas": [], "saltos": [], "inconsistencias": []},
        }

    eq_map = {str(e["id"]): e for e in equipamentos}
    ids = list(eq_map)
    threshold_parado = int(configuracoes_service.get_dias_sem_leitura())
    conn = get_conn()
    try:
        cur = conn.cursor()
        colunas = _listar_colunas(cur, "leituras")
        if not colunas:
            return {
                "kpis": {
                    "equipamentos_com_leitura": 0,
                    "equipamentos_sem_leitura": len(equipamentos),
                    "equipamentos_parados": len(equipamentos),
                    "leituras_na_janela": 0,
                },
                "ranking_rodados": [],
                "alertas_parados": [],
                "anomalias": {"travadas": [], "saltos": [], "inconsistencias": []},
            }

        eq_col = _nome_coluna(colunas, "equipamento_id")
        data_col = _nome_coluna(colunas, "data_leitura", "data", "data_registro", "created_at")
        km_col = _nome_coluna(colunas, "km_valor", "km", "valor_km", "odometro", "quilometragem")
        horas_col = _nome_coluna(colunas, "horas_valor", "horas", "valor_horas", "valor_hora", "horimetro")
        tipo_col = _nome_coluna(colunas, "tipo_leitura", "tipo")
        if not eq_col or not data_col:
            return {
                "kpis": {
                    "equipamentos_com_leitura": 0,
                    "equipamentos_sem_leitura": len(equipamentos),
                    "equipamentos_parados": len(equipamentos),
                    "leituras_na_janela": 0,
                },
                "ranking_rodados": [],
                "alertas_parados": [],
                "anomalias": {"travadas": [], "saltos": [], "inconsistencias": []},
            }

        km_sql = f"coalesce(l.{km_col}, 0) as km_valor" if km_col else "0 as km_valor"
        horas_sql = f"coalesce(l.{horas_col}, 0) as horas_valor" if horas_col else "0 as horas_valor"
        tipo_sql = f"coalesce(l.{tipo_col}::text, '') as tipo_leitura" if tipo_col else "'' as tipo_leitura"

        cur.execute(
            f"""
            select
                l.{eq_col}::text as equipamento_id,
                l.{data_col} as data_leitura,
                {tipo_sql},
                {km_sql},
                {horas_sql}
            from public.leituras l
            where l.{eq_col} is not null
            order by l.{eq_col}, l.{data_col} desc nulls last
            """
        )
        rows = cur.fetchall()
    finally:
        release_conn(conn)

    historico: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for equipamento_id, data_leitura, tipo_leitura, km_valor, horas_valor in rows:
        if str(equipamento_id) not in eq_map:
            continue
        historico[str(equipamento_id)].append({
            "data_leitura": data_leitura,
            "tipo_leitura": tipo_leitura,
            "km_valor": _safe_float(km_valor),
            "horas_valor": _safe_float(horas_valor),
        })

    ranking_rodados: list[dict[str, Any]] = []
    alertas_parados: list[dict[str, Any]] = []
    travadas: list[dict[str, Any]] = []
    saltos: list[dict[str, Any]] = []
    inconsistencias: list[dict[str, Any]] = []
    leituras_na_janela = 0
    equipamentos_com_leitura = 0

    for eq_id, equipamento in eq_map.items():
        hist = historico.get(eq_id, [])
        if hist:
            equipamentos_com_leitura += 1
            ult = hist[0]
            dias_sem = 0
            try:
                dias_sem = max((__import__('datetime').datetime.now() - ult["data_leitura"]).days, 0) if ult.get("data_leitura") else 999
            except Exception:
                dias_sem = 999

            for row in hist:
                try:
                    if row.get("data_leitura") and (__import__('datetime').datetime.now() - row["data_leitura"]).days <= janela_dias:
                        leituras_na_janela += 1
                except Exception:
                    continue

            label, delta = _delta_principal(equipamento, hist[0], hist[1] if len(hist) > 1 else None)
            ranking_rodados.append({
                "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                "Código": equipamento.get("codigo") or "-",
                "Setor": equipamento.get("setor_nome") or "-",
                "Controle": label,
                "Movimento recente": round(delta, 1),
                "Leitura atual": round(_medida_principal(equipamento, hist[0])[1], 1),
                "Última leitura": hist[0].get("data_leitura"),
            })

            if dias_sem >= threshold_parado:
                alertas_parados.append({
                    "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                    "Código": equipamento.get("codigo") or "-",
                    "Setor": equipamento.get("setor_nome") or "-",
                    "Dias parado": int(dias_sem),
                    "Última leitura": ult.get("data_leitura"),
                    "Controle": equipamento.get("tipo_controle") or "km",
                })

            if len(hist) >= 2:
                atual = hist[0]
                anterior = hist[1]
                label2, delta_principal = _delta_principal(equipamento, atual, anterior)
                if delta_principal == 0:
                    travadas.append({
                        "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                        "Setor": equipamento.get("setor_nome") or "-",
                        "Controle": label2,
                        "Valor repetido": round(_medida_principal(equipamento, atual)[1], 1),
                        "Última leitura": atual.get("data_leitura"),
                    })

                deltas_principais = []
                for idx in range(len(hist) - 1):
                    _, d = _delta_principal(equipamento, hist[idx], hist[idx + 1])
                    if d > 0:
                        deltas_principais.append(d)
                base = median(deltas_principais[:6]) if deltas_principais else 0.0
                limite_salto = max(1000.0 if label2 == "KM" else 24.0, base * 5)
                if delta_principal > 0 and delta_principal >= limite_salto:
                    saltos.append({
                        "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                        "Setor": equipamento.get("setor_nome") or "-",
                        "Controle": label2,
                        "Salto": round(delta_principal, 1),
                        "Limite de atenção": round(limite_salto, 1),
                        "Última leitura": atual.get("data_leitura"),
                    })

                km_delta = max(0.0, _safe_float(atual.get("km_valor")) - _safe_float(anterior.get("km_valor")))
                horas_delta = max(0.0, _safe_float(atual.get("horas_valor")) - _safe_float(anterior.get("horas_valor")))
                ratio = (km_delta / horas_delta) if horas_delta > 0 else None
                if (km_delta > 0 and horas_delta == 0) or (horas_delta > 0 and km_delta == 0) or (ratio is not None and (ratio < 0.5 or ratio > 120)):
                    inconsistencias.append({
                        "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                        "Setor": equipamento.get("setor_nome") or "-",
                        "Δ KM": round(km_delta, 1),
                        "Δ Horas": round(horas_delta, 1),
                        "Relação KM/H": round(ratio, 1) if ratio is not None else "—",
                        "Última leitura": atual.get("data_leitura"),
                    })
        else:
            ranking_rodados.append({
                "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                "Código": equipamento.get("codigo") or "-",
                "Setor": equipamento.get("setor_nome") or "-",
                "Controle": "Horas" if str(equipamento.get("tipo_controle") or "km").lower() == "horas" else "KM",
                "Movimento recente": 0.0,
                "Leitura atual": 0.0,
                "Última leitura": None,
            })
            alertas_parados.append({
                "Equipamento": f"{equipamento.get('codigo') or '-'} — {equipamento.get('nome') or '-'}",
                "Código": equipamento.get("codigo") or "-",
                "Setor": equipamento.get("setor_nome") or "-",
                "Dias parado": 999,
                "Última leitura": None,
                "Controle": equipamento.get("tipo_controle") or "km",
            })

    ranking_rodados.sort(key=lambda x: (-_safe_float(x.get("Movimento recente")), x.get("Equipamento") or ""))
    alertas_parados.sort(key=lambda x: (-int(x.get("Dias parado") or 0), x.get("Equipamento") or ""))
    travadas.sort(key=lambda x: (x.get("Setor") or "", x.get("Equipamento") or ""))
    saltos.sort(key=lambda x: (-_safe_float(x.get("Salto")), x.get("Equipamento") or ""))
    inconsistencias.sort(key=lambda x: (x.get("Setor") or "", x.get("Equipamento") or ""))

    return {
        "kpis": {
            "equipamentos_com_leitura": equipamentos_com_leitura,
            "equipamentos_sem_leitura": len(equipamentos) - equipamentos_com_leitura,
            "equipamentos_parados": len(alertas_parados),
            "leituras_na_janela": leituras_na_janela,
            "janela_dias": janela_dias,
            "threshold_parado": threshold_parado,
        },
        "ranking_rodados": ranking_rodados[:10],
        "alertas_parados": alertas_parados[:10],
        "anomalias": {
            "travadas": travadas[:10],
            "saltos": saltos[:10],
            "inconsistencias": inconsistencias[:10],
        },
    }
