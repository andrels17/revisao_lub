"""
Utilitários de exportação para Excel e PDF.
Uso:
- from ui.exportacao import botao_exportar_excel
- from ui.exportacao import botao_exportar_pdf_relatorio_manutencao
"""
import io
import datetime
import pandas as pd
import streamlit as st


def _normalizar_valor_excel(valor):
    if isinstance(valor, pd.Timestamp):
        return valor.tz_localize(None) if valor.tzinfo else valor
    if isinstance(valor, datetime.datetime):
        return valor.replace(tzinfo=None) if valor.tzinfo else valor
    return valor


def _normalizar_dataframe_excel(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    base = df.copy()
    for coluna in base.columns:
        serie = base[coluna]
        if pd.api.types.is_datetime64tz_dtype(serie):
            base[coluna] = serie.dt.tz_localize(None)
            continue
        if pd.api.types.is_object_dtype(serie):
            base[coluna] = serie.map(_normalizar_valor_excel)
    return base


def _df_para_excel(df: pd.DataFrame) -> bytes:
    df_excel = _normalizar_dataframe_excel(df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_excel.to_excel(writer, index=False, sheet_name="Dados")
        ws = writer.sheets["Dados"]
        for col_idx, col in enumerate(df_excel.columns, 1):
            max_len = max(len(str(col)), df_excel[col].astype(str).str.len().max() if not df_excel.empty else 0)
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = min(max_len + 4, 60)
    return buf.getvalue()


def botao_exportar_excel(df: pd.DataFrame, nome_arquivo: str, label: str = "⬇️ Exportar Excel", key: str = None):
    if df is None or df.empty:
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{nome_arquivo}_{ts}.xlsx"
    excel_bytes = _df_para_excel(df)
    st.download_button(
        label=label,
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key or f"export_{nome_arquivo}_{ts}",
    )


def _pdf_bytes_painel_360(equipamento: dict, saude: dict, pendencias: list[dict], insights: list[str], comentarios: list[dict]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError("Biblioteca reportlab não instalada. Adicione reportlab ao requirements.txt.") from exc

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _w, h = A4
    y = h - 20 * mm

    def line(txt: str, size: int = 10, bold: bool = False, gap: int = 6):
        nonlocal y
        if y < 18 * mm:
            c.showPage()
            y = h - 20 * mm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(15 * mm, y, str(txt)[:120])
        y -= gap * mm

    line("Painel 360° do Equipamento", 15, True, 8)
    line(f"Equipamento: {equipamento.get('codigo', '-')} - {equipamento.get('nome', '-')}", 11, True)
    line(f"Setor: {equipamento.get('setor_nome') or '-'} | Tipo: {equipamento.get('tipo') or '-'}")
    line(f"KM atual: {float(equipamento.get('km_atual') or 0):.0f} | Horas atuais: {float(equipamento.get('horas_atual') or 0):.0f}")
    line(f"Saúde: {saude.get('faixa')} ({saude.get('score')}%)")
    line("")
    line("Leitura gerencial", 12, True)
    for item in insights[:6]:
        line(f"- {item}")
    line("")
    line("Pendências prioritárias", 12, True)
    if pendencias:
        for p in pendencias[:12]:
            line(
                f"- {p.get('origem')}: {p.get('item')} | {p.get('status')} | atual {float(p.get('atual') or 0):.0f} | ref {float(p.get('referencia') or 0):.0f}"
            )
    else:
        line("- Sem pendências vencidas ou próximas.")
    line("")
    line("Comentários recentes", 12, True)
    if comentarios:
        for cmt in comentarios[:10]:
            autor = cmt.get("autor_nome") or "Usuário"
            data = str(cmt.get("created_at") or "-")[:19]
            line(f"- {data} | {autor}: {(cmt.get('comentario') or '')[:90]}")
    else:
        line("- Nenhum comentário registrado.")

    c.save()
    return buf.getvalue()


def botao_exportar_pdf_painel360(
    equipamento: dict,
    saude: dict,
    pendencias: list[dict],
    insights: list[str],
    comentarios: list[dict],
    key: str | None = None,
):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    nome = f"painel_360_{equipamento.get('codigo', 'equipamento')}_{ts}.pdf"
    pdf_bytes = _pdf_bytes_painel_360(equipamento, saude, pendencias, insights, comentarios)
    st.download_button(
        label="⬇️ PDF do Painel 360°",
        data=pdf_bytes,
        file_name=nome,
        mime="application/pdf",
        key=key or f"pdf_painel360_{equipamento.get('id', '')}_{ts}",
    )


def _safe_text(value, default="-") -> str:
    if value is None:
        return default
    txt = str(value).strip()
    return txt if txt else default


def _safe_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
    except Exception:
        pass
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _fmt_atraso_pdf(valor, controle: str) -> str:
    try:
        valor = max(float(valor or 0), 0.0)
    except Exception:
        valor = 0.0
    sufixo = "h" if str(controle).lower().startswith("h") else "km"
    return f"{valor:,.0f} {sufixo}".replace(",", ".")


def _dataframe_para_tabela(df: pd.DataFrame, max_rows: int = 30) -> list[list[str]]:
    if df is None or df.empty:
        return []
    base = df.copy().head(max_rows).fillna("-")
    cols = [str(c) for c in base.columns.tolist()]
    rows = [[_safe_text(v) for v in row] for row in base.astype(str).values.tolist()]
    return [cols] + rows


def _pdf_bytes_relatorio_manutencao(
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    setor_nome=None,
    equipamento_nome=None,
    setor_id=None,
    equipamento_id=None,
) -> bytes:
    # ── imports ──────────────────────────────────────────────────────────────
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, PageBreak, HRFlowable, KeepTogether,
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    except Exception as exc:
        raise RuntimeError("Biblioteca reportlab não instalada.") from exc

    from ui.relatorio_page import (
        _enriquecer_macro_revisoes,
        _enriquecer_macro_lubrificacoes,
        _resumir_macro,
    )
    from services import prioridades_service

    # ── paleta ───────────────────────────────────────────────────────────────
    C_NAVY     = colors.HexColor("#0f2744")
    C_BLUE     = colors.HexColor("#1a56a0")
    C_BLUE_LT  = colors.HexColor("#dbeafe")
    C_GREEN    = colors.HexColor("#166534")
    C_GREEN_LT = colors.HexColor("#dcfce7")
    C_RED      = colors.HexColor("#991b1b")
    C_RED_LT   = colors.HexColor("#fee2e2")
    C_GRAY     = colors.HexColor("#374151")
    C_GRAY_LT  = colors.HexColor("#f9fafb")
    C_GRAY_MID = colors.HexColor("#e5e7eb")
    C_MUTED    = colors.HexColor("#6b7280")
    C_WHITE    = colors.white
    C_AMBER    = colors.HexColor("#92400e")
    C_AMBER_LT = colors.HexColor("#fef3c7")
    C_STRIPE   = colors.HexColor("#f1f5f9")

    # ── estilos ──────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def S(name, **kw):
        base = kw.pop("parent", styles["Normal"])
        return ParagraphStyle(name, parent=base, **kw)

    s_title    = S("T", fontName="Helvetica-Bold", fontSize=20, textColor=C_WHITE, leading=24)
    s_subtitle = S("ST", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#bfdbfe"), leading=13)
    s_meta     = S("MT", fontName="Helvetica", fontSize=8, textColor=C_MUTED, leading=11)
    s_sec      = S("SC", fontName="Helvetica-Bold", fontSize=10, textColor=C_NAVY, leading=13, spaceBefore=4)
    s_sec_desc = S("SD", fontName="Helvetica", fontSize=8, textColor=C_MUTED, leading=11, spaceAfter=4)
    s_body     = S("BD", fontName="Helvetica", fontSize=8, textColor=C_GRAY, leading=11)
    s_empty    = S("EM", fontName="Helvetica", fontSize=8, textColor=C_MUTED, leading=11, alignment=TA_CENTER)
    s_footer   = S("FT", fontName="Helvetica", fontSize=7, textColor=C_MUTED)
    s_tbl_sub  = S("TS", fontName="Helvetica-Bold", fontSize=8, textColor=C_NAVY, spaceAfter=2, spaceBefore=6)

    # ── dados ────────────────────────────────────────────────────────────────
    df_rev = df_rev if df_rev is not None else pd.DataFrame()
    df_lub = df_lub if df_lub is not None else pd.DataFrame()
    df_rev_macro = _enriquecer_macro_revisoes(df_rev)
    df_lub_macro = _enriquecer_macro_lubrificacoes(df_lub)
    resumo_rev   = _resumir_macro(df_rev_macro, "rev")
    resumo_lub   = _resumir_macro(df_lub_macro, "lub")

    total_reg  = len(df_rev) + len(df_lub)
    total_rev  = len(df_rev)
    total_lub  = len(df_lub)
    total_eqp  = len(set(
        df_rev.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist() +
        df_lub.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist()
    ))
    no_prazo_rev   = int(resumo_rev["No prazo"].sum()) if not resumo_rev.empty else 0
    atrasadas_rev  = int(resumo_rev["Atrasadas"].sum()) if not resumo_rev.empty else 0
    no_prazo_lub   = int(resumo_lub["No prazo"].sum()) if not resumo_lub.empty else 0
    atrasadas_lub  = int(resumo_lub["Atrasadas"].sum()) if not resumo_lub.empty else 0

    periodo    = f"{pd.to_datetime(data_ini).strftime('%d/%m/%Y')} a {pd.to_datetime(data_fim).strftime('%d/%m/%Y')}"
    gerado_em  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    setor_txt  = _safe_text(setor_nome, "Todos")
    eqp_txt    = _safe_text(equipamento_nome, "Todos")
    sem_mov = prioridades_service.resumo_sem_movimentacao(setor_id=setor_id, equipamento_id=equipamento_id, limite=10)
    sem_mov_qtd = int(sem_mov.get("quantidade", 0))
    sem_mov_threshold = int(sem_mov.get("threshold", 0))
    sem_mov_top10 = pd.DataFrame(sem_mov.get("top10") or [])

    # ── helpers ──────────────────────────────────────────────────────────────
    PW = A4[0] - 24 * mm   # usable width

    def hr(thickness=0.5, color=C_GRAY_MID):
        return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=4, spaceBefore=4)

    def section_header(title: str, desc: str = "") -> list:
        elems = [hr(1, C_NAVY), Paragraph(title, s_sec)]
        if desc:
            elems.append(Paragraph(desc, s_sec_desc))
        return elems

    def kpi_table(items: list[tuple]) -> Table:
        """items = [(label, value, color_bg, color_txt), ...]"""
        n = len(items)
        w = PW / n
        header_row = [Paragraph(lbl, S(f"kh{i}", fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)) for i, (lbl, _, _, _) in enumerate(items)]
        value_row  = [Paragraph(str(val), S(f"kv{i}", fontName="Helvetica-Bold", fontSize=18, textColor=ctxt, alignment=TA_CENTER)) for i, (_, val, _, ctxt) in enumerate(items)]
        t = Table([header_row, value_row], colWidths=[w] * n, rowHeights=[10 * mm, 14 * mm])
        style_cmds = [
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0,0), (-1, -1), 4),
            ("LINEBELOW",   (0, 1), (-1, 1), 0.5, C_GRAY_MID),
        ]
        for i, (_, _, cbg, _) in enumerate(items):
            if cbg:
                style_cmds += [
                    ("BACKGROUND", (i, 0), (i, 1), cbg),
                    ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ]
            if i > 0:
                style_cmds.append(("LINEAFTER", (i - 1, 0), (i - 1, 1), 0.5, C_GRAY_MID))
        t.setStyle(TableStyle(style_cmds))
        return t

    def quant_table(resumo: pd.DataFrame, col_etapa: str, hdr_color, lt_color) -> Table | None:
        if resumo is None or resumo.empty:
            return None
        agg = (
            resumo.groupby(["Departamento", "Grupo", "Tipo", col_etapa, "Referência"], dropna=False)
            .agg(Total=("Execuções", "sum"), NoPrazo=("No prazo", "sum"), Atrasadas=("Atrasadas", "sum"))
            .reset_index()
        )
        total_g    = int(agg["Total"].sum())
        prazo_g    = int(agg["NoPrazo"].sum())
        atras_g    = int(agg["Atrasadas"].sum())
        pct_g      = f"{round(prazo_g / total_g * 100)}%" if total_g > 0 else "—"

        def P(txt, **kw):
            return Paragraph(_safe_text(txt), S("_", fontName=kw.get("fn","Helvetica"), fontSize=kw.get("fs",7.5), textColor=kw.get("tc", C_GRAY), alignment=kw.get("al", TA_LEFT), leading=10))

        hdr = [P("Departamento", fn="Helvetica-Bold", tc=C_WHITE),
               P("Grupo", fn="Helvetica-Bold", tc=C_WHITE),
               P("Tipo", fn="Helvetica-Bold", tc=C_WHITE),
               P(col_etapa, fn="Helvetica-Bold", tc=C_WHITE),
               P("Referência", fn="Helvetica-Bold", tc=C_WHITE),
               P("Total", fn="Helvetica-Bold", tc=C_WHITE, al=TA_CENTER),
               P("No prazo", fn="Helvetica-Bold", tc=C_WHITE, al=TA_CENTER),
               P("Atrasadas", fn="Helvetica-Bold", tc=C_WHITE, al=TA_CENTER),
               P("% prazo", fn="Helvetica-Bold", tc=C_WHITE, al=TA_CENTER)]

        rows = [hdr]
        for _, r in agg.iterrows():
            pct = round(r["NoPrazo"] / r["Total"] * 100) if r["Total"] > 0 else 0
            pct_s = f"{pct}%"
            pct_c = C_GREEN if pct == 100 else (C_AMBER if pct >= 50 else C_RED)
            rows.append([
                P(r["Departamento"]),
                P(r["Grupo"]),
                P(r["Tipo"]),
                P(r[col_etapa]),
                P(r["Referência"]),
                P(str(int(r["Total"])), al=TA_CENTER),
                P(str(int(r["NoPrazo"])), tc=C_GREEN, fn="Helvetica-Bold", al=TA_CENTER),
                P(str(int(r["Atrasadas"])), tc=C_RED, fn="Helvetica-Bold", al=TA_CENTER),
                P(pct_s, tc=pct_c, fn="Helvetica-Bold", al=TA_CENTER),
            ])

        # rodapé totais
        rows.append([
            P("Total geral", fn="Helvetica-Bold", tc=C_NAVY),
            P(""), P(""), P(""), P(""),
            P(str(total_g), fn="Helvetica-Bold", al=TA_CENTER),
            P(str(prazo_g), fn="Helvetica-Bold", tc=C_GREEN, al=TA_CENTER),
            P(str(atras_g), fn="Helvetica-Bold", tc=C_RED, al=TA_CENTER),
            P(pct_g, fn="Helvetica-Bold", tc=(C_GREEN if prazo_g == total_g else C_RED), al=TA_CENTER),
        ])

        cw = [38*mm, 28*mm, 18*mm, 32*mm, 22*mm, 13*mm, 15*mm, 16*mm, 14*mm]
        n  = len(rows)
        stripe_cmds = []
        for i in range(1, n - 1):
            bg = C_STRIPE if i % 2 == 0 else C_WHITE
            stripe_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        t = Table(rows, colWidths=cw, repeatRows=1)
        t.setStyle(TableStyle([
            # cabeçalho
            ("BACKGROUND",    (0, 0), (-1, 0), hdr_color),
            ("LINEBELOW",     (0, 0), (-1, 0), 1, colors.HexColor("#1e40af") if hdr_color == C_BLUE else C_GREEN),
            # listras
            *stripe_cmds,
            # linha de total
            ("BACKGROUND",    (0, n-1), (-1, n-1), lt_color),
            ("LINEABOVE",     (0, n-1), (-1, n-1), 1, C_GRAY_MID),
            ("LINEBELOW",     (0, n-1), (-1, n-1), 0.5, C_GRAY_MID),
            # grid leve
            ("INNERGRID",     (0, 1), (-1, n-2), 0.3, C_GRAY_MID),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_MID),
            # padding
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    def detail_table(df: pd.DataFrame, cols: list[str], hdr_color, col_widths: list) -> Table | None:
        if df is None or df.empty:
            return None
        base = df.copy().head(50)

        def P(txt, bold=False, color=C_GRAY, align=TA_LEFT):
            return Paragraph(_safe_text(txt), S("_d", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=7, textColor=color, alignment=align, leading=9))

        hdr = [P(c, bold=True, color=C_WHITE) for c in cols]
        rows = [hdr]
        for _, r in base.iterrows():
            row_data = []
            for c in cols:
                val = r.get(c, "-")
                if c == "Prazo":
                    color = C_RED if str(val) == "Atrasada" else C_GREEN
                    row_data.append(P(str(val), color=color, bold=True))
                elif c in ("Atraso",):
                    color = C_RED if str(val) not in ("-", "0 km", "0 h") else C_MUTED
                    row_data.append(P(str(val), color=color))
                else:
                    row_data.append(P(str(val) if pd.notna(val) else "-"))
            rows.append(row_data)

        n = len(rows)
        stripe_cmds = [("BACKGROUND", (0, i), (-1, i), C_STRIPE if i % 2 == 0 else C_WHITE) for i in range(1, n)]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), hdr_color),
            ("LINEBELOW",     (0, 0), (-1, 0), 1, C_NAVY),
            *stripe_cmds,
            ("INNERGRID",     (0, 1), (-1, -1), 0.3, C_GRAY_MID),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_MID),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    # ── montagem ─────────────────────────────────────────────────────────────
    buffer = io.BytesIO()

    def _header_footer(canvas_obj, doc):
        canvas_obj.saveState()
        w, h = A4
        # Faixa de cabeçalho azul escuro
        canvas_obj.setFillColor(C_NAVY)
        canvas_obj.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
        # Faixa decorativa azul médio (linha fina)
        canvas_obj.setFillColor(C_BLUE)
        canvas_obj.rect(0, h - 29.5 * mm, w, 1.5 * mm, fill=1, stroke=0)
        # Título
        canvas_obj.setFillColor(C_WHITE)
        canvas_obj.setFont("Helvetica-Bold", 16)
        canvas_obj.drawString(12 * mm, h - 14 * mm, "Relatório de manutenção")
        # Subtítulo
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#bfdbfe"))
        canvas_obj.drawString(12 * mm, h - 20 * mm, f"Período: {periodo}   ·   Setor: {setor_txt}   ·   Equipamento: {eqp_txt}")
        canvas_obj.drawString(12 * mm, h - 25 * mm, f"Gerado em {gerado_em}")
        # Rodapé
        canvas_obj.setFillColor(C_MUTED)
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.drawString(12 * mm, 8 * mm, "Relatório de manutenção — padrão SaaS")
        canvas_obj.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")
        canvas_obj.setStrokeColor(C_GRAY_MID)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(12 * mm, 11 * mm, w - 12 * mm, 11 * mm)
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=34 * mm,
        bottomMargin=16 * mm,
    )

    elements = []

    # ── KPIs ─────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 3 * mm))
    kpi_items = [
        ("Total de registros", total_reg,  None,       C_NAVY),
        ("Revisões",           total_rev,  None,       C_BLUE),
        ("Lubrificações",      total_lub,  None,       C_GREEN),
        ("Equipamentos",       total_eqp,  None,       C_GRAY),
        ("Sem movimentação",   sem_mov_qtd, None,      C_AMBER),
    ]
    elements.append(kpi_table(kpi_items))
    elements.append(Spacer(1, 4 * mm))

    # ── Quantitativo por departamento ────────────────────────────────────────
    elements += section_header(
        "Quantitativo por departamento",
        "Visão executiva de execuções realizadas no período, por departamento, grupo e etapa — com status de prazo.",
    )

    has_quant = False
    tq_rev = quant_table(resumo_rev, "Etapa", C_BLUE, C_BLUE_LT)
    if tq_rev:
        has_quant = True
        elements.append(Paragraph("Revisões", s_tbl_sub))
        elements.append(tq_rev)
        elements.append(Spacer(1, 4 * mm))

    tq_lub = quant_table(resumo_lub, "Item", colors.HexColor("#166534"), C_GREEN_LT)
    if tq_lub:
        has_quant = True
        elements.append(Paragraph("Lubrificações", S("ls", fontName="Helvetica-Bold", fontSize=8, textColor=C_GREEN, spaceAfter=2, spaceBefore=6)))
        elements.append(tq_lub)
        elements.append(Spacer(1, 4 * mm))

    if not has_quant:
        elements.append(Paragraph("Sem dados no período selecionado.", s_empty))
        elements.append(Spacer(1, 4 * mm))

    if sem_mov_qtd > 0:
        elements += section_header(
            "Sem movimentação / sem leitura",
            f"Equipamentos acima da janela configurada de {sem_mov_threshold} dia(s) sem atualização de KM/Horas.",
        )
        if not sem_mov_top10.empty:
            cols = [c for c in ["Equipamento", "Setor", "Dias sem leitura", "Última leitura"] if c in sem_mov_top10.columns]
            sm_rows = _dataframe_para_tabela(sem_mov_top10[cols], max_rows=10)
            if sm_rows:
                sm_tbl = Table(sm_rows, repeatRows=1, colWidths=[PW * 0.40, PW * 0.22, PW * 0.18, PW * 0.20])
                sm_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), C_AMBER),
                    ("TEXTCOLOR", (0,0), (-1,0), C_WHITE),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 7),
                    ("GRID", (0,0), (-1,-1), 0.25, C_GRAY_MID),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_STRIPE]),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ]))
                elements.append(sm_tbl)
                elements.append(Spacer(1, 4 * mm))

    # ── Macro revisões ───────────────────────────────────────────────────────
    elements += section_header(
        "Macro de revisões realizadas",
        "Visão por departamento, grupo, tipo de equipamento e etapa, com atraso médio e maior atraso.",
    )
    if resumo_rev.empty:
        elements.append(Paragraph("Sem dados de revisão no período selecionado.", s_empty))
    else:
        rev_pdf = resumo_rev.copy()
        for c in ["Equipamentos", "Execuções", "No prazo", "Atrasadas"]:
            rev_pdf[c] = rev_pdf[c].apply(_safe_int)

        def P(txt, bold=False, color=C_GRAY, align=TA_LEFT):
            return Paragraph(_safe_text(txt), S("_m", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=7, textColor=color, alignment=align, leading=9))

        mac_hdr = [P(c, bold=True, color=C_WHITE) for c in rev_pdf.columns]
        mac_rows = [mac_hdr]
        for _, r in rev_pdf.iterrows():
            row_d = []
            for ci, c in enumerate(rev_pdf.columns):
                val = _safe_text(r[c])
                if c == "Atrasadas":
                    row_d.append(P(val, color=C_RED if int(r[c] or 0) > 0 else C_GREEN, bold=True, align=TA_CENTER))
                elif c == "No prazo":
                    row_d.append(P(val, color=C_GREEN, bold=True, align=TA_CENTER))
                elif c in ("Execuções", "Equipamentos"):
                    row_d.append(P(val, align=TA_CENTER))
                else:
                    row_d.append(P(val))
            mac_rows.append(row_d)

        n = len(mac_rows)
        stripe_cmds = [("BACKGROUND", (0, i), (-1, i), C_STRIPE if i % 2 == 0 else C_WHITE) for i in range(1, n)]
        cw_mac = [28*mm, 25*mm, 18*mm, 28*mm, 18*mm, 13*mm, 13*mm, 13*mm, 13*mm, 19*mm, 19*mm]
        # ajuste se tiver menos colunas
        while len(cw_mac) > len(rev_pdf.columns):
            cw_mac.pop()
        while len(cw_mac) < len(rev_pdf.columns):
            cw_mac.append(18*mm)

        mac_t = Table(mac_rows, colWidths=cw_mac, repeatRows=1)
        mac_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), C_BLUE),
            ("LINEBELOW",     (0, 0), (-1, 0), 1, colors.HexColor("#1e40af")),
            *stripe_cmds,
            ("INNERGRID",     (0, 1), (-1, -1), 0.3, C_GRAY_MID),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_MID),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(mac_t)

    elements.append(Spacer(1, 5 * mm))

    # ── Macro lubrificações ──────────────────────────────────────────────────
    elements += section_header(
        "Macro de lubrificações realizadas",
        "Consolidado por item, intervalo e tipo de equipamento, com leitura de prazo versus atraso.",
    )
    if resumo_lub.empty:
        elements.append(Paragraph("Sem dados de lubrificação no período selecionado.", s_empty))
    else:
        lub_pdf = resumo_lub.copy()
        for c in ["Equipamentos", "Execuções", "No prazo", "Atrasadas"]:
            lub_pdf[c] = lub_pdf[c].apply(_safe_int)

        def Pl(txt, bold=False, color=C_GRAY, align=TA_LEFT):
            return Paragraph(_safe_text(txt), S("_ml", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=7, textColor=color, alignment=align, leading=9))

        mac_hdr_l = [Pl(c, bold=True, color=C_WHITE) for c in lub_pdf.columns]
        mac_rows_l = [mac_hdr_l]
        for _, r in lub_pdf.iterrows():
            row_d = []
            for c in lub_pdf.columns:
                val = _safe_text(r[c])
                if c == "Atrasadas":
                    row_d.append(Pl(val, color=C_RED if int(r[c] or 0) > 0 else C_GREEN, bold=True, align=TA_CENTER))
                elif c == "No prazo":
                    row_d.append(Pl(val, color=C_GREEN, bold=True, align=TA_CENTER))
                elif c in ("Execuções", "Equipamentos"):
                    row_d.append(Pl(val, align=TA_CENTER))
                else:
                    row_d.append(Pl(val))
            mac_rows_l.append(row_d)

        n = len(mac_rows_l)
        stripe_cmds_l = [("BACKGROUND", (0, i), (-1, i), C_STRIPE if i % 2 == 0 else C_WHITE) for i in range(1, n)]
        cw_mac_l = [28*mm, 25*mm, 18*mm, 28*mm, 18*mm, 13*mm, 13*mm, 13*mm, 13*mm, 19*mm, 19*mm]
        while len(cw_mac_l) > len(lub_pdf.columns):
            cw_mac_l.pop()
        while len(cw_mac_l) < len(lub_pdf.columns):
            cw_mac_l.append(18*mm)

        mac_t_l = Table(mac_rows_l, colWidths=cw_mac_l, repeatRows=1)
        mac_t_l.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#166534")),
            ("LINEBELOW",     (0, 0), (-1, 0), 1, C_GREEN),
            *stripe_cmds_l,
            ("INNERGRID",     (0, 1), (-1, -1), 0.3, C_GRAY_MID),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_MID),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(mac_t_l)

    # ── Detalhamento ─────────────────────────────────────────────────────────
    if not df_rev.empty or not df_lub.empty:
        elements.append(PageBreak())
        elements += section_header("Detalhamento resumido", "Registro individual de cada execução no período.")

        if not df_rev.empty:
            elements.append(Paragraph("Revisões", s_tbl_sub))
            rev_det = df_rev_macro.copy()
            if "Data" in rev_det.columns:
                rev_det["Data"] = pd.to_datetime(rev_det["Data"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "Atraso" in rev_det.columns:
                rev_det["Atraso"] = rev_det.apply(lambda r: _fmt_atraso_pdf(r.get("Atraso"), r.get("Controle", "km")), axis=1)
            cols_d = [c for c in ["Data", "Código", "Equipamento", "Setor", "Etapa", "Referência", "Prazo", "Atraso", "Responsável", "Status"] if c in rev_det.columns]
            cw_d = [16*mm, 12*mm, 28*mm, 26*mm, 28*mm, 18*mm, 16*mm, 14*mm, 20*mm, 18*mm]
            while len(cw_d) > len(cols_d): cw_d.pop()
            td = detail_table(rev_det[cols_d], cols_d, C_BLUE, cw_d)
            if td:
                elements.append(td)
                elements.append(Spacer(1, 4 * mm))

        if not df_lub.empty:
            elements.append(Paragraph("Lubrificações", S("lss", fontName="Helvetica-Bold", fontSize=8, textColor=C_GREEN, spaceAfter=2, spaceBefore=4)))
            lub_det = df_lub_macro.copy()
            if "Data" in lub_det.columns:
                lub_det["Data"] = pd.to_datetime(lub_det["Data"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "Atraso" in lub_det.columns:
                lub_det["Atraso"] = lub_det.apply(lambda r: _fmt_atraso_pdf(r.get("Atraso"), r.get("Controle", "km")), axis=1)
            cols_l = [c for c in ["Data", "Código", "Equipamento", "Setor", "Item", "Referência", "Prazo", "Atraso", "Responsável"] if c in lub_det.columns]
            cw_l = [16*mm, 12*mm, 28*mm, 26*mm, 30*mm, 18*mm, 16*mm, 14*mm, 20*mm]
            while len(cw_l) > len(cols_l): cw_l.pop()
            tl = detail_table(lub_det[cols_l], cols_l, colors.HexColor("#166534"), cw_l)
            if tl:
                elements.append(tl)

    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


def _pdf_bytes_relatorio_manutencao_OLD(
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    setor_nome=None,
    equipamento_nome=None,
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except Exception as exc:
        raise RuntimeError("Biblioteca reportlab não instalada. Adicione reportlab ao requirements.txt.") from exc

    from ui.relatorio_page import (
        _enriquecer_macro_revisoes,
        _enriquecer_macro_lubrificacoes,
        _resumir_macro,
    )
    from services import prioridades_service

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#16324f"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#5b6b7c"),
        leading=12,
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "SectionCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.white,
        backColor=colors.HexColor("#16324f"),
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "SmallCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#243447"),
    )

    elements = []

    total_registros = len(df_rev) + len(df_lub)
    total_revisoes = len(df_rev)
    total_lubrificacoes = len(df_lub)
    equipamentos = len(
        set(
            df_rev.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist()
            + df_lub.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist()
        )
    )

    periodo = f"{pd.to_datetime(data_ini).strftime('%d/%m/%Y')} a {pd.to_datetime(data_fim).strftime('%d/%m/%Y')}"
    gerado_em = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    elements.append(Paragraph("Relatório de manutenção", title_style))
    elements.append(Paragraph(f"Gerado em {gerado_em}", subtitle_style))
    elements.append(
        Paragraph(
            "Resumo executivo com foco em acompanhamento operacional, leitura macro por etapa e avaliação de prazo versus atraso.",
            subtitle_style,
        )
    )
    meta_html = (
        f"<b>Período</b>: {periodo}"
        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Setor</b>: {_safe_text(setor_nome, 'Todos')}"
        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Equipamento</b>: {_safe_text(equipamento_nome, 'Todos')}"
    )
    elements.append(Paragraph(meta_html, small_style))
    elements.append(Spacer(1, 5 * mm))

    kpi_data = [
        ["Total de registros", "Revisões", "Lubrificações", "Equipamentos"],
        [str(total_registros), str(total_revisoes), str(total_lubrificacoes), str(equipamentos)],
    ]
    kpi_table = Table(kpi_data, colWidths=[43 * mm, 35 * mm, 38 * mm, 35 * mm])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef4fb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d3e0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(kpi_table)
    elements.append(Spacer(1, 5 * mm))

    df_rev_macro = _enriquecer_macro_revisoes(df_rev)
    df_lub_macro = _enriquecer_macro_lubrificacoes(df_lub)
    resumo_rev = _resumir_macro(df_rev_macro, "rev")
    resumo_lub = _resumir_macro(df_lub_macro, "lub")

    # ── Tabela de quantitativo por departamento ──────────────────────────────
    quant_style = ParagraphStyle(
        "QuantSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#5b6b7c"),
        spaceAfter=3,
    )

    def _build_quant_table(resumo: pd.DataFrame, col_etapa: str, header_color) -> Table | None:
        if resumo is None or resumo.empty:
            return None
        agg = (
            resumo.groupby(["Departamento", "Grupo", "Tipo", col_etapa, "Referência"], dropna=False)
            .agg(Total=("Execuções", "sum"), NoPrazo=("No prazo", "sum"), Atrasadas=("Atrasadas", "sum"))
            .reset_index()
        )
        header = ["Departamento", "Grupo", "Tipo", col_etapa, "Referência", "Total", "No prazo", "Atrasadas", "% no prazo"]
        rows = [header]
        for _, r in agg.iterrows():
            pct = f"{round(r['NoPrazo'] / r['Total'] * 100)}%" if r["Total"] > 0 else "—"
            rows.append([
                _safe_text(r["Departamento"]),
                _safe_text(r["Grupo"]),
                _safe_text(r["Tipo"]),
                _safe_text(r[col_etapa]),
                _safe_text(r["Referência"]),
                str(int(r["Total"])),
                str(int(r["NoPrazo"])),
                str(int(r["Atrasadas"])),
                pct,
            ])
        total_row = [
            "Total geral", "", "", "", "",
            str(int(agg["Total"].sum())),
            str(int(agg["NoPrazo"].sum())),
            str(int(agg["Atrasadas"].sum())),
            f"{round(agg['NoPrazo'].sum() / agg['Total'].sum() * 100)}%" if agg["Total"].sum() > 0 else "—",
        ]
        rows.append(total_row)

        tbl = Table(
            rows,
            repeatRows=1,
            colWidths=[30 * mm, 24 * mm, 18 * mm, 30 * mm, 20 * mm, 12 * mm, 14 * mm, 14 * mm, 14 * mm],
        )
        n = len(rows)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -2), 0.35, colors.HexColor("#d4deea")),
            ("ROWBACKGROUNDS", (0, 1), (-1, n - 2), [colors.white, colors.HexColor("#f7fbff")]),
            ("BACKGROUND", (0, n - 1), (-1, n - 1), colors.HexColor("#e8eef5")),
            ("FONTNAME", (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
            ("LINEABOVE", (0, n - 1), (-1, n - 1), 0.8, colors.HexColor("#c7d3e0")),
            ("ALIGN", (5, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Destaque: "No prazo" em verde e "Atrasadas" em vermelho
            ("TEXTCOLOR", (6, 1), (6, n - 2), colors.HexColor("#15803d")),
            ("TEXTCOLOR", (7, 1), (7, n - 2), colors.HexColor("#b91c1c")),
        ]))
        return tbl

    section_quant_style = ParagraphStyle(
        "SectionQuant",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.white,
        backColor=colors.HexColor("#1e3a5f"),
        borderPadding=5,
        spaceBefore=4,
        spaceAfter=4,
    )
    elements.append(Paragraph("Quantitativo por departamento", section_quant_style))
    elements.append(Paragraph("Visão consolidada de execuções realizadas no período, separadas por status de prazo.", quant_style))

    tbl_rev_quant = _build_quant_table(resumo_rev, "Etapa", colors.HexColor("#2563eb"))
    if tbl_rev_quant:
        elements.append(Paragraph("Revisões", ParagraphStyle("QL", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#1e3a5f"), spaceAfter=2)))
        elements.append(tbl_rev_quant)
        elements.append(Spacer(1, 3 * mm))

    tbl_lub_quant = _build_quant_table(resumo_lub, "Item", colors.HexColor("#16a34a"))
    if tbl_lub_quant:
        elements.append(Paragraph("Lubrificações", ParagraphStyle("QL2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#166534"), spaceAfter=2)))
        elements.append(tbl_lub_quant)
        elements.append(Spacer(1, 3 * mm))

    if tbl_rev_quant is None and tbl_lub_quant is None:
        elements.append(Paragraph("Sem dados no período selecionado.", small_style))

    elements.append(Spacer(1, 4 * mm))
    # ────────────────────────────────────────────────────────────────────────

    elements.append(Paragraph("Macro de revisões realizadas", section_style))
    if resumo_rev.empty:
        elements.append(Paragraph("Sem dados de revisão no período selecionado.", small_style))
    else:
        resumo_rev_pdf = resumo_rev.copy()
        for col in ["Equipamentos", "Execuções", "No prazo", "Atrasadas"]:
            resumo_rev_pdf[col] = resumo_rev_pdf[col].apply(_safe_int)

        tabela_rev = _dataframe_para_tabela(resumo_rev_pdf, max_rows=28)
        rev_table = Table(
            tabela_rev,
            repeatRows=1,
            colWidths=[24 * mm, 22 * mm, 19 * mm, 30 * mm, 20 * mm, 16 * mm, 15 * mm, 15 * mm, 15 * mm, 19 * mm, 19 * mm],
        )
        rev_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f8cff")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.8),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d4deea")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fbff")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(
            Paragraph(
                "Visão macro por departamento, grupo, tipo de equipamento e etapa executada, incluindo prazo e atraso.",
                small_style,
            )
        )
        elements.append(rev_table)

    elements.append(Spacer(1, 5 * mm))

    elements.append(Paragraph("Macro de lubrificações realizadas", section_style))
    if resumo_lub.empty:
        elements.append(Paragraph("Sem dados de lubrificação no período selecionado.", small_style))
    else:
        resumo_lub_pdf = resumo_lub.copy()
        for col in ["Equipamentos", "Execuções", "No prazo", "Atrasadas"]:
            resumo_lub_pdf[col] = resumo_lub_pdf[col].apply(_safe_int)

        tabela_lub = _dataframe_para_tabela(resumo_lub_pdf, max_rows=28)
        lub_table = Table(
            tabela_lub,
            repeatRows=1,
            colWidths=[24 * mm, 22 * mm, 19 * mm, 30 * mm, 20 * mm, 16 * mm, 15 * mm, 15 * mm, 15 * mm, 19 * mm, 19 * mm],
        )
        lub_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22c55e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.8),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d4deea")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fff8")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(
            Paragraph(
                "Consolidado por item, intervalo e tipo de equipamento, com leitura de prazo versus atraso por departamento e grupo.",
                small_style,
            )
        )
        elements.append(lub_table)

    if not df_rev.empty or not df_lub.empty:
        elements.append(PageBreak())
        elements.append(Paragraph("Detalhamento resumido", section_style))

        if not df_rev.empty:
            elements.append(Paragraph("Revisões", small_style))
            rev_det = df_rev_macro.copy()
            if "Data" in rev_det.columns:
                rev_det["Data"] = pd.to_datetime(rev_det["Data"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "Atraso" in rev_det.columns:
                rev_det["Atraso"] = rev_det.apply(lambda row: _fmt_atraso_pdf(row.get("Atraso"), row.get("Controle", "km")), axis=1)
            rev_det = rev_det[[c for c in ["Data", "Código", "Equipamento", "Setor", "Etapa", "Referência", "Prazo", "Atraso", "Responsável", "Status"] if c in rev_det.columns]]
            tabela = _dataframe_para_tabela(rev_det, max_rows=18)
            t = Table(tabela, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce9ff")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d4deea")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
                    ]
                )
            )
            elements.append(t)
            elements.append(Spacer(1, 4 * mm))

        if not df_lub.empty:
            elements.append(Paragraph("Lubrificações", small_style))
            lub_det = df_lub_macro.copy()
            if "Data" in lub_det.columns:
                lub_det["Data"] = pd.to_datetime(lub_det["Data"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "Atraso" in lub_det.columns:
                lub_det["Atraso"] = lub_det.apply(lambda row: _fmt_atraso_pdf(row.get("Atraso"), row.get("Controle", "km")), axis=1)
            lub_det = lub_det[[c for c in ["Data", "Código", "Equipamento", "Setor", "Item", "Referência", "Prazo", "Atraso", "Responsável"] if c in lub_det.columns]]
            tabela = _dataframe_para_tabela(lub_det, max_rows=18)
            t = Table(tabela, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcffe7")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d4deea")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fffa")]),
                    ]
                )
            )
            elements.append(t)

    def _add_page_number(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6c7a89"))
        canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, f"Página {document.page}")
        canvas.drawString(12 * mm, 8 * mm, "Relatório de manutenção - padrão SaaS")

    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buffer.getvalue()


def botao_exportar_pdf_relatorio_manutencao(
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    setor_nome=None,
    equipamento_nome=None,
    setor_id=None,
    equipamento_id=None,
    key: str | None = None,
):
    if (df_rev is None or df_rev.empty) and (df_lub is None or df_lub.empty):
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    nome = f"relatorio_manutencao_{ts}.pdf"
    pdf_bytes = _pdf_bytes_relatorio_manutencao(
        df_rev=df_rev if df_rev is not None else pd.DataFrame(),
        df_lub=df_lub if df_lub is not None else pd.DataFrame(),
        data_ini=data_ini,
        data_fim=data_fim,
        setor_nome=setor_nome,
        equipamento_nome=equipamento_nome,
    )
    st.download_button(
        label="⬇️ PDF executivo",
        data=pdf_bytes,
        file_name=nome,
        mime="application/pdf",
        key=key or f"pdf_relatorio_manutencao_{ts}",
    )
