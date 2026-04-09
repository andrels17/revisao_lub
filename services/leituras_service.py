from psycopg2 import errors

from database.connection import get_conn
from services import auditoria_service, ciclos_service, validacoes_service


def registrar(equipamento_id, tipo_leitura, km_valor=None, horas_valor=None,
               data_leitura=None, responsavel_id=None, observacoes=None,
               permitir_regressao=False):
    contexto = validacoes_service.validar_leitura(
        equipamento_id=equipamento_id,
        tipo_leitura=tipo_leitura,
        km_valor=km_valor,
        horas_valor=horas_valor,
        permitir_regressao=permitir_regressao,
    )

    conn = get_conn()
    cur = conn.cursor()
    try:
        valor_antigo = {
            "km_atual": contexto.get("km_atual"),
            "horas_atual": contexto.get("horas_atual"),
        }
        ciclo_id = None
        if ciclos_service.tabela_tem_ciclo_id("leituras"):
            ciclo_id = ciclos_service.obter_ciclo_id_para_registro("geral")

        if ciclo_id:
            cur.execute(
                """
                insert into leituras
                    (equipamento_id, tipo_leitura, km_valor, horas_valor,
                     data_leitura, responsavel_id, observacoes, ciclo_id)
                values (%s, %s, %s, %s, %s, %s, %s, %s::uuid)
                returning id
                """,
                (equipamento_id, tipo_leitura, km_valor, horas_valor,
                 data_leitura, responsavel_id, observacoes, ciclo_id),
            )
        else:
            cur.execute(
                """
                insert into leituras
                    (equipamento_id, tipo_leitura, km_valor, horas_valor,
                     data_leitura, responsavel_id, observacoes)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (equipamento_id, tipo_leitura, km_valor, horas_valor,
                 data_leitura, responsavel_id, observacoes),
            )
        leitura_id = cur.fetchone()[0]

        if tipo_leitura in ("km", "ambos") and km_valor is not None:
            cur.execute(
                "update equipamentos set km_atual = greatest(coalesce(km_atual, 0), %s) where id = %s",
                (km_valor, equipamento_id),
            )
        if tipo_leitura in ("horas", "ambos") and horas_valor is not None:
            cur.execute(
                "update equipamentos set horas_atual = greatest(coalesce(horas_atual, 0), %s) where id = %s",
                (horas_valor, equipamento_id),
            )

        auditoria_service.registrar_no_conn(
            conn,
            acao="registrar_leitura",
            entidade="leituras",
            entidade_id=leitura_id,
            valor_antigo=valor_antigo,
            valor_novo={
                "equipamento_id": equipamento_id,
                "tipo_leitura": tipo_leitura,
                "km_valor": km_valor,
                "horas_valor": horas_valor,
                "data_leitura": str(data_leitura) if data_leitura else None,
                "responsavel_id": responsavel_id,
                "observacoes": observacoes,
            },
        )

        conn.commit()
        return leitura_id
    finally:
        conn.close()


def listar_por_equipamento(equipamento_id, limite=20):
    conn = get_conn()
    cur = conn.cursor()
    try:
        consultas = [
            """
            select l.id, l.data_leitura, l.tipo_leitura,
                   l.km_valor, l.horas_valor,
                   coalesce(r.nome, '-') as responsavel,
                   l.observacoes
            from leituras l
            left join responsaveis r on r.id = l.responsavel_id
            where l.equipamento_id = %s
            order by l.data_leitura desc, l.created_at desc
            limit %s
            """,
            """
            select l.id, l.data_leitura, l.tipo_leitura,
                   l.km_valor, l.horas_valor,
                   coalesce(r.nome, '-') as responsavel,
                   l.observacoes
            from leituras l
            left join responsaveis r on r.id = l.responsavel_id
            where l.equipamento_id = %s
            order by l.data_leitura desc, l.id desc
            limit %s
            """,
        ]

        rows = None
        for sql in consultas:
            try:
                cur.execute(sql, (equipamento_id, limite))
                rows = cur.fetchall()
                break
            except errors.UndefinedColumn:
                conn.rollback()
                continue
            except errors.UndefinedTable:
                conn.rollback()
                return []

        if rows is None:
            return []

        return [
            {
                "id": r[0],
                "data_leitura": r[1],
                "tipo_leitura": r[2],
                "km_valor": float(r[3] or 0),
                "horas_valor": float(r[4] or 0),
                "responsavel": r[5],
                "observacoes": r[6] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()
