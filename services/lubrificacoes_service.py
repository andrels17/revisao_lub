from database.connection import get_conn
import psycopg2

TOLERANCIA_PADRAO = 10


def _status_item_ciclo(leitura_atual, ultima_execucao, intervalo):
    """
    Define o status operacional do item dentro do ciclo atual.

    - REALIZADO: já houve execução no ciclo corrente
    - VENCIDO/PROXIMO/EM DIA: ainda não houve execução neste ciclo
    """
    if intervalo <= 0:
        return "EM DIA", max(0.0, leitura_atual), max(0.0, leitura_atual), 0.0

    leitura_atual = float(leitura_atual or 0)
    ultima_execucao = float(ultima_execucao or 0)
    intervalo = float(intervalo or 0)

    ciclo_atual = int(leitura_atual // intervalo) if leitura_atual > 0 else 0
    ciclo_ultima = int(ultima_execucao // intervalo) if ultima_execucao > 0 else -1
    inicio_ciclo_atual = ciclo_atual * intervalo
    proximo_vencimento = (ciclo_atual + 1) * intervalo

    # Considera realizado quando a execução já aconteceu dentro do mesmo ciclo de leitura atual.
    if ultima_execucao > 0 and ciclo_ultima == ciclo_atual:
        return "REALIZADO", inicio_ciclo_atual, proximo_vencimento, max(0.0, proximo_vencimento - leitura_atual)

    falta = proximo_vencimento - leitura_atual
    if leitura_atual >= proximo_vencimento:
        return "VENCIDO", inicio_ciclo_atual, proximo_vencimento, falta
    if falta <= TOLERANCIA_PADRAO:
        return "PROXIMO", inicio_ciclo_atual, proximo_vencimento, falta
    return "EM DIA", inicio_ciclo_atual, proximo_vencimento, falta


def _ultima_execucao_item(cur, equipamento_id, item_id, tipo_controle):
    coluna = "horas_execucao" if tipo_controle == "horas" else "km_execucao"
    cur.execute(
        f"""
        select coalesce(max({coluna}), 0)
        from execucoes_lubrificacao
        where equipamento_id = %s and item_id = %s
        """,
        (equipamento_id, item_id),
    )
    return float(cur.fetchone()[0] or 0)


def calcular_proximas_lubrificacoes(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select horas_atual, km_atual, template_lubrificacao_id from equipamentos where id = %s",
            (equipamento_id,),
        )
        row = cur.fetchone()
        if not row:
            return []

        horas_atual, km_atual, template_id = row
        if not template_id:
            return []

        cur.execute(
            "select tipo_controle from templates_lubrificacao where id = %s",
            (template_id,),
        )
        tipo_row = cur.fetchone()
        if not tipo_row:
            return []

        tipo_controle = tipo_row[0]
        leitura_atual = float(horas_atual if tipo_controle == "horas" else km_atual)

        cur.execute(
            """
            select id, nome_item, tipo_produto, intervalo_valor
            from itens_template_lubrificacao
            where template_id = %s and ativo = true
            order by intervalo_valor
            """,
            (template_id,),
        )
        itens = cur.fetchall()
        if not itens:
            return []

        resultados = []
        STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}

        for item_id, nome_item, tipo_produto, intervalo in itens:
            ultima = _ultima_execucao_item(cur, equipamento_id, item_id, tipo_controle)
            status, referencia_ciclo, proximo_vencimento, diff = _status_item_ciclo(
                leitura_atual=leitura_atual,
                ultima_execucao=ultima,
                intervalo=float(intervalo or 0),
            )

            resultados.append(
                {
                    "item_id": item_id,
                    "item": nome_item,
                    "tipo_produto": tipo_produto or "-",
                    "referencia_ciclo": referencia_ciclo,
                    "vencimento": proximo_vencimento,
                    "atual": leitura_atual,
                    "ultima_execucao": ultima,
                    "status": status,
                    "diferenca": diff,
                    "tipo_controle": tipo_controle,
                    "intervalo": float(intervalo),
                }
            )

        resultados.sort(key=lambda x: (STATUS_ORDEM.get(x["status"], 99), x["diferenca"], x["item"]))
        return resultados
    finally:
        conn.close()


def registrar_execucao(dados):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into execucoes_lubrificacao
                (equipamento_id, item_id, responsavel_id, nome_item, tipo_produto,
                 data_execucao, km_execucao, horas_execucao, observacoes)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                dados["equipamento_id"],
                dados.get("item_id"),
                dados.get("responsavel_id"),
                dados.get("nome_item"),
                dados.get("tipo_produto"),
                dados["data_execucao"],
                dados.get("km_execucao", 0),
                dados.get("horas_execucao", 0),
                dados.get("observacoes"),
            ),
        )
        execucao_id = cur.fetchone()[0]

        cur.execute(
            """
            update equipamentos
               set km_atual    = greatest(km_atual,    %s),
                   horas_atual = greatest(horas_atual, %s)
             where id = %s
            """,
            (dados.get("km_execucao", 0), dados.get("horas_execucao", 0), dados["equipamento_id"]),
        )
        conn.commit()
        return execucao_id
    finally:
        conn.close()


def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                select el.id, el.data_execucao, el.nome_item, el.tipo_produto,
                       el.km_execucao, el.horas_execucao,
                       coalesce(r.nome, '-') as responsavel, el.observacoes
                from execucoes_lubrificacao el
                left join responsaveis r on r.id = el.responsavel_id
                where el.equipamento_id = %s
                order by el.data_execucao desc, el.created_at desc
                """,
                (equipamento_id,),
            )
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            cur.execute(
                """
                select el.id, el.data_execucao, el.nome_item, el.tipo_produto,
                       el.km_execucao, el.horas_execucao,
                       coalesce(r.nome, '-') as responsavel, el.observacoes
                from execucoes_lubrificacao el
                left join responsaveis r on r.id = el.responsavel_id
                where el.equipamento_id = %s
                order by el.data_execucao desc, el.id desc
                """,
                (equipamento_id,),
            )
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedObject):
            conn.rollback()
            return []

        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "item": r[2],
                "produto": r[3] or "-",
                "km": float(r[4] or 0),
                "horas": float(r[5] or 0),
                "responsavel": r[6],
                "observacoes": r[7] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()


def listar_todos():
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                select el.id, el.data_execucao,
                       eq.codigo || ' - ' || eq.nome as equipamento,
                       coalesce(s.nome, '-') as setor,
                       el.nome_item, el.tipo_produto,
                       el.km_execucao, el.horas_execucao,
                       coalesce(r.nome, '-') as responsavel,
                       el.observacoes
                from execucoes_lubrificacao el
                join equipamentos eq on eq.id = el.equipamento_id
                left join setores s on s.id = eq.setor_id
                left join responsaveis r on r.id = el.responsavel_id
                order by el.data_execucao desc, el.created_at desc
                """
            )
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            cur.execute(
                """
                select el.id, el.data_execucao,
                       eq.codigo || ' - ' || eq.nome as equipamento,
                       coalesce(s.nome, '-') as setor,
                       el.nome_item, el.tipo_produto,
                       el.km_execucao, el.horas_execucao,
                       coalesce(r.nome, '-') as responsavel,
                       el.observacoes
                from execucoes_lubrificacao el
                join equipamentos eq on eq.id = el.equipamento_id
                left join setores s on s.id = eq.setor_id
                left join responsaveis r on r.id = el.responsavel_id
                order by el.data_execucao desc, el.id desc
                """
            )
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedObject):
            conn.rollback()
            return []

        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data": r[1],
                "equipamento": r[2],
                "setor": r[3],
                "item": r[4],
                "produto": r[5] or "-",
                "km": float(r[6] or 0),
                "horas": float(r[7] or 0),
                "responsavel": r[8],
                "observacoes": r[9] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()
