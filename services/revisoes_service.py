from database.connection import get_conn

TOLERANCIA_PADRAO = 50

def calcular_proximas_revisoes(equipamento_id: str):
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
        tipo_controle = cur.fetchone()[0]

        leitura_atual = horas_atual if tipo_controle == "horas" else km_atual

        cur.execute(
            "select id, nome_etapa, gatilho_valor from etapas_template_revisao where template_id = %s order by gatilho_valor",
            (template_id,),
        )
        etapas = cur.fetchall()

        cur.execute(
            "select coalesce(max(leitura_execucao), 0) from historico_revisoes where equipamento_id = %s",
            (equipamento_id,),
        )
        ultima = cur.fetchone()[0]

        resultados = []

        for etapa_id, nome, valor in etapas:
            proxima = float(ultima) + float(valor)

            if proxima >= float(leitura_atual):
                diff = proxima - float(leitura_atual)

                if leitura_atual >= proxima:
                    status = "VENCIDO"
                elif diff <= TOLERANCIA_PADRAO:
                    status = "PROXIMO"
                else:
                    status = "EM DIA"

                resultados.append({
                    "etapa": nome,
                    "vencimento": proxima,
                    "atual": leitura_atual,
                    "status": status,
                    "diferenca": diff,
                })

        return resultados

    finally:
        conn.close()
