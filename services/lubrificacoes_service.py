from psycopg2 import errors

from database.connection import get_conn

TOLERANCIA_PADRAO = 10


def calcular_proximas_lubrificacoes(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Tudo em uma única query com LEFT JOIN — elimina o N+1 anterior
        cur.execute(
            """
            select
                itl.id,
                itl.nome_item,
                itl.tipo_produto,
                itl.intervalo_valor,
                tl.tipo_controle,
                e.horas_atual,
                e.km_atual,
                coalesce(
                    max(case when tl.tipo_controle = 'horas'
                             then el.horas_execucao
                             else el.km_execucao end),
                    0
                ) as ultima_execucao
            from equipamentos e
            join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            join itens_template_lubrificacao itl on itl.template_id = tl.id and itl.ativo = true
            left join execucoes_lubrificacao el
                   on el.equipamento_id = e.id and el.item_id = itl.id
            where e.id = %s
            group by itl.id, itl.nome_item, itl.tipo_produto, itl.intervalo_valor,
                     tl.tipo_controle, e.horas_atual, e.km_atual
            order by itl.intervalo_valor
            """,
            (equipamento_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return []

        status_ordem = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}
        resultados = []

        for item_id, nome_item, tipo_produto, intervalo, tipo_controle, horas_atual, km_atual, ultima in rows:
            leitura_atual = float(horas_atual if tipo_controle == "horas" else km_atual)
            ultima = float(ultima or 0)
            proxima = ultima + float(intervalo)
            diff = proxima - leitura_atual

            if leitura_atual >= proxima:
                status = "VENCIDO"
            elif diff <= TOLERANCIA_PADRAO:
                status = "PROXIMO"
            else:
                status = "EM DIA"

            resultados.append(
                {
                    "item_id": item_id,
                    "item": nome_item,
                    "tipo_produto": tipo_produto or "-",
                    "vencimento": proxima,
                    "atual": leitura_atual,
                    "ultima_execucao": ultima,
                    "status": status,
                    "diferenca": diff,
                    "tipo_controle": tipo_controle,
                    "intervalo": float(intervalo),
                }
            )

        resultados.sort(key=lambda x: (status_ordem.get(x["status"], 99), x["diferenca"]))
        return resultados
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        conn.close()


def registrar_execucao(dados):
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
               set km_atual    = greatest(coalesce(km_atual, 0), %s),
                   horas_atual = greatest(coalesce(horas_atual, 0), %s)
             where id = %s
            """,
            (dados.get("km_execucao", 0), dados.get("horas_execucao", 0), dados["equipamento_id"]),
        )
        conn.commit()
        return execucao_id
    finally:
        conn.close()


def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    consultas = [
        """
        select el.id, el.data_execucao, el.nome_item, el.tipo_produto,
               el.km_execucao, el.horas_execucao,
               coalesce(r.nome, '-') as responsavel, el.observacoes
        from execucoes_lubrificacao el
        left join responsaveis r on r.id = el.responsavel_id
        where el.equipamento_id = %s
        order by el.data_execucao desc, el.created_at desc
        """,
        """
        select el.id, el.data_execucao, el.nome_item, el.tipo_produto,
               el.km_execucao, el.horas_execucao,
               coalesce(r.nome, '-') as responsavel, el.observacoes
        from execucoes_lubrificacao el
        left join responsaveis r on r.id = el.responsavel_id
        where el.equipamento_id = %s
        order by el.data_execucao desc, el.id desc
        """,
    ]
    try:
        rows = None
        for sql in consultas:
            try:
                cur.execute(sql, (equipamento_id,))
                rows = cur.fetchall()
                break
            except errors.UndefinedColumn:
                conn.rollback()
                continue
            except errors.UndefinedTable:
                conn.rollback()
                return []
        if rows is None:
            return []
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
    finally:
        conn.close()


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
            order by el.data_execucao desc, el.created_at desc
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
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        conn.close()
