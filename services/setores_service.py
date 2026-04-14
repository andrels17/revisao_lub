from database.connection import get_conn, release_conn
from services import auditoria_service, escopo_service


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                s.id,
                s.nome,
                s.tipo_nivel,
                s.setor_pai_id,
                s.ativo,
                coalesce(sp.nome, '-') as setor_pai_nome,
                count(e.id) as total_equipamentos
            from setores s
            left join setores sp on sp.id = s.setor_pai_id
            left join equipamentos e on e.setor_id = s.id
            group by s.id, s.nome, s.tipo_nivel, s.setor_pai_id, s.ativo, sp.nome
            order by s.nome
            """
        )
        rows = cur.fetchall()
        itens = [
            {
                "id": r[0],
                "nome": r[1],
                "tipo_nivel": r[2],
                "setor_pai_id": r[3],
                "ativo": r[4],
                "setor_pai_nome": r[5],
                "total_equipamentos": int(r[6] or 0),
            }
            for r in rows
        ]
        return escopo_service.filtrar_setores(itens)
    finally:
        release_conn(conn)


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
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo=None,
            valor_novo={
                "nome": nome,
                "tipo_nivel": tipo_nivel,
                "setor_pai_id": setor_pai_id,
                "ativo": bool(ativo),
            },
        )
        conn.commit()
        return setor_id
    finally:
        release_conn(conn)


def vincular_equipamentos(setor_id, equipamento_ids: list[int]):
    equipamento_ids = [int(x) for x in (equipamento_ids or [])]
    if not equipamento_ids:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome from setores where id = %s",
            (setor_id,),
        )
        setor = cur.fetchone()
        if not setor:
            raise ValueError("Setor não encontrado.")

        cur.execute(
            """
            update equipamentos
               set setor_id = %s
             where id = any(%s)
            """,
            (setor_id, equipamento_ids),
        )
        total = cur.rowcount or 0
        auditoria_service.registrar_no_conn(
            conn,
            acao="vincular_equipamentos_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo=None,
            valor_novo={"equipamento_ids": equipamento_ids, "total": total},
        )
        conn.commit()
        return total
    finally:
        release_conn(conn)


def excluir(setor_id, destino_setor_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome, setor_pai_id from setores where id = %s",
            (setor_id,),
        )
        atual = cur.fetchone()
        if not atual:
            raise ValueError("Setor não encontrado.")

        cur.execute("select count(1) from setores where setor_pai_id = %s", (setor_id,))
        filhos = int(cur.fetchone()[0] or 0)

        cur.execute("select count(1) from equipamentos where setor_id = %s", (setor_id,))
        equipamentos = int(cur.fetchone()[0] or 0)

        if destino_setor_id:
            if int(destino_setor_id) == int(setor_id):
                raise ValueError("O setor de destino deve ser diferente do setor excluído.")
            cur.execute("select id from setores where id = %s", (destino_setor_id,))
            if not cur.fetchone():
                raise ValueError("Setor de destino não encontrado.")

        if filhos and not destino_setor_id:
            raise ValueError("Este setor possui setores filhos. Informe um setor de destino antes de excluir.")
        if equipamentos and not destino_setor_id:
            raise ValueError("Este setor possui equipamentos vinculados. Informe um setor de destino antes de excluir.")

        if destino_setor_id:
            cur.execute("update setores set setor_pai_id = %s where setor_pai_id = %s", (destino_setor_id, setor_id))
            cur.execute("update equipamentos set setor_id = %s where setor_id = %s", (destino_setor_id, setor_id))
            cur.execute(
                "update vinculos_setor_responsavel set setor_id = %s where setor_id = %s",
                (destino_setor_id, setor_id),
            )

        auditoria_service.registrar_no_conn(
            conn,
            acao="excluir_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo={
                "nome": atual[1],
                "setor_pai_id": atual[2],
                "filhos": filhos,
                "equipamentos": equipamentos,
            },
            valor_novo={"destino_setor_id": destino_setor_id},
        )
        cur.execute("delete from setores where id = %s", (setor_id,))
        conn.commit()
        return True
    finally:
        release_conn(conn)
