from database.connection import get_conn


def criar_execucao(dados):
    conn = get_conn()
    cur = conn.cursor()
    try:
        km_execucao = dados.get("km_execucao")
        horas_execucao = dados.get("horas_execucao")

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

        if dados["tipo"] == "revisao":
            if km_execucao is not None:
                cur.execute(
                    """
                    update equipamentos
                       set km_atual = %s
                     where id = %s
                    """,
                    (km_execucao, dados["equipamento_id"]),
                )
            if horas_execucao is not None:
                cur.execute(
                    """
                    update equipamentos
                       set horas_atual = %s
                     where id = %s
                    """,
                    (horas_execucao, dados["equipamento_id"]),
                )

        conn.commit()
        return execucao_id
    finally:
        conn.close()


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                e.id,
                e.data_execucao,
                e.tipo,
                e.km_execucao,
                e.horas_execucao,
                e.status,
                eq.codigo,
                eq.nome,
                r.nome as responsavel,
                e.observacoes
            from execucoes_manutencao e
            join equipamentos eq on eq.id = e.equipamento_id
            left join responsaveis r on r.id = e.responsavel_id
            order by e.data_execucao desc, e.created_at desc
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data_execucao": r[1],
                "tipo": r[2],
                "km_execucao": float(r[3] or 0),
                "horas_execucao": float(r[4] or 0),
                "status": r[5],
                "equipamento": f"{r[6]} - {r[7]}",
                "responsavel": r[8] or "-",
                "observacoes": r[9] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()


def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                e.id,
                e.data_execucao,
                e.tipo,
                e.km_execucao,
                e.horas_execucao,
                e.status,
                r.nome as responsavel,
                e.observacoes
            from execucoes_manutencao e
            left join responsaveis r on r.id = e.responsavel_id
            where e.equipamento_id = %s
            order by e.data_execucao desc, e.created_at desc
            """,
            (equipamento_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data_execucao": r[1],
                "tipo": r[2],
                "km_execucao": float(r[3] or 0),
                "horas_execucao": float(r[4] or 0),
                "status": r[5],
                "responsavel": r[6] or "-",
                "observacoes": r[7] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()
