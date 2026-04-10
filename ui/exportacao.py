"""
Utilitários de exportação para Excel e PDF.
Uso: from ui.exportacao import botao_exportar_excel
"""
import io
import datetime
from typing import Iterable

import pandas as pd
import streamlit as st


def _df_para_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
        ws = writer.sheets["Dados"]
        # Ajusta largura das colunas automaticamente
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(len(str(col)), df[col].astype(str).str.len().max() if not df.empty else 0)
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = min(max_len + 4, 60)
    return buf.getvalue()


def botao_exportar_excel(df: pd.DataFrame, nome_arquivo: str, label: str = "⬇️ Exportar Excel", key: str = None):
    """
    Renderiza um botão de download Excel para qualquer DataFrame.
    Uso: botao_exportar_excel(df, "relatorio_revisoes")
    """
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


def _safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _safe_int(valor, default: int = 0) -> int:
    try:
        if valor is None or valor == "":
            return default
        return int(valor)
    except Exception:
        return default


def _normalizar_df_datas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Data" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    out["Data"] = pd.to_datetime(out["Data"], errors="coerce")
    return out


def _primeiro_valor_texto(df: pd.DataFrame, coluna: str, fallback: str = "-") -> str:
    if df is None or df.empty or coluna not in df.columns:
        return fallback
    serie = df[coluna].dropna().astype(str)
    return serie.iloc[0] if not serie.empty else fallback


def _join_unique(values: Iterable[str], limit: int = 5) -> str:
    vistos = []
    for value in values:
        txt = str(value).strip()
        if txt and txt != '-' and txt not in vistos:
            vistos.append(txt)
    if not vistos:
        return '-'
    if len(vistos) <= limit:
        return ', '.join(vistos)
    return ', '.join(vistos[:limit]) + f" +{len(vistos) - limit}"


def _build_relatorio_manutencao_pdf(
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    setor_nome: str | None = None,
    equipamento_nome: str | None = None,
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception as exc:
        raise RuntimeError("Biblioteca reportlab não instalada. Adicione reportlab ao requirements.txt.") from exc

    df_rev = _normalizar_df_datas(df_rev)
    df_lub = _normalizar_df_datas(df_lub)

    total_rev = len(df_rev)
    total_lub = len(df_lub)
    total_exec = total_rev + total_lub
    equipamentos = len(set(df_rev.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist() + df_lub.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist()))
    setores = len(set(df_rev.get("Setor", pd.Series(dtype=str)).dropna().astype(str).tolist() + df_lub.get("Setor", pd.Series(dtype=str)).dropna().astype(str).tolist()))
    responsaveis = len(set(df_rev.get("Responsável", pd.Series(dtype=str)).dropna().astype(str).tolist() + df_lub.get("Responsável", pd.Series(dtype=str)).dropna().astype(str).tolist()))

    setor_display = setor_nome or _join_unique(pd.concat([
        df_rev.get("Setor", pd.Series(dtype=str)),
        df_lub.get("Setor", pd.Series(dtype=str)),
    ], ignore_index=True).dropna().tolist(), 3)
    equipamento_display = equipamento_nome or _join_unique(pd.concat([
        df_rev.get("Equipamento", pd.Series(dtype=str)),
        df_lub.get("Equipamento", pd.Series(dtype=str)),
    ], ignore_index=True).dropna().tolist(), 3)

    combinado = []
    if not df_rev.empty:
        r = df_rev.copy()
        r["Tipo"] = "Revisão"
        combinado.append(r[["Data", "Setor", "Equipamento", "Responsável", "Tipo"]])
    if not df_lub.empty:
        l = df_lub.copy()
        l["Tipo"] = "Lubrificação"
        combinado.append(l[["Data", "Setor", "Equipamento", "Responsável", "Tipo"]])
    df_all = pd.concat(combinado, ignore_index=True) if combinado else pd.DataFrame(columns=["Data", "Setor", "Equipamento", "Responsável", "Tipo"])

    destaques = []
    if total_exec == 0:
        destaques.append("Nenhuma execução encontrada no período selecionado.")
    else:
        if not df_all.empty and "Setor" in df_all.columns:
            top_setor = df_all.groupby("Setor").size().sort_values(ascending=False)
            if not top_setor.empty:
                destaques.append(f"Setor com maior volume: {top_setor.index[0]} ({int(top_setor.iloc[0])} execução(ões)).")
        if not df_all.empty and "Responsável" in df_all.columns:
            top_resp = df_all.groupby("Responsável").size().sort_values(ascending=False)
            if not top_resp.empty:
                destaques.append(f"Responsável com maior volume: {top_resp.index[0]} ({int(top_resp.iloc[0])} registro(s)).")
        taxa_rev = 0 if total_exec == 0 else round((total_rev / total_exec) * 100)
        taxa_lub = 0 if total_exec == 0 else round((total_lub / total_exec) * 100)
        destaques.append(f"Mix operacional do período: {taxa_rev}% revisões e {taxa_lub}% lubrificações.")
        if "Data" in df_all.columns:
            validas = df_all["Data"].dropna()
            if not validas.empty:
                destaques.append(f"Janela coberta por registros entre {validas.min():%d/%m/%Y} e {validas.max():%d/%m/%Y}.")

    top_setores_rows = [["Setor", "Qtd"]]
    if not df_all.empty and "Setor" in df_all.columns:
        top_setores = df_all.groupby("Setor").size().sort_values(ascending=False).head(8)
        for setor, qtd in top_setores.items():
            top_setores_rows.append([str(setor), str(int(qtd))])
    else:
        top_setores_rows.append(["Sem dados", "0"])

    top_resp_rows = [["Responsável", "Qtd"]]
    if not df_all.empty and "Responsável" in df_all.columns:
        top_resp = df_all.groupby("Responsável").size().sort_values(ascending=False).head(8)
        for resp, qtd in top_resp.items():
            top_resp_rows.append([str(resp), str(int(qtd))])
    else:
        top_resp_rows.append(["Sem dados", "0"])

    def _fmt_date(v):
        if pd.isna(v):
            return '-'
        try:
            return pd.to_datetime(v).strftime('%d/%m/%Y')
        except Exception:
            return str(v)

    revisoes_rows = [["Data", "Código", "Equipamento", "Setor", "Responsável", "Status"]]
    if not df_rev.empty:
        for _, row in df_rev.head(18).iterrows():
            revisoes_rows.append([
                _fmt_date(row.get("Data")),
                str(row.get("Código", "-")),
                str(row.get("Equipamento", "-"))[:28],
                str(row.get("Setor", "-"))[:18],
                str(row.get("Responsável", "-"))[:18],
                str(row.get("Status", "-"))[:12],
            ])
    else:
        revisoes_rows.append(["-", "-", "Nenhuma revisão", "-", "-", "-"])

    lub_rows = [["Data", "Código", "Equipamento", "Item", "Produto", "Responsável"]]
    if not df_lub.empty:
        for _, row in df_lub.head(18).iterrows():
            lub_rows.append([
                _fmt_date(row.get("Data")),
                str(row.get("Código", "-")),
                str(row.get("Equipamento", "-"))[:24],
                str(row.get("Item", "-"))[:18],
                str(row.get("Produto", "-"))[:16],
                str(row.get("Responsável", "-"))[:18],
            ])
    else:
        lub_rows.append(["-", "-", "Nenhuma lubrificação", "-", "-", "-"])

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'TitleCard', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=22,
        leading=26, textColor=colors.HexColor('#0f2747'), spaceAfter=6, alignment=TA_LEFT,
    )
    subtitle = ParagraphStyle(
        'SubTitleCard', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5,
        leading=13, textColor=colors.HexColor('#58708e'), spaceAfter=2,
    )
    section = ParagraphStyle(
        'SectionCard', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12.5,
        leading=15, textColor=colors.HexColor('#143255'), spaceAfter=8, spaceBefore=10,
    )
    body = ParagraphStyle(
        'BodyCard', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.4,
        leading=13, textColor=colors.HexColor('#23384d'),
    )
    small = ParagraphStyle(
        'SmallCard', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.5,
        leading=11, textColor=colors.HexColor('#58708e'),
    )
    right = ParagraphStyle(
        'RightMeta', parent=small, alignment=TA_RIGHT,
    )

    story = []
    periodo_txt = f"{pd.to_datetime(data_ini).strftime('%d/%m/%Y')} a {pd.to_datetime(data_fim).strftime('%d/%m/%Y')}"

    cabecalho = Table([
        [
            Paragraph("Relatório de manutenção", title),
            Paragraph(f"Gerado em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", right),
        ],
        [
            Paragraph("Resumo executivo com foco em acompanhamento operacional e leitura gerencial do período selecionado.", subtitle),
            Paragraph("Padrão SaaS", right),
        ],
    ], colWidths=[122 * mm, 48 * mm])
    cabecalho.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f8fc')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#d8e4f2')),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.extend([cabecalho, Spacer(1, 8)])

    meta = Table([
        [Paragraph('<b>Período</b>', small), Paragraph('<b>Setor</b>', small), Paragraph('<b>Equipamento</b>', small)],
        [Paragraph(periodo_txt, body), Paragraph(setor_display, body), Paragraph(equipamento_display, body)],
    ], colWidths=[54 * mm, 58 * mm, 58 * mm])
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eaf1f8')),
        ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#d8e4f2')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d8e4f2')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.extend([meta, Spacer(1, 10)])

    kpi_data = [
        [Paragraph('<b>Total de registros</b>', small), Paragraph('<b>Revisões</b>', small), Paragraph('<b>Lubrificações</b>', small), Paragraph('<b>Equipamentos</b>', small)],
        [Paragraph(str(total_exec), title), Paragraph(str(total_rev), title), Paragraph(str(total_lub), title), Paragraph(str(equipamentos), title)],
        [Paragraph('Execuções no período', small), Paragraph('Ordens/revisões executadas', small), Paragraph('Itens lubrificados', small), Paragraph(f'{setores} setor(es) / {responsaveis} responsável(is)', small)],
    ]
    kpi = Table(kpi_data, colWidths=[42 * mm, 42 * mm, 42 * mm, 48 * mm])
    kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2747')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fbff')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#d8e4f2')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d8e4f2')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.extend([kpi, Spacer(1, 10)])

    story.append(Paragraph('Highlights automáticos', section))
    highlights_rows = [[Paragraph(f'• {txt}', body)] for txt in destaques]
    highlights = Table(highlights_rows, colWidths=[170 * mm])
    highlights.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f6f9fc')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#d8e4f2')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.extend([highlights, Spacer(1, 10)])

    story.append(Paragraph('Leitura de volume', section))
    duo = Table([
        [Paragraph('Top setores', body), Paragraph('Top responsáveis', body)],
        [Table(top_setores_rows, colWidths=[62 * mm, 18 * mm]), Table(top_resp_rows, colWidths=[62 * mm, 18 * mm])],
    ], colWidths=[85 * mm, 85 * mm])
    duo.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.extend([duo, Spacer(1, 10)])

    def _style_inner_table(tbl: Table):
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eaf1f8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#143255')),
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#d8e4f2')),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d8e4f2')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
        ]))
    _style_inner_table(duo._cellvalues[1][0])
    _style_inner_table(duo._cellvalues[1][1])

    story.append(Paragraph('Detalhamento de revisões', section))
    t_rev = Table(revisoes_rows, colWidths=[20 * mm, 17 * mm, 42 * mm, 30 * mm, 30 * mm, 25 * mm], repeatRows=1)
    t_rev.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2747')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fbff')]),
        ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#d8e4f2')),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d8e4f2')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.extend([t_rev, Spacer(1, 10)])

    story.append(Paragraph('Detalhamento de lubrificações', section))
    t_lub = Table(lub_rows, colWidths=[20 * mm, 17 * mm, 35 * mm, 31 * mm, 27 * mm, 40 * mm], repeatRows=1)
    t_lub.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#143255')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fbff')]),
        ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#d8e4f2')),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d8e4f2')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_lub)

    def _on_page(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#6b819a'))
        canvas.drawString(doc.leftMargin, 8 * mm, 'Relatório de manutenção - padrão SaaS')
        canvas.drawRightString(A4[0] - doc.rightMargin, 8 * mm, f'Página {doc.page}')

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def botao_exportar_pdf_relatorio_manutencao(
    df_rev: pd.DataFrame,
    df_lub: pd.DataFrame,
    data_ini,
    data_fim,
    setor_nome: str | None = None,
    equipamento_nome: str | None = None,
    label: str = '⬇️ PDF executivo',
    key: str | None = None,
):
    if (df_rev is None or df_rev.empty) and (df_lub is None or df_lub.empty):
        return

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    nome = f'relatorio_manutencao_{ts}.pdf'
    pdf_bytes = _build_relatorio_manutencao_pdf(df_rev, df_lub, data_ini, data_fim, setor_nome, equipamento_nome)
    st.download_button(
        label=label,
        data=pdf_bytes,
        file_name=nome,
        mime='application/pdf',
        key=key or f'pdf_relatorio_manutencao_{ts}',
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
    w, h = A4
    y = h - 20 * mm

    def line(txt: str, size: int = 10, bold: bool = False, gap: int = 6):
        nonlocal y
        if y < 18 * mm:
            c.showPage()
            y = h - 20 * mm
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        c.drawString(15 * mm, y, txt[:120])
        y -= gap * mm

    line('Painel 360° do Equipamento', 15, True, 8)
    line(f"Equipamento: {equipamento.get('codigo', '-')} - {equipamento.get('nome', '-')}", 11, True)
    line(f"Setor: {equipamento.get('setor_nome') or '-'} | Tipo: {equipamento.get('tipo') or '-'}")
    line(f"KM atual: {_safe_float(equipamento.get('km_atual')):.0f} | Horas atuais: {_safe_float(equipamento.get('horas_atual')):.0f}")
    line(f"Saúde: {saude.get('faixa')} ({_safe_int(saude.get('score'))}%)")
    line('')
    line('Leitura gerencial', 12, True)
    for item in insights[:6]:
        line(f"- {item}")
    line('')
    line('Pendências prioritárias', 12, True)
    if pendencias:
        for p in pendencias[:12]:
            line(f"- {p.get('origem')}: {p.get('item')} | {p.get('status')} | atual {_safe_float(p.get('atual')):.0f} | ref {_safe_float(p.get('referencia')):.0f}")
    else:
        line('- Sem pendências vencidas ou próximas.')
    line('')
    line('Comentários recentes', 12, True)
    if comentarios:
        for cmt in comentarios[:10]:
            autor = cmt.get('autor_nome') or 'Usuário'
            data = str(cmt.get('created_at') or '-')[:19]
            line(f"- {data} | {autor}: {(cmt.get('comentario') or '')[:90]}")
    else:
        line('- Nenhum comentário registrado.')

    c.save()
    return buf.getvalue()


def botao_exportar_pdf_painel360(equipamento: dict, saude: dict, pendencias: list[dict], insights: list[str], comentarios: list[dict], key: str | None = None):
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    nome = f"painel_360_{equipamento.get('codigo', 'equipamento')}_{ts}.pdf"
    pdf_bytes = _pdf_bytes_painel_360(equipamento, saude, pendencias, insights, comentarios)
    st.download_button(
        label='⬇️ PDF do Painel 360°',
        data=pdf_bytes,
        file_name=nome,
        mime='application/pdf',
        key=key or f"pdf_painel360_{equipamento.get('id', '')}_{ts}",
    )
