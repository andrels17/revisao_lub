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


def _df_para_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
        ws = writer.sheets["Dados"]
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(len(str(col)), df[col].astype(str).str.len().max() if not df.empty else 0)
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
    resumo_rev = _resumir_macro(df_rev_macro, "rev")
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

    df_lub_macro = _enriquecer_macro_lubrificacoes(df_lub)
    resumo_lub = _resumir_macro(df_lub_macro, "lub")
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
