from database.connection import get_conn

TOLERANCIA_PADRAO = 50


def _table_exists(cur, table_name):
    cur.execute(
        """
        select exists (
            select 1
            from information_schema.tables
            where table_schema = 'public' and table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])



def _ultima_leitura_execucao(cur, equipamento_id, tipo_controle):
    if _table_exists(cur, "execucoes_manutencao"):
        coluna = "horas_execucao" if tipo_controle == "horas" else "km_execucao"
        cur.execute(
            f"""
            select coalesce(max({coluna}), 0)
            from execucoes_manutencao
            where equipamento_id = %s
              and tipo = 'revisao'
              and status = 'concluida'
            """,
            (equipamento_id,),
        )
        return float(cur.fetchone()[0] or 0)

    if _table_exists(cur, "historico_revisoes"):
        cur.execute(
            """
            select coalesce(max(leitura_execucao), 0)
            from historico_revisoes
            where equipamento_id = %s
            """,
            (equipamento_id,),
        )
        return float(cur.fetchone()[0] or 0)

    return 0.0



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
            """
            select id, nome_etapa, gatilho_valor
            from etapas_template_revisao
            where template_id = %s and ativo = true
            order by gatilho_valor
            """,
            (template_id,),
        )
        etapas = cur.fetchall()
        if not etapas:
            return []

        ultima = _ultima_leitura_execucao(cur, equipamento_id, tipo_controle)

        resultados = []
        for etapa_id, nome, valor in etapas:
            proxima = ultima + float(valor)
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
                    "tipo_controle": tipo_controle,
                    "ultima_execucao": ultima,
                }
            )

        return resultados
    finally:
        conn.close()
