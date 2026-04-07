from database.connection import get_conn


def _formatar_resultado_execucao(km_execucao, horas_execucao):
    if km_execucao is not None:
        return f"Realizado com {float(km_execucao):.0f} km"
    if horas_execucao is not None:
        return f"Realizado com {float(horas_execucao):.0f} h"
    return "Realizado"


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
                       set km_atual = greatest(coalesce(km_atual, 0), %s)
                     where id = %s
                    """,
                    (km_execucao, dados["equipamento_id"]),
                )
            if horas_execucao is not None:
                cur.execute(
                    """
                    update equipamentos
                       set horas_atual = greatest(coalesce(horas_atual, 0), %s)
                     where id = %s
                    """,
                    (horas_execucao, dados["equipamento_id"]),
                )

        conn.commit()
        return execucao_id
    finally:
        conn.close()
