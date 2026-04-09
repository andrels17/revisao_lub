from __future__ import annotations

from database.connection import get_conn, release_conn
from services import auditoria_service, auth_service


def garantir_tabela():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            create extension if not exists pgcrypto;
            create table if not exists comentarios_equipamento (
                id uuid primary key default gen_random_uuid(),
                equipamento_id uuid not null references equipamentos(id) on delete cascade,
                usuario_id uuid null,
                autor_nome text,
                comentario text not null,
                created_at timestamptz not null default now()
            );
            create index if not exists idx_comentarios_equipamento_eqp
                on comentarios_equipamento (equipamento_id, created_at desc);
            """
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        release_conn(conn)


def _autor_atual() -> tuple[str | None, str | None]:
    usuario = auth_service.usuario_logado() or {}
    return usuario.get('id'), usuario.get('nome')


def listar_por_equipamento(equipamento_id: str, limite: int = 50) -> list[dict]:
    garantir_tabela()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select id::text, equipamento_id::text, usuario_id::text, coalesce(autor_nome, 'Usuário') as autor_nome,
                   comentario, created_at
            from comentarios_equipamento
            where equipamento_id = %s::uuid
            order by created_at desc
            limit %s
            """,
            (equipamento_id, limite),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        release_conn(conn)


def criar(equipamento_id: str, comentario: str) -> tuple[bool, str]:
    texto = (comentario or '').strip()
    if not texto:
        return False, 'Digite um comentário antes de salvar.'

    garantir_tabela()
    usuario_id, autor_nome = _autor_atual()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into comentarios_equipamento (equipamento_id, usuario_id, autor_nome, comentario)
            values (%s::uuid, %s::uuid, %s, %s)
            returning id::text, created_at
            """,
            (equipamento_id, usuario_id, autor_nome, texto),
        )
        row = cur.fetchone()
        auditoria_service.registrar_no_conn(
            conn,
            'comentario',
            'equipamento',
            entidade_id=equipamento_id,
            valor_novo={'comentario_id': row[0] if row else None, 'comentario': texto},
        )
        conn.commit()
        return True, 'Comentário registrado com sucesso.'
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f'Erro ao registrar comentário: {exc}'
    finally:
        release_conn(conn)
