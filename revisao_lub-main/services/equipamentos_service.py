from database.connection import get_conn

def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, codigo, nome, tipo, km_atual, horas_atual, template_revisao_id from equipamentos order by codigo")
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
            }
            for r in rows
        ]
    finally:
        conn.close()
