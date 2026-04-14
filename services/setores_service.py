from __future__ import annotations

from typing import Any

from database.connection import get_conn, release_conn
from services import auditoria_service, escopo_service


VINCULOS_TABLE = "vinculos_setor_responsavel"


def _to_id(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        select exists(
            select 1
              from information_schema.tables
             where table_schema = 'public'
               and table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])


def _coletar_descendentes(cur, setor_id: Any) -> list[str]:
    raiz = _to_id(setor_id)
    if not raiz:
        return []

    pendentes = [raiz]
    vistos: set[str] = set()
    ordem: list[str] = []

    while pendentes:
        atual = _to_id(pendentes.pop())
        if not atual or atual in vistos:
            continue
        vistos.add(atual)
        ordem.append(atual)
        cur.execute("select id::text from setores where setor_pai_id = %s", (atual,))
        pendentes.extend(_to_id(r[0]) for r in (cur.fetchall() or []))

    return ordem


def _buscar_setor(cur, setor_id: Any):
    sid = _to_id(setor_id)
    if not sid:
        return None
    cur.execute(
        """
        select id::text, nome, tipo_nivel, setor_pai_id::text, ativo
          from setores
         where id = %s
        """,
        (sid,),
    )
    return cur.fetchone()


def _validar_pai(cur, setor_id: Any, setor_pai_id: Any):
    sid = _to_id(setor_id)
    pai_id = _to_id(setor_pai_id)
    if not pai_id:
        return
    if sid and pai_id == sid:
        raise ValueError("Um setor não pode ser pai dele mesmo.")
    pai = _buscar_setor(cur, pai_id)
    if not pai:
        raise ValueError("Setor pai não encontrado.")
    if sid:
        descendentes = set(_coletar_descendentes(cur, sid))
        if pai_id in descendentes:
            raise ValueError("Não é permitido mover um setor para dentro de um descendente.")


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                s.id::text,
                s.nome,
                s.tipo_nivel,
                s.setor_pai_id::text,
                s.ativo,
                coalesce(sp.nome, '-') as setor_pai_nome,
                count(e.id) as total_equipamentos
            from setores s
            left join setores sp on sp.id = s.setor_pai_id
            left join equipamentos e on e.setor_id = s.id
            group by s.id, s.nome, s.tipo_nivel, s.setor_pai_id, s.ativo, sp.nome
            order by s.nome
            """
        )
        rows = cur.fetchall()
        itens = [
            {
                "id": r[0],
                "nome": r[1],
                "tipo_nivel": r[2],
                "setor_pai_id": r[3],
                "ativo": bool(r[4]),
                "setor_pai_nome": r[5],
                "total_equipamentos": int(r[6] or 0),
            }
            for r in rows
        ]
        return escopo_service.filtrar_setores(itens)
    finally:
        release_conn(conn)


def criar(nome, tipo_nivel="setor", setor_pai_id=None, ativo=True):
    nome = str(nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do setor.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        _validar_pai(cur, None, setor_pai_id)
        cur.execute(
            """
            insert into setores (nome, tipo_nivel, setor_pai_id, ativo)
            values (%s, %s, %s, %s)
            returning id::text
            """,
            (nome, tipo_nivel, _to_id(setor_pai_id), bool(ativo)),
        )
        setor_id = cur.fetchone()[0]
        auditoria_service.registrar_no_conn(
            conn,
            acao="criar_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo=None,
            valor_novo={
                "nome": nome,
                "tipo_nivel": tipo_nivel,
                "setor_pai_id": _to_id(setor_pai_id),
                "ativo": bool(ativo),
            },
        )
        conn.commit()
        return setor_id
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def editar(setor_id, nome, tipo_nivel="setor", setor_pai_id=None, ativo=True):
    sid = _to_id(setor_id)
    nome = str(nome or "").strip()
    if not sid:
        raise ValueError("Setor não informado.")
    if not nome:
        raise ValueError("Informe o nome do setor.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        atual = _buscar_setor(cur, sid)
        if not atual:
            raise ValueError("Setor não encontrado.")

        _validar_pai(cur, sid, setor_pai_id)
        novo_pai = _to_id(setor_pai_id)

        cur.execute(
            """
            update setores
               set nome = %s,
                   tipo_nivel = %s,
                   setor_pai_id = %s,
                   ativo = %s
             where id = %s
            """,
            (nome, tipo_nivel, novo_pai, bool(ativo), sid),
        )

        auditoria_service.registrar_no_conn(
            conn,
            acao="editar_setor",
            entidade="setores",
            entidade_id=sid,
            valor_antigo={
                "nome": atual[1],
                "tipo_nivel": atual[2],
                "setor_pai_id": atual[3],
                "ativo": bool(atual[4]),
            },
            valor_novo={
                "nome": nome,
                "tipo_nivel": tipo_nivel,
                "setor_pai_id": novo_pai,
                "ativo": bool(ativo),
            },
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def vincular_equipamentos(setor_id, equipamento_ids: list[int]):
    sid = _to_id(setor_id)
    eq_ids = sorted({int(x) for x in (equipamento_ids or []) if str(x).strip()})
    if not sid:
        raise ValueError("Setor não informado.")
    if not eq_ids:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    try:
        setor = _buscar_setor(cur, sid)
        if not setor:
            raise ValueError("Setor não encontrado.")

        cur.execute(
            """
            update equipamentos
               set setor_id = %s
             where id = any(%s::bigint[])
            """,
            (sid, eq_ids),
        )
        total = cur.rowcount or 0
        auditoria_service.registrar_no_conn(
            conn,
            acao="vincular_equipamentos_setor",
            entidade="setores",
            entidade_id=sid,
            valor_antigo=None,
            valor_novo={"equipamento_ids": eq_ids, "total": total},
        )
        conn.commit()
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def excluir(setor_id, destino_setor_id=None, exclusao_completa=False):
    sid = _to_id(setor_id)
    destino_id = _to_id(destino_setor_id)
    if not sid:
        raise ValueError("Setor não informado.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        atual = _buscar_setor(cur, sid)
        if not atual:
            raise ValueError("Setor não encontrado.")

        cur.execute("select count(1) from setores where setor_pai_id = %s", (sid,))
        filhos = int(cur.fetchone()[0] or 0)

        cur.execute("select count(1) from equipamentos where setor_id = %s", (sid,))
        equipamentos = int(cur.fetchone()[0] or 0)

        if destino_id:
            if destino_id == sid:
                raise ValueError("O setor de destino deve ser diferente do setor excluído.")
            destino = _buscar_setor(cur, destino_id)
            if not destino:
                raise ValueError("Setor de destino não encontrado.")
            if destino_id in set(_coletar_descendentes(cur, sid)):
                raise ValueError("Não é permitido mover vínculos para um setor descendente do setor excluído.")

        if exclusao_completa and destino_id:
            raise ValueError("Escolha apenas uma opção: exclusão completa ou mover para setor de destino.")

        if exclusao_completa:
            arvore_ids = _coletar_descendentes(cur, sid)
            cur.execute(
                "select count(1) from equipamentos where setor_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            total_equipamentos_arvore = int(cur.fetchone()[0] or 0)

            cur.execute(
                "update equipamentos set setor_id = null where setor_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            if _table_exists(cur, VINCULOS_TABLE):
                cur.execute(
                    f"delete from {VINCULOS_TABLE} where setor_id = any(%s::uuid[])",
                    (arvore_ids,),
                )
            cur.execute(
                "update setores set setor_pai_id = null where setor_pai_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            cur.execute(
                "delete from setores where id = any(%s::uuid[])",
                (arvore_ids,),
            )

            auditoria_service.registrar_no_conn(
                conn,
                acao="excluir_setor_completo",
                entidade="setores",
                entidade_id=sid,
                valor_antigo={
                    "nome": atual[1],
                    "setor_pai_id": atual[3],
                    "filhos_diretos": filhos,
                    "equipamentos_diretos": equipamentos,
                    "setores_excluidos": arvore_ids,
                    "equipamentos_desvinculados": total_equipamentos_arvore,
                },
                valor_novo={"destino_setor_id": None, "exclusao_completa": True},
            )
            conn.commit()
            return True

        if filhos and not destino_id:
            raise ValueError("Este setor possui setores filhos. Informe um setor de destino antes de excluir ou marque exclusão completa.")
        if equipamentos and not destino_id:
            raise ValueError("Este setor possui equipamentos vinculados. Informe um setor de destino antes de excluir ou marque exclusão completa.")

        if destino_id:
            cur.execute("update setores set setor_pai_id = %s where setor_pai_id = %s", (destino_id, sid))
            cur.execute("update equipamentos set setor_id = %s where setor_id = %s", (destino_id, sid))
            if _table_exists(cur, VINCULOS_TABLE):
                cur.execute(
                    f"update {VINCULOS_TABLE} set setor_id = %s where setor_id = %s",
                    (destino_id, sid),
                )

        auditoria_service.registrar_no_conn(
            conn,
            acao="excluir_setor",
            entidade="setores",
            entidade_id=sid,
            valor_antigo={
                "nome": atual[1],
                "setor_pai_id": atual[3],
                "filhos": filhos,
                "equipamentos": equipamentos,
            },
            valor_novo={"destino_setor_id": destino_id, "exclusao_completa": False},
        )
        cur.execute("delete from setores where id = %s", (sid,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
