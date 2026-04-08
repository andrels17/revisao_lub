from database.connection import get_conn
from services import escopo_service


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome, tipo_nivel, setor_pai_id, ativo from setores order by nome")
        rows = cur.fetchall()
        itens = [
            {"id": r[0], "nome": r[1], "tipo_nivel": r[2], "setor_pai_id": r[3], "ativo": r[4]}
            for r in rows
        ]
        return escopo_service.filtrar_setores(itens)
    finally:
        conn.close()


def criar(nome, tipo_nivel="setor", setor_pai_id=None, ativo=True):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into setores (nome, tipo_nivel, setor_pai_id, ativo)
            values (%s, %s, %s, %s)
            returning id
            """,
            (nome, tipo_nivel, setor_pai_id, ativo),
        )
        setor_id = cur.fetchone()[0]
        conn.commit()
        return setor_id
    finally:
        conn.close()
