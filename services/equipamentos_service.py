from __future__ import annotations

from typing import Any

import streamlit as st

from database.connection import get_conn, release_conn
from services import (
    auditoria_service,
    cache_service,
    escopo_service,
    lubrificacoes_service,
    revisoes_service,
)


TTL_EQ = 120


def _safe_close(conn) -> None:
    release_conn(conn)


def _colunas_equipamentos(cur) -> set[str]:
    cur.execute(
        """
        select column_name
          from information_schema.columns
         where table_schema = 'public'
           and table_name = 'equipamentos'
        """
    )
    return {str(r[0]) for r in cur.fetchall()}


def _ensure_base_planejamento_columns(cur) -> set[str]:
    colunas = _colunas_equipamentos(cur)
    faltantes = [c for c in ("km_inicial_plano", "horas_inicial_plano", "km_base_plano", "horas_base_plano") if c not in colunas]
    if not faltantes:
        return colunas
    try:
        for coluna in faltantes:
            cur.execute(f"alter table equipamentos add column if not exists {coluna} numeric")
        colunas = _colunas_equipamentos(cur)
    except Exception:
        cur.connection.rollback()
        colunas = _colunas_equipamentos(cur)
    return colunas


def _expr_base(colunas: set[str], prefer_col: str, legacy_col: str, atual_col: str) -> str:
    if prefer_col in colunas and legacy_col in colunas:
        return f"coalesce(e.{prefer_col}, e.{legacy_col}, e.{atual_col}, 0)"
    if prefer_col in colunas:
        return f"coalesce(e.{prefer_col}, e.{atual_col}, 0)"
    if legacy_col in colunas:
        return f"coalesce(e.{legacy_col}, e.{atual_col}, 0)"
    return f"coalesce(e.{atual_col}, 0)"


@st.cache_data(ttl=TTL_EQ, show_spinner=False)
def listar() -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _ensure_base_planejamento_columns(cur)
        cur.execute(
            f"""
            select
                e.id,
                e.codigo,
                e.nome,
                e.tipo,
                coalesce(e.km_atual, 0),
                coalesce(e.horas_atual, 0),
                {_expr_base(colunas, 'km_base_plano', 'km_atual')} as km_base_plano,
                {_expr_base(colunas, 'horas_base_plano', 'horas_atual')} as horas_base_plano,
                e.template_revisao_id,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome,
                e.template_lubrificacao_id,
                coalesce(e.ativo, true) as ativo
            from equipamentos e
            left join setores s on s.id = e.setor_id
            order by e.codigo, e.nome
            """
        )
        rows = cur.fetchall()
        itens = [
            {
                "id": r[0],
                "codigo": r[1],
                "nome": r[2],
                "tipo": r[3],
                "km_atual": float(r[4] or 0),
                "horas_atual": float(r[5] or 0),
                "km_inicial_plano": float(r[6] or 0),
                "km_base_plano": float(r[6] or 0),
                "horas_inicial_plano": float(r[7] or 0),
                "horas_base_plano": float(r[7] or 0),
                "template_revisao_id": r[8],
                "setor_id": r[9],
                "setor_nome": r[10],
                "template_lubrificacao_id": r[11],
                "ativo": bool(r[12]),
            }
            for r in rows
        ]
        return escopo_service.filtrar_equipamentos(itens)
    finally:
        _safe_close(conn)


def buscar(termo: str = "", somente_ativos: bool = False) -> list[dict[str, Any]]:
    termo_norm = (termo or "").strip().lower()
    itens = listar()
    if somente_ativos:
        itens = [item for item in itens if item.get("ativo", True)]
    if not termo_norm:
        return itens

    def _match(item: dict[str, Any]) -> bool:
        alvo = " ".join(
            [
                str(item.get("codigo", "")),
                str(item.get("nome", "")),
                str(item.get("tipo", "")),
                str(item.get("setor_nome", "")),
            ]
        ).lower()
        return termo_norm in alvo

    return [item for item in itens if _match(item)]


@st.cache_data(ttl=120, show_spinner=False)
def obter(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _ensure_base_planejamento_columns(cur)
        cur.execute(
            f"""
            select
                e.id,
                e.codigo,
                e.nome,
                e.tipo,
                coalesce(e.km_atual, 0),
                coalesce(e.horas_atual, 0),
                {_expr_base(colunas, 'km_base_plano', 'km_atual')} as km_base_plano,
                {_expr_base(colunas, 'horas_base_plano', 'horas_atual')} as horas_base_plano,
                e.template_revisao_id,
                coalesce(tr.nome, '-') as template_revisao_nome,
                e.template_lubrificacao_id,
                coalesce(tl.nome, '-') as template_lubrificacao_nome,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome,
                coalesce(e.ativo, true) as ativo
            from equipamentos e
            left join setores s on s.id = e.setor_id
            left join templates_revisao tr on tr.id = e.template_revisao_id
            left join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            where e.id = %s
            """,
            (equipamento_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        item = {
            "id": r[0],
            "codigo": r[1],
            "nome": r[2],
            "tipo": r[3],
            "km_atual": float(r[4] or 0),
            "horas_atual": float(r[5] or 0),
            "km_inicial_plano": float(r[6] or 0),
                "km_base_plano": float(r[6] or 0),
            "horas_inicial_plano": float(r[7] or 0),
                "horas_base_plano": float(r[7] or 0),
            "template_revisao_id": r[8],
            "template_revisao_nome": r[9],
            "template_lubrificacao_id": r[10],
            "template_lubrificacao_nome": r[11],
            "setor_id": r[12],
            "setor_nome": r[13],
            "ativo": bool(r[14]),
        }
        if not escopo_service.pode_ver_equipamento(item):
            return None
        return item
    finally:
        _safe_close(conn)


def obter_por_id(equipamento_id):
    return obter(equipamento_id)


@st.cache_data(ttl=TTL_EQ, show_spinner=False)
def listar_responsaveis_principais() -> dict[str, dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                ve.equipamento_id,
                ve.responsavel_id,
                coalesce(r.nome, '-') as responsavel_nome
            from vinculos_equipamento ve
            join responsaveis r on r.id = ve.responsavel_id
            where coalesce(ve.ativo, true) = true
              and coalesce(ve.principal, false) = true
              and coalesce(r.ativo, true) = true
            """
        )
        rows = cur.fetchall()
        return {
            row[0]: {
                "responsavel_id": row[1],
                "responsavel_nome": row[2],
            }
            for row in rows
        }
    except Exception:
        return {}
    finally:
        _safe_close(conn)


def _resumo_saude(revisoes: list[dict[str, Any]], lubrificacoes: list[dict[str, Any]]) -> dict[str, Any]:
    total_itens = len(revisoes) + len(lubrificacoes)
    vencidos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "VENCIDO")
    proximos = sum(1 for item in revisoes + lubrificacoes if item.get("status") == "PROXIMO")
    if total_itens == 0:
        return {
            "score": 100,
            "saude": "Sem plano",
            "vencidos": 0,
            "proximos": 0,
        }

    score = max(0, 100 - (vencidos * 25) - (proximos * 8))
    if vencidos >= 3 or score < 45:
        saude = "Crítico"
    elif vencidos >= 1 or score < 70:
        saude = "Atenção"
    else:
        saude = "Saudável"

    return {
        "score": score,
        "saude": saude,
        "vencidos": vencidos,
        "proximos": proximos,
    }


@st.cache_data(ttl=TTL_EQ, show_spinner="Carregando equipamentos…")
def carregar_snapshot_equipamentos() -> list[dict[str, Any]]:
    equipamentos = listar()
    if not equipamentos:
        return []

    ids = [e["id"] for e in equipamentos]
    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    principais = listar_responsaveis_principais()

    rows: list[dict[str, Any]] = []
    for eq in equipamentos:
        resumo = _resumo_saude(rev_idx.get(eq["id"], []), lub_idx.get(eq["id"], []))
        principal = principais.get(eq["id"], {})
        rows.append(
            {
                **eq,
                "responsavel_principal_id": principal.get("responsavel_id"),
                "responsavel_principal_nome": principal.get("responsavel_nome") or "-",
                "score_saude": resumo["score"],
                "saude": resumo["saude"],
                "vencidos": resumo["vencidos"],
                "proximos": resumo["proximos"],
                "tem_plano": bool(eq.get("template_revisao_id") or eq.get("template_lubrificacao_id")),
            }
        )

    rows.sort(key=lambda x: (x["saude"] != "Crítico", x["saude"] != "Atenção", x["codigo"], x["nome"]))
    return rows


def criar(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0, template_revisao_id=None, ativo=True, km_inicial_plano=None, horas_inicial_plano=None):
    return criar_completo(
        codigo=codigo,
        nome=nome,
        tipo=tipo,
        setor_id=setor_id,
        km_atual=km_atual,
        horas_atual=horas_atual,
        template_revisao_id=template_revisao_id,
        ativo=ativo,
        km_inicial_plano=km_inicial_plano,
        horas_inicial_plano=horas_inicial_plano,
    )


def criar_completo(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0, template_revisao_id=None, template_lubrificacao_id=None, ativo=True, km_inicial_plano=None, horas_inicial_plano=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _ensure_base_planejamento_columns(cur)
        km_inicial_plano = km_atual if km_inicial_plano is None else km_inicial_plano
        horas_inicial_plano = horas_atual if horas_inicial_plano is None else horas_inicial_plano

        insert_cols = [
            "codigo", "nome", "tipo", "setor_id",
            "km_atual", "horas_atual",
            "template_revisao_id", "template_lubrificacao_id", "ativo",
        ]
        values = [
            codigo, nome, tipo, setor_id,
            km_atual, horas_atual,
            template_revisao_id, template_lubrificacao_id, ativo,
        ]
        if "km_inicial_plano" in colunas:
            insert_cols.append("km_inicial_plano")
            values.append(km_inicial_plano)
        elif "km_base_plano" in colunas:
            insert_cols.append("km_base_plano")
            values.append(km_inicial_plano)
        if "horas_inicial_plano" in colunas:
            insert_cols.append("horas_inicial_plano")
            values.append(horas_inicial_plano)
        elif "horas_base_plano" in colunas:
            insert_cols.append("horas_base_plano")
            values.append(horas_inicial_plano)

        placeholders = ", ".join(["%s"] * len(insert_cols))
        cur.execute(
            f"""
            insert into equipamentos ({', '.join(insert_cols)})
            values ({placeholders})
            returning id
            """,
            values,
        )
        equipamento_id = cur.fetchone()[0]
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_equipamento",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo=None,
            valor_novo={
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo,
                "setor_id": setor_id,
                "km_atual": km_atual,
                "horas_atual": horas_atual,
                "template_revisao_id": template_revisao_id,
                "template_lubrificacao_id": template_lubrificacao_id,
                "km_inicial_plano": km_inicial_plano,
                "horas_inicial_plano": horas_inicial_plano,
                "ativo": ativo,
            },
        )
        conn.commit()
        limpar_cache()
        return equipamento_id
    finally:
        _safe_close(conn)


def atualizar_inline(equipamento_id, *, nome, tipo, setor_id, ativo, km_inicial_plano=None, horas_inicial_plano=None):
    atual = obter(equipamento_id)
    if not atual:
        raise ValueError("Equipamento não encontrado ou fora do escopo.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _ensure_base_planejamento_columns(cur)
        params = [nome, tipo, setor_id, bool(ativo)]
        set_parts = [
            "nome = %s",
            "tipo = %s",
            "setor_id = %s",
            "ativo = %s",
        ]
        if "km_inicial_plano" in colunas:
            set_parts.append("km_inicial_plano = %s")
            params.append(km_inicial_plano)
        elif "km_base_plano" in colunas:
            set_parts.append("km_base_plano = %s")
            params.append(km_inicial_plano)
        if "horas_inicial_plano" in colunas:
            set_parts.append("horas_inicial_plano = %s")
            params.append(horas_inicial_plano)
        elif "horas_base_plano" in colunas:
            set_parts.append("horas_base_plano = %s")
            params.append(horas_inicial_plano)
        params.append(equipamento_id)
        cur.execute(
            f"""
            update equipamentos
               set {', '.join(set_parts)}
             where id = %s
            """,
            params,
        )
        auditoria_service.registrar_no_conn(
            conn,
            acao="atualizar_equipamento_inline",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo={
                "nome": atual.get("nome"),
                "tipo": atual.get("tipo"),
                "setor_id": atual.get("setor_id"),
                "ativo": atual.get("ativo"),
                "km_inicial_plano": atual.get("km_inicial_plano", atual.get("km_base_plano")),
                "horas_inicial_plano": atual.get("horas_inicial_plano", atual.get("horas_base_plano")),
            },
            valor_novo={
                "nome": nome,
                "tipo": tipo,
                "setor_id": setor_id,
                "ativo": bool(ativo),
                "km_inicial_plano": km_inicial_plano,
                "horas_inicial_plano": horas_inicial_plano,
            },
        )
        conn.commit()
        limpar_cache()
    finally:
        _safe_close(conn)


def definir_responsavel_principal(equipamento_id, responsavel_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update vinculos_equipamento
               set principal = false
             where equipamento_id = %s
               and ativo = true
            """,
            (equipamento_id,),
        )

        if responsavel_id:
            cur.execute(
                """
                select tipo_vinculo
                  from vinculos_equipamento
                 where equipamento_id = %s
                   and responsavel_id = %s
                 order by ativo desc, principal desc
                 limit 1
                """,
                (equipamento_id, responsavel_id),
            )
            row = cur.fetchone()
            tipo_vinculo = (row[0] if row and row[0] else "operacional")

            cur.execute(
                """
                insert into vinculos_equipamento
                    (equipamento_id, responsavel_id, tipo_vinculo, principal, ativo)
                values (%s, %s, %s, true, true)
                on conflict (equipamento_id, responsavel_id, tipo_vinculo)
                do update set principal = true, ativo = true
                """,
                (equipamento_id, responsavel_id, tipo_vinculo),
            )

        auditoria_service.registrar_no_conn(
            conn,
            acao="definir_responsavel_principal",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo=None,
            valor_novo={"responsavel_id": responsavel_id},
        )
        conn.commit()
        limpar_cache()
    finally:
        _safe_close(conn)


def limpar_cache() -> None:
    cache_service.invalidate_planejamento()


def aplicar_templates_em_lote(equipamento_ids, template_revisao_id=None, template_lubrificacao_id=None):
    ids = [eid for eid in (equipamento_ids or []) if eid]
    if not ids:
        return 0

    set_parts = []
    params = []
    if template_revisao_id is not None:
        set_parts.append("template_revisao_id = %s")
        params.append(template_revisao_id)
    if template_lubrificacao_id is not None:
        set_parts.append("template_lubrificacao_id = %s")
        params.append(template_lubrificacao_id)
    if not set_parts:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(ids))
        params.extend(ids)
        cur.execute(
            f"""
            update equipamentos
               set {', '.join(set_parts)}
             where id in ({placeholders})
            """,
            tuple(params),
        )
        updated = cur.rowcount
        conn.commit()
        limpar_cache()
        return updated
    finally:
        _safe_close(conn)
