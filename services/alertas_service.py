import datetime
import urllib.parse

from database.connection import get_conn


# ── formatação de telefone / link ─────────────────────────────────────────────

def _limpar_telefone(telefone: str) -> str:
    if not telefone:
        return ""
    numeros = "".join(c for c in telefone if c.isdigit())
    if not numeros.startswith("55"):
        numeros = "55" + numeros
    return numeros


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    numero = _limpar_telefone(telefone)
    texto  = urllib.parse.quote(mensagem)
    return f"https://wa.me/{numero}?text={texto}"


# ── montagem de mensagens ─────────────────────────────────────────────────────

def _data_estimada(falta: float, unidade: str) -> str:
    """
    Gera texto de data estimada baseado na falta (km ou horas) e
    numa média diária fictícia — útil para dar contexto de urgência.
    Como não temos média real armazenada, retorna apenas a falta formatada.
    """
    if falta <= 0:
        return "imediatamente (já vencido)"
    return f"em aproximadamente {falta:.0f} {unidade}"


def montar_mensagem_revisao(equipamento: dict, etapa: dict, responsavel_nome: str) -> str:
    tipo    = etapa.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta   = float(etapa.get("diferenca", etapa.get("falta", 0)))
    status  = etapa.get("status", "-")

    linhas_status = ""
    if status == "VENCIDO":
        linhas_status = f"⚠️ *VENCIDO* há {abs(falta):.0f} {unidade} — ação imediata necessária!\n"
    elif status == "PROXIMO":
        linhas_status = f"⏰ Próximo do vencimento — faltam {falta:.0f} {unidade}\n"

    return (
        f"🔧 *ALERTA DE REVISÃO*\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Etapa: {etapa.get('etapa', etapa.get('nome_etapa', '-'))}\n\n"
        f"Leitura atual: {float(etapa.get('atual', etapa.get('leitura_atual', 0))):.0f} {unidade}\n"
        f"Vencimento:    {float(etapa.get('vencimento', etapa.get('vencimento_ciclo', 0))):.0f} {unidade}\n"
        f"{linhas_status}\n"
        f"Prazo estimado: {_data_estimada(falta, unidade)}\n\n"
        f"Responsável: {responsavel_nome}\n\n"
        f"Por favor, providencie a execução da revisão."
    )


def montar_mensagem_lubrificacao(equipamento: dict, item: dict, responsavel_nome: str) -> str:
    tipo    = item.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta   = float(item.get("diferenca", item.get("falta", 0)))
    status  = item.get("status", "-")

    linhas_status = ""
    if status == "VENCIDO":
        linhas_status = f"⚠️ *VENCIDO* há {abs(falta):.0f} {unidade} — ação imediata necessária!\n"
    elif status == "PROXIMO":
        linhas_status = f"⏰ Próximo do vencimento — faltam {falta:.0f} {unidade}\n"

    return (
        f"🛢️ *ALERTA DE LUBRIFICAÇÃO*\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Item: {item.get('item', '-')} ({item.get('tipo_produto', '-')})\n\n"
        f"Leitura atual: {float(item.get('atual', 0)):.0f} {unidade}\n"
        f"Próxima troca: {float(item.get('vencimento', 0)):.0f} {unidade}\n"
        f"{linhas_status}\n"
        f"Prazo estimado: {_data_estimada(falta, unidade)}\n\n"
        f"Responsável: {responsavel_nome}\n\n"
        f"Por favor, providencie a lubrificação."
    )


# ── consultas de histórico ────────────────────────────────────────────────────

def ja_enviado_hoje(equipamento_id: int, tipo_alerta: str) -> bool:
    """
    Retorna True se já foi registrado algum alerta para este equipamento
    e tipo hoje (data local). Evita spam de alertas repetidos.
    """
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            """
            select 1
            from alertas_enviados
            where equipamento_id = %s
              and tipo_alerta    = %s
              and enviado_em::date = current_date
            limit 1
            """,
            (equipamento_id, tipo_alerta),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def alertas_enviados_hoje_batch(equipamento_ids: list) -> dict:
    """
    Retorna dict {(equipamento_id, tipo_alerta): True}
    para todos os alertas enviados hoje, em uma única query.
    Usado pela página de alertas para marcar "já enviado hoje".
    """
    if not equipamento_ids:
        return {}
    placeholders = ",".join(["%s"] * len(equipamento_ids))
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            f"""
            select distinct equipamento_id, tipo_alerta
            from alertas_enviados
            where equipamento_id in ({placeholders})
              and enviado_em::date = current_date
            """,
            list(equipamento_ids),
        )
        return {(r[0], r[1]): True for r in cur.fetchall()}
    finally:
        conn.close()


def registrar_alerta(equipamento_id, responsavel_id, tipo_alerta, perfil, mensagem):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            """
            insert into alertas_enviados
                (equipamento_id, responsavel_id, tipo_alerta, perfil, mensagem)
            values (%s, %s, %s, %s, %s)
            returning id
            """,
            (equipamento_id, responsavel_id, tipo_alerta, perfil, mensagem),
        )
        alerta_id = cur.fetchone()[0]
        conn.commit()
        return alerta_id
    finally:
        conn.close()


def listar_historico(limite=200, data_inicio=None, data_fim=None, tipo=None, perfil=None):
    """
    Histórico com filtros opcionais de período, tipo e perfil.
    """
    conn = get_conn()
    cur  = conn.cursor()
    try:
        filtros   = []
        parametros = []

        if data_inicio:
            filtros.append("a.enviado_em::date >= %s")
            parametros.append(data_inicio)
        if data_fim:
            filtros.append("a.enviado_em::date <= %s")
            parametros.append(data_fim)
        if tipo:
            filtros.append("a.tipo_alerta = %s")
            parametros.append(tipo)
        if perfil:
            filtros.append("a.perfil = %s")
            parametros.append(perfil)

        where = ("where " + " and ".join(filtros)) if filtros else ""
        parametros.append(limite)

        cur.execute(
            f"""
            select a.id, a.enviado_em, a.tipo_alerta, a.perfil,
                   coalesce(eq.codigo || ' - ' || eq.nome, '-') as equipamento,
                   coalesce(r.nome, '-') as responsavel
            from alertas_enviados a
            left join equipamentos eq on eq.id = a.equipamento_id
            left join responsaveis r  on r.id  = a.responsavel_id
            {where}
            order by a.enviado_em desc
            limit %s
            """,
            parametros,
        )
        rows = cur.fetchall()
        return [
            {
                "id":          r[0],
                "enviado_em":  r[1],
                "tipo":        r[2],
                "perfil":      r[3],
                "equipamento": r[4],
                "responsavel": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()



def listar_historico_por_equipamento(equipamento_id, limite=50):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select a.id, a.enviado_em, a.tipo_alerta, a.perfil,
                   coalesce(r.nome, '-') as responsavel,
                   a.mensagem
            from alertas_enviados a
            left join responsaveis r on r.id = a.responsavel_id
            where a.equipamento_id = %s
            order by a.enviado_em desc, a.id desc
            limit %s
            """,
            (equipamento_id, limite),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "enviado_em": r[1],
                "tipo": r[2],
                "perfil": r[3],
                "responsavel": r[4],
                "mensagem": r[5] or "",
            }
            for r in rows
        ]
    except Exception:
        conn.rollback()
        return []
    finally:
        conn.close()


def gerar_fila_sugerida(max_por_tipo=100):
    from services import equipamentos_service, revisoes_service, lubrificacoes_service, vinculos_service

    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return {"revisao": [], "lubrificacao": [], "resumo": {"total": 0, "operacional": 0, "gestao": 0}}

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    enviados_hoje = alertas_enviados_hoje_batch(ids)

    filas = {"revisao": [], "lubrificacao": []}

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]
        responsaveis = vinculos_service.listar_por_equipamento(eqp_id)
        gestor = vinculos_service.responsavel_gestao_setor(eqp.get("setor_id")) if eqp.get("setor_id") else None

        for tipo, itens in (("revisao", rev_idx.get(eqp_id, [])), ("lubrificacao", lub_idx.get(eqp_id, []))):
            for item in itens:
                if item.get("status") not in {"VENCIDO", "PROXIMO"}:
                    continue
                filas[tipo].append({
                    "equipamento_id": eqp_id,
                    "equipamento": f"{eqp.get('codigo')} - {eqp.get('nome')}",
                    "setor": eqp.get("setor_nome") or "-",
                    "item": item.get("etapa") or item.get("item") or "-",
                    "status": item.get("status") or "-",
                    "falta": float(item.get("diferenca", item.get("falta", 0)) or 0),
                    "enviado_hoje": bool(enviados_hoje.get((eqp_id, tipo), False)),
                    "responsaveis_operacionais": ", ".join(v["responsavel_nome"] for v in responsaveis) if responsaveis else "-",
                    "gestao": gestor.get("nome") if gestor else "-",
                })

    ordem = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}
    for tipo in filas:
        filas[tipo].sort(key=lambda x: (x["enviado_hoje"], ordem.get(x["status"], 99), x["falta"], x["equipamento"]))
        filas[tipo] = filas[tipo][:max_por_tipo]

    resumo = {
        "total": len(filas["revisao"]) + len(filas["lubrificacao"]),
        "operacional": sum(1 for tipo in filas for item in filas[tipo] if item["responsaveis_operacionais"] != "-"),
        "gestao": sum(1 for tipo in filas for item in filas[tipo] if item["gestao"] != "-"),
    }
    filas["resumo"] = resumo
    return filas
