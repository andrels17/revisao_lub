from __future__ import annotations

from collections import defaultdict

import psycopg2
import streamlit as st

from database.connection import get_conn, release_conn
from services import cache_service, configuracoes_service


# ── helpers ─────────────────────────────────────────────────────────────────

def _status_item_ciclo(leitura_atual, ultima_execucao, intervalo, tolerancia, leitura_base=0):
    if intervalo <= 0:
        atual = max(0.0, float(leitura_atual or 0))
        return "EM DIA", atual, atual, 0.0

    leitura_atual = float(leitura_atual or 0)
    ultima_execucao = float(ultima_execucao or 0)
    intervalo = float(intervalo or 0)
    leitura_base = float(leitura_base or 0)

    if leitura_base > leitura_atual:
        leitura_base = leitura_atual

    if ultima_execucao <= 0:
        inicio_ciclo = leitura_base
        proximo_vencimento = inicio_ciclo + intervalo
        diferenca = proximo_vencimento - leitura_atual
        if leitura_atual >= proximo_vencimento:
            return "VENCIDO", inicio_ciclo, proximo_vencimento, diferenca
        if diferenca <= tolerancia:
            return "PROXIMO", inicio_ciclo, proximo_vencimento, diferenca
        return "EM DIA", inicio_ciclo, proximo_vencimento, diferenca

    offset_atual = max(0.0, leitura_atual - leitura_base)
    ciclo_atual = int(offset_atual // intervalo) if offset_atual > 0 else 0
    ciclo_ultima = int((max(ultima_execucao, leitura_base) - leitura_base) // intervalo)
    inicio_ciclo = leitura_base + (ciclo_atual * intervalo)
    proximo_vencimento = inicio_ciclo + intervalo

    if ciclo_ultima == ciclo_atual:
        return "REALIZADO", inicio_ciclo, proximo_vencimento, max(0.0, proximo_vencimento - leitura_atual)

    falta = proximo_vencimento - leitura_atual
    if leitura_atual >= proximo_vencimento:
        return "VENCIDO", inicio_ciclo, proximo_vencimento, falta
    if falta <= tolerancia:
        return "PROXIMO", inicio_ciclo, proximo_vencimento, falta
    return "EM DIA", inicio_ciclo, proximo_vencimento, falta


def _colunas_tabela(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        select column_name
          from information_schema.columns
         where table_schema = 'public'
           and table_name = %s
        """,
        (table_name,),
    )
    return {str(r[0]) for r in cur.fetchall()}


def _pick_column(columns: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _expr_base(colunas: set[str], prefer_col: str, legacy_col: str, atual_col: str) -> str:
    if prefer_col in colunas and legacy_col in colunas:
        return f"coalesce(e.{prefer_col}, e.{legacy_col}, e.{atual_col}, 0)"
    if prefer_col in colunas:
        return f"coalesce(e.{prefer_col}, e.{atual_col}, 0)"
    if legacy_col in colunas:
        return f"coalesce(e.{legacy_col}, e.{atual_col}, 0)"
    return f"coalesce(e.{atual_col}, 0)"


def _normalizar_tipo_controle(valor: str | None) -> str:
    texto = str(valor or "").strip().lower()
    if "hora" in texto:
        return "horas"
    return "km"


def _schema_lubrificacao(cur) -> dict[str, object]:
    eq_cols = _colunas_tabela(cur, "equipamentos")
    tl_cols = _colunas_tabela(cur, "templates_lubrificacao")
    it_cols = _colunas_tabela(cur, "itens_template_lubrificacao")
    ex_cols = _colunas_tabela(cur, "execucoes_lubrificacao")

    return {
        "eq_cols": eq_cols,
        "tl_cols": tl_cols,
        "it_cols": it_cols,
        "ex_cols": ex_cols,
        "item_fk_col": _pick_column(it_cols, "template_id", "template_lubrificacao_id", "lubrificacao_template_id"),
        "item_nome_col": _pick_column(it_cols, "nome_item", "nome", "item", "descricao"),
        "item_prod_col": _pick_column(it_cols, "tipo_produto", "produto", "tipo", "nome_produto"),
        "item_intervalo_col": _pick_column(it_cols, "intervalo_valor", "intervalo", "valor_intervalo"),
        "item_ativo_col": _pick_column(it_cols, "ativo"),
        "exec_item_col": _pick_column(ex_cols, "item_id"),
        "exec_nome_col": _pick_column(ex_cols, "nome_item", "item", "descricao"),
        "exec_km_col": _pick_column(ex_cols, "km_execucao", "km", "km_atual"),
        "exec_horas_col": _pick_column(ex_cols, "horas_execucao", "horas", "horimetro"),
        "template_tipo_col": _pick_column(tl_cols, "tipo_controle"),
    }


def _carregar_ultimas_execucoes_batch(cur, equipamento_ids, schema):
    if not equipamento_ids or not schema.get("exec_km_col") or not schema.get("exec_horas_col"):
        return {}, {}

    placeholders = ",".join(["%s"] * len(equipamento_ids))
    ex_item_col = schema.get("exec_item_col")
    ex_nome_col = schema.get("exec_nome_col")
    ex_km_col = schema["exec_km_col"]
    ex_horas_col = schema["exec_horas_col"]
    template_tipo_col = schema.get("template_tipo_col") or "tipo_controle"

    item_map: dict = defaultdict(dict)
    nome_map: dict = defaultdict(dict)

    if ex_item_col:
        cur.execute(
            f"""
            select
                el.equipamento_id,
                el.{ex_item_col} as item_ref,
                tl.{template_tipo_col} as tipo_controle,
                max(
                    case
                        when lower(coalesce(tl.{template_tipo_col}, 'km')) like '%hora%'
                            then coalesce(el.{ex_horas_col}, 0)
                        else coalesce(el.{ex_km_col}, 0)
                    end
                ) as ultima
            from execucoes_lubrificacao el
            join equipamentos e on e.id = el.equipamento_id
            join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            where el.equipamento_id in ({placeholders})
              and el.{ex_item_col} is not null
            group by el.equipamento_id, el.{ex_item_col}, tl.{template_tipo_col}
            """,
            list(equipamento_ids),
        )
        for eqp_id, item_ref, _tipo, ultima in cur.fetchall():
            item_map[eqp_id][item_ref] = float(ultima or 0)

    if ex_nome_col:
        cur.execute(
            f"""
            select
                el.equipamento_id,
                lower(trim(coalesce(el.{ex_nome_col}, ''))) as nome_ref,
                tl.{template_tipo_col} as tipo_controle,
                max(
                    case
                        when lower(coalesce(tl.{template_tipo_col}, 'km')) like '%hora%'
                            then coalesce(el.{ex_horas_col}, 0)
                        else coalesce(el.{ex_km_col}, 0)
                    end
                ) as ultima
            from execucoes_lubrificacao el
            join equipamentos e on e.id = el.equipamento_id
            join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            where el.equipamento_id in ({placeholders})
              and nullif(trim(coalesce(el.{ex_nome_col}, '')), '') is not null
            group by el.equipamento_id, lower(trim(coalesce(el.{ex_nome_col}, ''))), tl.{template_tipo_col}
            """,
            list(equipamento_ids),
        )
        for eqp_id, nome_ref, _tipo, ultima in cur.fetchall():
            nome_map[eqp_id][nome_ref] = float(ultima or 0)

    return dict(item_map), dict(nome_map)


@st.cache_data(ttl=120, show_spinner=False)
def diagnosticar_carregamento():
    conn = get_conn()
    cur = conn.cursor()
    try:
        schema = _schema_lubrificacao(cur)
        diag = {
            "equipamentos_com_template": 0,
            "itens_template": 0,
            "templates_com_itens": 0,
            "execucoes_lubrificacao": 0,
            "motivo": None,
        }

        cur.execute("select count(*) from equipamentos where template_lubrificacao_id is not null")
        diag["equipamentos_com_template"] = int(cur.fetchone()[0] or 0)

        if not schema.get("item_fk_col"):
            diag["motivo"] = "A tabela itens_template_lubrificacao não possui coluna de vínculo com o template."
            return diag

        item_intervalo_col = schema.get("item_intervalo_col")
        item_ativo_col = schema.get("item_ativo_col")
        if not schema.get("item_nome_col") or not item_intervalo_col:
            diag["motivo"] = "A tabela itens_template_lubrificacao não possui colunas mínimas para cálculo."
            return diag

        ativo_where = f"where coalesce({item_ativo_col}, true) = true" if item_ativo_col else ""
        cur.execute(f"select count(*) from itens_template_lubrificacao {ativo_where}")
        diag["itens_template"] = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"""
            select count(distinct {schema['item_fk_col']})
              from itens_template_lubrificacao
              {ativo_where}
            """
        )
        diag["templates_com_itens"] = int(cur.fetchone()[0] or 0)

        if schema.get("ex_cols"):
            cur.execute("select count(*) from execucoes_lubrificacao")
            diag["execucoes_lubrificacao"] = int(cur.fetchone()[0] or 0)

        if diag["equipamentos_com_template"] <= 0:
            diag["motivo"] = "Nenhum equipamento está vinculado a template de lubrificação."
        elif diag["itens_template"] <= 0:
            diag["motivo"] = "Os templates existem, mas não há itens de lubrificação ativos cadastrados."
        elif diag["templates_com_itens"] <= 0:
            diag["motivo"] = "Os itens de lubrificação não estão ligados ao template esperado."
        else:
            diag["motivo"] = "Estrutura encontrada. Se a tela continuar vazia, o problema era de compatibilidade da consulta."
        return diag
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        return {"motivo": f"Falha ao diagnosticar: {exc}"}
    finally:
        release_conn(conn)


@st.cache_data(ttl=120, show_spinner=False)
def calcular_proximas_lubrificacoes_batch(equipamento_ids):
    if not equipamento_ids:
        return {}

    conn = get_conn()
    cur = conn.cursor()
    try:
        schema = _schema_lubrificacao(cur)
        item_fk_col = schema.get("item_fk_col")
        item_nome_col = schema.get("item_nome_col")
        item_prod_col = schema.get("item_prod_col")
        item_intervalo_col = schema.get("item_intervalo_col")
        item_ativo_col = schema.get("item_ativo_col")
        template_tipo_col = schema.get("template_tipo_col") or "tipo_controle"
        eq_cols = schema["eq_cols"]

        if not item_fk_col or not item_nome_col or not item_intervalo_col:
            return {}

        placeholders = ",".join(["%s"] * len(equipamento_ids))
        km_base_expr = _expr_base(eq_cols, "km_inicial_plano", "km_base_plano", "km_atual")
        horas_base_expr = _expr_base(eq_cols, "horas_inicial_plano", "horas_base_plano", "horas_atual")
        nome_expr = f"itl.{item_nome_col}"
        produto_expr = f"itl.{item_prod_col}" if item_prod_col else "null::text"
        intervalo_expr = f"coalesce(itl.{item_intervalo_col}, 0)"
        ativo_pred = f" and coalesce(itl.{item_ativo_col}, true) = true" if item_ativo_col else ""

        cur.execute(
            f"""
            select
                e.id as equipamento_id,
                coalesce(e.km_atual, 0) as km_atual,
                coalesce(e.horas_atual, 0) as horas_atual,
                {km_base_expr} as km_inicial_plano,
                {horas_base_expr} as horas_inicial_plano,
                tl.{template_tipo_col} as tipo_controle,
                itl.id as item_id,
                {nome_expr} as nome_item,
                {produto_expr} as tipo_produto,
                {intervalo_expr} as intervalo_valor
            from equipamentos e
            join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            join itens_template_lubrificacao itl on itl.{item_fk_col} = tl.id{ativo_pred}
            where e.id in ({placeholders})
              and e.template_lubrificacao_id is not null
            order by e.id, {intervalo_expr}, {nome_expr}
            """,
            list(equipamento_ids),
        )
        rows = cur.fetchall()
        if not rows:
            return {}

        ultimas_por_item, ultimas_por_nome = _carregar_ultimas_execucoes_batch(cur, equipamento_ids, schema)
        status_ordem = {"SEM_BASE": 0, "VENCIDO": 1, "PROXIMO": 2, "EM DIA": 3, "REALIZADO": 4}
        resultado = defaultdict(list)

        for (
            eqp_id,
            km_atual,
            horas_atual,
            km_inicial_plano,
            horas_inicial_plano,
            tipo_controle,
            item_id,
            nome_item,
            tipo_produto,
            intervalo,
        ) in rows:
            tipo_controle = _normalizar_tipo_controle(tipo_controle)
            leitura_atual = float(horas_atual if tipo_controle == "horas" else km_atual)
            leitura_base = float(horas_inicial_plano if tipo_controle == "horas" else km_inicial_plano)
            if leitura_base > leitura_atual:
                leitura_base = leitura_atual

            nome_ref = str(nome_item or "").strip().lower()
            ultima = ultimas_por_item.get(eqp_id, {}).get(item_id)
            if ultima is None and nome_ref:
                ultima = ultimas_por_nome.get(eqp_id, {}).get(nome_ref)
            ultima = float(ultima or 0)

            tolerancia = _tolerancia_por_tipo(tipo_controle)
            status, ref_ciclo, prox_venc, diff = _status_item_ciclo(
                leitura_atual,
                ultima,
                float(intervalo or 0),
                tolerancia,
                leitura_base=leitura_base,
            )

            resultado[eqp_id].append(
                {
                    "item_id": item_id,
                    "item": nome_item,
                    "tipo_produto": tipo_produto or "-",
                    "referencia_ciclo": ref_ciclo,
                    "vencimento": prox_venc,
                    "atual": leitura_atual,
                    "leitura_base_plano": leitura_base,
                    "km_inicial_plano": float(km_inicial_plano or 0),
                    "horas_inicial_plano": float(horas_inicial_plano or 0),
                    "km_base_plano": float(km_inicial_plano or 0),
                    "horas_base_plano": float(horas_inicial_plano or 0),
                    "ultima_execucao": ultima,
                    "status": status,
                    "diferenca": diff,
                    "tipo_controle": tipo_controle,
                    "intervalo": float(intervalo or 0),
                }
            )

        for eqp_id in resultado:
            resultado[eqp_id].sort(
                key=lambda x: (status_ordem.get(x["status"], 99), x["diferenca"], str(x["item"] or ""))
            )

        return dict(resultado)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return {}
    finally:
        release_conn(conn)


def calcular_proximas_lubrificacoes(equipamento_id):
    resultado = calcular_proximas_lubrificacoes_batch([equipamento_id])
    return resultado.get(equipamento_id, [])


# ── escrita ──────────────────────────────────────────────────────────────────

def registrar_execucao(dados):
    from services import auditoria_service, validacoes_service

    contexto = validacoes_service.validar_execucao_lubrificacao(
        equipamento_id=dados["equipamento_id"],
        item_id=dados.get("item_id"),
        data_execucao=dados["data_execucao"],
        km_execucao=dados.get("km_execucao", 0),
        horas_execucao=dados.get("horas_execucao", 0),
    )

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into execucoes_lubrificacao
                (equipamento_id, item_id, responsavel_id, nome_item, tipo_produto,
                 data_execucao, km_execucao, horas_execucao, observacoes)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                dados["equipamento_id"],
                dados.get("item_id"),
                dados.get("responsavel_id"),
                dados.get("nome_item"),
                dados.get("tipo_produto"),
                dados["data_execucao"],
                dados.get("km_execucao", 0),
                dados.get("horas_execucao", 0),
                dados.get("observacoes"),
            ),
        )
        execucao_id = cur.fetchone()[0]
        cur.execute(
            """
            update equipamentos
               set km_atual    = greatest(coalesce(km_atual, 0),    coalesce(%s, 0)),
                   horas_atual = greatest(coalesce(horas_atual, 0), coalesce(%s, 0))
             where id = %s
            """,
            (dados.get("km_execucao", 0), dados.get("horas_execucao", 0), dados["equipamento_id"]),
        )
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_execucao_lubrificacao",
            entidade="execucoes_lubrificacao",
            entidade_id=execucao_id,
            valor_antigo={
                "km_atual": contexto.get("km_atual"),
                "horas_atual": contexto.get("horas_atual"),
            },
            valor_novo=dados,
        )
        conn.commit()
        cache_service.invalidate_planejamento()
        return execucao_id
    finally:
        release_conn(conn)


# ── leitura ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=90, show_spinner=False)
def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select el.id, el.data_execucao, el.nome_item, el.tipo_produto,
                   el.km_execucao, el.horas_execucao,
                   coalesce(r.nome, '-') as responsavel, el.observacoes
            from execucoes_lubrificacao el
            left join responsaveis r on r.id = el.responsavel_id
            where el.equipamento_id = %s
            order by el.data_execucao desc, el.id desc
            """,
            (equipamento_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "item": r[2],
                "produto": r[3] or "-",
                "km": float(r[4] or 0),
                "horas": float(r[5] or 0),
                "responsavel": r[6],
                "observacoes": r[7] or "",
            }
            for r in rows
        ]
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)


@st.cache_data(ttl=120, show_spinner=False)
def listar_todos():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select el.id, el.data_execucao,
                   eq.codigo || ' - ' || eq.nome as equipamento,
                   coalesce(s.nome, '-') as setor,
                   el.nome_item, el.tipo_produto,
                   el.km_execucao, el.horas_execucao,
                   coalesce(r.nome, '-') as responsavel,
                   el.observacoes
            from execucoes_lubrificacao el
            join equipamentos eq on eq.id = el.equipamento_id
            left join setores s on s.id = eq.setor_id
            left join responsaveis r on r.id = el.responsavel_id
            order by el.data_execucao desc, el.id desc
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "equipamento": r[2],
                "setor": r[3],
                "item": r[4],
                "produto": r[5] or "-",
                "km": float(r[6] or 0),
                "horas": float(r[7] or 0),
                "responsavel": r[8],
                "observacoes": r[9] or "",
            }
            for r in rows
        ]
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)
