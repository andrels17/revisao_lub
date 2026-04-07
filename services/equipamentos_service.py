from database.connection import get_conn


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                e.id,
                e.codigo,
                e.nome,
                e.tipo,
                e.km_atual,
                e.horas_atual,
                e.template_revisao_id,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome,
                e.template_lubrificacao_id,
                coalesce(e.ativo, true) as ativo
            from equipamentos e
            left join setores s on s.id = e.setor_id
            order by e.codigo
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "codigo": r[1],
                "nome": r[2],
                "tipo": r[3],
                "km_atual": float(r[4] or 0),
                "horas_atual": float(r[5] or 0),
                "template_revisao_id": r[6],
                "setor_id": r[7],
                "setor_nome": r[8],
                "template_lubrificacao_id": r[9],
                "ativo": bool(r[10]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def buscar(termo="", somente_ativos=False):
    termo_norm = (termo or "").strip().lower()
    itens = listar()
    if somente_ativos:
        itens = [item for item in itens if item.get("ativo", True)]
    if not termo_norm:
        return itens

    def _match(item):
        alvo = " ".join(
            [
                str(item.get("codigo", "")),
                str(item.get("nome", "")),
                str(item.get("tipo", "")),
                str(item.get("setor_nome", "")),
            ]
        ).lower()
        return termo_norm in alvo

    return [item for item in itens if _match(item)]


def obter_por_id(equipamento_id):
    for item in listar():
        if item["id"] == equipamento_id:
            return item
    return None


def criar(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0,
          template_revisao_id=None, ativo=True):
    return criar_completo(
        codigo=codigo, nome=nome, tipo=tipo, setor_id=setor_id,
        km_atual=km_atual, horas_atual=horas_atual,
        template_revisao_id=template_revisao_id, ativo=ativo,
    )


def criar_completo(codigo, nome, tipo, setor_id, km_atual=0, horas_atual=0,
                   template_revisao_id=None, template_lubrificacao_id=None, ativo=True):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into equipamentos (
                codigo, nome, tipo, setor_id,
                km_atual, horas_atual,
                template_revisao_id, template_lubrificacao_id, ativo
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                codigo, nome, tipo, setor_id,
                km_atual, horas_atual,
                template_revisao_id, template_lubrificacao_id, ativo,
            ),
        )
        equipamento_id = cur.fetchone()[0]
        conn.commit()
        return equipamento_id
    finally:
        conn.close()
