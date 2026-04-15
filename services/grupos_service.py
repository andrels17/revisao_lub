from __future__ import annotations

from typing import Any
from uuid import uuid4

from database.connection import get_conn, release_conn
from services import auditoria_service


TABLE_NAME = "grupos"


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


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        select exists(
            select 1
              from information_schema.columns
             where table_schema = 'public'
               and table_name = %s
               and column_name = %s
        )
        """,
        (table_name, column_name),
    )
    return bool(cur.fetchone()[0])


def _ensure_schema(cur) -> None:
    if not _table_exists(cur, TABLE_NAME):
        cur.execute(
            """
            create table if not exists grupos (
                id uuid primary key,
                nome text not null,
                setor_id uuid null,
                ativo boolean not null default true,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
        cur.execute("create index if not exists idx_grupos_setor on grupos(setor_id)")
        cur.execute("create index if not exists idx_grupos_ativo on grupos(ativo)")

    if not _column_exists(cur, 'equipamentos', 'grupo_id'):
        cur.execute("alter table equipamentos add column if not exists grupo_id uuid")
        cur.execute("create index if not exists idx_equipamentos_grupo_id on equipamentos(grupo_id)")


def _buscar_grupo(cur, grupo_id: Any):
    gid = _to_id(grupo_id)
    if not gid:
        return None
    _ensure_schema(cur)
    cur.execute(
        """
        select g.id::text, g.nome, g.setor_id::text, coalesce(s.nome, '-') as setor_nome, coalesce(g.ativo, true)
          from grupos g
          left join setores s on s.id = g.setor_id
         where g.id = %s
        """,
        (gid,),
    )
    return cur.fetchone()


def _validar_nome(cur, nome: str, setor_id: Any, grupo_id_atual: Any = None):
    _ensure_schema(cur)
    nome = str(nome or '').strip()
    if not nome:
        raise ValueError('Informe o nome do grupo.')
    sid = _to_id(setor_id)
    gid = _to_id(grupo_id_atual)
    cur.execute(
        """
        select id::text
          from grupos
         where lower(trim(nome)) = lower(trim(%s))
           and (setor_id::text is not distinct from %s)
           and (%s is null or id::text <> %s)
         limit 1
        """,
        (nome, sid, gid, gid),
    )
    if cur.fetchone():
        raise ValueError('Já existe um grupo com esse nome neste departamento.')


def listar() -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_schema(cur)
        cur.execute(
            """
            select
                g.id::text,
                g.nome,
                g.setor_id::text,
                coalesce(s.nome, '-') as setor_nome,
                coalesce(g.ativo, true) as ativo,
                count(e.id) as total_equipamentos
            from grupos g
            left join setores s on s.id = g.setor_id
            left join equipamentos e on e.grupo_id = g.id
            group by g.id, g.nome, g.setor_id, s.nome, g.ativo
            order by coalesce(s.nome, ''), g.nome
            """
        )
        rows = cur.fetchall()
        return [
            {
                'id': r[0],
                'nome': r[1],
                'setor_id': r[2],
                'setor_nome': r[3],
                'ativo': bool(r[4]),
                'total_equipamentos': int(r[5] or 0),
            }
            for r in rows
        ]
    finally:
        release_conn(conn)


def criar(nome: str, setor_id=None, ativo: bool = True) -> str:
    nome = str(nome or '').strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_schema(cur)
        _validar_nome(cur, nome, setor_id)
        grupo_id = str(uuid4())
        cur.execute(
            """
            insert into grupos (id, nome, setor_id, ativo)
            values (%s::uuid, %s, %s, %s)
            returning id::text
            """,
            (grupo_id, nome, _to_id(setor_id), bool(ativo)),
        )
        grupo_id = cur.fetchone()[0]
        auditoria_service.registrar_no_conn(
            conn,
            acao='criar_grupo',
            entidade='grupos',
            entidade_id=grupo_id,
            valor_antigo=None,
            valor_novo={'nome': nome, 'setor_id': _to_id(setor_id), 'ativo': bool(ativo)},
        )
        conn.commit()
        return grupo_id
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def editar(grupo_id, nome: str, setor_id=None, ativo: bool = True) -> bool:
    gid = _to_id(grupo_id)
    nome = str(nome or '').strip()
    if not gid:
        raise ValueError('Grupo não informado.')
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_schema(cur)
        atual = _buscar_grupo(cur, gid)
        if not atual:
            raise ValueError('Grupo não encontrado.')
        _validar_nome(cur, nome, setor_id, grupo_id_atual=gid)
        cur.execute(
            """
            update grupos
               set nome = %s,
                   setor_id = %s,
                   ativo = %s,
                   updated_at = now()
             where id = %s
            """,
            (nome, _to_id(setor_id), bool(ativo), gid),
        )
        auditoria_service.registrar_no_conn(
            conn,
            acao='editar_grupo',
            entidade='grupos',
            entidade_id=gid,
            valor_antigo={'nome': atual[1], 'setor_id': atual[2], 'ativo': bool(atual[4])},
            valor_novo={'nome': nome, 'setor_id': _to_id(setor_id), 'ativo': bool(ativo)},
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def vincular_equipamentos(grupo_id, equipamento_ids: list[int]) -> int:
    gid = _to_id(grupo_id)
    eq_ids = sorted({int(x) for x in (equipamento_ids or []) if str(x).strip()})
    if not gid:
        raise ValueError('Grupo não informado.')
    if not eq_ids:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_schema(cur)
        atual = _buscar_grupo(cur, gid)
        if not atual:
            raise ValueError('Grupo não encontrado.')
        cur.execute(
            """
            update equipamentos
               set grupo_id = %s
             where id = any(%s::bigint[])
            """,
            (gid, eq_ids),
        )
        total = cur.rowcount or 0
        auditoria_service.registrar_no_conn(
            conn,
            acao='vincular_equipamentos_grupo',
            entidade='grupos',
            entidade_id=gid,
            valor_antigo=None,
            valor_novo={'equipamento_ids': eq_ids, 'total': total},
        )
        conn.commit()
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def excluir(grupo_id, desvincular_equipamentos: bool = True) -> bool:
    gid = _to_id(grupo_id)
    if not gid:
        raise ValueError('Grupo não informado.')
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_schema(cur)
        atual = _buscar_grupo(cur, gid)
        if not atual:
            raise ValueError('Grupo não encontrado.')
        cur.execute('select count(1) from equipamentos where grupo_id = %s', (gid,))
        total_eq = int(cur.fetchone()[0] or 0)
        if total_eq and not desvincular_equipamentos:
            raise ValueError('Este grupo possui equipamentos vinculados. Marque a opção para desvincular antes de excluir.')
        if total_eq:
            cur.execute('update equipamentos set grupo_id = null where grupo_id = %s', (gid,))
        cur.execute('delete from grupos where id = %s', (gid,))
        auditoria_service.registrar_no_conn(
            conn,
            acao='excluir_grupo',
            entidade='grupos',
            entidade_id=gid,
            valor_antigo={'nome': atual[1], 'setor_id': atual[2], 'ativo': bool(atual[4]), 'equipamentos': total_eq},
            valor_novo={'desvincular_equipamentos': bool(desvincular_equipamentos)},
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
