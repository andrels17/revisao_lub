from database.connection import get_conn
from datetime import date


def listar_controle_revisoes():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                equipamento_id,
                codigo,
                equipamento_nome,
                equipamento_tipo,
                setor_id,
                setor_nome,
                template_id,
                template_nome,
                etapa_id,
                etapa,
                tipo_controle,
                gatilho_valor,
                km_atual,
                horas_atual,
                leitura_atual,
                ultima_execucao,
                vencimento,
                falta,
                status
            from public.vw_controle_revisoes
            order by
                case status
                    when 'VENCIDO' then 0
                    when 'PROXIMO' then 1
                    else 2
                end,
                falta,
                codigo,
                etapa
            """
        )
        rows = cur.fetchall()

        return [
            {
                "equipamento_id": r[0],
                "codigo": r[1],
                "equipamento_nome": r[2],
                "equipamento_tipo": r[3],
                "setor_id": r[4],
                "setor_nome": r[5],
                "template_id": r[6],
                "template_nome": r[7],
                "etapa_id": r[8],
                "etapa": r[9],
                "tipo_controle": r[10],
                "gatilho_valor": float(r[11] or 0),
                "km_atual": float(r[12] or 0),
                "horas_atual": float(r[13] or 0),
                "leitura_atual": float(r[14] or 0),
                "ultima_execucao": float(r[15] or 0),
                "vencimento": float(r[16] or 0),
                "falta": float(r[17] or 0),
                "status": r[18],
            }
            for r in rows
        ]
    finally:
        conn.close()


def registrar_execucao_revisao(
    equipamento_id,
    responsavel_id,
    tipo_controle,
    leitura_execucao,
    observacao=None,
):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if tipo_controle == "km":
            km_execucao = leitura_execucao
            horas_execucao = None
        else:
            km_execucao = None
            horas_execucao = leitura_execucao

        cur.execute(
            """
            insert into public.execucoes_manutencao (
                equipamento_id,
                responsavel_id,
                tipo,
                data_execucao,
                km_execucao,
                horas_execucao,
                status,
                observacao
            )
            values (%s, %s, 'revisao', %s, %s, %s, 'concluida', %s)
            """,
            (
                equipamento_id,
                responsavel_id,
                date.today(),
                km_execucao,
                horas_execucao,
                observacao,
            ),
        )

        if tipo_controle == "km":
            cur.execute(
                """
                update public.equipamentos
                set km_atual = %s
                where id = %s
                """,
                (leitura_execucao, equipamento_id),
            )
        else:
            cur.execute(
                """
                update public.equipamentos
                set horas_atual = %s
                where id = %s
                """,
                (leitura_execucao, equipamento_id),
            )

        conn.commit()

    finally:
        conn.close()
