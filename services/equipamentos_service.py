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
                coalesce(s.nome, '-') as setor_nome,
                e.template_lubrificacao_id,
                e.ativo
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
                "template_lubrificacao_id": r[9],
                "ativo": bool(r[10]),
            }
            for r in rows
        ]
    finally:
        conn.close()



def obter(equipamento_id):
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
                coalesce(tr.nome, '-') as template_revisao_nome,
                e.template_lubrificacao_id,
                coalesce(tl.nome, '-') as template_lubrificacao_nome,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome,
                e.ativo
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
        return {
            "id": r[0],
            "codigo": r[1],
            "nome": r[2],
            "tipo": r[3],
            "km_atual": float(r[4] or 0),
            "horas_atual": float(r[5] or 0),
            "template_revisao_id": r[6],
            "template_revisao_nome": r[7],
            "template_lubrificacao_id": r[8],
            "template_lubrificacao_nome": r[9],
            "setor_id": r[10],
            "setor_nome": r[11],
            "ativo": bool(r[12]),
        }
    finally:
        conn.close()



def criar(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0,
          template_revisao_id=None, ativo=True):
    return criar_completo(
        codigo=codigo, nome=nome, tipo=tipo, setor_id=setor_id,
        km_atual=km_atual, horas_atual=horas_atual,
        template_revisao_id=template_revisao_id, ativo=ativo,
    )



def criar_completo(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0,
                   template_revisao_id=None, template_lubrificacao_id=None, ativo=True):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into equipamentos (
                codigo, nome, tipo, setor_id,
                km_atual, horas_atual,
                template_revisao_id, template_lubrificacao_id, ativo
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                codigo, nome, tipo, setor_id,
                km_atual, horas_atual,
                template_revisao_id, template_lubrificacao_id, ativo,
            ),
        )
        equipamento_id = cur.fetchone()[0]
        conn.commit()
        return equipamento_id
    finally:
        conn.close()
