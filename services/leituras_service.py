from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg2 import errors
from psycopg2 import sql

from database.connection import get_conn, release_conn
from services import auditoria_service, validacoes_service


def _inferir_tipo_leitura(km_valor=None, horas_valor=None):
    tem_km = km_valor is not None and float(km_valor or 0) > 0
    tem_horas = horas_valor is not None and float(horas_valor or 0) > 0
    if tem_km and tem_horas:
        return "ambos"
    if tem_horas:
        return "horas"
    return "km"


def _safe_float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _table_columns(cur, table_name: str = "leituras") -> set[str]:
    cur.execute(
        """
        select column_name
        from information_schema.columns
        where table_schema = 'public' and table_name = %s
        """,
        (table_name,),
    )
    return {r[0] for r in cur.fetchall()}


def _pick(columns: set[str], *candidates: str) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def _schema_map(columns: set[str]) -> dict[str, str | None]:
    return {
        "id": _pick(columns, "id"),
        "equipamento_id": _pick(columns, "equipamento_id"),
        "tipo_leitura": _pick(columns, "tipo_leitura", "tipo"),
        "km": _pick(columns, "km_valor", "km", "valor_km", "odometro", "quilometragem"),
        "horas": _pick(columns, "horas_valor", "horas", "valor_horas", "valor_hora", "horimetro"),
        "data": _pick(columns, "data_leitura", "data", "data_registro", "created_at"),
        "responsavel_id": _pick(columns, "responsavel_id"),
        "observacoes": _pick(columns, "observacoes", "observacao", "obs"),
        "created_at": _pick(columns, "created_at"),
    }


def _coerce_date(value: Any):
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        text = str(value).strip()
        if not text:
            return None
        return dt.date.fromisoformat(text[:10])
    except Exception:
        return value


def _registrar_no_conn(
    conn,
    cur,
    *,
    equipamento_id,
    tipo_leitura,
    km_valor=None,
    horas_valor=None,
    data_leitura=None,
    responsavel_id=None,
    observacoes=None,
    permitir_regressao=False,
    cols: set[str] | None = None,
    schema: dict[str, str | None] | None = None,
):
    contexto = validacoes_service.validar_leitura(
        equipamento_id=equipamento_id,
        tipo_leitura=tipo_leitura,
        km_valor=km_valor,
        horas_valor=horas_valor,
        permitir_regressao=permitir_regressao,
    )

    cols = cols or _table_columns(cur)
    if not cols:
        raise RuntimeError("A tabela 'leituras' não existe no schema public.")
    m = schema or _schema_map(cols)
    if not m["equipamento_id"]:
        raise RuntimeError("A tabela 'leituras' não possui a coluna equipamento_id.")

    valor_antigo = {
        "km_atual": contexto.get("km_atual"),
        "horas_atual": contexto.get("horas_atual"),
    }

    payload = []
    if m["equipamento_id"]:
        payload.append((m["equipamento_id"], equipamento_id))
    if m["tipo_leitura"]:
        payload.append((m["tipo_leitura"], tipo_leitura))
    if m["km"] and km_valor is not None:
        payload.append((m["km"], km_valor))
    if m["horas"] and horas_valor is not None:
        payload.append((m["horas"], horas_valor))
    if m["data"] and data_leitura is not None and m["data"] != "created_at":
        payload.append((m["data"], _coerce_date(data_leitura)))
    if m["responsavel_id"] and responsavel_id:
        payload.append((m["responsavel_id"], responsavel_id))
    if m["observacoes"] and observacoes:
        payload.append((m["observacoes"], observacoes))

    if not payload:
        raise RuntimeError("Não foi possível montar o insert da tabela 'leituras'.")

    col_idents = [sql.Identifier(c) for c, _ in payload]
    values = [v for _, v in payload]
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in payload)

    query = sql.SQL("insert into public.leituras ({cols}) values ({vals})").format(
        cols=sql.SQL(", ").join(col_idents),
        vals=placeholders,
    )
    if m["id"]:
        query += sql.SQL(" returning {}").format(sql.Identifier(m["id"]))

    cur.execute(query, values)
    leitura_id = cur.fetchone()[0] if m["id"] else None

    if tipo_leitura in ("km", "ambos") and km_valor is not None:
        cur.execute(
            "update equipamentos set km_atual = greatest(coalesce(km_atual, 0), %s) where id = %s",
            (km_valor, equipamento_id),
        )
    if tipo_leitura in ("horas", "ambos") and horas_valor is not None:
        cur.execute(
            "update equipamentos set horas_atual = greatest(coalesce(horas_atual, 0), %s) where id = %s",
            (horas_valor, equipamento_id),
        )

    auditoria_service.registrar_no_conn(
        conn,
        acao="registrar_leitura",
        entidade="leituras",
        entidade_id=leitura_id,
        valor_antigo=valor_antigo,
        valor_novo={
            "equipamento_id": equipamento_id,
            "tipo_leitura": tipo_leitura,
            "km_valor": km_valor,
            "horas_valor": horas_valor,
            "data_leitura": str(data_leitura) if data_leitura else None,
            "responsavel_id": responsavel_id,
            "observacoes": observacoes,
        },
    )
    return leitura_id


def registrar(
    equipamento_id,
    tipo_leitura,
    km_valor=None,
    horas_valor=None,
    data_leitura=None,
    responsavel_id=None,
    observacoes=None,
    permitir_regressao=False,
):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cols = _table_columns(cur)
        schema = _schema_map(cols)
        leitura_id = _registrar_no_conn(
            conn,
            cur,
            equipamento_id=equipamento_id,
            tipo_leitura=tipo_leitura,
            km_valor=km_valor,
            horas_valor=horas_valor,
            data_leitura=data_leitura,
            responsavel_id=responsavel_id,
            observacoes=observacoes,
            permitir_regressao=permitir_regressao,
            cols=cols,
            schema=schema,
        )
        conn.commit()
        return leitura_id
    finally:
        release_conn(conn)


def registrar_lote(
    itens: list[dict[str, Any]],
    responsavel_id=None,
    observacoes_padrao: str | None = None,
    permitir_regressao: bool = False,
) -> dict[str, Any]:
    if not itens:
        return {"importados": 0, "falhas": 0, "erros": []}

    conn = get_conn()
    cur = conn.cursor()
    erros: list[dict[str, Any]] = []
    importados = 0
    try:
        cols = _table_columns(cur)
        schema = _schema_map(cols)
        for item in itens:
            try:
                observacoes = item.get("observacoes") or observacoes_padrao
                _registrar_no_conn(
                    conn,
                    cur,
                    equipamento_id=item["equipamento_id"],
                    tipo_leitura=item["tipo_leitura"],
                    km_valor=item.get("km_valor"),
                    horas_valor=item.get("horas_valor"),
                    data_leitura=item.get("data_leitura"),
                    responsavel_id=item.get("responsavel_id") or responsavel_id,
                    observacoes=observacoes,
                    permitir_regressao=permitir_regressao,
                    cols=cols,
                    schema=schema,
                )
                importados += 1
            except Exception as exc:
                erros.append(
                    {
                        "linha": item.get("linha"),
                        "codigo": item.get("codigo"),
                        "erro": str(exc),
                    }
                )
        if erros:
            conn.rollback()
        else:
            conn.commit()
        return {"importados": importados, "falhas": len(erros), "erros": erros}
    finally:
        release_conn(conn)


def listar_por_equipamento(equipamento_id, limite=20):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cols = _table_columns(cur)
        if not cols:
            return []
        m = _schema_map(cols)
        if not m["equipamento_id"]:
            return []

        select_parts = [
            sql.SQL("l.{c}").format(c=sql.Identifier(m["id"] or "equipamento_id")),
            sql.SQL("l.{c}").format(c=sql.Identifier(m["data"] or m["created_at"] or m["equipamento_id"])),
        ]

        if m["tipo_leitura"]:
            select_parts.append(sql.SQL("l.{c}").format(c=sql.Identifier(m["tipo_leitura"])))
        else:
            select_parts.append(sql.SQL("null::text"))

        if m["km"]:
            select_parts.append(sql.SQL("l.{c}").format(c=sql.Identifier(m["km"])))
        else:
            select_parts.append(sql.SQL("null::numeric"))

        if m["horas"]:
            select_parts.append(sql.SQL("l.{c}").format(c=sql.Identifier(m["horas"])))
        else:
            select_parts.append(sql.SQL("null::numeric"))

        if m["responsavel_id"]:
            select_parts.append(sql.SQL("coalesce(r.nome, '-')"))
            join_sql = sql.SQL(" left join responsaveis r on r.id = l.{rid} ").format(rid=sql.Identifier(m["responsavel_id"]))
        else:
            select_parts.append(sql.SQL("'-'"))
            join_sql = sql.SQL("")

        if m["observacoes"]:
            select_parts.append(sql.SQL("l.{c}").format(c=sql.Identifier(m["observacoes"])))
        else:
            select_parts.append(sql.SQL("null::text"))

        order_candidates = []
        if m["data"] and m["data"] != "created_at":
            order_candidates.append(sql.SQL("l.{c} desc").format(c=sql.Identifier(m["data"])))
        if m["created_at"]:
            order_candidates.append(sql.SQL("l.{c} desc").format(c=sql.Identifier(m["created_at"])))
        if m["id"]:
            order_candidates.append(sql.SQL("l.{c} desc").format(c=sql.Identifier(m["id"])))
        order_sql = sql.SQL(", ").join(order_candidates) if order_candidates else sql.SQL("1 desc")

        query = sql.SQL(
            """
            select {fields}
            from public.leituras l
            {join_sql}
            where l.{equip_col} = %s
            order by {order_sql}
            limit %s
            """
        ).format(
            fields=sql.SQL(", ").join(select_parts),
            join_sql=join_sql,
            equip_col=sql.Identifier(m["equipamento_id"]),
            order_sql=order_sql,
        )

        cur.execute(query, (equipamento_id, limite))
        rows = cur.fetchall()
        out = []
        for r in rows:
            tipo = r[2] if len(r) > 2 else None
            km = r[3] if len(r) > 3 else None
            horas = r[4] if len(r) > 4 else None
            out.append({
                "id": r[0],
                "data_leitura": r[1],
                "tipo_leitura": tipo or _inferir_tipo_leitura(km, horas),
                "km_valor": _safe_float(km),
                "horas_valor": _safe_float(horas),
                "responsavel": r[5] if len(r) > 5 else "-",
                "observacoes": (r[6] if len(r) > 6 else "") or "",
            })
        return out
    except errors.UndefinedTable:
        conn.rollback()
        return []
    finally:
        release_conn(conn)
