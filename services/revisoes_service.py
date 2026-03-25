from database.connection import get_conn

TOLERANCIA_PADRAO = 50

def calcular_proximas_revisoes(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select horas_atual, km_atual, template_revisao_id from equipamentos where id = %s",
            (equipamento_id,),
        )
        row = cur.fetchone()
        if not row:
            return []

        horas_atual, km_atual, template_id = row
        if not template_id:
            return []

        cur.execute(
            "select tipo_controle from templates_revisao where id = %s",
            (template_id,),
        )
        tipo_row = cur.fetchone()
        if not tipo_row:
            return []

        tipo_controle = tipo_row[0]
        leitura_atual = float(horas_atual if tipo_controle == "horas" else km_atual)

        cur.execute(
            "select id, nome_etapa, gatilho_valor from etapas_template_revisao where template_id = %s and ativo = true order by gatilho_valor",
            (template_id,),
        )
        etapas = cur.fetchall()
        if not etapas:
            return []

        cur.execute(
            "select coalesce(max(leitura_execucao), 0) from historico_revisoes where equipamento_id = %s",
            (equipamento_id,),
        )
        ultima = float(cur.fetchone()[0] or 0)

        resultados = []
        for etapa_id, nome, valor in etapas:
            proxima = ultima + float(valor)
            if proxima >= leitura_atual:
                diff = proxima - leitura_atual
                if leitura_atual >= proxima:
                    status = "VENCIDO"
                elif diff <= TOLERANCIA_PADRAO:
                    status = "PROXIMO"
                else:
                    status = "EM DIA"

                resultados.append(
                    {
                        "etapa_id": etapa_id,
                        "etapa": nome,
                        "vencimento": proxima,
                        "atual": leitura_atual,
                        "status": status,
                        "diferenca": diff,
                    }
                )

        return resultados
    finally:
        conn.close()
