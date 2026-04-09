from __future__ import annotations

from typing import Any

from database.connection import get_conn, release_conn
from services import equipamentos_service, templates_lubrificacao_service, templates_revisao_service

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


DDL_VINCULOS = """
create table if not exists public.vinculos_templates_manutencao (
    id uuid primary key default gen_random_uuid(),
    template_revisao_id uuid not null references public.templates_revisao(id) on delete cascade,
    template_lubrificacao_id uuid not null references public.templates_lubrificacao(id) on delete cascade,
    observacoes text,
    ativo boolean not null default true,
    created_at timestamptz not null default now(),
    unique (template_revisao_id, template_lubrificacao_id)
);

create table if not exists public.vinculos_templates_manutencao_etapas (
    id uuid primary key default gen_random_uuid(),
    vinculo_id uuid not null references public.vinculos_templates_manutencao(id) on delete cascade,
    etapa_template_revisao_id text not null,
    aplicar_lubrificacao boolean not null default true,
    created_at timestamptz not null default now(),
    unique (vinculo_id, etapa_template_revisao_id)
);
""".strip()


def _close(conn) -> None:
    try:
        if conn and not conn.closed:
            release_conn(conn)
    except Exception:
        pass


def _eh_erro_estrutura(exc: Exception) -> bool:
    if not psycopg2:
        return False
    return isinstance(
        exc,
        (
            psycopg2.errors.UndefinedTable,
            psycopg2.errors.UndefinedColumn,
            psycopg2.errors.UndefinedObject,
            psycopg2.errors.InvalidSchemaName,
        ),
    )


def _id_key(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None



def listar_vinculos() -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                v.id,
                tr.id,
                tr.nome,
                tr.tipo_controle,
                tl.id,
                tl.nome,
                tl.tipo_controle,
                v.observacoes,
                coalesce(v.ativo, true) as ativo,
                v.created_at,
                count(e.id) filter (
                    where e.template_revisao_id = tr.id
                      and e.template_lubrificacao_id = tl.id
                      and coalesce(e.ativo, true) = true
                ) as equipamentos_vinculados
            from vinculos_templates_manutencao v
            join templates_revisao tr on tr.id = v.template_revisao_id
            join templates_lubrificacao tl on tl.id = v.template_lubrificacao_id
            left join equipamentos e on e.template_revisao_id = tr.id and e.template_lubrificacao_id = tl.id
            group by v.id, tr.id, tr.nome, tr.tipo_controle, tl.id, tl.nome, tl.tipo_controle, v.observacoes, v.ativo, v.created_at
            order by tr.nome, tl.nome
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "template_revisao_id": r[1],
                "template_revisao_nome": r[2],
                "tipo_controle": r[3],
                "template_lubrificacao_id": r[4],
                "template_lubrificacao_nome": r[5],
                "observacoes": r[7] or "",
                "ativo": bool(r[8]),
                "created_at": r[9],
                "equipamentos_vinculados": int(r[10] or 0),
            }
            for r in rows
        ]
    except Exception as exc:
        if _eh_erro_estrutura(exc):
            conn.rollback()
            return []
        raise
    finally:
        _close(conn)



def obter_vinculo_por_par(template_revisao_id: Any, template_lubrificacao_id: Any) -> dict[str, Any] | None:
    rev_key = _id_key(template_revisao_id)
    lub_key = _id_key(template_lubrificacao_id)
    if not rev_key or not lub_key:
        return None
    for vinculo in listar_vinculos():
        if _id_key(vinculo.get("template_revisao_id")) == rev_key and _id_key(vinculo.get("template_lubrificacao_id")) == lub_key:
            return vinculo
    return None



def salvar_vinculo(template_revisao_id: Any, template_lubrificacao_id: Any, observacoes: str | None = None) -> Any:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            insert into vinculos_templates_manutencao
                (template_revisao_id, template_lubrificacao_id, observacoes)
            values (%s, %s, %s)
            on conflict (template_revisao_id, template_lubrificacao_id)
            do update set
                observacoes = excluded.observacoes,
                ativo = true
            returning id
            """,
            (template_revisao_id, template_lubrificacao_id, observacoes),
        )
        vinculo_id = cur.fetchone()[0]
        conn.commit()
        return vinculo_id
    finally:
        _close(conn)



def listar_overrides_etapas(vinculo_id: Any) -> dict[str, bool]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select etapa_template_revisao_id, aplicar_lubrificacao
            from vinculos_templates_manutencao_etapas
            where vinculo_id = %s
            """,
            (vinculo_id,),
        )
        return {str(r[0]): bool(r[1]) for r in cur.fetchall()}
    except Exception as exc:
        if _eh_erro_estrutura(exc):
            conn.rollback()
            return {}
        raise
    finally:
        _close(conn)



def salvar_overrides_etapas(vinculo_id: Any, etapa_flags: dict[str, bool]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "delete from vinculos_templates_manutencao_etapas where vinculo_id = %s",
            (vinculo_id,),
        )
        for etapa_id, aplicar in (etapa_flags or {}).items():
            cur.execute(
                """
                insert into vinculos_templates_manutencao_etapas
                    (vinculo_id, etapa_template_revisao_id, aplicar_lubrificacao)
                values (%s, %s, %s)
                """,
                (vinculo_id, str(etapa_id), bool(aplicar)),
            )
        conn.commit()
    except Exception as exc:
        if _eh_erro_estrutura(exc):
            conn.rollback()
            raise RuntimeError(
                "A tabela de overrides por etapa ainda não existe. Rode o SQL de migração de vínculos novamente."
            ) from exc
        raise
    finally:
        _close(conn)



def analisar_compatibilidade(
    template_revisao: dict[str, Any] | None,
    template_lubrificacao: dict[str, Any] | None,
    etapa_overrides: dict[str, bool] | None = None,
) -> dict[str, Any]:
    if not template_revisao or not template_lubrificacao:
        return {"ok": False, "motivo": "Selecione um template de revisão e um de lubrificação."}

    tipo_rev = (template_revisao.get("tipo_controle") or "").lower()
    tipo_lub = (template_lubrificacao.get("tipo_controle") or "").lower()
    if tipo_rev != tipo_lub:
        return {
            "ok": False,
            "motivo": f"Os templates usam controles diferentes ({tipo_rev} x {tipo_lub}).",
        }

    etapa_overrides = {str(k): bool(v) for k, v in (etapa_overrides or {}).items()}
    etapas = sorted(template_revisao.get("etapas") or [], key=lambda x: float(x.get("gatilho_valor") or 0))
    itens = sorted(template_lubrificacao.get("itens") or [], key=lambda x: float(x.get("intervalo_valor") or 0))
    linhas: list[dict[str, Any]] = []
    total_match = 0
    total_itens_acionados = 0

    for etapa in etapas:
        etapa_id = str(etapa.get("id") or "")
        gatilho = float(etapa.get("gatilho_valor") or 0)
        itens_disparados = []
        for item in itens:
            intervalo = float(item.get("intervalo_valor") or 0)
            if intervalo > 0 and gatilho > 0 and abs(gatilho % intervalo) < 1e-9:
                itens_disparados.append(item)

        aplica_automatico = bool(itens_disparados)
        aplicar_lubrificacao = etapa_overrides.get(etapa_id, aplica_automatico)
        if aplicar_lubrificacao and itens_disparados:
            total_match += 1
            total_itens_acionados += len(itens_disparados)

        itens_acionados = [
            {
                "id": item.get("id"),
                "nome_item": item.get("nome_item") or "Item sem nome",
                "tipo_produto": item.get("tipo_produto") or "-",
                "intervalo_valor": float(item.get("intervalo_valor") or 0),
            }
            for item in itens_disparados
        ]
        itens_texto = ", ".join(
            f"{item.get('nome_item')} ({int(float(item.get('intervalo_valor') or 0))})"
            for item in itens_disparados
        ) or "—"

        linhas.append(
            {
                "etapa_id": etapa_id,
                "etapa": etapa.get("nome_etapa") or f"Etapa {int(gatilho)}",
                "gatilho_valor": gatilho,
                "aplica_automatico": aplica_automatico,
                "aplicar_lubrificacao": aplicar_lubrificacao,
                "dispara_lubrificacao": "Sim" if aplicar_lubrificacao else "Não",
                "itens_acionados": itens_texto,
                "itens_acionados_lista": itens_acionados,
                "todos_itens_template": [
                    {
                        "id": item.get("id"),
                        "nome_item": item.get("nome_item") or "Item sem nome",
                        "tipo_produto": item.get("tipo_produto") or "-",
                        "intervalo_valor": float(item.get("intervalo_valor") or 0),
                    }
                    for item in itens
                ],
                "qtd_itens": len(itens_disparados) if aplicar_lubrificacao else 0,
            }
        )

    return {
        "ok": True,
        "tipo_controle": tipo_rev,
        "linhas": linhas,
        "resumo": {
            "etapas": len(etapas),
            "itens": len(itens),
            "etapas_com_lubrificacao": total_match,
            "etapas_sem_lubrificacao": max(0, len(etapas) - total_match),
            "itens_acionados_total": total_itens_acionados,
            "cobertura": (total_match / len(etapas)) if etapas else 0.0,
        },
    }



def sugerir_vinculos_automaticos() -> list[dict[str, Any]]:
    revisoes = templates_revisao_service.listar_com_etapas()
    lubrificacoes = templates_lubrificacao_service.listar_com_itens()
    existentes = {
        (_id_key(v.get("template_revisao_id")), _id_key(v.get("template_lubrificacao_id")))
        for v in listar_vinculos()
    }

    melhores: dict[str, dict[str, Any]] = {}
    for revisao in revisoes:
        rev_id = _id_key(revisao.get("id"))
        if not rev_id:
            continue
        for lub in lubrificacoes:
            if (rev_id, _id_key(lub.get("id"))) in existentes:
                continue
            analise = analisar_compatibilidade(revisao, lub)
            if not analise.get("ok"):
                continue
            resumo = analise.get("resumo") or {}
            etapas_com_lub = int(resumo.get("etapas_com_lubrificacao") or 0)
            if etapas_com_lub <= 0:
                continue
            sugestao = {
                "template_revisao_id": revisao.get("id"),
                "template_revisao_nome": revisao.get("nome"),
                "template_lubrificacao_id": lub.get("id"),
                "template_lubrificacao_nome": lub.get("nome"),
                "tipo_controle": analise.get("tipo_controle") or revisao.get("tipo_controle"),
                "cobertura": float(resumo.get("cobertura") or 0.0),
                "etapas_com_lubrificacao": etapas_com_lub,
                "etapas": int(resumo.get("etapas") or 0),
                "itens": int(resumo.get("itens") or 0),
                "itens_acionados_total": int(resumo.get("itens_acionados_total") or 0),
                "analise": analise,
                "motivo": f"Compatível em {etapas_com_lub} de {int(resumo.get('etapas') or 0)} etapa(s).",
            }
            atual = melhores.get(rev_id)
            if not atual or (
                sugestao["cobertura"],
                sugestao["etapas_com_lubrificacao"],
                sugestao["itens_acionados_total"],
                sugestao["template_lubrificacao_nome"] or "",
            ) > (
                atual["cobertura"],
                atual["etapas_com_lubrificacao"],
                atual["itens_acionados_total"],
                atual["template_lubrificacao_nome"] or "",
            ):
                melhores[rev_id] = sugestao
    return sorted(melhores.values(), key=lambda x: (x["template_revisao_nome"] or "", -(x["cobertura"])))



def obter_mapa_vinculos_por_template_revisao() -> dict[str, dict[str, Any]]:
    return {
        key: v
        for v in listar_vinculos()
        if v.get("ativo", True) and (key := _id_key(v.get("template_revisao_id")))
    }



def obter_integracao_automatica_por_item(
    item: dict[str, Any],
    mapa_vinculos: dict[str, dict[str, Any]] | None = None,
    templates_lub: dict[str, dict[str, Any]] | None = None,
    cache_analises: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    mapa_vinculos = mapa_vinculos or obter_mapa_vinculos_por_template_revisao()
    templates_lub = templates_lub or {
        _id_key(t.get("id")): t for t in templates_lubrificacao_service.listar_com_itens() if _id_key(t.get("id"))
    }
    cache_analises = cache_analises if cache_analises is not None else {}

    template_rev_id = _id_key(item.get("template_id"))
    if not template_rev_id:
        return None

    vinculo = mapa_vinculos.get(template_rev_id)
    lub_template = None
    origem = "vinculo"
    etapa_overrides = None

    if vinculo:
        lub_template = templates_lub.get(_id_key(vinculo.get("template_lubrificacao_id")))
        etapa_overrides = listar_overrides_etapas(vinculo.get("id"))

    if not lub_template:
        equipamento = equipamentos_service.obter(item.get("equipamento_id")) or {}
        lub_equipment_id = _id_key(equipamento.get("template_lubrificacao_id"))
        if not lub_equipment_id:
            return None
        lub_template = templates_lub.get(lub_equipment_id)
        if not lub_template:
            return None
        vinculo = {
            "template_revisao_id": template_rev_id,
            "template_lubrificacao_id": lub_equipment_id,
            "template_lubrificacao_nome": lub_template.get("nome"),
            "equipamentos_vinculados": 1,
            "observacoes": "Integração automática usando os templates já associados ao equipamento.",
        }
        origem = "equipamento"
        etapa_overrides = None

    cache_key = (template_rev_id, _id_key(vinculo.get("template_lubrificacao_id")), str(item.get("etapa_id") or ""))
    analise = cache_analises.get(cache_key)
    if analise is None:
        revisao_stub = {
            "id": template_rev_id,
            "tipo_controle": item.get("tipo_controle"),
            "etapas": [{
                "id": item.get("etapa_id"),
                "nome_etapa": item.get("etapa"),
                "gatilho_valor": item.get("gatilho_valor"),
            }],
        }
        analise = analisar_compatibilidade(revisao_stub, lub_template, etapa_overrides=etapa_overrides)
        cache_analises[cache_key] = analise
    if not analise.get("ok"):
        return None
    linhas = analise.get("linhas") or []
    if not linhas:
        return None
    linha = linhas[0]
    return {
        "origem": origem,
        "template_lubrificacao_nome": vinculo.get("template_lubrificacao_nome") or lub_template.get("nome") or "Lubrificação vinculada",
        "equipamentos_vinculados": int(vinculo.get("equipamentos_vinculados") or 0),
        "observacoes": vinculo.get("observacoes") or "",
        "dispara": bool(linha.get("aplicar_lubrificacao")),
        "aplica_automatico": bool(linha.get("aplica_automatico")),
        "itens_acionados": linha.get("itens_acionados") or "—",
        "itens_acionados_lista": list(linha.get("itens_acionados_lista") or []),
        "todos_itens_template": list(linha.get("todos_itens_template") or []),
        "qtd_itens": int(linha.get("qtd_itens") or 0),
    }



def atualizar_vinculo(vinculo_id: Any, *, ativo: bool | None = None, observacoes: str | None = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        campos = []
        params = []
        if ativo is not None:
            campos.append("ativo = %s")
            params.append(bool(ativo))
        if observacoes is not None:
            campos.append("observacoes = %s")
            params.append(observacoes)
        if not campos:
            return
        params.append(vinculo_id)
        cur.execute(
            f"update vinculos_templates_manutencao set {', '.join(campos)} where id = %s",
            tuple(params),
        )
        conn.commit()
    finally:
        _close(conn)
