from collections import defaultdict

from database.connection import get_conn, release_conn
import psycopg2
from services import configuracoes_service


# ── helpers de status ────────────────────────────────────────────────────────

def _status_item_ciclo(leitura_atual, ultima_execucao, intervalo, tolerancia):
    if intervalo <= 0:
        return "EM DIA", max(0.0, leitura_atual), max(0.0, leitura_atual), 0.0

    leitura_atual   = float(leitura_atual   or 0)
    ultima_execucao = float(ultima_execucao or 0)
    intervalo       = float(intervalo       or 0)

    ciclo_atual       = int(leitura_atual   // intervalo) if leitura_atual   > 0 else 0
    ciclo_ultima      = int(ultima_execucao // intervalo) if ultima_execucao > 0 else -1
    inicio_ciclo      = ciclo_atual * intervalo
    proximo_vencimento = (ciclo_atual + 1) * intervalo

    if ultima_execucao > 0 and ciclo_ultima == ciclo_atual:
        return "REALIZADO", inicio_ciclo, proximo_vencimento, max(0.0, proximo_vencimento - leitura_atual)

    falta = proximo_vencimento - leitura_atual
    if leitura_atual >= proximo_vencimento:
        return "VENCIDO", inicio_ciclo, proximo_vencimento, falta
    if falta <= tolerancia:
        return "PROXIMO", inicio_ciclo, proximo_vencimento, falta
    return "EM DIA", inicio_ciclo, proximo_vencimento, falta


# ── batch loading (1 query para todos os equipamentos) ───────────────────────

def _carregar_ultimas_execucoes_batch(cur, equipamento_ids):
    """
    Retorna dict: {equipamento_id: {item_id: ultima_leitura}}
    Em vez de 1 query por item, faz UMA query para todos os equipamentos.
    """
    if not equipamento_ids:
        return {}
    placeholders = ",".join(["%s"] * len(equipamento_ids))
    cur.execute(
        f"""
        select
            el.equipamento_id,
            el.item_id,
            tl.tipo_controle,
            max(case when tl.tipo_controle = 'horas' then el.horas_execucao
                     else el.km_execucao end) as ultima
        from execucoes_lubrificacao el
        join equipamentos e on e.id = el.equipamento_id
        join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
        where el.equipamento_id in ({placeholders})
          and el.item_id is not null
        group by el.equipamento_id, el.item_id, tl.tipo_controle
        """,
        list(equipamento_ids),
    )
    resultado = defaultdict(dict)
    for eqp_id, item_id, _tipo, ultima in cur.fetchall():
        resultado[eqp_id][item_id] = float(ultima or 0)
    return resultado


def calcular_proximas_lubrificacoes_batch(equipamento_ids):
    """
    Calcula lubrificações para VÁRIOS equipamentos de uma só vez.
    Retorna dict {equipamento_id: [lista_de_itens]}.
    Usado pelo dashboard e alertas para evitar N+1.
    """
    if not equipamento_ids:
        return {}

    conn = get_conn()
    cur  = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(equipamento_ids))
        cur.execute(
            f"""
            select
                e.id as equipamento_id,
                e.km_atual,
                e.horas_atual,
                tl.tipo_controle,
                itl.id as item_id,
                itl.nome_item,
                itl.tipo_produto,
                itl.intervalo_valor
            from equipamentos e
            join templates_lubrificacao tl  on tl.id  = e.template_lubrificacao_id
            join itens_template_lubrificacao itl on itl.template_id = tl.id and itl.ativo = true
            where e.id in ({placeholders})
            order by e.id, itl.intervalo_valor
            """,
            list(equipamento_ids),
        )
        rows = cur.fetchall()
        if not rows:
            return {}

        # Busca ultimas execuções de uma vez só
        ultimas = _carregar_ultimas_execucoes_batch(cur, equipamento_ids)

        STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
        resultado = defaultdict(list)
        tolerancia = configuracoes_service.get_tolerancia_padrao()

        for eqp_id, km_atual, horas_atual, tipo_controle, item_id, nome_item, tipo_produto, intervalo in rows:
            leitura_atual = float(horas_atual if tipo_controle == "horas" else km_atual)
            ultima = ultimas.get(eqp_id, {}).get(item_id, 0.0)

            status, ref_ciclo, prox_venc, diff = _status_item_ciclo(leitura_atual, ultima, float(intervalo or 0), tolerancia)

            resultado[eqp_id].append({
                "item_id":          item_id,
                "item":             nome_item,
                "tipo_produto":     tipo_produto or "-",
                "referencia_ciclo": ref_ciclo,
                "vencimento":       prox_venc,
                "atual":            leitura_atual,
                "ultima_execucao":  ultima,
                "status":           status,
                "diferenca":        diff,
                "tipo_controle":    tipo_controle,
                "intervalo":        float(intervalo),
            })

        # Ordena por status e diferença dentro de cada equipamento
        for eqp_id in resultado:
            resultado[eqp_id].sort(
                key=lambda x: (STATUS_ORDEM.get(x["status"], 99), x["diferenca"], x["item"])
            )

        return dict(resultado)

    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        conn.rollback()
        return {}
    finally:
        release_conn(conn)


def calcular_proximas_lubrificacoes(equipamento_id):
    """Mantém interface original para compatibilidade (painel 360° do equipamento)."""
    resultado = calcular_proximas_lubrificacoes_batch([equipamento_id])
    return resultado.get(equipamento_id, [])


# ── escrita ──────────────────────────────────────────────────────────────────

def registrar_execucao(dados):
    from services import auditoria_service, validacoes_service

    contexto = validacoes_service.validar_execucao_lubrificacao(
        equipamento_id=dados["equipamento_id"],
        item_id=dados.get("item_id"),
        data_execucao=dados["data_execucao"],
        km_execucao=dados.get("km_execucao", 0),
        horas_execucao=dados.get("horas_execucao", 0),
    )

    conn = get_conn()
    cur  = conn.cursor()
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
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_execucao_lubrificacao",
            entidade="execucoes_lubrificacao",
            entidade_id=execucao_id,
            valor_antigo={
                "km_atual": contexto.get("km_atual"),
                "horas_atual": contexto.get("horas_atual"),
            },
            valor_novo=dados,
        )
        conn.commit()
        return execucao_id
    finally:
        release_conn(conn)


# ── leitura ──────────────────────────────────────────────────────────────────

def listar_por_equipamento(equipamento_id):
    conn = get_conn()
    cur  = conn.cursor()
    try:
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
        rows = cur.fetchall()
        return [
            {
                "id":          r[0],
                "data":        r[1],
                "item":        r[2],
                "produto":     r[3] or "-",
                "km":          float(r[4] or 0),
                "horas":       float(r[5] or 0),
                "responsavel": r[6],
                "observacoes": r[7] or "",
            }
            for r in rows
        ]
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)


def listar_todos():
    conn = get_conn()
    cur  = conn.cursor()
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
            left join setores s   on s.id  = eq.setor_id
            left join responsaveis r on r.id = el.responsavel_id
            order by el.data_execucao desc, el.id desc
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id":          r[0],
                "data":        r[1],
                "equipamento": r[2],
                "setor":       r[3],
                "item":        r[4],
                "produto":     r[5] or "-",
                "km":          float(r[6] or 0),
                "horas":       float(r[7] or 0),
                "responsavel": r[8],
                "observacoes": r[9] or "",
            }
            for r in rows
        ]
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        conn.rollback()
        return []
    finally:
        release_conn(conn)
