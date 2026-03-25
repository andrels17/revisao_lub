from database.connection import get_conn


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                e.id,
                e.codigo,
                e.nome,
                e.tipo,
                e.km_atual,
                e.horas_atual,
                e.template_revisao_id,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome
            from equipamentos e
            left join setores s on s.id = e.setor_id
            order by e.codigo
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "codigo": r[1],
                "nome": r[2],
                "tipo": r[3],
                "km_atual": float(r[4] or 0),
                "horas_atual": float(r[5] or 0),
                "template_revisao_id": r[6],
                "setor_id": r[7],
                "setor_nome": r[8],
            }
            for r in rows
        ]
    finally:
        conn.close()



def criar(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0, template_revisao_id=None, ativo=True):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into equipamentos (
                codigo,
                nome,
                tipo,
                setor_id,
                km_atual,
                horas_atual,
                template_revisao_id,
                ativo
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                codigo,
                nome,
                tipo,
                setor_id,
                km_atual,
                horas_atual,
                template_revisao_id,
                ativo,
            ),
        )
        equipamento_id = cur.fetchone()[0]
        conn.commit()
        return equipamento_id
    finally:
        conn.close()
