from database.connection import get_conn


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
        conn.close()


def listar_com_itens():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select t.id, t.nome, t.tipo_controle,
                   i.id as item_id, i.nome_item, i.tipo_produto, i.intervalo_valor
            from templates_lubrificacao t
            left join itens_template_lubrificacao i
                   on i.template_id = t.id and i.ativo = true
            where t.ativo = true
            order by t.nome, i.intervalo_valor
            """
        )
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
                templates[tid]["itens"].append(
                    {
                        "id": r[3],
                        "nome_item": r[4],
                        "tipo_produto": r[5] or "-",
                        "intervalo_valor": float(r[6]),
                    }
                )
        return list(templates.values())
    finally:
        conn.close()


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
        return template_id
    finally:
        conn.close()


def adicionar_item(template_id, nome_item, tipo_produto, intervalo_valor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into itens_template_lubrificacao
                (template_id, nome_item, tipo_produto, intervalo_valor)
            values (%s, %s, %s, %s) returning id
            """,
            (template_id, nome_item, tipo_produto, intervalo_valor),
        )
        item_id = cur.fetchone()[0]
        conn.commit()
        return item_id
    finally:
        conn.close()
