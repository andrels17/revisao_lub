from __future__ import annotations

import streamlit as st

from database.connection import get_conn, release_conn
from services import cache_service

TABLE_NAME = "itens_template_lubrificacao"


@st.cache_data(ttl=600, show_spinner=False)
def _get_table_columns_cached(table_name: str) -> tuple[str, ...]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            """,
            (table_name,),
        )
        return tuple(sorted(r[0] for r in cur.fetchall()))
    finally:
        release_conn(conn)


def _get_table_columns(cur, table_name: str) -> set[str]:
    try:
        cached = _get_table_columns_cached(table_name)
        if cached:
            return set(cached)
    except Exception:
        pass
    cur.execute(
        """
        select column_name
        from information_schema.columns
        where table_schema = 'public' and table_name = %s
        """,
        (table_name,),
    )
    return {r[0] for r in cur.fetchall()}


def _pick_column(columns: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


@st.cache_data(ttl=300, show_spinner=False)
def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome, tipo_controle, ativo from templates_lubrificacao order by nome"
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "nome": r[1], "tipo_controle": r[2], "ativo": r[3]}
            for r in rows
        ]
    finally:
        release_conn(conn)



@st.cache_data(ttl=300, show_spinner=False)
def listar_com_itens():
    conn = get_conn()
    cur = conn.cursor()
    try:
        columns = _get_table_columns(cur, TABLE_NAME)
        name_col = _pick_column(columns, "nome_item", "nome", "item", "descricao")
        product_col = _pick_column(columns, "tipo_produto", "produto", "tipo", "nome_produto")
        interval_col = _pick_column(columns, "intervalo_valor", "intervalo", "valor_intervalo")
        active_col = _pick_column(columns, "ativo")

        name_expr = f"i.{name_col}" if name_col else "null::text"
        product_expr = f"i.{product_col}" if product_col else "null::text"
        interval_expr = f"coalesce(i.{interval_col}, 0)" if interval_col else "0::numeric"
        join_extra = f" and i.{active_col} = true" if active_col else ""

        query = f"""
            select t.id, t.nome, t.tipo_controle,
                   i.id as item_id,
                   {name_expr} as nome_item,
                   {product_expr} as tipo_produto,
                   {interval_expr} as intervalo_valor
            from templates_lubrificacao t
            left join {TABLE_NAME} i
                   on i.template_id = t.id{join_extra}
            where t.ativo = true
            order by t.nome, {interval_expr}, {name_expr}
        """
        cur.execute(query)
        rows = cur.fetchall()
        templates = {}
        for r in rows:
            tid = r[0]
            if tid not in templates:
                templates[tid] = {
                    "id": tid,
                    "nome": r[1],
                    "tipo_controle": r[2],
                    "itens": [],
                }
            if r[3]:
                try:
                    intervalo = float(r[6] or 0)
                except Exception:
                    intervalo = 0.0
                templates[tid]["itens"].append(
                    {
                        "id": r[3],
                        "nome_item": r[4] or "Item sem nome",
                        "tipo_produto": r[5] or "-",
                        "intervalo_valor": intervalo,
                    }
                )
        return list(templates.values())
    finally:
        release_conn(conn)



def criar(nome, tipo_controle):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "insert into templates_lubrificacao (nome, tipo_controle) values (%s, %s) returning id",
            (nome, tipo_controle),
        )
        template_id = cur.fetchone()[0]
        conn.commit()
        cache_service.invalidate_templates()
        return template_id
    finally:
        release_conn(conn)



def adicionar_item(template_id, nome_item, tipo_produto, intervalo_valor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        columns = _get_table_columns(cur, TABLE_NAME)
        name_col = _pick_column(columns, "nome_item", "nome", "item", "descricao")
        product_col = _pick_column(columns, "tipo_produto", "produto", "tipo", "nome_produto")
        interval_col = _pick_column(columns, "intervalo_valor", "intervalo", "valor_intervalo")
        active_col = _pick_column(columns, "ativo")

        if not name_col or not interval_col:
            raise RuntimeError(
                "A tabela de itens de lubrificação não possui as colunas mínimas esperadas."
            )

        cols = ["template_id", name_col, interval_col]
        vals = [template_id, nome_item, intervalo_valor]

        if product_col:
            cols.append(product_col)
            vals.append(tipo_produto)
        if active_col:
            cols.append(active_col)
            vals.append(True)

        placeholders = ", ".join(["%s"] * len(cols))
        columns_sql = ", ".join(cols)

        cur.execute(
            f"insert into {TABLE_NAME} ({columns_sql}) values ({placeholders}) returning id",
            tuple(vals),
        )
        item_id = cur.fetchone()[0]
        conn.commit()
        cache_service.invalidate_templates()
        return item_id
    finally:
        release_conn(conn)



def atualizar_template(template_id, nome, tipo_controle):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update templates_lubrificacao
               set nome = %s,
                   tipo_controle = %s
             where id = %s
            """,
            (nome, tipo_controle, template_id),
        )
        conn.commit()
        cache_service.invalidate_templates()
    finally:
        release_conn(conn)



def atualizar_item(item_id, nome_item, tipo_produto, intervalo_valor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        columns = _get_table_columns(cur, TABLE_NAME)
        name_col = _pick_column(columns, "nome_item", "nome", "item", "descricao")
        product_col = _pick_column(columns, "tipo_produto", "produto", "tipo", "nome_produto")
        interval_col = _pick_column(columns, "intervalo_valor", "intervalo", "valor_intervalo")

        if not name_col or not interval_col:
            raise RuntimeError(
                "A tabela de itens de lubrificação não possui as colunas mínimas esperadas para edição."
            )

        campos = [f"{name_col} = %s", f"{interval_col} = %s"]
        params = [nome_item, intervalo_valor]

        if product_col:
            campos.append(f"{product_col} = %s")
            params.append(tipo_produto)

        params.append(item_id)
        cur.execute(
            f"update {TABLE_NAME} set {', '.join(campos)} where id = %s",
            tuple(params),
        )
        conn.commit()
        cache_service.invalidate_templates()
    finally:
        release_conn(conn)
