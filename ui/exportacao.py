"""
Utilitários de exportação para Excel.
Uso: from ui.exportacao import botao_exportar_excel
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
    line(f"KM atual: {float(equipamento.get('km_atual') or 0):.0f} | Horas atuais: {float(equipamento.get('horas_atual') or 0):.0f}")
    line(f"Saúde: {saude.get('faixa')} ({saude.get('score')}%)")
    line('')
    line('Leitura gerencial', 12, True)
    for item in insights[:6]:
        line(f"- {item}")
    line('')
    line('Pendências prioritárias', 12, True)
    if pendencias:
        for p in pendencias[:12]:
            line(f"- {p.get('origem')}: {p.get('item')} | {p.get('status')} | atual {float(p.get('atual') or 0):.0f} | ref {float(p.get('referencia') or 0):.0f}")
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
