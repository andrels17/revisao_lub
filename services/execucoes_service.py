import re
from database.connection import get_conn, release_conn
from services import auditoria_service, validacoes_service

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


ETAPA_REGEX = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _extrair_etapa(observacoes):
    if not observacoes:
        return None
    m = ETAPA_REGEX.search(observacoes)
    return m.group(1).strip() if m else None


def _formatar_resultado_execucao(km_execucao, horas_execucao):
    if km_execucao is not None:
        return f"Realizado com {float(km_execucao):.0f} km"
    if horas_execucao is not None:
        return f"Realizado com {float(horas_execucao):.0f} h"
    return "Realizado"


def _itens_execucao_disponiveis(cur) -> bool:
    try:
        cur.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'public'
              and table_name = 'execucao_manutencao_itens'
            limit 1
            """
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def _colunas_execucao_itens(cur):
    if not _itens_execucao_disponiveis(cur):
        return set()
    try:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public'
              and table_name = 'execucao_manutencao_itens'
            """
        )
        return {r[0] for r in cur.fetchall()}
    except Exception:
        return set()


def salvar_itens_execucao_no_conn(cur, execucao_id, itens_executados):
    if not itens_executados:
        return
    colunas = _colunas_execucao_itens(cur)
    if not colunas:
        return

    insert_cols = ["execucao_id"]
    if "item_id_referencia" in colunas:
        insert_cols.append("item_id_referencia")
    if "item_nome" in colunas:
        insert_cols.append("item_nome")
    if "produto" in colunas:
        insert_cols.append("produto")
    if "intervalo_valor" in colunas:
        insert_cols.append("intervalo_valor")
    if "marcado" in colunas:
        insert_cols.append("marcado")

    placeholders = ", ".join(["%s"] * len(insert_cols))
    cols_sql = ", ".join(insert_cols)
    sql = f"insert into execucao_manutencao_itens ({cols_sql}) values ({placeholders})"

    for item in itens_executados:
        values = [execucao_id]
        if "item_id_referencia" in colunas:
            values.append(item.get("id"))
        if "item_nome" in colunas:
            values.append(item.get("nome_item") or item.get("item_nome") or "Item sem nome")
        if "produto" in colunas:
            values.append(item.get("tipo_produto") or item.get("produto"))
        if "intervalo_valor" in colunas:
            values.append(item.get("intervalo_valor"))
        if "marcado" in colunas:
            values.append(True)
        cur.execute(sql, tuple(values))


def listar_itens_execucao(execucao_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        colunas = _colunas_execucao_itens(cur)
        if not colunas:
            return []

        select_cols = ["id"]
        select_cols.append("item_id_referencia" if "item_id_referencia" in colunas else "NULL as item_id_referencia")
        select_cols.append("item_nome" if "item_nome" in colunas else "NULL as item_nome")
        select_cols.append("produto" if "produto" in colunas else "NULL as produto")
        select_cols.append("intervalo_valor" if "intervalo_valor" in colunas else "NULL as intervalo_valor")
        select_cols.append("marcado" if "marcado" in colunas else "TRUE as marcado")

        sql = f"""
            select {', '.join(select_cols)}
            from execucao_manutencao_itens
            where execucao_id = %s
            order by 3 nulls last
        """
        cur.execute(sql, (execucao_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "item_id_referencia": r[1],
                "item_nome": r[2] or "Item",
                "produto": r[3],
                "intervalo_valor": float(r[4] or 0),
                "marcado": bool(r[5]),
            }
            for r in rows
        ]
    finally:
        release_conn(conn)



def criar_execucao(dados):
    km_execucao = dados.get("km_execucao")
    horas_execucao = dados.get("horas_execucao")

    if dados["tipo"] == "revisao":
        contexto = validacoes_service.validar_execucao_revisao(
            equipamento_id=dados["equipamento_id"],
            data_execucao=dados["data_execucao"],
            km_execucao=km_execucao,
            horas_execucao=horas_execucao,
            observacoes=dados.get("observacoes"),
            status=dados.get("status", "concluida"),
        )
    else:
        contexto = validacoes_service.obter_equipamento_contexto(dados["equipamento_id"])

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into execucoes_manutencao (
                equipamento_id,
                responsavel_id,
                tipo,
                data_execucao,
                km_execucao,
                horas_execucao,
                observacoes,
                status
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                dados["equipamento_id"],
                dados.get("responsavel_id"),
                dados["tipo"],
                dados["data_execucao"],
                km_execucao,
                horas_execucao,
                dados.get("observacoes"),
                dados.get("status", "concluida"),
            ),
        )
        execucao_id = cur.fetchone()[0]

        salvar_itens_execucao_no_conn(cur, execucao_id, dados.get("itens_executados") or [])

        if dados["tipo"] == "revisao":
            if km_execucao is not None:
                cur.execute(
                    """
                    update equipamentos
                       set km_atual = greatest(coalesce(km_atual, 0), %s)
                     where id = %s
                    """,
                    (km_execucao, dados["equipamento_id"]),
                )
            if horas_execucao is not None:
                cur.execute(
                    """
                    update equipamentos
                       set horas_atual = greatest(coalesce(horas_atual, 0), %s)
                     where id = %s
                    """,
                    (horas_execucao, dados["equipamento_id"]),
                )

        auditoria_service.registrar_no_conn(
            conn,
            acao=f"criar_execucao_{dados['tipo']}",
            entidade="execucoes_manutencao",
            entidade_id=execucao_id,
            valor_antigo={
                "km_atual": contexto.get("km_atual") if contexto else None,
                "horas_atual": contexto.get("horas_atual") if contexto else None,
            },
            valor_novo=dados,
        )

        conn.commit()
        return execucao_id
    finally:
        release_conn(conn)



def listar_revisoes_por_equipamento(equipamento_id, limite=20):
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                select em.id,
                       em.data_execucao,
                       em.km_execucao,
                       em.horas_execucao,
                       coalesce(r.nome, '-') as responsavel,
                       coalesce(em.status, 'concluida') as status,
                       em.observacoes
                from execucoes_manutencao em
                left join responsaveis r on r.id = em.responsavel_id
                where em.equipamento_id = %s
                  and em.tipo = 'revisao'
                order by em.data_execucao desc, em.created_at desc
                limit %s
                """,
                (equipamento_id, limite),
            )
        except Exception as exc:
            if not psycopg2 or not isinstance(
                exc,
                (
                    psycopg2.errors.UndefinedColumn,
                    psycopg2.errors.UndefinedTable,
                    psycopg2.errors.UndefinedObject,
                ),
            ):
                raise
            conn.rollback()
            if isinstance(exc, psycopg2.errors.UndefinedColumn):
                cur.execute(
                    """
                    select em.id,
                           em.data_execucao,
                           em.km_execucao,
                           em.horas_execucao,
                           coalesce(r.nome, '-') as responsavel,
                           coalesce(em.status, 'concluida') as status,
                           em.observacoes
                    from execucoes_manutencao em
                    left join responsaveis r on r.id = em.responsavel_id
                    where em.equipamento_id = %s
                      and em.tipo = 'revisao'
                    order by em.data_execucao desc, em.id desc
                    limit %s
                    """,
                    (equipamento_id, limite),
                )
            else:
                return []

        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "km": float(r[2] or 0),
                "horas": float(r[3] or 0),
                "responsavel": r[4],
                "status": r[5],
                "observacoes": r[6] or "",
                "resultado": _formatar_resultado_execucao(r[2], r[3]),
                "etapa_referencia": _extrair_etapa(r[6]),
                "itens_executados": listar_itens_execucao(r[0]),
            }
            for r in rows
        ]
    finally:
        release_conn(conn)



def resumo_revisoes_por_equipamento(equipamento_id):
    historico = listar_revisoes_por_equipamento(equipamento_id, limite=200)
    if not historico:
        return {
            "total": 0,
            "concluidas": 0,
            "pendentes": 0,
            "ultima_data": None,
        }

    return {
        "total": len(historico),
        "concluidas": sum(1 for item in historico if item.get("status") == "concluida"),
        "pendentes": sum(1 for item in historico if item.get("status") == "pendente"),
        "ultima_data": historico[0].get("data"),
    }
