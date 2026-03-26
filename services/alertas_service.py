import urllib.parse
from database.connection import get_conn


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


def montar_mensagem_revisao(equipamento: dict, etapa: dict, responsavel_nome: str) -> str:
    tipo = etapa.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    return (
        f"🔧 *ALERTA DE REVISÃO*\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Etapa: {etapa.get('etapa', etapa.get('nome_etapa', '-'))}\n\n"
        f"Leitura atual: {float(etapa.get('atual', etapa.get('leitura_atual', 0))):.0f} {unidade}\n"
        f"Vencimento: {float(etapa.get('vencimento', 0)):.0f} {unidade}\n"
        f"Status: {etapa.get('status', '-')}\n\n"
        f"Responsável: {responsavel_nome}\n\n"
        f"Por favor, providencie a execução da revisão."
    )


def montar_mensagem_lubrificacao(equipamento: dict, item: dict, responsavel_nome: str) -> str:
    tipo = item.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    return (
        f"🛢️ *ALERTA DE LUBRIFICAÇÃO*\n\n"
        f"Equipamento: *{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}*\n"
        f"Setor: {equipamento.get('setor_nome', '-')}\n"
        f"Item: {item.get('item', '-')} ({item.get('tipo_produto', '-')})\n\n"
        f"Leitura atual: {float(item.get('atual', 0)):.0f} {unidade}\n"
        f"Vencimento: {float(item.get('vencimento', 0)):.0f} {unidade}\n"
        f"Status: {item.get('status', '-')}\n\n"
        f"Responsável: {responsavel_nome}\n\n"
        f"Por favor, providencie a lubrificação."
    )


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
        conn.close()


def listar_historico(limite=100):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select a.id, a.enviado_em, a.tipo_alerta, a.perfil,
                   coalesce(eq.codigo || ' - ' || eq.nome, '-') as equipamento,
                   coalesce(r.nome, '-') as responsavel
            from alertas_enviados a
            left join equipamentos eq on eq.id = a.equipamento_id
            left join responsaveis r on r.id = a.responsavel_id
            order by a.enviado_em desc
            limit %s
            """,
            (limite,),
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
        conn.close()
