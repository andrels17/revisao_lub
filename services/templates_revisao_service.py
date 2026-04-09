import streamlit as st

from database.connection import get_conn, release_conn
from services import cache_service


@st.cache_data(ttl=300, show_spinner=False)
def listar():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "select id, nome, tipo_controle, ativo from templates_revisao order by nome"
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "nome": r[1], "tipo_controle": r[2], "ativo": r[3]}
            for r in rows
        ]
    finally:
        release_conn(conn)


@st.cache_data(ttl=300, show_spinner=False)
def listar_com_etapas():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select t.id, t.nome, t.tipo_controle,
                   e.id as etapa_id, e.nome_etapa, e.gatilho_valor
            from templates_revisao t
            left join etapas_template_revisao e
                   on e.template_id = t.id and e.ativo = true
            where t.ativo = true
            order by t.nome, e.gatilho_valor
            """
        )
        rows = cur.fetchall()
        templates = {}
        for r in rows:
            tid = r[0]
            if tid not in templates:
                templates[tid] = {
                    "id": tid,
                    "nome": r[1],
                    "tipo_controle": r[2],
                    "etapas": [],
                }
            if r[3]:
                templates[tid]["etapas"].append(
                    {"id": r[3], "nome_etapa": r[4], "gatilho_valor": float(r[5])}
                )
        return list(templates.values())
    finally:
        release_conn(conn)


def criar(nome, tipo_controle, etapas=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "insert into templates_revisao (nome, tipo_controle) values (%s, %s) returning id",
            (nome, tipo_controle),
        )
        template_id = cur.fetchone()[0]
        for etapa in etapas or []:
            cur.execute(
                """
                insert into etapas_template_revisao (template_id, nome_etapa, gatilho_valor)
                values (%s, %s, %s)
                """,
                (template_id, etapa["nome_etapa"], etapa["gatilho_valor"]),
            )
        conn.commit()
        cache_service.invalidate_templates()
        return template_id
    finally:
        release_conn(conn)


def adicionar_etapa(template_id, nome_etapa, gatilho_valor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into etapas_template_revisao (template_id, nome_etapa, gatilho_valor)
            values (%s, %s, %s) returning id
            """,
            (template_id, nome_etapa, gatilho_valor),
        )
        etapa_id = cur.fetchone()[0]
        conn.commit()
        cache_service.invalidate_templates()
        return etapa_id
    finally:
        release_conn(conn)



def atualizar_template(template_id, nome, tipo_controle):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update templates_revisao
               set nome = %s,
                   tipo_controle = %s
             where id = %s
            """,
            (nome, tipo_controle, template_id),
        )
        conn.commit()
        cache_service.invalidate_templates()
    finally:
        release_conn(conn)


def atualizar_etapa(etapa_id, nome_etapa, gatilho_valor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update etapas_template_revisao
               set nome_etapa = %s,
                   gatilho_valor = %s
             where id = %s
            """,
            (nome_etapa, gatilho_valor, etapa_id),
        )
        conn.commit()
        cache_service.invalidate_templates()
    finally:
        release_conn(conn)
