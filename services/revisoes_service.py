import math
import re
from collections import defaultdict

from database.connection import get_conn
from ui.constants import TOLERANCIA_PADRAO

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


STATUS_ORDEM = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2, "REALIZADO": 3}
ETAPA_REGEX = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _extrair_etapa(observacoes):
    if not observacoes:
        return None
    m = ETAPA_REGEX.search(observacoes)
    return m.group(1).strip() if m else None


def _normalizar_numero(valor):
    return float(valor or 0)


def _status_por_diferenca(diff):
    if diff <= 0:
        return "VENCIDO"
    if diff <= TOLERANCIA_PADRAO:
        return "PROXIMO"
    return "EM DIA"


def _valor_leitura_execucao(tipo_controle, km_execucao, horas_execucao):
    return _normalizar_numero(horas_execucao if tipo_controle == "horas" else km_execucao)


def _carregar_base_revisoes(cur):
    cur.execute(
        """
        select
            e.id as equipamento_id,
            e.codigo,
            e.nome as equipamento_nome,
            e.tipo as equipamento_tipo,
            e.setor_id,
            coalesce(s.nome, '-') as setor_nome,
            tr.id as template_id,
            tr.nome as template_nome,
            tr.tipo_controle,
            e.km_atual,
            e.horas_atual,
            et.id as etapa_id,
            et.nome_etapa,
            et.gatilho_valor
        from equipamentos e
        left join setores s on s.id = e.setor_id
        left join templates_revisao tr on tr.id = e.template_revisao_id
        left join etapas_template_revisao et
               on et.template_id = tr.id and et.ativo = true
        where e.template_revisao_id is not null
        order by e.codigo, et.gatilho_valor, et.nome_etapa
        """
    )
    return cur.fetchall()


def _carregar_execucoes_revisao(cur):
    try:
        cur.execute(
            """
            select
                equipamento_id,
                data_execucao,
                km_execucao,
                horas_execucao,
                observacoes,
                coalesce(status, 'concluida') as status
            from execucoes_manutencao
            where tipo = 'revisao'
            order by data_execucao desc, created_at desc
            """
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
        cur.connection.rollback()
        if isinstance(exc, psycopg2.errors.UndefinedColumn):
            cur.execute(
                """
                select
                    equipamento_id,
                    data_execucao,
                    km_execucao,
                    horas_execucao,
                    observacoes,
                    coalesce(status, 'concluida') as status
                from execucoes_manutencao
                where tipo = 'revisao'
                order by data_execucao desc, id desc
                """
            )
        else:
            return []
    return cur.fetchall()


def _agrupar_execucoes_por_etapa(exec_rows, tipo_por_equipamento):
    agrupado = defaultdict(lambda: defaultdict(list))
    for equipamento_id, _data, km_execucao, horas_execucao, observacoes, status in exec_rows:
        if status != "concluida":
            continue
        etapa = _extrair_etapa(observacoes)
        if not etapa:
            continue
        tipo_controle = tipo_por_equipamento.get(equipamento_id) or "km"
        leitura = _valor_leitura_execucao(tipo_controle, km_execucao, horas_execucao)
        agrupado[equipamento_id][etapa].append(leitura)
    for etapas in agrupado.values():
        for leitura_list in etapas.values():
            leitura_list.sort()
    return agrupado


def _montar_item_controle(base, execucoes_por_etapa, modo="dashboard"):
    tipo_controle = (base["tipo_controle"] or "km").lower()
    leitura_atual = _normalizar_numero(base["horas_atual"] if tipo_controle == "horas" else base["km_atual"])
    gatilho = _normalizar_numero(base["gatilho_valor"])
    ciclo = max(_normalizar_numero(base["ciclo_maximo"]), gatilho, 1.0)

    # Mantém o equipamento na janela correta mesmo em limites exatos do ciclo.
    leitura_ref = leitura_atual - 1e-9 if leitura_atual > 0 else leitura_atual
    inicio_ciclo = math.floor(leitura_ref / ciclo) * ciclo
    vencimento_ciclo = inicio_ciclo + gatilho

    leituras_etapa = execucoes_por_etapa.get(base["etapa"], [])
    execucoes_no_ciclo = [v for v in leituras_etapa if inicio_ciclo < v <= inicio_ciclo + ciclo]
    ultima_execucao = max(execucoes_no_ciclo) if execucoes_no_ciclo else 0.0
    realizado_no_ciclo = bool(execucoes_no_ciclo)

    if modo == "painel":
        if realizado_no_ciclo:
            status = "REALIZADO"
            diferenca = 0.0
            proximo_vencimento = inicio_ciclo + ciclo + gatilho
        else:
            diferenca = vencimento_ciclo - leitura_atual
            status = _status_por_diferenca(diferenca)
            proximo_vencimento = vencimento_ciclo
    else:
        proximo_vencimento = inicio_ciclo + ciclo + gatilho if realizado_no_ciclo else vencimento_ciclo
        diferenca = proximo_vencimento - leitura_atual
        status = _status_por_diferenca(diferenca)

    item = {
        "equipamento_id": base["equipamento_id"],
        "codigo": base["codigo"],
        "equipamento_nome": base["equipamento_nome"],
        "equipamento_tipo": base["equipamento_tipo"],
        "setor_id": base["setor_id"],
        "setor_nome": base["setor_nome"],
        "template_id": base["template_id"],
        "template_nome": base["template_nome"],
        "etapa_id": base["etapa_id"],
        "etapa": base["etapa"],
        "tipo_controle": tipo_controle,
        "gatilho_valor": gatilho,
        "km_atual": _normalizar_numero(base["km_atual"]),
        "horas_atual": _normalizar_numero(base["horas_atual"]),
        "leitura_atual": leitura_atual,
        "ultima_execucao": ultima_execucao,
        "vencimento": proximo_vencimento,
        "vencimento_ciclo": vencimento_ciclo,
        "proximo_vencimento": proximo_vencimento,
        "falta": diferenca,
        "status": status,
        "realizado_no_ciclo": realizado_no_ciclo,
        "ciclo_atual_inicio": inicio_ciclo,
        "ciclo_atual_fim": inicio_ciclo + ciclo,
    }
    return _compatibilizar(item)


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


def _construir_controles(modo="dashboard"):
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            base_rows = _carregar_base_revisoes(cur)
        except Exception as exc:
            if psycopg2 and isinstance(
                exc,
                (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn, psycopg2.errors.UndefinedObject),
            ):
                conn.rollback()
                return []
            raise

        if not base_rows:
            return []

        bases = []
        tipo_por_equipamento = {}
        ciclo_por_template = defaultdict(float)
        for row in base_rows:
            if not row[11]:
                continue
            base = {
                "equipamento_id": row[0],
                "codigo": row[1],
                "equipamento_nome": row[2],
                "equipamento_tipo": row[3],
                "setor_id": row[4],
                "setor_nome": row[5],
                "template_id": row[6],
                "template_nome": row[7],
                "tipo_controle": row[8],
                "km_atual": row[9],
                "horas_atual": row[10],
                "etapa_id": row[11],
                "etapa": row[12],
                "gatilho_valor": row[13],
            }
            bases.append(base)
            tipo_por_equipamento[base["equipamento_id"]] = (base["tipo_controle"] or "km").lower()
            ciclo_por_template[base["template_id"]] = max(ciclo_por_template[base["template_id"]], _normalizar_numero(base["gatilho_valor"]))

        exec_rows = _carregar_execucoes_revisao(cur)
        execucoes = _agrupar_execucoes_por_etapa(exec_rows, tipo_por_equipamento)

        itens = []
        for base in bases:
            base["ciclo_maximo"] = ciclo_por_template.get(base["template_id"], base["gatilho_valor"])
            itens.append(_montar_item_controle(base, execucoes.get(base["equipamento_id"], {}), modo=modo))

        itens.sort(key=lambda x: (STATUS_ORDEM.get(x["status"], 99), x["diferenca"], x["codigo"], x["etapa"]))
        return itens
    finally:
        conn.close()


def listar_controle_revisoes():
    return _construir_controles(modo="dashboard")


def listar_controle_revisoes_por_equipamento():
    agrupado = defaultdict(list)
    for item in listar_controle_revisoes():
        agrupado[item["equipamento_id"]].append(item)
    return dict(agrupado)


def listar_controle_revisoes_painel(equipamento_id=None):
    itens = _construir_controles(modo="painel")
    if equipamento_id is None:
        return itens
    return [item for item in itens if item["equipamento_id"] == equipamento_id]


def calcular_proximas_revisoes(equipamento_id, dados_indexados=None):
    if dados_indexados is None:
        return listar_controle_revisoes_painel(equipamento_id)
    return list(dados_indexados.get(equipamento_id, []))
