import datetime
import urllib.parse

from database.connection import get_conn, release_conn
from services import configuracoes_service


def _limpar_telefone(telefone: str) -> str:
    if not telefone:
        return ""
    numeros = "".join(c for c in telefone if c.isdigit())
    if not numeros.startswith("55"):
        numeros = "55" + numeros
    return numeros


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    numero = _limpar_telefone(telefone)
    texto = urllib.parse.quote(mensagem)
    return f"https://wa.me/{numero}?text={texto}"


def _data_estimada(falta: float, unidade: str) -> str:
    if falta <= 0:
        return "execução imediata (item já vencido)"
    return f"em aproximadamente {falta:.0f} {unidade}"


def _linha_situacao(status: str, falta: float, unidade: str) -> str:
    if status == "VENCIDO":
        return f"Situação: *Vencido* há {abs(falta):.0f} {unidade}"
    if status == "PROXIMO":
        return f"Situação: *Próximo do vencimento* — faltam {falta:.0f} {unidade}"
    return f"Situação: {status or '-'}"


def montar_mensagem_revisao(equipamento: dict, etapa: dict, responsavel_nome: str) -> str:
    tipo = etapa.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta = float(etapa.get("diferenca", etapa.get("falta", 0)) or 0)
    status = etapa.get("status", "-")
    leitura_atual = float(etapa.get("atual", etapa.get("leitura_atual", 0)) or 0)
    vencimento = float(etapa.get("vencimento", etapa.get("vencimento_ciclo", 0)) or 0)
    etapa_nome = etapa.get("etapa", etapa.get("nome_etapa", "-"))

    return (
        f"*Alerta de revisão*\n\n"
        f"Olá, *{responsavel_nome}*.\n"
        f"Foi identificada uma revisão que exige acompanhamento.\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Etapa: {etapa_nome}\n"
        f"Leitura atual: {leitura_atual:.0f} {unidade}\n"
        f"Vencimento: {vencimento:.0f} {unidade}\n"
        f"{_linha_situacao(status, falta, unidade)}\n"
        f"Janela estimada: {_data_estimada(falta, unidade)}\n\n"
        f"Ação recomendada: programar a execução da revisão e registrar o apontamento no sistema."
    )


def montar_mensagem_lubrificacao(equipamento: dict, item: dict, responsavel_nome: str) -> str:
    tipo = item.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    status = item.get("status", "-")
    leitura_atual = float(item.get("atual", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    item_nome = item.get("item", "-")
    produto = item.get("tipo_produto", "-")

    return (
        f"*Alerta de lubrificação*\n\n"
        f"Olá, *{responsavel_nome}*.\n"
        f"Foi identificado um item de lubrificação que exige acompanhamento.\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Item: {item_nome}\n"
        f"Produto: {produto}\n"
        f"Leitura atual: {leitura_atual:.0f} {unidade}\n"
        f"Próxima troca: {vencimento:.0f} {unidade}\n"
        f"{_linha_situacao(status, falta, unidade)}\n"
        f"Janela estimada: {_data_estimada(falta, unidade)}\n\n"
        f"Ação recomendada: programar a lubrificação e registrar o apontamento no sistema."
    )


STATUS_EMOJI = {
    "VENCIDO": "🔴",
    "PROXIMO": "🟡",
    "SEM_BASE": "⭐",
    "SEM BASE": "⭐",
    "EM_DIA": "⚪",
    "EM DIA": "⚪",
}


def _emoji_status(status: str, realizado: bool = False) -> str:
    if realizado:
        return "✅"
    return STATUS_EMOJI.get(str(status or "").upper(), "⚪")


# Aliases públicos (usados pela UI) — mantêm os nomes internos por compatibilidade.
emoji_status = _emoji_status


def coletar_itens_equipamento(equipamento_id) -> list[dict]:
    """Junta etapas de revisão + itens de lubrificação de um equipamento num
    formato único, para montar o resumo consolidado (WhatsApp/e-mail)."""
    from services import revisoes_service, lubrificacoes_service

    itens = []
    try:
        rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
        for etapa in rev_idx.get(equipamento_id, []):
            itens.append({
                "tipo": "revisao",
                "nome": etapa.get("etapa") or etapa.get("nome_etapa") or "-",
                "status": str(etapa.get("status") or "-").upper(),
                "realizado": bool(etapa.get("realizado_no_ciclo")),
                "falta": float(etapa.get("diferenca", etapa.get("falta", 0)) or 0),
                "unidade": "h" if (etapa.get("tipo_controle") == "horas") else "km",
            })
    except Exception:
        pass
    try:
        lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch([equipamento_id])
        for item in lub_idx.get(equipamento_id, []):
            itens.append({
                "tipo": "lubrificacao",
                "nome": item.get("item") or "-",
                "status": str(item.get("status") or "-").upper(),
                "realizado": bool(item.get("realizado_no_ciclo")),
                "falta": float(item.get("diferenca", 0) or 0),
                "unidade": "h" if (item.get("tipo_controle") == "horas") else "km",
            })
    except Exception:
        pass
    return itens


def _texto_situacao_item(item: dict) -> str:
    unidade = item.get("unidade", "km")
    falta = float(item.get("falta", 0) or 0)
    status = item.get("status")
    if item.get("realizado"):
        return "realizado neste ciclo"
    if status == "VENCIDO":
        return f"vencido há {abs(falta):.0f} {unidade}"
    if status == "PROXIMO":
        return f"faltam {falta:.0f} {unidade}"
    if status in ("SEM_BASE", "SEM BASE"):
        return "aguardando 1ª execução"
    return f"faltam {falta:.0f} {unidade}" if falta > 0 else "em dia"


texto_situacao_item = _texto_situacao_item


def montar_mensagem_resumo_equipamento(equipamento: dict, itens: list[dict], responsavel_nome: str) -> str:
    """Mensagem única de WhatsApp com o status de TODOS os itens do equipamento
    (revisão + lubrificação), no estilo do resumo visual do PDF."""
    eqp_label = f"{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}"
    linhas = [
        "*Resumo de manutenção*",
        "",
        f"Olá, *{responsavel_nome}*.",
        f"Situação atual do equipamento *{eqp_label}*:",
        "",
    ]
    if not itens:
        linhas.append("Nenhum item de revisão ou lubrificação configurado para este equipamento.")
    else:
        for item in itens:
            emoji = _emoji_status(item["status"], item["realizado"])
            linhas.append(f"{emoji} {item['nome']} — {_texto_situacao_item(item)}")

    linhas.append("")
    vencidos = sum(1 for i in itens if i["status"] == "VENCIDO" and not i["realizado"])
    proximos = sum(1 for i in itens if i["status"] == "PROXIMO" and not i["realizado"])
    if vencidos:
        linhas.append(f"⚠️ {vencidos} item(ns) vencido(s) — recomendamos priorizar.")
    elif proximos:
        linhas.append(f"ℹ️ {proximos} item(ns) próximo(s) do vencimento.")
    else:
        linhas.append("✅ Tudo certo por aqui — nenhuma pendência crítica no momento.")
    return "\n".join(linhas)


def ja_enviado_hoje(equipamento_id, tipo_alerta: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select 1
            from alertas_enviados
            where equipamento_id = %s
              and tipo_alerta = %s
              and enviado_em::date = current_date
            limit 1
            """,
            (equipamento_id, tipo_alerta),
        )
        return cur.fetchone() is not None
    finally:
        release_conn(conn)


def responsavel_recebeu_recentemente(responsavel_id, tipo_alerta: str, dias: int = 7) -> bool:
    """Verifica se um responsável já recebeu esse tipo de alerta nos últimos N dias
    (usado para o resumo semanal, que não deve repetir todo dia)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select 1
            from alertas_enviados
            where responsavel_id = %s
              and tipo_alerta = %s
              and enviado_em >= now() - (%s || ' days')::interval
            limit 1
            """,
            (responsavel_id, tipo_alerta, dias),
        )
        return cur.fetchone() is not None
    except Exception:
        conn.rollback()
        return False
    finally:
        release_conn(conn)


def enviar_resumos_semanais_pendentes(dias: int = 7) -> dict:
    """Envia (por e-mail) o resumo consolidado de todos os equipamentos vinculados
    a cada responsável, uma vez a cada `dias` dias. Chamado automaticamente uma
    vez por dia (ver main.py) — cada responsável só recebe de fato quando já
    passou o período configurado, graças ao `responsavel_recebeu_recentemente`.

    OBS: cobre apenas e-mail. Não existe envio automático de WhatsApp sem uma
    integração paga com a API oficial (Twilio/Meta) — ver `montar_fila_semanal_whatsapp`
    para o equivalente "pronto para clicar" usado na tela de Alertas.
    """
    from services import email_service, equipamentos_service, responsaveis_service, vinculos_service

    resultado = {"enviados": 0, "pulados": 0, "erros": 0, "sem_email_configurado": False}

    if not email_service.email_configurado():
        resultado["sem_email_configurado"] = True
        return resultado

    try:
        equipamentos = {e["id"]: e for e in equipamentos_service.listar()}
        mapa_por_eqp = vinculos_service.mapa_responsaveis_operacionais()
        responsaveis_por_id = {r["id"]: r for r in responsaveis_service.listar() if r.get("ativo", True)}
    except Exception:
        resultado["erros"] += 1
        return resultado

    # Inverte o mapa: responsavel_id -> lista de equipamento_ids
    eqps_por_responsavel: dict = {}
    for eqp_id, vinculos in mapa_por_eqp.items():
        for v in vinculos:
            eqps_por_responsavel.setdefault(v["responsavel_id"], set()).add(eqp_id)

    for responsavel_id, eqp_ids in eqps_por_responsavel.items():
        responsavel = responsaveis_por_id.get(responsavel_id)
        if not responsavel or not responsavel.get("email"):
            resultado["pulados"] += 1
            continue
        if responsavel_recebeu_recentemente(responsavel_id, "resumo_semanal", dias):
            resultado["pulados"] += 1
            continue

        blocos = []
        for eqp_id in sorted(eqp_ids, key=lambda i: str(i)):
            eqp = equipamentos.get(eqp_id)
            if not eqp:
                continue
            itens = coletar_itens_equipamento(eqp_id)
            if itens:
                blocos.append({"equipamento": eqp, "itens": itens})

        if not blocos:
            resultado["pulados"] += 1
            continue

        html, texto = email_service.montar_html_resumo_responsavel(responsavel["nome"], blocos)
        assunto = f"Resumo semanal de manutenção — {len(blocos)} equipamento(s)"
        ok, _msg = email_service.enviar_email(responsavel["email"], assunto, html, texto)
        if ok:
            registrar_alerta_lote(
                [{"equipamento_id": eqp_id, "responsavel_id": responsavel_id, "tipo_alerta": "resumo_semanal"}
                 for eqp_id in eqp_ids],
                perfil="resumo_semanal",
                observacao="resumo_semanal_automatico",
            )
            resultado["enviados"] += 1
        else:
            resultado["erros"] += 1

    return resultado


def montar_fila_semanal_whatsapp(dias: int = 7) -> list[dict]:
    """Monta a fila de resumos da semana prontos para envio manual por WhatsApp
    (um link por responsável, já com a mensagem pronta). Não envia nada sozinho —
    WhatsApp sempre exige que alguém clique em "Enviar" na conversa."""
    from services import equipamentos_service, responsaveis_service, vinculos_service

    fila = []
    try:
        equipamentos = {e["id"]: e for e in equipamentos_service.listar()}
        mapa_por_eqp = vinculos_service.mapa_responsaveis_operacionais()
        responsaveis_por_id = {r["id"]: r for r in responsaveis_service.listar() if r.get("ativo", True)}
    except Exception:
        return fila

    eqps_por_responsavel: dict = {}
    for eqp_id, vinculos in mapa_por_eqp.items():
        for v in vinculos:
            eqps_por_responsavel.setdefault(v["responsavel_id"], set()).add(eqp_id)

    for responsavel_id, eqp_ids in eqps_por_responsavel.items():
        responsavel = responsaveis_por_id.get(responsavel_id)
        if not responsavel or not responsavel.get("telefone"):
            continue
        if responsavel_recebeu_recentemente(responsavel_id, "resumo_semanal_whatsapp", dias):
            continue

        for eqp_id in sorted(eqp_ids, key=lambda i: str(i)):
            eqp = equipamentos.get(eqp_id)
            if not eqp:
                continue
            itens = coletar_itens_equipamento(eqp_id)
            if not itens:
                continue
            mensagem = montar_mensagem_resumo_equipamento(eqp, itens, responsavel["nome"])
            fila.append({
                "responsavel_id": responsavel_id,
                "responsavel_nome": responsavel["nome"],
                "telefone": responsavel["telefone"],
                "equipamento_id": eqp_id,
                "equipamento": f"{eqp.get('codigo')} - {eqp.get('nome')}",
                "mensagem": mensagem,
                "link": gerar_link_whatsapp(responsavel["telefone"], mensagem),
            })
    return fila


def alertas_enviados_hoje_batch(equipamento_ids: list) -> dict:
    if not equipamento_ids:
        return {}
    placeholders = ",".join(["%s"] * len(equipamento_ids))
    conn = get_conn()
    cur = conn.cursor()
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
        release_conn(conn)


def ultimos_alertas_batch(equipamento_ids: list) -> dict:
    if not equipamento_ids:
        return {}
    placeholders = ",".join(["%s"] * len(equipamento_ids))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            select equipamento_id, tipo_alerta, max(enviado_em) as ultimo_envio
            from alertas_enviados
            where equipamento_id in ({placeholders})
            group by equipamento_id, tipo_alerta
            """,
            list(equipamento_ids),
        )
        return {(r[0], r[1]): r[2] for r in cur.fetchall()}
    except Exception:
        conn.rollback()
        return {}
    finally:
        release_conn(conn)


def registrar_alerta(equipamento_id, responsavel_id, tipo_alerta, perfil, mensagem):
    conn = get_conn()
    cur = conn.cursor()
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
        release_conn(conn)


def registrar_alerta_lote(itens: list, perfil: str, observacao: str = "envio_em_lote") -> int:
    if not itens:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    enviados = 0
    try:
        for item in itens:
            cur.execute(
                """
                insert into alertas_enviados
                    (equipamento_id, responsavel_id, tipo_alerta, perfil, mensagem)
                values (%s, %s, %s, %s, %s)
                """,
                (
                    item.get("equipamento_id"),
                    item.get("responsavel_id"),
                    item.get("tipo_alerta"),
                    perfil,
                    item.get("mensagem") or observacao,
                ),
            )
            enviados += 1
        conn.commit()
        return enviados
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def listar_historico(limite=200, data_inicio=None, data_fim=None, tipo=None, perfil=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = []
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
            left join responsaveis r on r.id = a.responsavel_id
            {where}
            order by a.enviado_em desc
            limit %s
            """,
            parametros,
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "enviado_em": r[1],
                "tipo": r[2],
                "perfil": r[3],
                "equipamento": r[4],
                "responsavel": r[5],
            }
            for r in rows
        ]
    finally:
        release_conn(conn)


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
        release_conn(conn)


def _prioridade_item(status: str, falta: float, tem_operacional: bool, tem_gestao: bool, bloqueado: bool) -> int:
    score = 0
    if status == "VENCIDO":
        score += 100
    elif status == "PROXIMO":
        score += 40
    score += min(50, int(abs(min(falta, 0))))
    if not tem_operacional:
        score -= 15
    if not tem_gestao:
        score -= 5
    if bloqueado:
        score -= 80
    return score


def _dias_desde(data_envio):
    if not data_envio:
        return None
    agora = datetime.datetime.now(datetime.timezone.utc)
    try:
        delta = agora - data_envio
    except TypeError:
        delta = agora.replace(tzinfo=None) - data_envio
    return max(0, delta.days)


def gerar_fila_sugerida(max_por_tipo=None):
    from services import equipamentos_service, revisoes_service, lubrificacoes_service, vinculos_service

    max_por_tipo = int(max_por_tipo or configuracoes_service.get_fila_alertas_limite())
    equipamentos = equipamentos_service.listar()
    if not equipamentos:
        return {"revisao": [], "lubrificacao": [], "resumo": {"total": 0, "operacional": 0, "gestao": 0, "bloqueados": 0, "sem_cobertura": 0, "prontos_envio": 0}, "cobertura": {"percentual_operacional": 0, "percentual_gestao": 0, "setores": []}}

    ids = [e["id"] for e in equipamentos]
    eqp_map = {e["id"]: e for e in equipamentos}
    rev_idx = revisoes_service.listar_controle_revisoes_por_equipamento()
    lub_idx = lubrificacoes_service.calcular_proximas_lubrificacoes_batch(ids)
    enviados_hoje = alertas_enviados_hoje_batch(ids)
    ultimos = ultimos_alertas_batch(ids)

    filas = {"revisao": [], "lubrificacao": []}
    cooldown_horas = max(1, int(configuracoes_service.get_alerta_cooldown_horas()))
    agora = datetime.datetime.now(datetime.timezone.utc)
    mapa_operacionais = vinculos_service.mapa_responsaveis_operacionais()
    mapa_gestao = vinculos_service.mapa_responsaveis_gestao()

    for eqp_id in ids:
        eqp = eqp_map[eqp_id]
        responsaveis = mapa_operacionais.get(eqp_id, [])
        gestor = mapa_gestao.get(eqp.get("setor_id")) if eqp.get("setor_id") else None

        for tipo, itens in (("revisao", rev_idx.get(eqp_id, [])), ("lubrificacao", lub_idx.get(eqp_id, []))):
            for item in itens:
                if item.get("status") not in {"VENCIDO", "PROXIMO"}:
                    continue
                ultimo_envio = ultimos.get((eqp_id, tipo))
                bloqueado = False
                if ultimo_envio is not None:
                    try:
                        horas_desde = (agora - ultimo_envio).total_seconds() / 3600
                    except TypeError:
                        horas_desde = (agora.replace(tzinfo=None) - ultimo_envio).total_seconds() / 3600
                    bloqueado = horas_desde < cooldown_horas
                tem_operacional = bool(responsaveis)
                tem_gestao = bool(gestor)
                falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
                prioridade = _prioridade_item(item.get("status") or "-", falta, tem_operacional, tem_gestao, bloqueado)
                motivo = []
                if item.get("status") == "VENCIDO":
                    motivo.append("vencido")
                if enviados_hoje.get((eqp_id, tipo), False):
                    motivo.append("já enviado hoje")
                if bloqueado:
                    motivo.append(f"cooldown {cooldown_horas}h")
                if not tem_operacional:
                    motivo.append("sem operacional")
                if not tem_gestao:
                    motivo.append("sem gestão")
                if not motivo:
                    motivo.append("pronto para enviar")
                filas[tipo].append({
                    "equipamento_id": eqp_id,
                    "tipo_alerta": tipo,
                    "equipamento": f"{eqp.get('codigo')} - {eqp.get('nome')}",
                    "setor": eqp.get("setor_nome") or "-",
                    "item": item.get("etapa") or item.get("item") or "-",
                    "status": item.get("status") or "-",
                    "falta": falta,
                    "enviado_hoje": bool(enviados_hoje.get((eqp_id, tipo), False)),
                    "ultimo_envio": ultimo_envio,
                    "dias_desde_ultimo_alerta": _dias_desde(ultimo_envio),
                    "bloqueado_cooldown": bool(bloqueado),
                    "responsaveis_operacionais": ", ".join(v["responsavel_nome"] for v in responsaveis) if responsaveis else "-",
                    "gestao": gestor.get("nome") if gestor else "-",
                    "tem_operacional": tem_operacional,
                    "tem_gestao": tem_gestao,
                    "prioridade": prioridade,
                    "motivo_fila": ", ".join(motivo),
                })

    ordem = {"VENCIDO": 0, "PROXIMO": 1, "EM DIA": 2}
    for tipo in filas:
        filas[tipo].sort(key=lambda x: (-x["prioridade"], ordem.get(x["status"], 99), x["enviado_hoje"], x["equipamento"]))
        filas[tipo] = filas[tipo][:max_por_tipo]

    todas = filas["revisao"] + filas["lubrificacao"]
    resumo = {
        "total": len(todas),
        "operacional": sum(1 for item in todas if item["tem_operacional"]),
        "gestao": sum(1 for item in todas if item["tem_gestao"]),
        "bloqueados": sum(1 for item in todas if item["bloqueado_cooldown"]),
        "sem_cobertura": sum(1 for item in todas if not item["tem_operacional"] and not item["tem_gestao"]),
        "prontos_envio": sum(1 for item in todas if not item["bloqueado_cooldown"]),
    }
    filas["resumo"] = resumo
    filas["cobertura"] = resumo_cobertura(filas)
    return filas


def resumo_cobertura(filas: dict | None = None):
    if filas is None:
        filas = gerar_fila_sugerida()
    itens = filas.get("revisao", []) + filas.get("lubrificacao", [])
    total = len(itens) or 1
    setores = {}
    for item in itens:
        setor = item.get("setor") or "-"
        agg = setores.setdefault(setor, {"setor": setor, "total": 0, "com_operacional": 0, "com_gestao": 0, "bloqueados": 0, "criticos": 0})
        agg["total"] += 1
        agg["com_operacional"] += int(bool(item.get("tem_operacional")))
        agg["com_gestao"] += int(bool(item.get("tem_gestao")))
        agg["bloqueados"] += int(bool(item.get("bloqueado_cooldown")))
        agg["criticos"] += int(item.get("status") == "VENCIDO")
    ranking = sorted(setores.values(), key=lambda x: (-x["criticos"], -x["total"], x["setor"]))
    return {
        "percentual_operacional": round(100 * sum(1 for i in itens if i.get("tem_operacional")) / total, 1),
        "percentual_gestao": round(100 * sum(1 for i in itens if i.get("tem_gestao")) / total, 1),
        "setores": ranking,
    }
