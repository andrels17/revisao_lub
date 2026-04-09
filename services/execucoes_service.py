import re
from database.connection import get_conn
from services import auditoria_service, validacoes_service

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


ETAPA_REGEX = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _extrair_etapa(observacoes):
    if not observacoes:
        return None
    m = ETAPA_REGEX.search(observacoes)
    return m.group(1).strip() if m else None


def _formatar_resultado_execucao(km_execucao, horas_execucao):
    if km_execucao is not None:
        return f"Realizado com {float(km_execucao):.0f} km"
    if horas_execucao is not None:
        return f"Realizado com {float(horas_execucao):.0f} h"
    return "Realizado"



def criar_execucao(dados):
    km_execucao = dados.get("km_execucao")
    horas_execucao = dados.get("horas_execucao")

    if dados["tipo"] == "revisao":
        contexto = validacoes_service.validar_execucao_revisao(
            equipamento_id=dados["equipamento_id"],
            data_execucao=dados["data_execucao"],
            km_execucao=km_execucao,
            horas_execucao=horas_execucao,
            observacoes=dados.get("observacoes"),
            status=dados.get("status", "concluida"),
        )
    else:
        contexto = validacoes_service.obter_equipamento_contexto(dados["equipamento_id"])

    conn = get_conn()
    cur = conn.cursor()
    try:
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

        auditoria_service.registrar_no_conn(
            conn,
            acao=f"criar_execucao_{dados['tipo']}",
            entidade="execucoes_manutencao",
            entidade_id=execucao_id,
            valor_antigo={
                "km_atual": contexto.get("km_atual") if contexto else None,
                "horas_atual": contexto.get("horas_atual") if contexto else None,
            },
            valor_novo=dados,
        )

        conn.commit()
        return execucao_id
    finally:
        conn.close()



def listar_revisoes_por_equipamento(equipamento_id, limite=20):
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                select em.id,
                       em.data_execucao,
                       em.km_execucao,
                       em.horas_execucao,
                       coalesce(r.nome, '-') as responsavel,
                       coalesce(em.status, 'concluida') as status,
                       em.observacoes
                from execucoes_manutencao em
                left join responsaveis r on r.id = em.responsavel_id
                where em.equipamento_id = %s
                  and em.tipo = 'revisao'
                order by em.data_execucao desc, em.created_at desc
                limit %s
                """,
                (equipamento_id, limite),
            )
        except Exception as exc:
            if not psycopg2 or not isinstance(
                exc,
                (
                    psycopg2.errors.UndefinedColumn,
                    psycopg2.errors.UndefinedTable,
                    psycopg2.errors.UndefinedObject,
                ),
            ):
                raise
            conn.rollback()
            if isinstance(exc, psycopg2.errors.UndefinedColumn):
                cur.execute(
                    """
                    select em.id,
                           em.data_execucao,
                           em.km_execucao,
                           em.horas_execucao,
                           coalesce(r.nome, '-') as responsavel,
                           coalesce(em.status, 'concluida') as status,
                           em.observacoes
                    from execucoes_manutencao em
                    left join responsaveis r on r.id = em.responsavel_id
                    where em.equipamento_id = %s
                      and em.tipo = 'revisao'
                    order by em.data_execucao desc, em.id desc
                    limit %s
                    """,
                    (equipamento_id, limite),
                )
            else:
                return []

        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "km": float(r[2] or 0),
                "horas": float(r[3] or 0),
                "responsavel": r[4],
                "status": r[5],
                "observacoes": r[6] or "",
                "resultado": _formatar_resultado_execucao(r[2], r[3]),
                "etapa_referencia": _extrair_etapa(r[6]),
            }
            for r in rows
        ]
    finally:
        conn.close()



def resumo_revisoes_por_equipamento(equipamento_id):
    historico = listar_revisoes_por_equipamento(equipamento_id, limite=200)
    if not historico:
        return {
            "total": 0,
            "concluidas": 0,
            "pendentes": 0,
            "ultima_data": None,
        }

    return {
        "total": len(historico),
        "concluidas": sum(1 for item in historico if item.get("status") == "concluida"),
        "pendentes": sum(1 for item in historico if item.get("status") == "pendente"),
        "ultima_data": historico[0].get("data"),
    }
