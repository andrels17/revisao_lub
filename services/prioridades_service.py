from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

import streamlit as st

from database.connection import get_conn, release_conn
from services import configuracoes_service, equipamentos_service, lubrificacoes_service, revisoes_service

TTL_PRIORIDADES = 90
STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "SEM_LEITURA": 2, "PARADO": 3, "EM DIA": 4, "REALIZADO": 5}


def _to_float(valor: Any) -> float:
    try:
        return float(valor or 0)
    except Exception:
        return 0.0


def _unidade(tipo_controle: str | None) -> str:
    return "h" if (tipo_controle or "").lower() == "horas" else "km"


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(valor: Any) -> datetime | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day, tzinfo=timezone.utc)
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("Z", "+00:00")
    for parser in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%d/%m/%Y %H:%M"),
        lambda t: datetime.strptime(t, "%d/%m/%Y"),
        lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"),
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
    ):
        try:
            dt = parser(texto)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _nome_coluna_disponivel(colunas: set[str], candidatos: list[str]) -> str | None:
    for nome in candidatos:
        if nome in colunas:
            return nome
    return None


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


@st.cache_data(ttl=TTL_PRIORIDADES, show_spinner=False)
def _carregar_ultimas_leituras() -> dict[str, dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        colunas = _listar_colunas(cur, "leituras")
        if not colunas:
            return {}

        eq_col = _nome_coluna_disponivel(colunas, ["equipamento_id"])
        data_col = _nome_coluna_disponivel(colunas, ["data_leitura", "data", "data_registro", "created_at"])
        km_col = _nome_coluna_disponivel(colunas, ["km_valor", "km", "valor_km", "odometro", "quilometragem"])
        horas_col = _nome_coluna_disponivel(colunas, ["horas_valor", "horas", "valor_horas", "valor_hora", "horimetro"])
        tipo_col = _nome_coluna_disponivel(colunas, ["tipo_leitura", "tipo"])

        if not eq_col or not data_col:
            return {}

        tipo_sql = f"coalesce(l.{tipo_col}::text, '') as tipo_leitura" if tipo_col else "'' as tipo_leitura"
        km_sql = f"coalesce(l.{km_col}, 0) as km_valor" if km_col else "0 as km_valor"
        horas_sql = f"coalesce(l.{horas_col}, 0) as horas_valor" if horas_col else "0 as horas_valor"

        cur.execute(
            f"""
            with ranked as (
                select
                    l.{eq_col}::text as equipamento_id,
                    l.{data_col} as data_leitura,
                    {tipo_sql},
                    {km_sql},
                    {horas_sql},
                    row_number() over (
                        partition by l.{eq_col}
                        order by l.{data_col} desc nulls last
                    ) as rn
                from public.leituras l
                where l.{eq_col} is not null
            )
            select equipamento_id, data_leitura, tipo_leitura, km_valor, horas_valor
              from ranked
             where rn = 1
            """
        )
        rows = cur.fetchall()
        dados: dict[str, dict[str, Any]] = {}
        for equipamento_id, data_leitura, tipo_leitura, km_valor, horas_valor in rows:
            dados[str(equipamento_id)] = {
                "data_leitura": _normalize_dt(data_leitura),
                "tipo_leitura": (tipo_leitura or "").strip().lower(),
                "km_valor": _to_float(km_valor),
                "horas_valor": _to_float(horas_valor),
            }
        return dados
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return {}
    finally:
        release_conn(conn)


def _item_base(eqp: dict[str, Any], origem: str, subtipo: str, status: str) -> dict[str, Any]:
    return {
        "equipamento_id": eqp.get("id"),
        "codigo": eqp.get("codigo") or "-",
        "equipamento_nome": eqp.get("nome") or "-",
        "equipamento_label": f"{eqp.get('codigo') or '-'} — {eqp.get('nome') or '-'}",
        "setor_nome": eqp.get("setor_nome") or "-",
        "origem": origem,
        "subtipo": subtipo,
        "status": status,
    }


def _criar_item_prioridade_revisao(eqp: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    unidade = _unidade(item.get("tipo_controle"))
    falta = _to_float(item.get("diferenca", item.get("falta", 0)))
    atraso = abs(falta) if falta < 0 else 0.0
    base = _item_base(eqp, "Revisão", str(item.get("etapa") or "Etapa"), item.get("status") or "EM DIA")
    prioridade = 1000 + atraso if base["status"] == "VENCIDO" else 500 + max(0.0, (500 if unidade == "km" else 50) - falta)
    return {
        **base,
        "tipo_controle": item.get("tipo_controle") or "km",
        "unidade": unidade,
        "falta": falta,
        "atraso": atraso,
        "vencimento": _to_float(item.get("vencimento", 0)),
        "atual": _to_float(item.get("atual", item.get("leitura_atual", 0))),
        "titulo": f"{eqp.get('codigo')} — {item.get('etapa')}",
        "descricao": (
            f"{eqp.get('nome')} · revisão {item.get('etapa')} atrasada em {atraso:.0f} {unidade}"
            if base["status"] == "VENCIDO"
            else f"{eqp.get('nome')} · revisão {item.get('etapa')} vence em {max(falta, 0):.0f} {unidade}"
        ),
        "prioridade_score": prioridade,
        "destino": "revisoes",
    }


def _criar_item_prioridade_lubrificacao(eqp: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    unidade = _unidade(item.get("tipo_controle"))
    falta = _to_float(item.get("diferenca", item.get("falta", 0)))
    atraso = abs(falta) if falta < 0 else 0.0
    nome_item = str(item.get("item") or item.get("nome") or "Item")
    base = _item_base(eqp, "Lubrificação", nome_item, item.get("status") or "EM DIA")
    prioridade = 950 + atraso if base["status"] == "VENCIDO" else 450 + max(0.0, (500 if unidade == "km" else 50) - falta)
    return {
        **base,
        "tipo_controle": item.get("tipo_controle") or "km",
        "unidade": unidade,
        "falta": falta,
        "atraso": atraso,
        "vencimento": _to_float(item.get("vencimento", 0)),
        "atual": _to_float(item.get("atual", item.get("leitura_atual", 0))),
        "titulo": f"{eqp.get('codigo')} — {nome_item}",
        "descricao": (
            f"{eqp.get('nome')} · {nome_item} atrasada em {atraso:.0f} {unidade}"
            if base["status"] == "VENCIDO"
            else f"{eqp.get('nome')} · {nome_item} vence em {max(falta, 0):.0f} {unidade}"
        ),
        "prioridade_score": prioridade,
        "destino": "lubrificacoes",
    }


def _criar_item_sem_leitura(eqp: dict[str, Any], ultima: dict[str, Any] | None) -> dict[str, Any]:
    data_leitura = _normalize_dt((ultima or {}).get("data_leitura"))
    if data_leitura is None:
        dias = 999
        descricao = f"{eqp.get('nome')} · sem leitura registrada"
    else:
        dias = max((_agora_utc() - data_leitura).days, 0)
        descricao = f"{eqp.get('nome')} · sem leitura há {dias} dia(s)"
    return {
        **_item_base(eqp, "Leitura", "Sem leitura recente", "SEM_LEITURA"),
        "tipo_controle": "ambos",
        "unidade": "dias",
        "falta": float(dias),
        "atraso": float(dias),
        "vencimento": 0.0,
        "atual": 0.0,
        "titulo": f"{eqp.get('codigo')} — leitura",
        "descricao": descricao,
        "prioridade_score": 300 + dias,
        "dias_sem_leitura": dias,
        "destino": "leituras",
        "data_leitura": data_leitura,
    }


@st.cache_data(ttl=TTL_PRIORIDADES, show_spinner="Carregando prioridades…")
def carregar_prioridades() -> dict[str, Any]:
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return {
            "itens": [],
            "resumo": {},
            "ranking_setores": [],
            "ranking_equipamentos": [],
            "sem_leitura": [],
            "equipamentos_map": {},
        }

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    revisoes_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    ultimas_leituras = _carregar_ultimas_leituras()

    itens: list[dict[str, Any]] = []
    sem_leitura: list[dict[str, Any]] = []
    agora = _agora_utc()

    for eq_id in ids:
        eqp = eqp_map[eq_id]
        for item in revisoes_idx.get(eq_id, []):
            status = item.get("status")
            if status in {"VENCIDO", "PROXIMO"}:
                itens.append(_criar_item_prioridade_revisao(eqp, item))
        for item in lub_idx.get(eq_id, []):
            status = item.get("status")
            if status in {"VENCIDO", "PROXIMO"}:
                itens.append(_criar_item_prioridade_lubrificacao(eqp, item))

        ultima = ultimas_leituras.get(str(eq_id))
        dt_ultima = _normalize_dt((ultima or {}).get("data_leitura"))
        dias = 999 if dt_ultima is None else max((agora - dt_ultima).days, 0)
        if dt_ultima is None or dias >= int(configuracoes_service.get_dias_sem_leitura()):
            item_leitura = _criar_item_sem_leitura(eqp, ultima)
            sem_leitura.append(item_leitura)
            itens.append(item_leitura)

    itens.sort(key=lambda x: (STATUS_ORDEM.get(x.get("status"), 99), -_to_float(x.get("prioridade_score")), x.get("equipamento_label", ""), x.get("origem", "")))

    contagem_status = Counter(item.get("status") for item in itens)
    contagem_origem = Counter(item.get("origem") for item in itens)
    equipamentos_criticos = {item["equipamento_id"] for item in itens if item.get("status") in {"VENCIDO", "SEM_LEITURA"}}

    ranking_setores_map = defaultdict(lambda: {"itens": 0, "vencidos": 0, "proximos": 0, "sem_leitura": 0})
    ranking_eq_map = defaultdict(lambda: {"setor": "-", "itens": 0, "vencidos": 0, "proximos": 0, "sem_leitura": 0, "crit_score": 0.0})
    for item in itens:
        setor = item.get("setor_nome") or "-"
        rset = ranking_setores_map[setor]
        rset["itens"] += 1
        status = item.get("status")
        if status == "VENCIDO":
            rset["vencidos"] += 1
        elif status == "PROXIMO":
            rset["proximos"] += 1
        elif status == "SEM_LEITURA":
            rset["sem_leitura"] += 1

        req = ranking_eq_map[item["equipamento_label"]]
        req["setor"] = setor
        req["itens"] += 1
        req["crit_score"] += _to_float(item.get("prioridade_score"))
        if status == "VENCIDO":
            req["vencidos"] += 1
        elif status == "PROXIMO":
            req["proximos"] += 1
        elif status == "SEM_LEITURA":
            req["sem_leitura"] += 1

    ranking_setores = [
        {
            "Setor": setor,
            "Pendências": dados["itens"],
            "Vencidos": dados["vencidos"],
            "Próximos": dados["proximos"],
            "Sem leitura": dados["sem_leitura"],
            "Criticidade": dados["vencidos"] * 3 + dados["proximos"] + dados["sem_leitura"] * 2,
        }
        for setor, dados in ranking_setores_map.items()
    ]
    ranking_setores.sort(key=lambda x: (-x["Criticidade"], -x["Pendências"], x["Setor"]))

    ranking_equipamentos = [
        {
            "Equipamento": label,
            "Setor": dados["setor"],
            "Pendências": dados["itens"],
            "Vencidos": dados["vencidos"],
            "Próximos": dados["proximos"],
            "Sem leitura": dados["sem_leitura"],
            "Criticidade": round(dados["crit_score"], 1),
        }
        for label, dados in ranking_eq_map.items()
    ]
    ranking_equipamentos.sort(key=lambda x: (-x["Criticidade"], -x["Vencidos"], -x["Sem leitura"], x["Equipamento"]))

    return {
        "itens": itens,
        "resumo": {
            "total_pendencias": len(itens),
            "equipamentos_criticos": len(equipamentos_criticos),
            "vencidos": contagem_status.get("VENCIDO", 0),
            "proximos": contagem_status.get("PROXIMO", 0),
            "sem_leitura": contagem_status.get("SEM_LEITURA", 0),
            "rev": contagem_origem.get("Revisão", 0),
            "lub": contagem_origem.get("Lubrificação", 0),
            "leitura": contagem_origem.get("Leitura", 0),
            "total_equipamentos": len(equipamentos),
        },
        "ranking_setores": ranking_setores,
        "ranking_equipamentos": ranking_equipamentos[:10],
        "sem_leitura": sem_leitura[:10],
        "equipamentos_map": eqp_map,
    }


@st.cache_data(ttl=TTL_PRIORIDADES, show_spinner=False)
def listar_opcoes_filtro() -> dict[str, list[str]]:
    dados = carregar_prioridades()
    itens = dados.get("itens") or []
    return {
        "setores": sorted({str(item.get("setor_nome") or "-") for item in itens}),
        "equipamentos": sorted({str(item.get("equipamento_label") or "-") for item in itens}),
        "origens": ["Todos", "Revisão", "Lubrificação", "Leitura"],
        "status": ["Todos", "VENCIDO", "PROXIMO", "SEM_LEITURA"],
    }


def limpar_cache() -> None:
    for fn in (carregar_prioridades, listar_opcoes_filtro, _carregar_ultimas_leituras):
        try:
            fn.clear()
        except Exception:
            pass


def resumo_sem_movimentacao(setor_id: str | None = None, equipamento_id: str | None = None, limite: int = 10) -> dict[str, Any]:
    equipamentos = equipamentos_service.listar()
    if setor_id:
        equipamentos = [e for e in equipamentos if str(e.get("setor_id") or "") == str(setor_id)]
    if equipamento_id:
        equipamentos = [e for e in equipamentos if str(e.get("id") or "") == str(equipamento_id)]

    threshold = int(configuracoes_service.get_dias_sem_leitura())
    if not equipamentos:
        return {"quantidade": 0, "threshold": threshold, "top10": []}

    leituras = _carregar_ultimas_leituras()
    agora = _agora_utc()
    ranking: list[dict[str, Any]] = []
    for eq in equipamentos:
        ultima = leituras.get(str(eq.get("id")))
        data_leitura = _normalize_dt((ultima or {}).get("data_leitura"))
        dias = 999 if data_leitura is None else max((agora - data_leitura).days, 0)
        if data_leitura is None or dias >= threshold:
            ranking.append({
                "Equipamento": f"{eq.get('codigo') or '-'} — {eq.get('nome') or '-'}",
                "Código": eq.get("codigo") or "-",
                "Nome": eq.get("nome") or "-",
                "Setor": eq.get("setor_nome") or "-",
                "Dias sem leitura": int(dias),
                "Última leitura": data_leitura.strftime("%d/%m/%Y") if data_leitura else "Sem registro",
            })

    ranking.sort(key=lambda x: (-int(x["Dias sem leitura"]), str(x["Equipamento"])))
    return {"quantidade": len(ranking), "threshold": threshold, "top10": ranking[:limite]}
