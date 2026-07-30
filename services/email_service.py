"""Serviço de envio de e-mail via SMTP.

Configuração em .streamlit/secrets.toml:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = "seu@email.com"
    SMTP_PASS = "sua_senha_de_app"
    SMTP_FROM = "seu@email.com"  # opcional, usa SMTP_USER se omitido
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import streamlit as st


def _get_smtp_config() -> dict[str, Any] | None:
    """Lê configurações SMTP do secrets.toml. Retorna None se não configurado."""
    try:
        secrets = st.secrets
        host = secrets.get("SMTP_HOST")
        if not host:
            return None
        return {
            "host": host,
            "port": int(secrets.get("SMTP_PORT", 587)),
            "user": secrets.get("SMTP_USER", ""),
            "password": secrets.get("SMTP_PASS", ""),
            "from_addr": secrets.get("SMTP_FROM") or secrets.get("SMTP_USER", ""),
        }
    except Exception:
        return None


def email_configurado() -> bool:
    """Verifica se o e-mail está configurado no secrets."""
    return _get_smtp_config() is not None


def enviar_email(
    destinatario: str,
    assunto: str,
    corpo_html: str,
    corpo_texto: str = "",
    anexos: list[tuple[bytes, str]] | None = None,
) -> tuple[bool, str]:
    """
    Envia um e-mail via SMTP, opcionalmente com anexos.
    `anexos`: lista de tuplas (bytes_do_arquivo, nome_do_arquivo.pdf).
    Retorna (sucesso: bool, mensagem: str).
    """
    config = _get_smtp_config()
    if not config:
        return False, "Envio de e-mail não configurado. Adicione SMTP_HOST ao secrets.toml."

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = assunto
        msg["From"] = config["from_addr"]
        msg["To"] = destinatario

        corpo = MIMEMultipart("alternative")
        if corpo_texto:
            corpo.attach(MIMEText(corpo_texto, "plain", "utf-8"))
        corpo.attach(MIMEText(corpo_html, "html", "utf-8"))
        msg.attach(corpo)

        for conteudo, nome_arquivo in (anexos or []):
            parte = MIMEApplication(conteudo, _subtype="pdf")
            parte.add_header("Content-Disposition", "attachment", filename=nome_arquivo)
            msg.attach(parte)

        context = ssl.create_default_context()
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(config["user"], config["password"])
            server.sendmail(config["from_addr"], destinatario, msg.as_string())

        return True, "E-mail enviado com sucesso."
    except smtplib.SMTPAuthenticationError as e:
        detalhe = ""
        try:
            detalhe = e.smtp_error.decode("utf-8", errors="ignore")
        except Exception:
            detalhe = str(e)
        return False, f"Falha na autenticação SMTP. Verifique SMTP_USER e SMTP_PASS. Detalhe do servidor: {detalhe}"
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {e}"


def _cor_emoji_texto_item(item: dict) -> tuple[str, str, str]:
    """Retorna (cor_hex, emoji, texto_situação) para um item do resumo consolidado."""
    status = str(item.get("status") or "-").upper()
    realizado = bool(item.get("realizado"))
    unidade = item.get("unidade", "km")
    falta = float(item.get("falta", 0) or 0)
    if realizado:
        vencimento = float(item.get("vencimento", 0) or 0)
        txt = f"realizado — próxima em {vencimento:.0f} {unidade}" if vencimento > 0 else "realizado neste ciclo"
        return "#22c55e", "✓", txt
    if status == "VENCIDO":
        return "#ef4444", "▶", f"vencido há {abs(falta):.0f} {unidade}"
    if status == "PROXIMO":
        return "#f59e0b", "◎", f"faltam {falta:.0f} {unidade}"
    if status in ("SEM_BASE", "SEM BASE"):
        return "#8b5cf6", "★", "aguardando 1ª execução"
    return "#64748b", "○", (f"faltam {falta:.0f} {unidade}" if falta > 0 else "em dia")


def _linha_badge_html(item: dict) -> str:
    cor, emoji, txt = _cor_emoji_texto_item(item)
    nome = item.get("nome", "-")
    return f"""
    <tr>
      <td style="padding:7px 0;border-bottom:1px solid rgba(255,255,255,.08);">
        <span style="display:inline-block;width:18px;height:18px;line-height:18px;text-align:center;
            border-radius:50%;background:{cor};color:#fff;font-size:10px;font-weight:bold;margin-right:8px;">{emoji}</span>
        <span style="color:#e8f1ff;font-weight:600;font-size:13px;">{nome}</span>
      </td>
      <td style="padding:7px 0;border-bottom:1px solid rgba(255,255,255,.08);text-align:right;
          color:{cor};font-size:12px;font-weight:600;white-space:nowrap;">{txt}</td>
    </tr>"""


def montar_html_resumo_equipamento(equipamento: dict, itens: list[dict], responsavel_nome: str) -> tuple[str, str]:
    """HTML de e-mail com os itens que precisam de atenção de um equipamento —
    versão "sob demanda" a partir da tela de Alertas. Itens em dia/realizados
    entram só na contagem, não poluem a lista."""
    from services.alertas_service import priorizar_itens

    eqp_label = f"{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}"
    criticos, sem_pendencia = priorizar_itens(itens)

    if criticos:
        linhas_html = "".join(_linha_badge_html(i) for i in criticos)
    else:
        linhas_html = "<tr><td style='color:#86efac;padding:8px 0;font-size:13px;'>✅ Nenhuma pendência — todos os itens estão em dia.</td></tr>"

    rodape_contagem = (
        f'<p style="color:#7fa8cc;font-size:12px;margin:10px 0 0;">+ {sem_pendencia} item(ns) em dia, sem necessidade de ação agora.</p>'
        if sem_pendencia else ""
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1929;color:#e8f1ff;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1e3a5f,#0d1929);padding:24px 28px;">
        <h2 style="margin:0;color:#fff;font-size:20px;">📋 Resumo de Manutenção</h2>
        <p style="margin:8px 0 0;color:#9db0c7;font-size:14px;">{eqp_label}</p>
      </div>
      <div style="padding:24px 28px;">
        <p style="color:#c8dcf4;">Olá, <strong style="color:#fff;">{responsavel_nome}</strong>.</p>
        <p style="color:#9db0c7;font-size:13px;">Itens que precisam de atenção:</p>
        <table style="width:100%;border-collapse:collapse;margin-top:6px;">{linhas_html}</table>
        {rodape_contagem}
      </div>
    </div>
    """
    texto = f"Resumo de manutenção - {eqp_label}\n\n" + (
        "\n".join(f"{i.get('nome', '-')}: {_cor_emoji_texto_item(i)[2]}" for i in criticos)
        if criticos else "Nenhuma pendência — todos os itens estão em dia."
    )
    return html, texto


def montar_html_resumo_proximos_servicos(responsavel_nome: str, itens_criticos: list[dict], sem_pendencia: int, total_equipamentos: int) -> tuple[str, str]:
    """HTML consolidado com os serviços mais próximos/urgentes de TODOS os
    equipamentos de um responsável — usado no resumo semanal automático.
    Substitui a listagem exaustiva de cada item de cada equipamento por um
    resumo focado no que realmente precisa de ação."""
    if itens_criticos:
        linhas_html = "".join(f"""
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.08);">
            <span style="display:inline-block;width:18px;height:18px;line-height:18px;text-align:center;
                border-radius:50%;background:{_cor_emoji_texto_item(i)[0]};color:#fff;font-size:10px;font-weight:bold;margin-right:8px;">{_cor_emoji_texto_item(i)[1]}</span>
            <span style="color:#e8f1ff;font-weight:600;font-size:13px;">{i.get('nome', '-')}</span><br>
            <span style="color:#7fa8cc;font-size:11px;margin-left:26px;">{i.get('equipamento', '-')}</span>
          </td>
          <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.08);text-align:right;
              color:{_cor_emoji_texto_item(i)[0]};font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">{_cor_emoji_texto_item(i)[2]}</td>
        </tr>""" for i in itens_criticos)
    else:
        linhas_html = "<tr><td style='color:#86efac;padding:10px 0;font-size:13px;'>✅ Nenhuma pendência em nenhum dos seus equipamentos.</td></tr>"

    vencidos = sum(1 for i in itens_criticos if str(i.get("status", "")).upper() == "VENCIDO")
    alerta_top = (
        f'<p style="color:#fca5a5;font-size:13px;margin:0 0 14px;">⚠️ {vencidos} item(ns) vencido(s) — priorize esses.</p>'
        if vencidos else
        '<p style="color:#86efac;font-size:13px;margin:0 0 14px;">✅ Nenhum item vencido esta semana.</p>'
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1929;color:#e8f1ff;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1e3a5f,#0d1929);padding:24px 28px;">
        <h2 style="margin:0;color:#fff;font-size:20px;">📋 Resumo semanal de manutenção</h2>
        <p style="margin:8px 0 0;color:#9db0c7;font-size:14px;">{total_equipamentos} equipamento(s) sob sua responsabilidade</p>
      </div>
      <div style="padding:24px 28px;">
        <p style="color:#c8dcf4;">Olá, <strong style="color:#fff;">{responsavel_nome}</strong>.</p>
        <p style="color:#9db0c7;font-size:13px;margin-bottom:2px;">Serviços mais próximos e vencidos:</p>
        {alerta_top}
        <table style="width:100%;border-collapse:collapse;">{linhas_html}</table>
        <p style="color:#7fa8cc;font-size:12px;margin-top:10px;">+ {sem_pendencia} item(ns) em dia entre todos os seus equipamentos — sem necessidade de ação agora.</p>
        <p style="color:#6b8bb0;font-size:11px;margin-top:8px;">O PDF em anexo traz o mesmo resumo em formato pra impressão/arquivo. Registre as execuções no sistema para atualizar o status.</p>
      </div>
    </div>
    """
    texto = f"Resumo semanal de manutenção — {total_equipamentos} equipamento(s)\n\n" + (
        "\n".join(f"[{i.get('equipamento','-')}] {i.get('nome','-')}: {_cor_emoji_texto_item(i)[2]}" for i in itens_criticos)
        if itens_criticos else "Nenhuma pendência."
    ) + f"\n\n+ {sem_pendencia} item(ns) em dia."
    return html, texto


def montar_html_resumo_responsavel(responsavel_nome: str, blocos: list[dict]) -> tuple[str, str]:
    """HTML consolidado com TODOS os equipamentos de um responsável — usado no
    resumo semanal automático. `blocos` = [{"equipamento": {...}, "itens": [...]}, ...]"""
    secoes_html = []
    secoes_texto = []
    total_vencidos = 0
    for bloco in blocos:
        eqp = bloco["equipamento"]
        itens = bloco["itens"]
        eqp_label = f"{eqp.get('codigo', '')} - {eqp.get('nome', '')}"
        total_vencidos += sum(1 for i in itens if str(i.get("status", "")).upper() == "VENCIDO" and not i.get("realizado"))
        linhas_html = "".join(_linha_badge_html(i) for i in itens) or \
            "<tr><td style='color:#9db0c7;padding:8px 0;font-size:13px;'>Nenhum item configurado.</td></tr>"
        secoes_html.append(f"""
        <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
            border-radius:10px;padding:14px 16px;margin:0 0 14px;">
          <p style="margin:0 0 6px;color:#fff;font-weight:bold;font-size:14px;">{eqp_label}</p>
          <table style="width:100%;border-collapse:collapse;">{linhas_html}</table>
        </div>""")
        secoes_texto.append(f"{eqp_label}\n" + "\n".join(
            f"  {i.get('nome', '-')}: {_cor_emoji_texto_item(i)[2]}" for i in itens
        ))

    alerta_top = (
        f'<p style="color:#fca5a5;font-size:13px;margin:0 0 14px;">⚠️ {total_vencidos} item(ns) vencido(s) no total — priorize esses equipamentos.</p>'
        if total_vencidos else
        '<p style="color:#86efac;font-size:13px;margin:0 0 14px;">✅ Nenhum item vencido nos seus equipamentos esta semana.</p>'
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1929;color:#e8f1ff;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1e3a5f,#0d1929);padding:24px 28px;">
        <h2 style="margin:0;color:#fff;font-size:20px;">📋 Resumo semanal de manutenção</h2>
        <p style="margin:8px 0 0;color:#9db0c7;font-size:14px;">{len(blocos)} equipamento(s) sob sua responsabilidade</p>
      </div>
      <div style="padding:24px 28px;">
        <p style="color:#c8dcf4;">Olá, <strong style="color:#fff;">{responsavel_nome}</strong>.</p>
        {alerta_top}
        {"".join(secoes_html)}
        <p style="color:#6b8bb0;font-size:11px;margin-top:8px;">Você recebe este resumo semanalmente enquanto tiver equipamentos vinculados. Registre as execuções no sistema para atualizar o status.</p>
      </div>
    </div>
    """
    texto = f"Resumo semanal de manutenção — {len(blocos)} equipamento(s)\n\n" + "\n\n".join(secoes_texto)
    return html, texto


def montar_html_revisao(equipamento: dict, etapa: dict, responsavel_nome: str) -> tuple[str, str]:
    """Monta o HTML e texto plano para alerta de revisão."""
    tipo = etapa.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta = float(etapa.get("diferenca", etapa.get("falta", 0)) or 0)
    status = etapa.get("status", "-")
    leitura_atual = float(etapa.get("atual", 0) or 0)
    vencimento = float(etapa.get("vencimento", 0) or 0)
    etapa_nome = etapa.get("etapa", etapa.get("nome_etapa", "-"))
    eqp_label = f"{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}"

    status_cor = "#ef4444" if status == "VENCIDO" else ("#f59e0b" if status == "PROXIMO" else "#22c55e")
    status_texto = "Vencido" if status == "VENCIDO" else ("Próximo do vencimento" if status == "PROXIMO" else status)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1929;color:#e8f1ff;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1e3a5f,#0d1929);padding:24px 28px;">
        <h2 style="margin:0;color:#fff;font-size:20px;">⚠️ Alerta de Revisão</h2>
        <p style="margin:8px 0 0;color:#9db0c7;font-size:14px;">Sistema de Revisão e Lubrificação</p>
      </div>
      <div style="padding:24px 28px;">
        <p style="color:#c8dcf4;">Olá, <strong style="color:#fff;">{responsavel_nome}</strong>.</p>
        <p style="color:#9db0c7;">Foi identificada uma revisão que exige acompanhamento:</p>
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="color:#8fa4c0;padding:4px 0;">Equipamento</td><td style="color:#fff;font-weight:bold;">{eqp_label}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Setor</td><td style="color:#e8f1ff;">{equipamento.get('setor_nome', '-')}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Etapa</td><td style="color:#e8f1ff;">{etapa_nome}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Leitura atual</td><td style="color:#e8f1ff;">{leitura_atual:.0f} {unidade}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Vencimento</td><td style="color:#e8f1ff;">{vencimento:.0f} {unidade}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Status</td><td><span style="color:{status_cor};font-weight:bold;">{status_texto}</span></td></tr>
          </table>
        </div>
        <p style="color:#9db0c7;font-size:13px;">Ação recomendada: programar a execução da revisão e registrar o apontamento no sistema.</p>
      </div>
    </div>
    """
    texto = f"Alerta de revisão\n\nOlá, {responsavel_nome}.\nEquipamento: {eqp_label}\nEtapa: {etapa_nome}\nStatus: {status_texto}\nLeitura: {leitura_atual:.0f} {unidade} | Vencimento: {vencimento:.0f} {unidade}"
    return html, texto


def montar_html_lubrificacao(equipamento: dict, item: dict, responsavel_nome: str) -> tuple[str, str]:
    """Monta o HTML e texto plano para alerta de lubrificação."""
    tipo = item.get("tipo_controle", "")
    unidade = "h" if tipo == "horas" else "km"
    falta = float(item.get("diferenca", item.get("falta", 0)) or 0)
    status = item.get("status", "-")
    leitura_atual = float(item.get("atual", 0) or 0)
    vencimento = float(item.get("vencimento", 0) or 0)
    item_nome = item.get("item", "-")
    produto = item.get("tipo_produto", "-")
    eqp_label = f"{equipamento.get('codigo', '')} - {equipamento.get('nome', '')}"

    status_cor = "#ef4444" if status == "VENCIDO" else ("#f59e0b" if status == "PROXIMO" else "#22c55e")
    status_texto = "Vencido" if status == "VENCIDO" else ("Próximo do vencimento" if status == "PROXIMO" else status)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1929;color:#e8f1ff;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1a4a2e,#0d1929);padding:24px 28px;">
        <h2 style="margin:0;color:#fff;font-size:20px;">🛢️ Alerta de Lubrificação</h2>
        <p style="margin:8px 0 0;color:#9db0c7;font-size:14px;">Sistema de Revisão e Lubrificação</p>
      </div>
      <div style="padding:24px 28px;">
        <p style="color:#c8dcf4;">Olá, <strong style="color:#fff;">{responsavel_nome}</strong>.</p>
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="color:#8fa4c0;padding:4px 0;">Equipamento</td><td style="color:#fff;font-weight:bold;">{eqp_label}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Setor</td><td style="color:#e8f1ff;">{equipamento.get('setor_nome', '-')}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Item</td><td style="color:#e8f1ff;">{item_nome}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Produto</td><td style="color:#e8f1ff;">{produto}</td></tr>
            <tr><td style="color:#8fa4c0;padding:4px 0;">Status</td><td><span style="color:{status_cor};font-weight:bold;">{status_texto}</span></td></tr>
          </table>
        </div>
      </div>
    </div>
    """
    texto = f"Alerta de lubrificação\n\nOlá, {responsavel_nome}.\nEquipamento: {eqp_label}\nItem: {item_nome}\nStatus: {status_texto}"
    return html, texto
