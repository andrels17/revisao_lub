from database.connection import get_conn

def criar_execucao(dados):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
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
    """, (
        dados["equipamento_id"],
        dados["responsavel_id"],
        dados["tipo"],
        dados["data_execucao"],
        dados["km_execucao"],
        dados["horas_execucao"],
        dados["observacoes"],
        dados["status"]
    ))

    # 🔥 Atualiza o equipamento automaticamente
    cur.execute("""
        update equipamentos
        set km_atual = %s,
            horas_atual = %s
        where id = %s
    """, (
        dados["km_execucao"],
        dados["horas_execucao"],
        dados["equipamento_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()
