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
        "navy":     colors.HexColor("#0b1e3d"),
        "blue":     colors.HexColor("#2563eb"),
        "blue_lt":  colors.HexColor("#eff6ff"),
        "green":    colors.HexColor("#15803d"),
        "green_lt": colors.HexColor("#f0fdf4"),
        "red":      colors.HexColor("#b91c1c"),
        "red_lt":   colors.HexColor("#fef2f2"),
        "amber":    colors.HexColor("#b45309"),
        "amber_lt": colors.HexColor("#fffbeb"),
        "gray":     colors.HexColor("#1f2937"),
        "gray_lt":  colors.HexColor("#f8fafc"),
        "gray_mid": colors.HexColor("#e2e8f0"),
        "muted":    colors.HexColor("#64748b"),
        "stripe":   colors.HexColor("#f8fafc"),
        "white":    colors.white,
        "purple":   colors.HexColor("#6d28d9"),
        "purple_lt":colors.HexColor("#f5f3ff"),
    }


def _hexstr(color) -> str:
    """Converte uma reportlab.lib.colors.Color em string '#rrggbb' para uso em markup de Paragraph."""
    return "#%02x%02x%02x" % (round(color.red * 255), round(color.green * 255), round(color.blue * 255))


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


def _linha_tempo_etapas(itens_ordenados, P, largura):
    """Desenha uma linha do tempo horizontal com uma bolinha numerada por etapa
    de revisão (na ordem de acionamento dentro do ciclo), destacando quais já
    foram concluídas neste ciclo (verde) e quais ainda faltam (vencido/próximo/
    pendente) — mesma ideia de uma linha do tempo de períodos, só que aplicada
    ao progresso do ciclo atual de revisão."""
    from reportlab.graphics.shapes import Drawing, Circle, Line, String
    from reportlab.lib.units import mm
    from reportlab.lib import colors as _colors

    n = len(itens_ordenados)
    if n == 0:
        return None

    altura = 26 * mm
    d = Drawing(largura, altura)
    y_linha = altura / 2 + 2
    margem = 10 * mm
    passo = (largura - 2 * margem) / max(1, n - 1) if n > 1 else 0
    raio = 4.0 * mm

    def _cor_no(item):
        if item.get("realizado_no_ciclo"):
            return P["green"], _colors.white
        status = str(item.get("status") or "").upper()
        if status == "VENCIDO":
            return P["red"], _colors.white
        if status == "PROXIMO":
            return P["amber"], _colors.white
        if status in ("SEM_BASE", "SEM BASE"):
            return P["purple"], _colors.white
        return _colors.white, P["muted"]  # pendente — ainda não chegou a vez neste ciclo

    xs = [margem + i * passo for i in range(n)] if n > 1 else [largura / 2]

    d.add(Line(xs[0], y_linha, xs[-1], y_linha, strokeColor=P["gray_mid"], strokeWidth=2.2))
    for i in range(n - 1):
        if itens_ordenados[i].get("realizado_no_ciclo"):
            d.add(Line(xs[i], y_linha, xs[i + 1], y_linha, strokeColor=P["green"], strokeWidth=2.2))

    for i, item in enumerate(itens_ordenados):
        cx = xs[i]
        bg, fg = _cor_no(item)
        borda = P["muted"] if bg == _colors.white else bg
        d.add(Circle(cx, y_linha, raio, fillColor=bg, strokeColor=borda, strokeWidth=1.2))
        d.add(String(cx, y_linha - 3.1, str(i + 1), fontName="Helvetica-Bold", fontSize=9,
                      fillColor=fg, textAnchor="middle"))

        largura_rotulo = passo + 16 if n > 1 else largura - 8
        nome = _fit_text(_safe(item.get("etapa") or item.get("nome_etapa")), "Helvetica-Bold", 6.6, largura_rotulo)
        if i % 2 == 0:
            ly = y_linha + raio + 8
        else:
            ly = y_linha - raio - 12
        d.add(String(cx, ly, nome, fontName="Helvetica-Bold", fontSize=6.6,
                      fillColor=P["navy"], textAnchor="middle"))

    return d


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

    # Fina linha de destaque logo abaixo da faixa (cor de acento do relatório)
    canvas_obj.setFillColor(P["blue"])
    canvas_obj.rect(0, h - 30.9 * mm, w, 0.9 * mm, fill=1, stroke=0)

    # Empresa (kicker, canto superior esquerdo)
    canvas_obj.setFillColor(colors.HexColor("#93c5fd"))
    canvas_obj.setFont("Helvetica-Bold", 7)
    canvas_obj.drawString(12 * mm, h - 8.3 * mm, NOME_EMPRESA.upper())
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(colors.HexColor("#60a5fa"))
    empresa_w = canvas_obj.stringWidth(NOME_EMPRESA.upper(), "Helvetica-Bold", 7)
    canvas_obj.drawString(12 * mm + empresa_w + 4, h - 8.3 * mm, f"·  {SUBTITULO_SISTEMA}")

    # Título
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica-Bold", 16)
    canvas_obj.drawString(12 * mm, h - 18 * mm, titulo_relatorio)

    # Subtítulo / filtros
    canvas_obj.setFont("Helvetica", 8.5)
    canvas_obj.setFillColor(colors.HexColor("#bfdbfe"))
    canvas_obj.drawString(12 * mm, h - 24 * mm, subtitulo)
    if filtros_txt:
        canvas_obj.setFont("Helvetica-Oblique", 7.5)
        canvas_obj.setFillColor(colors.HexColor("#93c5fd"))
        canvas_obj.drawString(12 * mm, h - 28.2 * mm, filtros_txt)

    # Selo "Gerado em" (canto superior direito, estilo pill)
    canvas_obj.setFont("Helvetica", 7)
    data_txt = f"Emitido em {gerado_em}"
    tw = canvas_obj.stringWidth(data_txt, "Helvetica", 7)
    pill_w = tw + 10
    canvas_obj.setFillColor(colors.HexColor("#13294f"))
    canvas_obj.roundRect(w - 12 * mm - pill_w, h - 12 * mm, pill_w, 5.6 * mm, 2.8 * mm, fill=1, stroke=0)
    canvas_obj.setFillColor(colors.HexColor("#dbeafe"))
    canvas_obj.drawString(w - 12 * mm - pill_w + 5, h - 12 * mm + 1.8 * mm, data_txt)

    # Rodapé
    canvas_obj.setStrokeColor(P["gray_mid"])
    canvas_obj.setLineWidth(0.6)
    canvas_obj.line(12 * mm, 11.5 * mm, w - 12 * mm, 11.5 * mm)
    canvas_obj.setFillColor(P["blue"])
    canvas_obj.rect(12 * mm, 11.5 * mm, 14 * mm, 0.6, fill=1, stroke=0)

    canvas_obj.setFillColor(P["muted"])
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(12 * mm, 8 * mm, f"{NOME_EMPRESA}  ·  Gerado em {gerado_em}  ·  Confidencial")
    canvas_obj.setFont("Helvetica-Bold", 7)
    canvas_obj.setFillColor(P["navy"])
    canvas_obj.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")

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
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    accent = _hexstr(P["blue"])
    s_sec = ParagraphStyle("sec", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10.5, textColor=P["navy"],
        leading=13, spaceBefore=10, spaceAfter=1)
    s_desc = ParagraphStyle("desc", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=P["muted"],
        leading=11, spaceAfter=5, leftIndent=8)
    titulo_marcado = f'<font color="{accent}">▎</font> {titulo}'
    elems = [Paragraph(titulo_marcado, s_sec)]
    if desc:
        elems.append(Paragraph(desc, s_desc))
    else:
        elems.append(Spacer(1, 2))
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

    def _hcell(txt, align=TA_LEFT):
        style = ParagraphStyle("_th", fontName="Helvetica-Bold",
            fontSize=7.3, textColor=P["white"], alignment=align, leading=9)
        return Paragraph(_safe(txt).upper(), style)

    hdr_row = [_hcell(c) for c in colunas]
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
        ("TOPPADDING",    (0, 0), (-1, 0), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5.5),
        ("LINEBELOW",     (0, 0), (-1, 0), 1.2, P["navy"]),
        *stripe_cmds,
        ("INNERGRID",     (0, 1), (-1, -1), 0.25, P["gray_mid"]),
        ("BOX",           (0, 0), (-1, -1), 0.6,  P["gray_mid"]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _kpi_bar(items, P, PW):
    """Linha de KPI cards (fundo suave + borda na cor do indicador)."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    # mapa aproximado cor "forte" -> versão clara, para o fundo do card
    tons_claros = {
        _hexstr(P["blue"]):   P["blue_lt"],
        _hexstr(P["green"]):  P["green_lt"],
        _hexstr(P["red"]):    P["red_lt"],
        _hexstr(P["amber"]):  P["amber_lt"],
        _hexstr(P["purple"]): P["purple_lt"],
        _hexstr(P["navy"]):   P["blue_lt"],
        _hexstr(P["muted"]):  P["gray_lt"],
    }

    n = len(items)
    gap = 2.5
    w = (PW - gap * (n - 1)) / n
    hdr = [
        Paragraph(_safe(label).upper(), ParagraphStyle("kh", fontName="Helvetica-Bold",
            fontSize=6.6, textColor=P["muted"], alignment=TA_CENTER, leading=8))
        for label, value, cor in items
    ]
    vals = [
        Paragraph(str(value), ParagraphStyle("kv", fontName="Helvetica-Bold",
            fontSize=19, textColor=cor, alignment=TA_CENTER, leading=22))
        for label, value, cor in items
    ]

    rows_flat = []
    col_widths = []
    for idx, (label, value, cor) in enumerate(items):
        col_widths.append(w)
        if idx < n - 1:
            col_widths.append(gap)

    hdr_row, val_row = [], []
    for idx in range(n):
        hdr_row.append(hdr[idx])
        val_row.append(vals[idx])
        if idx < n - 1:
            hdr_row.append("")
            val_row.append("")

    t = Table([hdr_row, val_row], colWidths=col_widths, rowHeights=[10, 16])
    cmds = [
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for idx, (label, value, cor) in enumerate(items):
        col = idx * 2
        cor_hex = _hexstr(cor)
        fundo = tons_claros.get(cor_hex, P["gray_lt"])
        cmds.append(("BACKGROUND", (col, 0), (col, 1), fundo))
        cmds.append(("BOX", (col, 0), (col, 1), 0.8, cor))
    t.setStyle(TableStyle(cmds))
    return t


def _fit_text(txt, font, size, max_width):
    """Corta o texto (com reticências) para caber em uma única linha na largura dada."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if stringWidth(txt, font, size) <= max_width:
        return txt
    while txt and stringWidth(txt + "…", font, size) > max_width:
        txt = txt[:-1]
    return (txt + "…") if txt else txt


def _status_card(nome, icone, texto, bg, fg, w, P):
    """Card de status arredondado (nome + ícone grande + texto), usado nas barras
    de progresso de lubrificação e de revisão."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    nome_fit = _fit_text(nome, "Helvetica-Bold", 7.2, w - 4)
    s_nome = ParagraphStyle("bcn", fontName="Helvetica-Bold", fontSize=7.2,
        textColor=fg, alignment=TA_CENTER, leading=8.6)
    s_ic = ParagraphStyle("bci", fontName="Helvetica-Bold", fontSize=13,
        textColor=fg, alignment=TA_CENTER, leading=15)
    s_tx = ParagraphStyle("bct", fontName="Helvetica", fontSize=6.4,
        textColor=fg, alignment=TA_CENTER, leading=7.8)
    card = Table(
        [[Paragraph(nome_fit, s_nome)], [Paragraph(icone, s_ic)], [Paragraph(texto, s_tx)]],
        colWidths=[w], rowHeights=[13, 16, 11],
    )
    card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
    ]))
    return card


def _cards_row(cards, PW):
    """Organiza uma lista de cards em uma única linha, com espaçamento entre eles."""
    from reportlab.platypus import Table, TableStyle
    n = len(cards)
    if n == 0:
        return None
    gap = 2.2
    w_card = (PW - gap * (n - 1)) / n if n > 1 else PW
    col_widths, linha = [], []
    for i, card in enumerate(cards):
        linha.append(card)
        col_widths.append(w_card)
        if i < n - 1:
            linha.append("")
            col_widths.append(gap)
    t = Table([linha], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
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
    equipamentos_progresso: list[dict],  # lista de dicts com etapas por equipamento
    data_ini,
    data_fim,
    setor_nome: str | None = None,
) -> bytes:
    """
    Relatório 2: Conformidade de revisões predefinidas.
    Para cada equipamento, exibe:
      - Leitura atual (KM/Horas)
      - Barra de progresso com cada etapa marcada como ✓ (feita), ✗ (vencida) ou ○ (futura)
      - Quanto falta para a próxima
      - Resumo geral de conformidade
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
            "Progresso de cada etapa de revisão por equipamento",
            f"Execuções: {periodo}   ·   Setor: {setor_txt}",
            gerado_em,
        )

    elements = []

    # ── KPIs de topo ───────────────────────────────────────────────────────
    total_itens    = len(equipamentos_progresso)
    itens_em_dia   = sum(1 for e in equipamentos_progresso if e.get("status_geral") == "EM_DIA")
    itens_vencidos = sum(1 for e in equipamentos_progresso if e.get("status_geral") == "VENCIDO")
    itens_proximos = sum(1 for e in equipamentos_progresso if e.get("status_geral") == "PROXIMO")
    pct_conf = round(itens_em_dia / max(total_itens, 1) * 100)
    total_rev = len(df_rev) if df_rev is not None and not df_rev.empty else 0

    elements.append(Spacer(1, 3 * mm))
    elements.append(_kpi_bar([
        ("Equipamentos",        total_itens,  P["navy"]),
        ("Revisões realizadas", total_rev,   P["blue"]),
        ("Em dia",              itens_em_dia,  P["green"]),
        ("Vencidos",            itens_vencidos, P["red"] if itens_vencidos > 0 else P["muted"]),
        ("Próximos",           itens_proximos, P["amber"] if itens_proximos > 0 else P["muted"]),
        ("Conformidade",        f"{pct_conf}%", P["green"] if pct_conf >= 80 else (P["amber"] if pct_conf >= 50 else P["red"])),
    ], P, PW))
    elements.append(Spacer(1, 3 * mm))

    # Barra de conformidade visual
    from reportlab.lib.styles import ParagraphStyle
    pct = pct_conf / 100
    cor_bar = P["green"] if pct_conf >= 80 else (P["amber"] if pct_conf >= 50 else P["red"])
    bar_preenche = max(PW * pct, 1)
    bar_vazia    = max(PW - bar_preenche, 0.5)
    bar_t = Table([["" , ""]], colWidths=[bar_preenche, bar_vazia], rowHeights=[5])
    bar_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), cor_bar),
        ("BACKGROUND", (1, 0), (1, 0), P["gray_mid"]),
        ("LEFTPADDING",  (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0), ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    elements.append(bar_t)
    s_conf_label = ParagraphStyle("cbl", fontName="Helvetica", fontSize=7.5, textColor=P["muted"], spaceAfter=4)
    elements.append(Paragraph(f"{pct_conf}% dos equipamentos estão em dia no ciclo atual.", s_conf_label))
    elements.append(Spacer(1, 4 * mm))

    # ── Progresso por equipamento ───────────────────────────────────────────────
    elements += _secao(
        "Progresso de revisões por equipamento",
        "Cada célula representa uma etapa do ciclo de revisão. ✓ = realizada  ◎ = próxima  ▶ = vencida  ○ = futura",
        styles, P,
    )

    s_eqp_hdr = ParagraphStyle("eh", fontName="Helvetica-Bold", fontSize=9,
        textColor=P["navy"], leading=12)
    s_eqp_sub = ParagraphStyle("es", fontName="Helvetica", fontSize=7.3,
        textColor=P["muted"], leading=10, spaceBefore=1)
    s_falta   = ParagraphStyle("fl", fontName="Helvetica", fontSize=7.5,
        textColor=P["muted"], leading=10)

    from reportlab.lib import colors

    if not equipamentos_progresso:
        elements.append(Paragraph("Nenhum equipamento com template de revisão configurado.",
            ParagraphStyle("em", fontName="Helvetica", fontSize=9, textColor=P["muted"], alignment=TA_CENTER)))
    else:
        for eqp in equipamentos_progresso:
            codigo   = _safe(eqp.get("codigo"))
            nome     = _safe(eqp.get("equipamento_nome"))
            setor_e  = _safe(eqp.get("setor_nome"))
            tipo_ctrl = _safe(eqp.get("tipo_controle", "km")).lower()
            unidade  = "h" if tipo_ctrl.startswith("h") else "km"
            leit_atu = float(eqp.get("leitura_atual", 0) or 0)
            etapas   = eqp.get("etapas", [])
            status_g = eqp.get("status_geral", "EM_DIA")

            # Próxima revisão
            prox = next((e for e in etapas if e.get("status") in ("VENCIDO", "PROXIMO")), None)
            if prox is None:
                prox = next((e for e in etapas if not e.get("realizado_no_ciclo")), None)
            prox_etapa = _safe(prox.get("etapa")) if prox else "-"
            prox_falta = float(prox.get("falta", 0) or 0) if prox else 0
            prox_venc  = float(prox.get("vencimento", 0) or 0) if prox else 0

            if status_g == "VENCIDO":
                cor_status, txt_status = P["red"], "▶ VENCIDO"
            elif status_g == "PROXIMO":
                cor_status, txt_status = P["amber"], "◎ PRÓXIMO"
            else:
                cor_status, txt_status = P["green"], "✓ EM DIA"

            bloco = []

            # Cabeçalho do equipamento: nome à esquerda, selo de status (pill) à direita
            pill_style = ParagraphStyle("pill", fontName="Helvetica-Bold", fontSize=7.5,
                textColor=colors.white, alignment=TA_CENTER, leading=9)
            pill = Table([[Paragraph(txt_status, pill_style)]], colWidths=[26 * mm], rowHeights=[6.5 * mm])
            pill.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), cor_status),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
            ]))

            hdr_txt = Table([[
                Paragraph(f"{codigo} — {nome}", s_eqp_hdr)
            ], [
                Paragraph(
                    f"Setor: {setor_e}  ·  Leitura atual: {_fmt_num(leit_atu)} {unidade}  ·  "
                    f"Próxima: {prox_etapa} em {_fmt_num(prox_venc)} {unidade}  ·  Faltam: {_fmt_num(abs(prox_falta))} {unidade}",
                    s_eqp_sub,
                )
            ]], colWidths=[PW * 0.82])
            hdr_txt.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))

            hdr_t = Table([[hdr_txt, pill]], colWidths=[PW * 0.82, PW * 0.18])
            hdr_t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
            ]))
            bloco.append(hdr_t)
            bloco.append(Spacer(1, 2 * mm))

            # Barra de progresso de etapas — cards arredondados com espaçamento
            if etapas:
                n_etapas = len(etapas)
                w_etapa = (PW - 2.2 * (n_etapas - 1)) / n_etapas if n_etapas > 1 else PW
                cards_etapa = []
                for etapa in etapas:
                    st   = str(etapa.get("status", "EM_DIA")).upper()
                    real = etapa.get("realizado_no_ciclo", False)
                    gate = float(etapa.get("gatilho_valor", 0) or 0)
                    nome_e = _safe(etapa.get("etapa"))
                    falta_e = float(etapa.get("falta", 0) or 0)
                    ult_exec = float(etapa.get("ultima_execucao", 0) or 0)

                    if real:
                        bg, fg, icone = P["green"], colors.white, "✓"
                        val_txt = f"feita em {_fmt_num(ult_exec)} {unidade}" if ult_exec > 0 else "realizada"
                    elif st == "VENCIDO":
                        bg, fg, icone = P["red"], colors.white, "▶"
                        val_txt = f"{_fmt_num(abs(falta_e))} {unidade} atraso"
                    elif st == "PROXIMO":
                        bg, fg, icone = P["amber"], colors.white, "◎"
                        val_txt = f"faltam {_fmt_num(abs(falta_e))} {unidade}"
                    else:
                        bg, fg, icone = P["gray_lt"], P["muted"], "○"
                        val_txt = f"faltam {_fmt_num(abs(falta_e))} {unidade}" if falta_e > 0 else "ótimo!"

                    lbl = nome_e if nome_e and nome_e != "-" else f"{_fmt_num(gate)} {unidade}"
                    cards_etapa.append(_status_card(lbl, icone, val_txt, bg, fg, w_etapa, P))

                bloco.append(_cards_row(cards_etapa, PW))
            else:
                bloco.append(Paragraph("Sem etapas configuradas no template deste equipamento.",
                    ParagraphStyle("nem", fontName="Helvetica", fontSize=8, textColor=P["muted"])))

            bloco.append(Spacer(1, 2.5 * mm))
            bloco.append(_hr(P, 0.5))
            elements.append(KeepTogether(bloco))

    # ── Tabela de revisões realizadas no período ─────────────────────────────────
    if df_rev is not None and not df_rev.empty:
        elements.append(PageBreak())
        elements += _secao(
            f"Revisões realizadas no período ({len(df_rev)} registro(s))",
            f"Execuções confirmadas entre {periodo}.",
            styles, P,
        )
        import re as _re
        ETAPA_RE = _re.compile(r"^Etapa:\s*(.+)$", _re.IGNORECASE | _re.MULTILINE)
        def _etapa_obs(obs):
            if not obs: return "-"
            m = ETAPA_RE.search(str(obs))
            return m.group(1).strip() if m else "-"

        df_r = df_rev.copy()
        obs_col = "Observações" if "Observações" in df_r.columns else None
        df_r["Etapa"] = df_r[obs_col].apply(_etapa_obs) if obs_col else "-"

        cols_rev = ["Data", "Código", "Equipamento", "Setor", "Etapa", "KM", "Horas", "Responsável"]
        cw_rev   = [18*mm, 16*mm, 30*mm, 28*mm, 38*mm, 14*mm, 14*mm, 22*mm]
        linhas_rev = []
        for _, r in df_r.sort_values(["Código", "Data"] if "Código" in df_r.columns else ["Data"],
                                     ascending=[True, False] if "Código" in df_r.columns else False).head(80).iterrows():
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

    elements.append(Spacer(1, 8 * mm))
    # Campo de assinatura
    s_ass = ParagraphStyle("ass", fontName="Helvetica", fontSize=8, textColor=P["muted"])
    ass_t = Table([
        [Paragraph("Responsável pela conferência:", s_ass), Paragraph("Data:", s_ass)],
        [Paragraph("_" * 60, s_ass), Paragraph("___/___/______", s_ass)],
    ], colWidths=[PW * 0.72, PW * 0.28])
    ass_t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "BOTTOM"), ("TOPPADDING", (0,0), (-1,-1), 4)]))
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
# RELATÓRIO — Resumo de serviços próximos por responsável (usado nos alertas)
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_resumo_responsavel(
    responsavel_nome: str,
    itens_criticos: list[dict],
    sem_pendencia: int,
    total_equipamentos: int,
    gerado_em: str | None = None,
) -> bytes:
    """PDF compacto com os serviços mais próximos/vencidos de TODOS os
    equipamentos de um responsável — anexo do resumo semanal (e do envio sob
    demanda), no lugar de mandar a ficha técnica inteira de cada máquina."""
    import io
    import datetime as _dt
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = _novo_doc(buf)
    styles = getSampleStyleSheet()
    P = _paleta()
    PW = doc.width
    gerado_em = gerado_em or _dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    vencidos = sum(1 for i in itens_criticos if not i.get("realizado") and str(i.get("status", "")).upper() == "VENCIDO")
    proximos = sum(1 for i in itens_criticos if not i.get("realizado") and str(i.get("status", "")).upper() == "PROXIMO")
    realizados = sum(1 for i in itens_criticos if i.get("realizado"))
    sem_base = len(itens_criticos) - vencidos - proximos - realizados

    elements = []
    elements += _secao(
        f"Serviços prioritários — {responsavel_nome}",
        "Itens vencidos, próximos e já realizados (com a próxima execução prevista) de todos os equipamentos sob sua responsabilidade, ordenados por urgência.",
        styles, P,
    )
    elements.append(_kpi_bar([
        ("Equipamentos", total_equipamentos, P["blue"]),
        ("Vencidos", vencidos, P["red"]),
        ("Próximos", proximos, P["amber"]),
        ("Sem base", sem_base, P["purple"]),
        ("Realizados", realizados, P["green"]),
        ("Em dia", sem_pendencia, P["muted"]),
    ], P, PW))
    elements.append(Spacer(1, 5 * mm))

    if not itens_criticos:
        elements.append(Paragraph(
            "✅ Nenhuma pendência — todos os itens de todos os equipamentos estão em dia.",
            ParagraphStyle("ok", fontName="Helvetica-Bold", fontSize=10, textColor=P["green"], alignment=TA_CENTER),
        ))
    else:
        TIPO_LABEL = {"revisao": "Revisão", "lubrificacao": "Lubrificação"}
        linhas = []
        for item in itens_criticos:
            status = str(item.get("status", "")).upper()
            realizado = bool(item.get("realizado"))
            unidade = item.get("unidade", "km")
            falta = float(item.get("falta", 0) or 0)
            atual = float(item.get("atual", 0) or 0)
            vencimento = float(item.get("vencimento", 0) or 0)
            tipo_txt = TIPO_LABEL.get(item.get("tipo"), "-")
            if realizado:
                cor, txt, status_txt = P["green"], f"próxima em {vencimento:.0f} {unidade}", "REALIZADA"
            elif status == "VENCIDO":
                cor, txt, status_txt = P["red"], f"{abs(falta):.0f} {unidade} atraso", status
            elif status == "PROXIMO":
                cor, txt, status_txt = P["amber"], f"faltam {falta:.0f} {unidade}", status
            else:
                cor, txt, status_txt = P["purple"], "1ª execução", status.replace("_", " ")
            venc_txt = f"{vencimento:.0f} {unidade}" if vencimento > 0 else "-"
            atual_txt = f"{atual:.0f} {unidade}" if atual > 0 else "-"
            linhas.append([
                item.get("equipamento", "-"),
                item.get("nome", "-"),
                tipo_txt,
                atual_txt,
                venc_txt,
                (txt, True, cor, TA_LEFT),
                (status_txt, True, cor, TA_LEFT),
            ])
        elements.append(_tabela_simples(
            ["Equipamento", "Item", "Tipo", "Atual", "Próxima", "Faltam", "Status"],
            linhas, P,
            [PW * 0.18, PW * 0.20, PW * 0.12, PW * 0.13, PW * 0.13, PW * 0.14, PW * 0.10],
        ))

    hdr = lambda c, d: _cabeçalho_padrao(
        c, d, "Resumo de Manutenção — Serviços Prioritários",
        f"{responsavel_nome}", f"{total_equipamentos} equipamento(s) sob responsabilidade", gerado_em,
    )
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

    # ── Linha do tempo das etapas de revisão ──────────────────────────────────
    if status_revisoes:
        concluidas = sum(1 for s in status_revisoes if s.get("realizado_no_ciclo"))
        elements += _secao(
            "Linha do tempo das etapas",
            f"{concluidas} de {len(status_revisoes)} etapa(s) já concluída(s) neste ciclo — as demais aparecem na ordem em que vencem.",
            styles, P,
        )
        itens_tl = sorted(
            status_revisoes,
            key=lambda s: float(s.get("vencimento_ciclo") or s.get("gatilho_valor") or s.get("vencimento") or 0),
        )
        tl_drawing = _linha_tempo_etapas(itens_tl, P, PW)
        if tl_drawing:
            elements.append(tl_drawing)
        elements.append(Spacer(1, 2 * mm))

    # ── Status atual das revisões ─────────────────────────────────────────────
    elements += _secao(
        "Status atual das revisões",
        "Situação de cada etapa de revisão predefinida no ciclo atual.",
        styles, P,
    )
    if status_revisoes:
        linhas_sr = []
        for s in status_revisoes:
            realizado = bool(s.get("realizado_no_ciclo", False))
            ult_exec  = float(s.get("ultima_execucao", 0) or 0)
            unidade   = _safe(s.get("unidade", "km"))
            st = str(s.get("status", "")).upper()

            if realizado:
                # Etapa já executada no ciclo atual
                cor_st, txt_st = P["green"], "✓ REALIZADA"
                falta_txt = f"Realizada em {_fmt_num(ult_exec)} {unidade}" if ult_exec > 0 else "Realizada neste ciclo"
            elif st == "VENCIDO":
                cor_st, txt_st = P["red"], "VENCIDO"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"{abs(falta_v):.0f} {unidade} atraso"
            elif st == "PROXIMO":
                cor_st, txt_st = P["amber"], "PRÓXIMO"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"Faltam {abs(falta_v):.0f} {unidade}"
            else:
                cor_st, txt_st = P["green"], "EM DIA"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"Faltam {abs(falta_v):.0f} {unidade}"

            linhas_sr.append([
                _safe(s.get("etapa") or s.get("nome_etapa")),
                _safe(s.get("tipo_controle", "km")).upper(),
                _fmt_num(s.get("atual")),
                _fmt_num(s.get("vencimento")),
                (txt_st, True, cor_st, TA_CENTER),
                falta_txt,
            ])
        elements.append(_tabela_simples(
            ["Etapa", "Controle", "Leitura atual", "Vencimento", "Status", "Situação"],
            linhas_sr, P, [52*mm, 18*mm, 22*mm, 22*mm, 22*mm, 20*mm],
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
        from reportlab.lib import colors as _colors

        n_lub = len(status_lubrificacoes)
        w_lub = (PW - 2.2 * (n_lub - 1)) / n_lub if n_lub > 1 else PW

        cards_lub = []
        for i, s in enumerate(status_lubrificacoes):
            realizado  = bool(s.get("realizado_no_ciclo", False))
            ult_exec   = float(s.get("ultima_execucao", 0) or 0)
            unidade    = _safe(s.get("unidade", "km"))
            st_lub     = str(s.get("status", "")).upper()
            falta_lub  = float(s.get("diferenca", 0) or 0)
            nome_lub   = _safe(s.get("item") or s.get("nome_item"))

            if realizado:
                bg_lub, fg_lub, icone_lub = P["green"], _colors.white, "✓"
                val_lub = f"feita em {_fmt_num(ult_exec)} {unidade}" if ult_exec > 0 else "realizada"
            elif st_lub == "VENCIDO":
                bg_lub, fg_lub, icone_lub = P["red"], _colors.white, "▶"
                val_lub = f"{_fmt_num(abs(falta_lub))} {unidade} atraso"
            elif st_lub == "PROXIMO":
                bg_lub, fg_lub, icone_lub = P["amber"], _colors.white, "◎"
                val_lub = f"faltam {_fmt_num(abs(falta_lub))} {unidade}"
            elif st_lub in ("SEM_BASE", "SEM BASE"):
                bg_lub, fg_lub, icone_lub = P["purple"], _colors.white, "★"
                val_lub = "1ª troca"
            else:
                bg_lub, fg_lub, icone_lub = P["gray_lt"], P["muted"], "○"
                val_lub = f"faltam {_fmt_num(abs(falta_lub))} {unidade}" if falta_lub > 0 else "em dia"

            nome_exib = nome_lub if nome_lub and nome_lub != "-" else f"{i+1}º item"
            cards_lub.append(_status_card(nome_exib, icone_lub, val_lub, bg_lub, fg_lub, w_lub, P))

        elements.append(_cards_row(cards_lub, PW))
        elements.append(Spacer(1, 3.5 * mm))

        # ── Tabela detalhada de status ────────────────────────────────────────
        linhas_sl = []
        for s in status_lubrificacoes:
            realizado = bool(s.get("realizado_no_ciclo", False))
            ult_exec  = float(s.get("ultima_execucao", 0) or 0)
            unidade   = _safe(s.get("unidade", "km"))
            st = str(s.get("status", "")).upper()

            if realizado:
                cor_st, txt_st = P["green"], "✓ REALIZADA"
                falta_txt = f"Realizada em {_fmt_num(ult_exec)} {unidade}" if ult_exec > 0 else "Realizada neste ciclo"
            elif st == "VENCIDO":
                cor_st, txt_st = P["red"], "VENCIDO"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"{abs(falta_v):.0f} {unidade} atraso"
            elif st == "PROXIMO":
                cor_st, txt_st = P["amber"], "PRÓXIMO"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"Faltam {abs(falta_v):.0f} {unidade}"
            elif st in ("SEM_BASE", "SEM BASE"):
                cor_st, txt_st = P["purple"], "SEM BASE"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"Agendar 1ª troca — faltam {abs(falta_v):.0f} {unidade}" if falta_v > 0 else "Agendar 1ª troca"
            else:
                cor_st, txt_st = P["green"], "EM DIA"
                falta_v   = float(s.get("diferenca") or 0)
                falta_txt = f"Faltam {abs(falta_v):.0f} {unidade}"

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
            ["Item", "Produto", "Controle", "Atual", "Vencimento", "Status", "Situação"],
            linhas_sl, P, [38*mm, 26*mm, 15*mm, 17*mm, 19*mm, 22*mm, 19*mm],
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
