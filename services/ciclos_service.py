from __future__ import annotations

from pathlib import Path

import datetime as dt
from typing import Any

import streamlit as st
from psycopg2.extras import RealDictCursor

from database.connection import get_conn, release_conn
from services import lubrificacoes_service, revisoes_service


TIPOS_CICLO = {
    "geral": "Geral",
    "revisao": "Revisão",
    "lubrificacao": "Lubrificação",
}


@st.cache_data(ttl=120, show_spinner=False)
def diagnostico_schema() -> dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            select table_name
              from information_schema.tables
             where table_schema = 'public'
               and table_name in ('ciclos_operacionais', 'ciclos_snapshot', 'execucoes_manutencao', 'execucoes_lubrificacao', 'leituras')
            """
        )
        tabelas = {r['table_name'] for r in cur.fetchall()}
        cur.execute(
            """
            select table_name, column_name
              from information_schema.columns
             where table_schema = 'public'
               and table_name in ('execucoes_manutencao', 'execucoes_lubrificacao', 'leituras')
               and column_name = 'ciclo_id'
            """
        )
        colunas = {(r['table_name'], r['column_name']) for r in cur.fetchall()}
        return {
            'tabelas': tabelas,
            'tem_ciclos': 'ciclos_operacionais' in tabelas,
            'tem_snapshot': 'ciclos_snapshot' in tabelas,
            'tem_execucoes_manutencao': 'execucoes_manutencao' in tabelas,
            'tem_execucoes_lubrificacao': 'execucoes_lubrificacao' in tabelas,
            'tem_leituras': 'leituras' in tabelas,
            'tem_ciclo_exec_manut': ('execucoes_manutencao', 'ciclo_id') in colunas,
            'tem_ciclo_exec_lub': ('execucoes_lubrificacao', 'ciclo_id') in colunas,
            'tem_ciclo_leituras': ('leituras', 'ciclo_id') in colunas,
        }
    finally:
        release_conn(conn)


@st.cache_data(ttl=120, show_spinner=False)
def listar_ciclos(limite: int = 50) -> list[dict[str, Any]]:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return []
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            select co.id::text,
                   co.tipo,
                   co.titulo,
                   co.data_inicio,
                   co.data_fim,
                   co.status,
                   co.criado_em,
                   co.fechado_em,
                   co.criado_por::text,
                   co.fechado_por::text,
                   co.observacoes
              from public.ciclos_operacionais co
             order by co.data_inicio desc, co.criado_em desc
             limit %s
            """,
            (limite,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        release_conn(conn)


@st.cache_data(ttl=120, show_spinner=False)
def obter_ciclo_aberto(tipo: str | None = None) -> dict[str, Any] | None:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return None
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if tipo:
            cur.execute(
                """
                select id::text, tipo, titulo, data_inicio, data_fim, status, criado_em, observacoes
                  from public.ciclos_operacionais
                 where status = 'aberto' and tipo = %s
                 order by data_inicio desc, criado_em desc
                 limit 1
                """,
                (tipo,),
            )
        else:
            cur.execute(
                """
                select id::text, tipo, titulo, data_inicio, data_fim, status, criado_em, observacoes
                  from public.ciclos_operacionais
                 where status = 'aberto'
                 order by data_inicio desc, criado_em desc
                 limit 1
                """
            )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)


def _intervalo_semana_base(ref: dt.date | None = None) -> tuple[dt.date, dt.date]:
    ref = ref or dt.date.today()
    inicio = ref - dt.timedelta(days=ref.weekday())
    fim = inicio + dt.timedelta(days=6)
    return inicio, fim


def intervalo_semana_sugerido(ref: dt.date | None = None) -> tuple[dt.date, dt.date]:
    return _intervalo_semana_base(ref)


def titulo_padrao(tipo: str, inicio: dt.date, fim: dt.date) -> str:
    semana_iso = inicio.isocalendar().week
    nome = TIPOS_CICLO.get(tipo, tipo.title())
    return f"{nome} · Semana {semana_iso:02d} · {inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"


def abrir_ciclo(*, tipo: str, data_inicio: dt.date, data_fim: dt.date, criado_por: str | None = None, titulo: str | None = None, observacoes: str | None = None) -> tuple[bool, str, str | None]:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return False, 'A tabela public.ciclos_operacionais ainda não existe. Rode o SQL de migração primeiro.', None

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            select id::text, tipo, data_inicio, data_fim
              from public.ciclos_operacionais
             where status = 'aberto'
               and tipo = %s
             order by data_inicio desc
             limit 1
            """,
            (tipo,),
        )
        aberto = cur.fetchone()
        if aberto:
            return False, f"Já existe um ciclo aberto de {TIPOS_CICLO.get(tipo, tipo)}.", aberto['id']

        cur.execute(
            """
            insert into public.ciclos_operacionais (tipo, titulo, data_inicio, data_fim, status, criado_por, observacoes)
            values (%s, %s, %s, %s, 'aberto', %s::uuid, %s)
            returning id::text
            """,
            (tipo, titulo or titulo_padrao(tipo, data_inicio, data_fim), data_inicio, data_fim, criado_por or None, observacoes or None),
        )
        ciclo_id = cur.fetchone()['id']
        conn.commit()
        limpar_cache()
        return True, 'Ciclo aberto com sucesso.', ciclo_id
    except Exception as exc:
        conn.rollback()
        return False, f'Erro ao abrir ciclo: {exc}', None
    finally:
        release_conn(conn)


def _contar_execucoes(cur, tabela: str, campo_tipo: str | None, ciclo_id: str, tipo_valor: str | None = None) -> int:
    where_tipo = f' and {campo_tipo} = %s' if campo_tipo and tipo_valor else ''
    params: list[Any] = [ciclo_id]
    if tipo_valor:
        params.append(tipo_valor)
    cur.execute(f"select count(*) as total from public.{tabela} where ciclo_id = %s{where_tipo}", params)
    return int(cur.fetchone()['total'] or 0)


def resumo_ciclo(ciclo_id: str) -> dict[str, Any]:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return {}

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            select id::text, tipo, titulo, data_inicio, data_fim, status, criado_em, fechado_em, observacoes
              from public.ciclos_operacionais
             where id = %s::uuid
            """,
            (ciclo_id,),
        )
        ciclo = cur.fetchone()
        if not ciclo:
            return {}

        total_exec = 0
        total_rev = 0
        total_lub = 0
        total_leit = 0

        if diag.get('tem_execucoes_manutencao') and diag.get('tem_ciclo_exec_manut'):
            total_exec += _contar_execucoes(cur, 'execucoes_manutencao', None, ciclo_id)
            total_rev = _contar_execucoes(cur, 'execucoes_manutencao', 'tipo', ciclo_id, 'revisao')
            total_lub += _contar_execucoes(cur, 'execucoes_manutencao', 'tipo', ciclo_id, 'lubrificacao')

        if diag.get('tem_execucoes_lubrificacao') and diag.get('tem_ciclo_exec_lub'):
            total_lub_extra = _contar_execucoes(cur, 'execucoes_lubrificacao', None, ciclo_id)
            total_lub = max(total_lub, total_lub_extra)

        if diag.get('tem_leituras') and diag.get('tem_ciclo_leituras'):
            total_leit = _contar_execucoes(cur, 'leituras', None, ciclo_id)

        resumo = {
            **dict(ciclo),
            'total_execucoes': total_exec,
            'total_revisoes': total_rev,
            'total_lubrificacoes': total_lub,
            'total_leituras': total_leit,
            'total_vencidos': 0,
            'total_proximos': 0,
            'total_em_dia': 0,
            'total_realizados': 0,
        }

        try:
            revisoes = revisoes_service.listar_controle_revisoes() or []
            resumo['total_vencidos'] += sum(1 for item in revisoes if item.get('status') == 'VENCIDO')
            resumo['total_proximos'] += sum(1 for item in revisoes if item.get('status') == 'PROXIMO')
            resumo['total_em_dia'] += sum(1 for item in revisoes if item.get('status') == 'EM DIA')
            resumo['total_realizados'] += sum(1 for item in revisoes if item.get('status') == 'REALIZADO')
        except Exception:
            pass

        try:
            if hasattr(lubrificacoes_service, 'listar_controle_lubrificacoes'):
                lubs = lubrificacoes_service.listar_controle_lubrificacoes() or []
                resumo['total_vencidos'] += sum(1 for item in lubs if item.get('status') == 'VENCIDO')
                resumo['total_proximos'] += sum(1 for item in lubs if item.get('status') == 'PROXIMO')
                resumo['total_em_dia'] += sum(1 for item in lubs if item.get('status') == 'EM DIA')
                resumo['total_realizados'] += sum(1 for item in lubs if item.get('status') == 'REALIZADO')
        except Exception:
            pass

        return resumo
    finally:
        release_conn(conn)


def fechar_ciclo(ciclo_id: str, fechado_por: str | None = None, observacoes: str | None = None) -> tuple[bool, str]:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return False, 'A tabela public.ciclos_operacionais ainda não existe.'

    resumo = resumo_ciclo(ciclo_id)
    if not resumo:
        return False, 'Ciclo não encontrado.'

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            update public.ciclos_operacionais
               set status = 'fechado',
                   fechado_em = now(),
                   fechado_por = %s::uuid,
                   observacoes = coalesce(%s, observacoes)
             where id = %s::uuid
            """,
            (fechado_por or None, observacoes or None, ciclo_id),
        )

        if diag.get('tem_snapshot'):
            cur.execute(
                """
                insert into public.ciclos_snapshot (
                    ciclo_id, total_execucoes, total_revisoes, total_lubrificacoes, total_leituras,
                    total_vencidos, total_proximos, total_em_dia, total_realizados, payload
                ) values (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    ciclo_id,
                    int(resumo.get('total_execucoes', 0)),
                    int(resumo.get('total_revisoes', 0)),
                    int(resumo.get('total_lubrificacoes', 0)),
                    int(resumo.get('total_leituras', 0)),
                    int(resumo.get('total_vencidos', 0)),
                    int(resumo.get('total_proximos', 0)),
                    int(resumo.get('total_em_dia', 0)),
                    int(resumo.get('total_realizados', 0)),
                    __import__('json').dumps(resumo),
                ),
            )

        conn.commit()
        limpar_cache()
        return True, 'Ciclo fechado com sucesso.'
    except Exception as exc:
        conn.rollback()
        return False, f'Erro ao fechar ciclo: {exc}'
    finally:
        release_conn(conn)


def reabrir_ciclo(ciclo_id: str, usuario_id: str | None = None) -> tuple[bool, str]:
    diag = diagnostico_schema()
    if not diag.get('tem_ciclos'):
        return False, 'A tabela public.ciclos_operacionais ainda não existe.'
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update public.ciclos_operacionais
               set status = 'aberto',
                   fechado_em = null,
                   fechado_por = null,
                   observacoes = coalesce(observacoes, '') || case when %s is not null then E'
Reaberto por ' || %s else '' end
             where id = %s::uuid
            """,
            (usuario_id, usuario_id, ciclo_id),
        )
        conn.commit()
        limpar_cache()
        return True, 'Ciclo reaberto com sucesso.'
    except Exception as exc:
        conn.rollback()
        return False, f'Erro ao reabrir ciclo: {exc}'
    finally:
        release_conn(conn)


def obter_ciclo_id_para_registro(tipo: str) -> str | None:
    """Retorna o ciclo aberto mais aderente para o tipo de registro.

    Prioridade: ciclo aberto do mesmo tipo; depois um ciclo geral.
    Só retorna se a tabela e a coluna de destino existirem.
    """
    try:
        ciclo = obter_ciclo_aberto(tipo)
        if ciclo:
            return ciclo.get('id')
        ciclo = obter_ciclo_aberto('geral')
        return ciclo.get('id') if ciclo else None
    except Exception:
        return None


def tabela_tem_ciclo_id(nome_tabela: str) -> bool:
    diag = diagnostico_schema()
    mapa = {
        'execucoes_manutencao': diag.get('tem_ciclo_exec_manut'),
        'execucoes_lubrificacao': diag.get('tem_ciclo_exec_lub'),
        'leituras': diag.get('tem_ciclo_leituras'),
    }
    return bool(mapa.get(nome_tabela))


def sql_migracao() -> str:
    return (
        __import__('pathlib').Path(__file__).resolve().parents[1] / 'database' / 'ciclos_operacionais.sql'
    ).read_text(encoding='utf-8')


def limpar_cache() -> None:
    for fn in (diagnostico_schema, listar_ciclos, obter_ciclo_aberto):
        try:
            fn.clear()
        except Exception:
            pass
