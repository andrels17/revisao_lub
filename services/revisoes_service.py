from database.connection import get_conn


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


def calcular_proximas_revisoes(equipamento_id):
    dados = listar_controle_revisoes()
    filtrados = [item for item in dados if item["equipamento_id"] == equipamento_id]

    resultado = []
    for item in filtrados:
        resultado.append(
            {
                # formato novo
                "equipamento_id": item["equipamento_id"],
                "codigo": item["codigo"],
                "equipamento_nome": item["equipamento_nome"],
                "equipamento_tipo": item["equipamento_tipo"],
                "setor_id": item["setor_id"],
                "setor_nome": item["setor_nome"],
                "template_id": item["template_id"],
                "template_nome": item["template_nome"],
                "etapa_id": item["etapa_id"],
                "etapa": item["etapa"],
                "tipo_controle": item["tipo_controle"],
                "gatilho_valor": item["gatilho_valor"],
                "km_atual": item["km_atual"],
                "horas_atual": item["horas_atual"],
                "leitura_atual": item["leitura_atual"],
                "ultima_execucao": item["ultima_execucao"],
                "vencimento": item["vencimento"],
                "falta": item["falta"],
                "status": item["status"],

                # compatibilidade com código antigo
                "nome_etapa": item["etapa"],
                "tipo": item["tipo_controle"],
                "gatilho": item["gatilho_valor"],
                "atual": item["leitura_atual"],
                "ultima_leitura_execucao": item["ultima_execucao"],
            }
        )

    return resultado
