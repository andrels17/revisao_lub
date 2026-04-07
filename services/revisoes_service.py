from collections import defaultdict

from psycopg2 import errors

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
    except (errors.UndefinedTable, errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        conn.close()


def indexar_por_equipamento(dados=None):
    dados = dados if dados is not None else listar_controle_revisoes()
    agrupado = defaultdict(list)
    for item in dados:
        agrupado[item["equipamento_id"]].append(_compatibilizar(item))

    for equipamento_id in agrupado:
        agrupado[equipamento_id].sort(
            key=lambda x: (STATUS_ORDEM.get(x.get("status"), 99), x.get("diferenca", 0), x.get("etapa", ""))
        )
    return dict(agrupado)


def listar_controle_revisoes_por_equipamento():
    return indexar_por_equipamento()


def calcular_proximas_revisoes(equipamento_id, dados_indexados=None, indice=None):
    base = dados_indexados if dados_indexados is not None else indice
    if base is None:
        base = listar_controle_revisoes_por_equipamento()
    return list(base.get(equipamento_id, []))
