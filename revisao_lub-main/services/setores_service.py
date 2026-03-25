from database.connection import get_conn

def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome, tipo_nivel, setor_pai_id, ativo from setores order by nome")
        rows = cur.fetchall()
        return [
            {"id": r[0], "nome": r[1], "tipo_nivel": r[2], "setor_pai_id": r[3], "ativo": r[4]}
            for r in rows
        ]
    finally:
        conn.close()
