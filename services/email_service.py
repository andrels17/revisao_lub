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


def enviar_email(destinatario: str, assunto: str, corpo_html: str, corpo_texto: str = "") -> tuple[bool, str]:
    """
    Envia um e-mail via SMTP.
    Retorna (sucesso: bool, mensagem: str).
    """
    config = _get_smtp_config()
    if not config:
        return False, "Envio de e-mail não configurado. Adicione SMTP_HOST ao secrets.toml."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = config["from_addr"]
        msg["To"] = destinatario

        if corpo_texto:
            msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(config["user"], config["password"])
            server.sendmail(config["from_addr"], destinatario, msg.as_string())

        return True, "E-mail enviado com sucesso."
    except smtplib.SMTPAuthenticationError:
        return False, "Falha na autenticação SMTP. Verifique SMTP_USER e SMTP_PASS."
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {e}"


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
