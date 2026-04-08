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
