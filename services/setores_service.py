from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

from database.connection import get_conn, release_conn
from services import auditoria_service, escopo_service


BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1


def _is_uuid_like(value: Any) -> bool:
    if value is None:
        return False
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


def _normalizar_setor_id(value: Any, *, permitir_nulo: bool = False) -> str | None:
    if value is None:
        if permitir_nulo:
            return None
        raise ValueError("Setor não informado.")

    valor = str(value).strip()
    if not valor:
        if permitir_nulo:
            return None
        raise ValueError("Setor não informado.")

    if not _is_uuid_like(valor):
        raise ValueError(f"ID de setor inválido: {valor}")

    return valor



def _normalizar_id_generico(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    texto = str(value).strip()
    if not texto:
        return None

    if _is_uuid_like(texto):
        return texto

    if texto.lstrip("-").isdigit():
        numero = int(texto)
        if BIGINT_MIN <= numero <= BIGINT_MAX:
            return numero

    return texto



def _normalizar_lista_ids(valores: Iterable[Any] | None) -> list[Any]:
    vistos = set()
    saida = []

    for valor in valores or []:
        normalizado = _normalizar_id_generico(valor)
        if normalizado is None:
            continue
        chave = str(normalizado)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(normalizado)

    return saida



def _coletar_descendentes(cur, setor_id: str) -> list[str]:
    raiz = _normalizar_setor_id(setor_id)
    pendentes = [raiz]
    vistos = set()
    ordem = []

    while pendentes:
        atual = pendentes.pop()
        if atual in vistos:
            continue

        vistos.add(atual)
        ordem.append(atual)

        cur.execute("select id from setores where setor_pai_id = %s", (atual,))
        filhos = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]

        for filho_id in filhos:
            if filho_id not in vistos:
                pendentes.append(filho_id)

    return ordem



def _contar_filhos_diretos(cur, setor_id: str) -> int:
    cur.execute("select count(1) from setores where setor_pai_id = %s", (setor_id,))
    return int(cur.fetchone()[0] or 0)



def _contar_equipamentos_diretos(cur, setor_id: str) -> int:
    cur.execute("select count(1) from equipamentos where setor_id = %s", (setor_id,))
    return int(cur.fetchone()[0] or 0)



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
        rows = cur.fetchall()
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
    nome = str(nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do setor.")

    setor_pai_id = _normalizar_setor_id(setor_pai_id, permitir_nulo=True)

    conn = get_conn()
    cur = conn.cursor()
    try:
        if setor_pai_id:
            cur.execute("select id from setores where id = %s", (setor_pai_id,))
            if not cur.fetchone():
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



def vincular_equipamentos(setor_id, equipamento_ids: list[Any]):
    setor_id = _normalizar_setor_id(setor_id)
    equipamento_ids_norm = _normalizar_lista_ids(equipamento_ids)
    if not equipamento_ids_norm:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome from setores where id = %s", (setor_id,))
        setor = cur.fetchone()
        if not setor:
            raise ValueError("Setor não encontrado.")

        cur.execute(
            """
            update equipamentos
               set setor_id = %s
             where id = any(%s)
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
    setor_id = _normalizar_setor_id(setor_id)
    destino_setor_id = _normalizar_setor_id(destino_setor_id, permitir_nulo=True)

    if exclusao_completa and destino_setor_id:
        raise ValueError("Escolha apenas uma opção: exclusão completa ou mover para setor de destino.")

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

        filhos = _contar_filhos_diretos(cur, setor_id)
        equipamentos = _contar_equipamentos_diretos(cur, setor_id)
        arvore_ids = _coletar_descendentes(cur, setor_id)
        arvore_ids_set = set(arvore_ids)

        if destino_setor_id:
            if destino_setor_id == setor_id:
                raise ValueError("O setor de destino deve ser diferente do setor excluído.")

            cur.execute("select id from setores where id = %s", (destino_setor_id,))
            if not cur.fetchone():
                raise ValueError("Setor de destino não encontrado.")

            if destino_setor_id in arvore_ids_set:
                raise ValueError(
                    "O setor de destino não pode ser o próprio setor excluído nem um de seus descendentes."
                )

        if exclusao_completa:
            cur.execute(
                "select count(1) from equipamentos where setor_id = any(%s)",
                (arvore_ids,),
            )
            total_equipamentos_arvore = int(cur.fetchone()[0] or 0)

            cur.execute(
                "update equipamentos set setor_id = null where setor_id = any(%s)",
                (arvore_ids,),
            )
            cur.execute(
                "delete from vinculos_setor_responsavel where setor_id = any(%s)",
                (arvore_ids,),
            )
            cur.execute(
                "update setores set setor_pai_id = null where id = any(%s)",
                (arvore_ids,),
            )
            cur.execute("delete from setores where id = any(%s)", (arvore_ids,))

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
                "setores_na_arvore": len(arvore_ids),
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
