from collections import defaultdict

from database.connection import get_conn


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}


def _map_row(r):
    return {
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


def _compatibilizar(item):
    return {
        **item,
        # compatibilidade com código antigo
        "nome_etapa": item["etapa"],
        "tipo": item["tipo_controle"],
        "gatilho": item["gatilho_valor"],
        "atual": item["leitura_atual"],
        "ultima_leitura_execucao": item["ultima_execucao"],
        "diferenca": item["falta"],
    }


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
        return [_map_row(r) for r in cur.fetchall()]
    finally:
        conn.close()


def listar_controle_revisoes_por_equipamento():
    agrupado = defaultdict(list)
    for item in listar_controle_revisoes():
        agrupado[item["equipamento_id"]].append(_compatibilizar(item))

    for equipamento_id in agrupado:
        agrupado[equipamento_id].sort(
            key=lambda x: (STATUS_ORDEM.get(x["status"], 99), x["diferenca"], x["etapa"])
        )
    return dict(agrupado)


def calcular_proximas_revisoes(equipamento_id, dados_indexados=None):
    if dados_indexados is None:
        dados_indexados = listar_controle_revisoes_por_equipamento()
    return list(dados_indexados.get(equipamento_id, []))
