from __future__ import annotations

from database.connection import get_conn, release_conn


class ValidacaoNegocioError(ValueError):
    pass


class ConfirmacaoNecessariaError(ValidacaoNegocioError):
    pass


def obter_equipamento_contexto(equipamento_id) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select
                e.id,
                e.codigo,
                e.nome,
                coalesce(e.km_atual, 0),
                coalesce(e.horas_atual, 0),
                e.template_revisao_id,
                e.template_lubrificacao_id,
                coalesce(s.nome, '-') as setor_nome
            from equipamentos e
            left join setores s on s.id = e.setor_id
            where e.id = %s
            """,
            (equipamento_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "codigo": row[1],
            "nome": row[2],
            "km_atual": float(row[3] or 0),
            "horas_atual": float(row[4] or 0),
            "template_revisao_id": row[5],
            "template_lubrificacao_id": row[6],
            "setor_nome": row[7],
        }
    finally:
        release_conn(conn)


def validar_leitura(equipamento_id, tipo_leitura: str, km_valor=None, horas_valor=None, permitir_regressao: bool = False):
    eqp = obter_equipamento_contexto(equipamento_id)
    if not eqp:
        raise ValidacaoNegocioError("Equipamento não encontrado.")

    erros = []
    if tipo_leitura in ("km", "ambos") and km_valor is not None and float(km_valor) < float(eqp["km_atual"]):
        erros.append(f"KM informado ({float(km_valor):.0f}) menor que o atual ({float(eqp['km_atual']):.0f}).")
    if tipo_leitura in ("horas", "ambos") and horas_valor is not None and float(horas_valor) < float(eqp["horas_atual"]):
        erros.append(f"Horas informadas ({float(horas_valor):.0f}) menores que as atuais ({float(eqp['horas_atual']):.0f}).")

    if erros and not permitir_regressao:
        raise ValidacaoNegocioError(" ".join(erros))
    return eqp


def validar_execucao_revisao(equipamento_id, data_execucao, km_execucao=None, horas_execucao=None, observacoes=None, status="concluida"):
    eqp = obter_equipamento_contexto(equipamento_id)
    if not eqp:
        raise ValidacaoNegocioError("Equipamento não encontrado.")
    if not eqp.get("template_revisao_id"):
        raise ValidacaoNegocioError("Equipamento sem template de revisão configurado.")

    km = float(km_execucao or 0)
    horas = float(horas_execucao or 0)
    if km <= 0 and horas <= 0:
        raise ValidacaoNegocioError("Informe KM ou horas da execução.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        # Verifica duplicata por janela de 2 minutos com mesmos dados principais.
        # Observações são intencionalmente excluídas da comparação para evitar
        # falsos positivos causados por reruns do Streamlit ou variações de texto.
        cur.execute(
            """
            select 1
            from execucoes_manutencao
            where equipamento_id = %s
              and tipo = 'revisao'
              and data_execucao = %s
              and coalesce(km_execucao, 0) = %s
              and coalesce(horas_execucao, 0) = %s
              and coalesce(status, 'concluida') = %s
              and created_at >= NOW() - INTERVAL '2 minutes'
            limit 1
            """,
            (equipamento_id, data_execucao, km, horas, status or "concluida"),
        )
        if cur.fetchone():
            raise ValidacaoNegocioError(
                "Essa revisão já foi registrada agora mesmo. "
                "Aguarde alguns instantes antes de registrar novamente."
            )
    except ValidacaoNegocioError:
        raise
    except Exception:
        # Se created_at não existir no schema, faz checagem simples sem janela de tempo
        try:
            conn.rollback()
        except Exception:
            pass
        conn2 = get_conn()
        cur2 = conn2.cursor()
        try:
            cur2.execute(
                """
                select 1
                from execucoes_manutencao
                where equipamento_id = %s
                  and tipo = 'revisao'
                  and data_execucao = %s
                  and coalesce(km_execucao, 0) = %s
                  and coalesce(horas_execucao, 0) = %s
                  and coalesce(status, 'concluida') = %s
                limit 1
                """,
                (equipamento_id, data_execucao, km, horas, status or "concluida"),
            )
            if cur2.fetchone():
                raise ValidacaoNegocioError(
                    "Já existe uma execução de revisão idêntica para este equipamento."
                )
        finally:
            release_conn(conn2)
    finally:
        release_conn(conn)
    return eqp


def validar_execucao_lubrificacao(equipamento_id, item_id, data_execucao, km_execucao=None, horas_execucao=None):
    eqp = obter_equipamento_contexto(equipamento_id)
    if not eqp:
        raise ValidacaoNegocioError("Equipamento não encontrado.")
    if not eqp.get("template_lubrificacao_id"):
        raise ValidacaoNegocioError("Equipamento sem template de lubrificação configurado.")

    km    = float(km_execucao or 0)
    horas = float(horas_execucao or 0)

    conn = get_conn()
    cur  = conn.cursor()
    try:
        # Verifica duplicata com janela de 2 minutos — protege contra duplo-clique.
        # Se a tabela ainda não existir no schema, ignora a verificação e prossegue.
        try:
            cur.execute(
                """
                select 1
                from execucoes_lubrificacao
                where equipamento_id = %s
                  and coalesce(item_id, 0) = coalesce(%s, 0)
                  and data_execucao = %s
                  and coalesce(km_execucao, 0) = %s
                  and coalesce(horas_execucao, 0) = %s
                  and created_at >= NOW() - INTERVAL '2 minutes'
                limit 1
                """,
                (equipamento_id, item_id, data_execucao, km, horas),
            )
            if cur.fetchone():
                raise ValidacaoNegocioError(
                    "Essa lubrificação já foi registrada agora mesmo. "
                    "Aguarde alguns instantes antes de registrar novamente."
                )
        except ValidacaoNegocioError:
            raise
        except Exception:
            # Tabela não existe ou coluna created_at ausente — tenta sem janela de tempo
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                cur.execute(
                    """
                    select 1
                    from execucoes_lubrificacao
                    where equipamento_id = %s
                      and coalesce(item_id, 0) = coalesce(%s, 0)
                      and data_execucao = %s
                      and coalesce(km_execucao, 0) = %s
                      and coalesce(horas_execucao, 0) = %s
                    limit 1
                    """,
                    (equipamento_id, item_id, data_execucao, km, horas),
                )
                if cur.fetchone():
                    raise ValidacaoNegocioError(
                        "Já existe uma execução de lubrificação idêntica para este item/equipamento."
                    )
            except ValidacaoNegocioError:
                raise
            except Exception:
                # Tabela execucoes_lubrificacao não existe ainda — permite prosseguir;
                # o service de lubrificação criará a tabela ao inserir.
                pass
    finally:
        release_conn(conn)
    return eqp
