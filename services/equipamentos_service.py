from database.connection import get_conn
from services import auditoria_service, escopo_service


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
        itens = [
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
        return escopo_service.filtrar_equipamentos(itens)
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


def obter(equipamento_id):
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
                coalesce(tr.nome, '-') as template_revisao_nome,
                e.template_lubrificacao_id,
                coalesce(tl.nome, '-') as template_lubrificacao_nome,
                e.setor_id,
                coalesce(s.nome, '-') as setor_nome,
                coalesce(e.ativo, true) as ativo
            from equipamentos e
            left join setores s on s.id = e.setor_id
            left join templates_revisao tr on tr.id = e.template_revisao_id
            left join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            where e.id = %s
            """,
            (equipamento_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        item = {
            "id": r[0],
            "codigo": r[1],
            "nome": r[2],
            "tipo": r[3],
            "km_atual": float(r[4] or 0),
            "horas_atual": float(r[5] or 0),
            "template_revisao_id": r[6],
            "template_revisao_nome": r[7],
            "template_lubrificacao_id": r[8],
            "template_lubrificacao_nome": r[9],
            "setor_id": r[10],
            "setor_nome": r[11],
            "ativo": bool(r[12]),
        }
        if not escopo_service.pode_ver_equipamento(item):
            return None
        return item
    finally:
        conn.close()


def obter_por_id(equipamento_id):
    return obter(equipamento_id)


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
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_equipamento",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo=None,
            valor_novo={
                "codigo": codigo,
                "nome": nome,
                "tipo": tipo,
                "setor_id": setor_id,
                "km_atual": km_atual,
                "horas_atual": horas_atual,
                "template_revisao_id": template_revisao_id,
                "template_lubrificacao_id": template_lubrificacao_id,
                "ativo": ativo,
            },
        )
        conn.commit()
        return equipamento_id
    finally:
        conn.close()


def atualizar_inline(equipamento_id, *, nome, tipo, setor_id, ativo):
    """
    Atualiza os campos expostos na edição inline da tela de equipamentos.
    """
    atual = obter(equipamento_id)
    if not atual:
        raise ValueError("Equipamento não encontrado ou fora do escopo.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update equipamentos
               set nome = %s,
                   tipo = %s,
                   setor_id = %s,
                   ativo = %s
             where id = %s
            """,
            (nome, tipo, setor_id, bool(ativo), equipamento_id),
        )

        auditoria_service.registrar_no_conn(
            conn,
            acao="atualizar_equipamento_inline",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo={
                "nome": atual.get("nome"),
                "tipo": atual.get("tipo"),
                "setor_id": atual.get("setor_id"),
                "ativo": atual.get("ativo"),
            },
            valor_novo={
                "nome": nome,
                "tipo": tipo,
                "setor_id": setor_id,
                "ativo": bool(ativo),
            },
        )
        conn.commit()
    finally:
        conn.close()


def definir_responsavel_principal(equipamento_id, responsavel_id):
    """
    Define o responsável principal operacional do equipamento.
    Se responsavel_id vier vazio/None, remove o principal atual.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update vinculos_equipamento
               set principal = false
             where equipamento_id = %s
               and ativo = true
            """,
            (equipamento_id,),
        )

        if responsavel_id:
            cur.execute(
                """
                select tipo_vinculo
                  from vinculos_equipamento
                 where equipamento_id = %s
                   and responsavel_id = %s
                 order by ativo desc, principal desc
                 limit 1
                """,
                (equipamento_id, responsavel_id),
            )
            row = cur.fetchone()
            tipo_vinculo = (row[0] if row and row[0] else "operacional")

            cur.execute(
                """
                insert into vinculos_equipamento
                    (equipamento_id, responsavel_id, tipo_vinculo, principal, ativo)
                values (%s, %s, %s, true, true)
                on conflict (equipamento_id, responsavel_id, tipo_vinculo)
                do update set principal = true, ativo = true
                """,
                (equipamento_id, responsavel_id, tipo_vinculo),
            )

        auditoria_service.registrar_no_conn(
            conn,
            acao="definir_responsavel_principal",
            entidade="equipamentos",
            entidade_id=equipamento_id,
            valor_antigo=None,
            valor_novo={"responsavel_id": responsavel_id},
        )
        conn.commit()
    finally:
        conn.close()
