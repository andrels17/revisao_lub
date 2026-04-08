"""
Constantes compartilhadas entre as páginas da UI.
Centraliza STATUS_LABEL, STATUS_ORDEM e STATUS_COR — antes duplicados em 6+ arquivos.
"""

STATUS_LABEL = {
    "VENCIDO":   "🔴 Vencido",
    "PROXIMO":   "🟡 Próximo",
    "EM DIA":    "🟢 Em dia",
    "REALIZADO": "✅ Realizado",
}

# Usado em global_search.py (nome ligeiramente diferente no original — unificado aqui)
STATUS_LABELS = STATUS_LABEL

STATUS_ORDEM = {
    "VENCIDO":   0,
    "PROXIMO":   1,
    "EM DIA":    2,
    "REALIZADO": 3,
}

STATUS_COR = {
    "VENCIDO":   "#ef4444",
    "PROXIMO":   "#f59e0b",
    "EM DIA":    "#22c55e",
    "REALIZADO": "#3b82f6",
}

TIPOS_EQUIPAMENTO = [
    "Caminhão", "Trator", "Colheitadeira", "Pulverizador",
    "Implemento", "Máquina", "Outro",
]
