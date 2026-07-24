"""
Serviço de geração de relatórios PDF específicos.
Nome da empresa configurável via NOME_EMPRESA.

Relatórios disponíveis:
  1. historico_lubrificacoes  — histórico de trocas por equipamento
  2. conformidade_revisoes     — revisões realizadas vs. previstas
  3. executivo_frota           — visão gerencial consolidada (1 página resumo)
  4. ficha_tecnica_equipamento — documento individual por máquina
"""
from __future__ import annotations

import datetime
import io
from typing import Any

import pandas as pd

# ── Nome da empresa (altere aqui para customizar o cabeçalho dos PDFs) ────────
NOME_EMPRESA = "Usina Monte Alegre"
SUBTITULO_SISTEMA = "Sistema de Revisão e Lubrificação"


# ── Helpers de cores e estilos ───────────────────────────────────────────────

def _paleta():
    from reportlab.lib import colors
    return {
        "navy":     colors.HexColor("#0f2744"),
        "blue":     colors.HexColor("#1a56a0"),
        "blue_lt":  colors.HexColor("#dbeafe"),
        "green":    colors.HexColor("#166534"),
        "green_lt": colors.HexColor("#dcfce7"),
        "red":      colors.HexColor("#991b1b"),
        "red_lt":   colors.HexColor("#fee2e2"),
        "amber":    colors.HexColor("#92400e"),
        "amber_lt": colors.HexColor("#fef3c7"),
        "gray":     colors.HexColor("#374151"),
        "gray_lt":  colors.HexColor("#f9fafb"),
        "gray_mid": colors.HexColor("#e5e7eb"),
        "muted":    colors.HexColor("#6b7280"),
        "stripe":   colors.HexColor("#f1f5f9"),
        "white":    colors.white,
        "purple":   colors.HexColor("#4c1d95"),
        "purple_lt":colors.HexColor("#ede9fe"),
    }


def _safe(v, default="-") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s and s != "nan" else default


def _fmt_num(v, sufixo="") -> str:
    try:
        return f"{float(v or 0):,.0f}{' ' + sufixo if sufixo else ''}".replace(",", ".")
    except Exception:
        return "-"


def _fmt_data(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y")
    except Exception:
        return "-"


def _cabeçalho_padrao(canvas_obj, doc, titulo_relatorio: str, subtitulo: str, filtros_txt: str, gerado_em: str):
    """Função de cabeçalho/rodapé padrão para todos os relatórios."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4

    P = _paleta()
    w, h = A4
    canvas_obj.saveState()

    # Faixa navy (topo)
    canvas_obj.setFillColor(P["navy"])
    canvas_obj.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)

    # Linha decorativa azul
    canvas_obj.setFillColor(P["blue"])
    canvas_obj.rect(0, h - 31.5 * mm, w, 1.5 * mm, fill=1, stroke=0)

    # Empresa (pequeno, canto superior esquerdo)
    canvas_obj.setFillColor(colors.HexColor("#93c5fd"))
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.drawString(12 * mm, h - 8 * mm, f"{NOME_EMPRESA}  ·  {SUBTITULO_SISTEMA}")

    # Título
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica-Bold", 15)
    canvas_obj.drawString(12 * mm, h - 17 * mm, titulo_relatorio)

    # Subtítulo / filtros
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#bfdbfe"))
    canvas_obj.drawString(12 * mm, h - 23 * mm, subtitulo)
    if filtros_txt:
        canvas_obj.drawString(12 * mm, h - 27.5 * mm, filtros_txt)

    # Rodapé
    canvas_obj.setFillColor(P["muted"])
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(12 * mm, 8 * mm, f"{NOME_EMPRESA}  ·  Gerado em {gerado_em}  ·  Confidencial")
    canvas_obj.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")
    canvas_obj.setStrokeColor(P["gray_mid"])
    canvas_obj.setLineWidth(0.4)
    canvas_obj.line(12 * mm, 11.5 * mm, w - 12 * mm, 11.5 * mm)

    canvas_obj.restoreState()


def _novo_doc(buffer, top_margin_mm=34):
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=top_margin_mm * mm,
        bottomMargin=16 * mm,
    )


def _P(texto, style):
    from reportlab.platypus import Paragraph
    return Paragraph(_safe(texto), style)


def _hr(P, thickness=0.5):
    from reportlab.platypus import HRFlowable
    return HRFlowable(width="100%", thickness=thickness, color=P["gray_mid"], spaceAfter=3, spaceBefore=3)


def _secao(titulo, desc, styles, P):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    s_sec = ParagraphStyle("sec", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, textColor=P["navy"],
        leading=13, spaceBefore=6, spaceAfter=2)
    s_desc = ParagraphStyle("desc", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=P["muted"],
        leading=11, spaceAfter=4)
    elems = [_hr(P, 1), Paragraph(titulo, s_sec)]
    if desc:
        elems.append(Paragraph(desc, s_desc))
    return elems


def _tabela_simples(colunas, linhas, P, col_widths, cor_cabecalho=None):
    """Tabela genérica com cabeçalho colorido e listras."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    if cor_cabecalho is None:
        cor_cabecalho = P["blue"]

    def _cell(txt, bold=False, color=None, align=TA_LEFT):
        c = color or P["gray"]
        style = ParagraphStyle("_tc", fontName="Helvetica-Bold" if bold else "Helvetica",
            fontSize=7.5, textColor=c, alignment=align, leading=10)
        return Paragraph(_safe(txt), style)

    hdr_row = [_cell(c, bold=True, color=P["white"]) for c in colunas]
    rows = [hdr_row]
    for i, linha in enumerate(linhas):
        row = []
        for j, val in enumerate(linha):
            if isinstance(val, tuple):
                txt, bold, color, align = val
                row.append(_cell(txt, bold=bold, color=color, align=align))
            else:
                row.append(_cell(str(val) if val is not None else "-"))
        rows.append(row)

    n = len(rows)
    stripe_cmds = [
        ("BACKGROUND", (0, i), (-1, i), P["stripe"] if i % 2 == 1 else P["white"])
        for i in range(1, n)
    ]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), cor_cabecalho),
        ("LINEBELOW",     (0, 0), (-1, 0), 1, P["navy"]),
        *stripe_cmds,
        ("INNERGRID",     (0, 1), (-1, -1), 0.25, P["gray_mid"]),
        ("BOX",           (0, 0), (-1, -1), 0.5,  P["gray_mid"]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _kpi_bar(items, P, PW):
    """Linha de KPI cards em tabela."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    n = len(items)
    w = PW / n
    hdr = [
        Paragraph(_safe(label), ParagraphStyle("kh", fontName="Helvetica",
            fontSize=7, textColor=P["muted"], alignment=TA_CENTER))
        for label, value, cor in items
    ]
    vals = [
        Paragraph(str(value), ParagraphStyle("kv", fontName="Helvetica-Bold",
            fontSize=18, textColor=cor, alignment=TA_CENTER))
        for label, value, cor in items
    ]
    t = Table([hdr, vals], colWidths=[w] * n, rowHeights=[9, 14])
    cmds = [
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW",  (0, 1), (-1, 1), 0.5, P["gray_mid"]),
    ]
    for i in range(1, n):
        cmds.append(("LINEAFTER", (i-1, 0), (i-1, 1), 0.5, P["gray_mid"]))
    t.setStyle(TableStyle(cmds))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO 1 — Histórico de Lubrificações por Equipamento
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_historico_lubrificacoes(
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    todos_equipamentos: list[dict],
    setor_nome: str | None = None,
) -> bytes:
    """
    Relatório 1: Histórico de lubrificações por equipamento.
    Mostra todas as trocas realizadas, agrupadas por equipamento,
    mais resumo por produto e equipamentos sem troca no período.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    P = _paleta()
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = _novo_doc(buf)
    PW = A4[0] - 24 * mm
    gerado_em = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    periodo = f"{_fmt_data(data_ini)} a {_fmt_data(data_fim)}"
    setor_txt = setor_nome or "Todos os setores"
    filtros_txt = f"Período: {periodo}   ·   Setor: {setor_txt}"

    def hdr(canvas_obj, doc):
        _cabeçalho_padrao(
            canvas_obj, doc,
            "Relatório de Lubrificações",
            "Histórico de trocas de lubrificante por equipamento",
            filtros_txt, gerado_em,
        )

    elements = []

    # ── KPIs ─────────────────────────────────────────────────────────────────
    if df_lub is None or df_lub.empty:
        total_trocas = 0
        equip_atendidos = 0
        produtos_distintos = 0
    else:
        total_trocas = len(df_lub)
        equip_atendidos = df_lub["Código"].nunique() if "Código" in df_lub.columns else 0
        produtos_distintos = df_lub["Produto"].nunique() if "Produto" in df_lub.columns else 0

    # Equipamentos sem troca
    codigos_com_troca = set(df_lub["Código"].dropna().astype(str).tolist()) if df_lub is not None and not df_lub.empty else set()
    sem_troca = [e for e in todos_equipamentos if str(e.get("codigo", "")) not in codigos_com_troca]

    elements.append(Spacer(1, 3 * mm))
    elements.append(_kpi_bar([
        ("Total de trocas",       total_trocas,     P["navy"]),
        ("Equipamentos atendidos", equip_atendidos,  P["green"]),
        ("Produtos distintos",    produtos_distintos, P["blue"]),
        ("Sem troca no período",  len(sem_troca),    P["red"] if sem_troca else P["muted"]),
    ], P, PW))
    elements.append(Spacer(1, 5 * mm))

    # ── Histórico por equipamento ─────────────────────────────────────────────
    from reportlab.lib.styles import ParagraphStyle
    s_eqp = ParagraphStyle("eqp", fontName="Helvetica-Bold", fontSize=9,
        textColor=P["navy"], leading=12, spaceBefore=6, spaceAfter=2)

    if df_lub is None or df_lub.empty:
        elements += _secao("Histórico por equipamento", "", styles, P)
        elements.append(Paragraph("Nenhuma lubrificação registrada no período.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"], alignment=TA_CENTER)))
    else:
        elements += _secao(
            "Histórico por equipamento",
            "Todas as trocas de lubrificante realizadas no período, agrupadas por máquina.",
            styles, P,
        )
        colunas_lub = ["Data", "Item lubrificado", "Produto", "KM / Horas", "Responsável", "Observações"]
        cw_lub = [18*mm, 42*mm, 35*mm, 22*mm, 28*mm, 30*mm]

        df_sorted = df_lub.sort_values(["Código", "Data"], ascending=[True, False]) if "Código" in df_lub.columns else df_lub

        for codigo, grupo in (df_sorted.groupby("Código") if "Código" in df_sorted.columns else [("—", df_sorted)]):
            nome_eqp = grupo["Equipamento"].iloc[0] if "Equipamento" in grupo.columns else codigo
            setor_eqp = grupo["Setor"].iloc[0] if "Setor" in grupo.columns else "-"
            bloco = []
            bloco.append(Paragraph(
                f"{codigo} — {nome_eqp}   <font size='8' color='#6b7280'>Setor: {setor_eqp} · {len(grupo)} troca(s)</font>",
                s_eqp,
            ))
            linhas = []
            for _, r in grupo.iterrows():
                km = _fmt_num(r.get("KM")) if pd.notna(r.get("KM")) and float(r.get("KM") or 0) > 0 else None
                h = _fmt_num(r.get("Horas")) if pd.notna(r.get("Horas")) and float(r.get("Horas") or 0) > 0 else None
                leit = f"{km} km" if km else (f"{h} h" if h else "-")
                linhas.append([
                    _fmt_data(r.get("Data")),
                    _safe(r.get("Item")),
                    _safe(r.get("Produto")),
                    leit,
                    _safe(r.get("Responsável")),
                    _safe(r.get("Observações"))[:50],
                ])
            bloco.append(_tabela_simples(colunas_lub, linhas, P, cw_lub, cor_cabecalho=P["green"]))
            bloco.append(Spacer(1, 3 * mm))
            elements.append(KeepTogether(bloco))

    # ── Resumo por produto ────────────────────────────────────────────────────
    if df_lub is not None and not df_lub.empty and "Produto" in df_lub.columns:
        elements.append(PageBreak())
        elements += _secao(
            "Resumo por produto lubrificante",
            "Quantidade de aplicações de cada produto no período.",
            styles, P,
        )
        resumo_prod = (
            df_lub.groupby("Produto")
            .agg(Aplicações=("ID", "count"), Equipamentos=("Código", pd.Series.nunique))
            .reset_index()
            .sort_values("Aplicações", ascending=False)
        )
        cw_p = [70*mm, 30*mm, 40*mm]
        linhas_p = [
            [_safe(r["Produto"]), str(int(r["Aplicações"])), str(int(r["Equipamentos"]))]
            for _, r in resumo_prod.iterrows()
        ]
        elements.append(_tabela_simples(
            ["Produto", "Aplicações", "Equipamentos distintos"],
            linhas_p, P, cw_p, cor_cabecalho=P["green"],
        ))
        elements.append(Spacer(1, 5 * mm))

    # ── Equipamentos sem troca ────────────────────────────────────────────────
    if sem_troca:
        elements += _secao(
            "Equipamentos sem troca de lubrificante no período",
            f"{len(sem_troca)} equipamento(s) não tiveram nenhuma lubrificação registrada no período analisado.",
            styles, P,
        )
        linhas_s = [
            [(e.get("codigo") or "-", True, P["red"], TA_LEFT), _safe(e.get("nome")), _safe(e.get("setor_nome"))]
            for e in sem_troca
        ]
        elements.append(_tabela_simples(
            ["Código", "Equipamento", "Setor"],
            linhas_s, P, [25*mm, 80*mm, 60*mm], cor_cabecalho=P["red"],
        ))
        elements.append(Spacer(1, 8 * mm))

    # ── Campo de assinatura ───────────────────────────────────────────────────
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    s_ass = ParagraphStyle("ass", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    ass_data = [
        [Paragraph("Responsável pela conferência:", s_ass), Paragraph("Data:", s_ass)],
        [Paragraph("_" * 60, s_ass), Paragraph("___/___/______", s_ass)],
    ]
    ass_t = Table(ass_data, colWidths=[PW * 0.72, PW * 0.28])
    ass_t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ass_t)

    doc.build(elements, onFirstPage=hdr, onLaterPages=hdr)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO 2 — Conformidade de Revisões
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_conformidade_revisoes(
    df_rev: pd.DataFrame,
    df_status_atual: list[dict],  # lista de {codigo, nome, setor_nome, etapa, status, falta, unidade}
    data_ini,
    data_fim,
    setor_nome: str | None = None,
) -> bytes:
    """
    Relatório 2: Conformidade de revisões predefinidas.
    Mostra quantas revisões foram realizadas, percentual de conformidade,
    equipamentos em atraso e equipamentos em dia.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    P = _paleta()
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = _novo_doc(buf)
    PW = A4[0] - 24 * mm
    gerado_em = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    periodo = f"{_fmt_data(data_ini)} a {_fmt_data(data_fim)}"
    setor_txt = setor_nome or "Todos os setores"

    def hdr(canvas_obj, doc):
        _cabeçalho_padrao(
            canvas_obj, doc,
            "Relatório de Conformidade — Revisões",
            "Cumprimento das revisões predefinidas no ciclo atual",
            f"Período de execuções: {periodo}   ·   Setor: {setor_txt}",
            gerado_em,
        )

    elements = []

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total_rev = len(df_rev) if df_rev is not None and not df_rev.empty else 0

    vencidos = [s for s in df_status_atual if str(s.get("status", "")).upper() == "VENCIDO"]
    proximos = [s for s in df_status_atual if str(s.get("status", "")).upper() == "PROXIMO"]
    em_dia   = [s for s in df_status_atual if str(s.get("status", "")).upper() == "EM_DIA"]
    total_itens = len(df_status_atual)
    pct_conformidade = round((len(em_dia) / total_itens * 100)) if total_itens > 0 else 0

    elements.append(Spacer(1, 3 * mm))
    elements.append(_kpi_bar([
        ("Revisões realizadas",  total_rev,           P["blue"]),
        ("Itens em dia",         len(em_dia),          P["green"]),
        ("Itens vencidos",       len(vencidos),        P["red"] if vencidos else P["muted"]),
        ("Próximos ao vencimento", len(proximos),      P["amber"]),
        ("Conformidade atual",   f"{pct_conformidade}%", P["green"] if pct_conformidade >= 80 else (P["amber"] if pct_conformidade >= 50 else P["red"])),
    ], P, PW))
    elements.append(Spacer(1, 4 * mm))

    # ── Barra de conformidade ─────────────────────────────────────────────────
    from reportlab.lib.styles import ParagraphStyle
    s_conf = ParagraphStyle("conf", fontName="Helvetica-Bold", fontSize=9,
        textColor=P["navy"], leading=12)
    elements.append(Paragraph("Índice de conformidade do ciclo atual", s_conf))
    elements.append(Spacer(1, 2 * mm))

    # Barra visual via canvas — usando Table com fundo colorido
    pct = pct_conformidade / 100
    cor_bar = P["green"] if pct_conformidade >= 80 else (P["amber"] if pct_conformidade >= 50 else P["red"])
    bar_preenchida = PW * pct
    bar_vazia = PW - bar_preenchida
    bar_data = [["" , ""]]
    bar_cw = [max(bar_preenchida, 1), max(bar_vazia, 1)] if bar_preenchida < PW else [PW, 0.1]
    bar_t = Table(bar_data, colWidths=bar_cw, rowHeights=[6])
    bar_style = [
        ("BACKGROUND", (0, 0), (0, 0), cor_bar),
        ("BACKGROUND", (1, 0), (1, 0), P["gray_mid"]),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]
    bar_t.setStyle(TableStyle(bar_style))
    elements.append(bar_t)
    s_label = ParagraphStyle("lb", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    elements.append(Paragraph(f"{pct_conformidade}% dos itens monitorados estão em dia no ciclo atual.", s_label))
    elements.append(Spacer(1, 5 * mm))

    # ── Revisões realizadas no período por etapa ──────────────────────────────
    elements += _secao(
        "Revisões realizadas no período (por etapa)",
        "Cada linha representa uma execução registrada. Agrupada por código de equipamento.",
        styles, P,
    )
    if df_rev is None or df_rev.empty:
        s_em = ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"], alignment=TA_CENTER)
        elements.append(Paragraph("Nenhuma revisão realizada no período selecionado.", s_em))
    else:
        # Tenta extrair etapa das observações
        import re
        ETAPA_RE = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        def _etapa(obs):
            if not obs: return "-"
            m = ETAPA_RE.search(str(obs))
            return m.group(1).strip() if m else "-"

        df_r = df_rev.copy()
        df_r["Etapa"] = df_r.get("Observações", pd.Series([""] * len(df_r))).apply(_etapa)
        cols_rev = ["Data", "Código", "Equipamento", "Setor", "Etapa", "KM", "Horas", "Responsável"]
        cw_rev = [18*mm, 16*mm, 32*mm, 28*mm, 36*mm, 14*mm, 14*mm, 22*mm]
        linhas_rev = []
        for _, r in df_r.sort_values(["Código", "Data"], ascending=[True, False]).head(80).iterrows():
            km_v = _fmt_num(r.get("KM")) if pd.notna(r.get("KM")) and float(r.get("KM") or 0) > 0 else "-"
            h_v  = _fmt_num(r.get("Horas")) if pd.notna(r.get("Horas")) and float(r.get("Horas") or 0) > 0 else "-"
            linhas_rev.append([
                _fmt_data(r.get("Data")),
                _safe(r.get("Código")),
                _safe(r.get("Equipamento")),
                _safe(r.get("Setor")),
                _safe(r.get("Etapa")),
                km_v, h_v,
                _safe(r.get("Responsável")),
            ])
        elements.append(_tabela_simples(cols_rev, linhas_rev, P, cw_rev, cor_cabecalho=P["blue"]))
    elements.append(Spacer(1, 4 * mm))

    # ── Equipamentos vencidos ─────────────────────────────────────────────────
    if vencidos:
        elements.append(PageBreak())
        elements += _secao(
            "⚠ Equipamentos com revisão vencida (situação atual)",
            f"{len(vencidos)} item(ns) com revisão já ultrapassada na data de geração deste relatório.",
            styles, P,
        )
        linhas_v = [
            [
                (_safe(s.get("codigo")), True, P["red"], TA_LEFT),
                _safe(s.get("nome")),
                _safe(s.get("setor_nome")),
                _safe(s.get("etapa")),
                _fmt_num(s.get("falta")) + " " + _safe(s.get("unidade")),
            ]
            for s in vencidos
        ]
        elements.append(_tabela_simples(
            ["Código", "Equipamento", "Setor", "Etapa", "Atraso"],
            linhas_v, P, [18*mm, 50*mm, 38*mm, 45*mm, 24*mm],
            cor_cabecalho=P["red"],
        ))
        elements.append(Spacer(1, 4 * mm))

    # ── Equipamentos em dia ───────────────────────────────────────────────────
    if em_dia:
        elements += _secao(
            "✓ Equipamentos em dia (situação atual)",
            f"{len(em_dia)} item(ns) dentro do prazo de revisão na data de geração deste relatório.",
            styles, P,
        )
        linhas_d = [
            [
                (_safe(s.get("codigo")), True, P["green"], TA_LEFT),
                _safe(s.get("nome")),
                _safe(s.get("setor_nome")),
                _safe(s.get("etapa")),
                _fmt_num(s.get("falta")) + " " + _safe(s.get("unidade")),
            ]
            for s in em_dia
        ]
        elements.append(_tabela_simples(
            ["Código", "Equipamento", "Setor", "Etapa", "Faltam"],
            linhas_d, P, [18*mm, 50*mm, 38*mm, 45*mm, 24*mm],
            cor_cabecalho=P["green"],
        ))

    elements.append(Spacer(1, 8 * mm))
    # Campo de assinatura
    from reportlab.platypus import Table, TableStyle
    s_ass = ParagraphStyle("ass", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    ass_t = Table([
        [Paragraph("Responsável pela conferência:", s_ass), Paragraph("Data:", s_ass)],
        [Paragraph("_" * 60, s_ass), Paragraph("___/___/______", s_ass)],
    ], colWidths=[PW * 0.72, PW * 0.28])
    ass_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    elements.append(ass_t)

    doc.build(elements, onFirstPage=hdr, onLaterPages=hdr)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO 3 — Executivo de Frota
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_executivo_frota(
    kpis_alertas: dict,
    mov: dict,
    ranking_setores: list[dict],
    ranking_equipamentos: list[dict],
    health_score: dict,
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
) -> bytes:
    """
    Relatório 3: Relatório executivo de frota para diretoria/gerência.
    Página 1: resumo executivo com Fleet Health Score e KPIs.
    Página 2: tabelas de revisões e lubrificações do período.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    P = _paleta()
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = _novo_doc(buf)
    PW = A4[0] - 24 * mm
    gerado_em = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    periodo = f"{_fmt_data(data_ini)} a {_fmt_data(data_fim)}"

    def hdr(canvas_obj, doc):
        _cabeçalho_padrao(
            canvas_obj, doc,
            "Relatório Executivo de Frota",
            f"{NOME_EMPRESA}  ·  Gestão de Manutenção Preventiva",
            f"Período: {periodo}   ·   Gerado em: {gerado_em}",
            gerado_em,
        )

    elements = []

    # ── Fleet Health Score ────────────────────────────────────────────────────
    score = float(health_score.get("score", 0))
    nivel = health_score.get("nivel", "-")
    from reportlab.lib import colors
    cor_score_hex = health_score.get("cor", "#22c55e")
    cor_score = colors.HexColor(cor_score_hex)

    s_hs_label = ParagraphStyle("hsl", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    s_hs_score = ParagraphStyle("hss", fontName="Helvetica-Bold", fontSize=36, textColor=cor_score, leading=40)
    s_hs_nivel = ParagraphStyle("hsn", fontName="Helvetica-Bold", fontSize=12, textColor=cor_score)
    s_hs_desc  = ParagraphStyle("hsd", fontName="Helvetica", fontSize=8, textColor=P["muted"])

    hs_data = [
        [
            Paragraph("Fleet Health Score", s_hs_label),
            Paragraph("", s_hs_label),
        ],
        [
            Paragraph(f"{score:.0f}%", s_hs_score),
            Paragraph(
                f"<b>Nível: {nivel}</b><br/>"
                f"Índice composto de saúde da frota baseado em alertas,<br/>"
                f"equipamentos parados e anomalias de leitura.",
                s_hs_desc,
            ),
        ],
    ]
    hs_t = Table(hs_data, colWidths=[50*mm, PW - 50*mm])
    hs_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 1, P["gray_mid"]),
        ("BACKGROUND",    (0, 0), (-1, -1), P["gray_lt"]),
        ("LINEAFTER",     (0, 0), (0, -1), 0.5, P["gray_mid"]),
    ]))
    elements.append(Spacer(1, 3 * mm))
    elements.append(hs_t)

    # Barra de score
    pct = score / 100
    bar_cw = [max(PW * pct, 1), max(PW * (1 - pct), 1)]
    bar_t = Table([["" , ""]], colWidths=bar_cw, rowHeights=[5])
    bar_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), cor_score),
        ("BACKGROUND", (1, 0), (1, 0), P["gray_mid"]),
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",  (0,0), (-1,-1), 0), ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    elements.append(bar_t)
    elements.append(Spacer(1, 5 * mm))

    # ── KPIs principais ───────────────────────────────────────────────────────
    total_eqp    = int(kpis_alertas.get("total_equipamentos", 0))
    com_alerta   = int(kpis_alertas.get("equipamentos_com_alerta", 0))
    vencidos     = int(kpis_alertas.get("vencidos", 0))
    em_dia_eqp   = total_eqp - com_alerta
    pct_em_dia   = round(em_dia_eqp / max(total_eqp, 1) * 100)
    sem_leitura  = int(mov.get("kpis", {}).get("equipamentos_sem_leitura", 0))

    elements.append(_kpi_bar([
        ("Equipamentos ativos", total_eqp,           P["navy"]),
        ("Em dia",              f"{pct_em_dia}%",     P["green"]),
        ("Com alertas vencidos", vencidos,            P["red"] if vencidos > 0 else P["muted"]),
        ("Sem leitura recente", sem_leitura,          P["amber"] if sem_leitura > 0 else P["muted"]),
    ], P, PW))
    elements.append(Spacer(1, 5 * mm))

    # ── Top 5 equipamentos críticos ───────────────────────────────────────────
    elements += _secao("Top equipamentos críticos", "Máquinas com maior número de alertas vencidos.", styles, P)
    if ranking_equipamentos:
        top5_eqp = ranking_equipamentos[:5]
        linhas_eqp = [
            [
                (_safe(r.get("Código") or r.get("codigo")), True, P["red"], TA_LEFT),
                _safe(r.get("Equipamento") or r.get("nome")),
                _safe(r.get("Setor") or r.get("setor_nome")),
                str(int(r.get("Vencidos", r.get("vencidos", 0)) or 0)),
                str(int(r.get("Total", r.get("total", 0)) or 0)),
            ]
            for r in top5_eqp
        ]
        elements.append(_tabela_simples(
            ["Código", "Equipamento", "Setor", "Vencidos", "Total alertas"],
            linhas_eqp, P, [18*mm, 60*mm, 45*mm, 22*mm, 25*mm],
        ))
    else:
        elements.append(Paragraph("Nenhum equipamento crítico no momento.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["green"])))
    elements.append(Spacer(1, 4 * mm))

    # ── Top 5 setores ─────────────────────────────────────────────────────────
    elements += _secao("Top setores com mais alertas", "Setores com maior concentração de pendências.", styles, P)
    if ranking_setores:
        top5_set = ranking_setores[:5]
        linhas_set = [
            [
                _safe(r.get("Setor") or r.get("setor")),
                str(int(r.get("Vencidos", r.get("vencidos", 0)) or 0)),
                str(int(r.get("Próximos", r.get("proximos", 0)) or 0)),
                str(int((r.get("Vencidos", 0) or 0) + (r.get("Próximos", 0) or 0))),
            ]
            for r in top5_set
        ]
        elements.append(_tabela_simples(
            ["Setor", "Vencidos", "Próximos", "Total"],
            linhas_set, P, [80*mm, 30*mm, 30*mm, 30*mm],
        ))
    elements.append(Spacer(1, 4 * mm))

    # ── Página 2: Detalhamento ────────────────────────────────────────────────
    elements.append(PageBreak())
    elements += _secao(
        "Revisões realizadas no período",
        f"Período: {periodo}  ·  {len(df_rev) if df_rev is not None else 0} registro(s)",
        styles, P,
    )
    if df_rev is not None and not df_rev.empty:
        cw_r = [18*mm, 16*mm, 35*mm, 30*mm, 18*mm, 18*mm, 25*mm]
        linhas_r = [
            [
                _fmt_data(r.get("Data")),
                _safe(r.get("Código")),
                _safe(r.get("Equipamento")),
                _safe(r.get("Setor")),
                _fmt_num(r.get("KM")),
                _fmt_num(r.get("Horas")),
                _safe(r.get("Responsável")),
            ]
            for _, r in df_rev.sort_values("Data", ascending=False).head(50).iterrows()
        ]
        elements.append(_tabela_simples(
            ["Data", "Código", "Equipamento", "Setor", "KM", "Horas", "Responsável"],
            linhas_r, P, cw_r,
        ))
    else:
        elements.append(Paragraph("Sem revisões no período.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))

    elements.append(Spacer(1, 5 * mm))
    elements += _secao(
        "Lubrificações realizadas no período",
        f"Período: {periodo}  ·  {len(df_lub) if df_lub is not None else 0} registro(s)",
        styles, P,
    )
    if df_lub is not None and not df_lub.empty:
        cw_l = [18*mm, 16*mm, 30*mm, 25*mm, 30*mm, 20*mm, 21*mm]
        linhas_l = [
            [
                _fmt_data(r.get("Data")),
                _safe(r.get("Código")),
                _safe(r.get("Equipamento")),
                _safe(r.get("Setor")),
                _safe(r.get("Item")),
                _safe(r.get("Produto")),
                _safe(r.get("Responsável")),
            ]
            for _, r in df_lub.sort_values("Data", ascending=False).head(50).iterrows()
        ]
        elements.append(_tabela_simples(
            ["Data", "Código", "Equipamento", "Setor", "Item", "Produto", "Responsável"],
            linhas_l, P, cw_l, cor_cabecalho=P["green"],
        ))
    else:
        elements.append(Paragraph("Sem lubrificações no período.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))

    doc.build(elements, onFirstPage=hdr, onLaterPages=hdr)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO 4 — Ficha Técnica do Equipamento
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_ficha_tecnica(
    equipamento: dict,
    status_revisoes: list[dict],
    status_lubrificacoes: list[dict],
    historico_revisoes: list[dict],
    historico_lubrificacoes: list[dict],
    ultima_leitura: dict | None,
) -> bytes:
    """
    Relatório 4: Ficha técnica individual do equipamento.
    Inclui dados cadastrais, status atual de revisões e lubrificações,
    histórico das últimas execuções e campo de assinatura.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    P = _paleta()
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = _novo_doc(buf)
    PW = A4[0] - 24 * mm
    gerado_em = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    codigo  = _safe(equipamento.get("codigo"))
    nome    = _safe(equipamento.get("nome"))
    setor   = _safe(equipamento.get("setor_nome"))
    tipo    = _safe(equipamento.get("tipo"))
    km_atual   = _fmt_num(equipamento.get("km_atual")) + " km"
    h_atual    = _fmt_num(equipamento.get("horas_atual")) + " h"

    def hdr(canvas_obj, doc):
        _cabeçalho_padrao(
            canvas_obj, doc,
            "Ficha Técnica do Equipamento",
            f"{codigo} — {nome}   ·   Setor: {setor}",
            f"Tipo: {tipo}   ·   KM atual: {km_atual}   ·   Horas: {h_atual}",
            gerado_em,
        )

    elements = []
    elements.append(Spacer(1, 2 * mm))

    # ── Dados cadastrais ──────────────────────────────────────────────────────
    s_campo = ParagraphStyle("campo", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    s_valor = ParagraphStyle("valor", fontName="Helvetica-Bold", fontSize=9, textColor=P["gray"])

    cad_data = [
        [
            Paragraph("Código", s_campo), Paragraph(codigo, s_valor),
            Paragraph("Nome", s_campo),   Paragraph(nome, s_valor),
        ],
        [
            Paragraph("Setor", s_campo),  Paragraph(setor, s_valor),
            Paragraph("Tipo", s_campo),   Paragraph(tipo, s_valor),
        ],
        [
            Paragraph("KM atual", s_campo),   Paragraph(km_atual, s_valor),
            Paragraph("Horas atuais", s_campo), Paragraph(h_atual, s_valor),
        ],
    ]
    if ultima_leitura:
        ult_data = _fmt_data(ultima_leitura.get("data_leitura"))
        cad_data.append([
            Paragraph("Última leitura", s_campo), Paragraph(ult_data, s_valor),
            Paragraph("Registrada por", s_campo),
            Paragraph(_safe(ultima_leitura.get("responsavel")), s_valor),
        ])

    cad_t = Table(cad_data, colWidths=[25*mm, 60*mm, 25*mm, 65*mm])
    cad_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), P["gray_lt"]),
        ("BOX",        (0, 0), (-1, -1), 0.5, P["gray_mid"]),
        ("INNERGRID",  (0, 0), (-1, -1), 0.25, P["gray_mid"]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    elements.append(cad_t)
    elements.append(Spacer(1, 5 * mm))

    # ── Status atual das revisões ─────────────────────────────────────────────
    elements += _secao(
        "Status atual das revisões",
        "Situação de cada etapa de revisão predefinida no ciclo atual.",
        styles, P,
    )
    if status_revisoes:
        linhas_sr = []
        for s in status_revisoes:
            st = str(s.get("status", "")).upper()
            if st == "VENCIDO":
                cor_st, txt_st = P["red"],   "VENCIDO"
            elif st == "PROXIMO":
                cor_st, txt_st = P["amber"], "PRÓXIMO"
            else:
                cor_st, txt_st = P["green"], "EM DIA"
            falta_v = float(s.get("diferenca") or s.get("falta") or 0)
            falta_txt = f"{abs(falta_v):.0f} {_safe(s.get('unidade', 'km'))}"
            linhas_sr.append([
                _safe(s.get("etapa") or s.get("nome_etapa")),
                _safe(s.get("tipo_controle", "km")).upper(),
                _fmt_num(s.get("atual")),
                _fmt_num(s.get("vencimento")),
                (txt_st, True, cor_st, TA_CENTER),
                falta_txt,
            ])
        elements.append(_tabela_simples(
            ["Etapa", "Controle", "Leitura atual", "Vencimento", "Status", "Diferença"],
            linhas_sr, P, [52*mm, 18*mm, 22*mm, 22*mm, 20*mm, 22*mm],
        ))
    else:
        elements.append(Paragraph("Sem template de revisão configurado.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))
    elements.append(Spacer(1, 4 * mm))

    # ── Status atual das lubrificações ────────────────────────────────────────
    elements += _secao(
        "Status atual das lubrificações",
        "Situação de cada item de lubrificação predefinido no ciclo atual.",
        styles, P,
    )
    if status_lubrificacoes:
        linhas_sl = []
        for s in status_lubrificacoes:
            st = str(s.get("status", "")).upper()
            if st == "VENCIDO":
                cor_st, txt_st = P["red"],   "VENCIDO"
            elif st == "PROXIMO":
                cor_st, txt_st = P["amber"], "PRÓXIMO"
            else:
                cor_st, txt_st = P["green"], "EM DIA"
            falta_v = float(s.get("diferenca") or s.get("falta") or 0)
            falta_txt = f"{abs(falta_v):.0f} {_safe(s.get('unidade', 'km'))}"
            linhas_sl.append([
                _safe(s.get("item") or s.get("nome_item")),
                _safe(s.get("tipo_produto") or s.get("produto", "-")),
                _safe(s.get("tipo_controle", "km")).upper(),
                _fmt_num(s.get("atual")),
                _fmt_num(s.get("vencimento")),
                (txt_st, True, cor_st, TA_CENTER),
                falta_txt,
            ])
        elements.append(_tabela_simples(
            ["Item", "Produto", "Controle", "Atual", "Vencimento", "Status", "Diferença"],
            linhas_sl, P, [40*mm, 28*mm, 15*mm, 17*mm, 19*mm, 19*mm, 18*mm],
            cor_cabecalho=P["green"],
        ))
    else:
        elements.append(Paragraph("Sem template de lubrificação configurado.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))

    # ── Histórico das últimas revisões ────────────────────────────────────────
    elements.append(PageBreak())
    elements += _secao(
        f"Histórico de revisões ({len(historico_revisoes)} registro(s))",
        "Últimas revisões realizadas neste equipamento.",
        styles, P,
    )
    if historico_revisoes:
        import re
        ETAPA_RE = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        def _etapa_obs(obs):
            if not obs: return "-"
            m = ETAPA_RE.search(str(obs))
            return m.group(1).strip() if m else "-"

        linhas_hr = []
        for r in historico_revisoes[:15]:
            km_v = _fmt_num(r.get("KM") or r.get("km_execucao")) if (r.get("KM") or r.get("km_execucao")) else "-"
            h_v  = _fmt_num(r.get("Horas") or r.get("horas_execucao")) if (r.get("Horas") or r.get("horas_execucao")) else "-"
            linhas_hr.append([
                _fmt_data(r.get("Data") or r.get("data_execucao")),
                _etapa_obs(r.get("Observações") or r.get("observacoes")),
                km_v, h_v,
                _safe(r.get("Responsável") or r.get("responsavel")),
                _safe(r.get("Status") or r.get("status", "Concluída")),
            ])
        elements.append(_tabela_simples(
            ["Data", "Etapa", "KM", "Horas", "Responsável", "Status"],
            linhas_hr, P, [20*mm, 55*mm, 18*mm, 18*mm, 32*mm, 20*mm],
        ))
    else:
        elements.append(Paragraph("Nenhuma revisão registrada para este equipamento.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))
    elements.append(Spacer(1, 4 * mm))

    # ── Histórico das últimas lubrificações ───────────────────────────────────
    elements += _secao(
        f"Histórico de lubrificações ({len(historico_lubrificacoes)} registro(s))",
        "Últimas trocas de lubrificante realizadas neste equipamento.",
        styles, P,
    )
    if historico_lubrificacoes:
        linhas_hl = []
        for r in historico_lubrificacoes[:15]:
            km_v = _fmt_num(r.get("KM") or r.get("km_execucao")) if (r.get("KM") or r.get("km_execucao")) else "-"
            h_v  = _fmt_num(r.get("Horas") or r.get("horas_execucao")) if (r.get("Horas") or r.get("horas_execucao")) else "-"
            linhas_hl.append([
                _fmt_data(r.get("Data") or r.get("data_execucao")),
                _safe(r.get("Item") or r.get("nome_item")),
                _safe(r.get("Produto") or r.get("tipo_produto")),
                km_v, h_v,
                _safe(r.get("Responsável") or r.get("responsavel")),
            ])
        elements.append(_tabela_simples(
            ["Data", "Item", "Produto", "KM", "Horas", "Responsável"],
            linhas_hl, P, [20*mm, 40*mm, 35*mm, 18*mm, 18*mm, 32*mm],
            cor_cabecalho=P["green"],
        ))
    else:
        elements.append(Paragraph("Nenhuma lubrificação registrada para este equipamento.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"])))

    # ── Campo de assinatura ───────────────────────────────────────────────────
    elements.append(Spacer(1, 10 * mm))
    s_ass = ParagraphStyle("ass", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    s_rot = ParagraphStyle("rot", fontName="Helvetica-Bold", fontSize=9, textColor=P["navy"])
    elements.append(Paragraph("Confirmação de vistoria", s_rot))
    elements.append(Spacer(1, 2 * mm))
    ass_data = [
        [Paragraph("Responsável técnico:", s_ass), Paragraph("Operador / Motorista:", s_ass), Paragraph("Data:", s_ass)],
        [Paragraph("_" * 42, s_ass), Paragraph("_" * 42, s_ass), Paragraph("___/___/______", s_ass)],
    ]
    ass_t = Table(ass_data, colWidths=[PW * 0.40, PW * 0.40, PW * 0.20])
    ass_t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ass_t)

    doc.build(elements, onFirstPage=hdr, onLaterPages=hdr)
    return buf.getvalue()
