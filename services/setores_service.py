from __future__ import annotations

from typing import Iterable, Optional

from database.connection import get_conn, release_conn
from services import auditoria_service, escopo_service


def _normalize_uuid(value) -> Optional[str]:
    """
    Normaliza IDs UUID para string.
    Aceita None, string, UUID-like objects e números.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_uuid_list(values: Iterable) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values or []:
        item = _normalize_uuid(value)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _setor_existe(cur, setor_id: str) -> bool:
    cur.execute("select 1 from setores where id = %s limit 1", (setor_id,))
    return cur.fetchone() is not None


def _coletar_descendentes(cur, setor_id) -> list[str]:
    """
    Percorre a árvore de setores de forma iterativa.
    Compatível com UUID e protegido contra loops/ciclos.
    """
    raiz = _normalize_uuid(setor_id)
    if not raiz:
        return []

    pendentes = [raiz]
    vistos: set[str] = set()
    ordem: list[str] = []

    while pendentes:
        atual = pendentes.pop()
        if atual in vistos:
            continue

        vistos.add(atual)
        ordem.append(atual)

        cur.execute(
            "select id from setores where setor_pai_id = %s",
            (atual,),
        )
        filhos = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]

        for filho_id in filhos:
            if filho_id not in vistos:
                pendentes.append(filho_id)

    return ordem


def _setor_esta_na_subarvore(cur, setor_origem_id, possivel_descendente_id) -> bool:
    origem = _normalize_uuid(setor_origem_id)
    candidato = _normalize_uuid(possivel_descendente_id)
    if not origem or not candidato:
        return False
    if origem == candidato:
        return True
    return candidato in set(_coletar_descendentes(cur, origem))


def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                s.id,
                s.nome,
                s.tipo_nivel,
                s.setor_pai_id,
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
        rows = cur.fetchall() or []
        itens = [
            {
                "id": r[0],
                "nome": r[1],
                "tipo_nivel": r[2],
                "setor_pai_id": r[3],
                "ativo": r[4],
                "setor_pai_nome": r[5],
                "total_equipamentos": int(r[6] or 0),
            }
            for r in rows
        ]
        return escopo_service.filtrar_setores(itens)
    finally:
        release_conn(conn)


def criar(nome, tipo_nivel="setor", setor_pai_id=None, ativo=True):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do setor.")

    setor_pai_id = _normalize_uuid(setor_pai_id)

    conn = get_conn()
    cur = conn.cursor()
    try:
        if setor_pai_id and not _setor_existe(cur, setor_pai_id):
            raise ValueError("Setor pai não encontrado.")

        cur.execute(
            """
            insert into setores (nome, tipo_nivel, setor_pai_id, ativo)
            values (%s, %s, %s, %s)
            returning id
            """,
            (nome, tipo_nivel, setor_pai_id, bool(ativo)),
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
                "setor_pai_id": setor_pai_id,
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


def vincular_equipamentos(setor_id, equipamento_ids: list[str] | list[int]):
    setor_id = _normalize_uuid(setor_id)
    equipamento_ids_norm = _normalize_uuid_list(equipamento_ids)

    if not setor_id:
        raise ValueError("Setor inválido.")
    if not equipamento_ids_norm:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome from setores where id = %s",
            (setor_id,),
        )
        setor = cur.fetchone()
        if not setor:
            raise ValueError("Setor não encontrado.")

        cur.execute(
            """
            update equipamentos
               set setor_id = %s
             where id = any(%s::bigint[])
            """,
            (setor_id, equipamento_ids_norm),
        )
        total = cur.rowcount or 0

        auditoria_service.registrar_no_conn(
            conn,
            acao="vincular_equipamentos_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo=None,
            valor_novo={"equipamento_ids": equipamento_ids_norm, "total": total},
        )
        conn.commit()
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def excluir(setor_id, destino_setor_id=None, exclusao_completa=False):
    setor_id = _normalize_uuid(setor_id)
    destino_setor_id = _normalize_uuid(destino_setor_id)

    if not setor_id:
        raise ValueError("Setor inválido.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome, setor_pai_id from setores where id = %s",
            (setor_id,),
        )
        atual = cur.fetchone()
        if not atual:
            raise ValueError("Setor não encontrado.")

        if exclusao_completa and destino_setor_id:
            raise ValueError(
                "Escolha apenas uma opção: exclusão completa ou mover para setor de destino."
            )

        if destino_setor_id:
            if destino_setor_id == setor_id:
                raise ValueError("O setor de destino deve ser diferente do setor excluído.")
            if not _setor_existe(cur, destino_setor_id):
                raise ValueError("Setor de destino não encontrado.")
            if _setor_esta_na_subarvore(cur, setor_id, destino_setor_id):
                raise ValueError(
                    "O setor de destino não pode estar dentro da árvore do setor excluído."
                )

        cur.execute("select count(1) from setores where setor_pai_id = %s", (setor_id,))
        filhos = int(cur.fetchone()[0] or 0)

        cur.execute("select count(1) from equipamentos where setor_id = %s", (setor_id,))
        equipamentos = int(cur.fetchone()[0] or 0)

        if exclusao_completa:
            arvore_ids = _coletar_descendentes(cur, setor_id)
            if not arvore_ids:
                raise ValueError("Nenhum setor encontrado para exclusão.")

            cur.execute(
                "select count(1) from equipamentos where setor_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            total_equipamentos_arvore = int(cur.fetchone()[0] or 0)

            # Evita violações transitórias de FK e deixa o delete mais previsível.
            cur.execute(
                "update equipamentos set setor_id = null where setor_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            cur.execute(
                "delete from vinculos_setor_responsavel where setor_id = any(%s::uuid[])",
                (arvore_ids,),
            )
            cur.execute(
                "update setores set setor_pai_id = null where id = any(%s::uuid[])",
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
                entidade_id=setor_id,
                valor_antigo={
                    "nome": atual[1],
                    "setor_pai_id": atual[2],
                    "filhos_diretos": filhos,
                    "equipamentos_diretos": equipamentos,
                    "setores_excluidos": arvore_ids,
                    "equipamentos_desvinculados": total_equipamentos_arvore,
                },
                valor_novo={"destino_setor_id": None, "exclusao_completa": True},
            )
            conn.commit()
            return True

        if filhos and not destino_setor_id:
            raise ValueError(
                "Este setor possui setores filhos. Informe um setor de destino antes de excluir ou marque exclusão completa."
            )
        if equipamentos and not destino_setor_id:
            raise ValueError(
                "Este setor possui equipamentos vinculados. Informe um setor de destino antes de excluir ou marque exclusão completa."
            )

        if destino_setor_id:
            cur.execute(
                "update setores set setor_pai_id = %s where setor_pai_id = %s",
                (destino_setor_id, setor_id),
            )
            cur.execute(
                "update equipamentos set setor_id = %s where setor_id = %s",
                (destino_setor_id, setor_id),
            )
            cur.execute(
                "update vinculos_setor_responsavel set setor_id = %s where setor_id = %s",
                (destino_setor_id, setor_id),
            )

        auditoria_service.registrar_no_conn(
            conn,
            acao="excluir_setor",
            entidade="setores",
            entidade_id=setor_id,
            valor_antigo={
                "nome": atual[1],
                "setor_pai_id": atual[2],
                "filhos": filhos,
                "equipamentos": equipamentos,
            },
            valor_novo={"destino_setor_id": destino_setor_id, "exclusao_completa": False},
        )
        cur.execute("delete from setores where id = %s", (setor_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
