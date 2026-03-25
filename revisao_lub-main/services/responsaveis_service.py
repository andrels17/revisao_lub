from database.connection import get_conn

def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome, funcao_principal, telefone, email, ativo from responsaveis order by nome")
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nome": r[1],
                "funcao_principal": r[2],
                "telefone": r[3],
                "email": r[4],
                "ativo": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()
