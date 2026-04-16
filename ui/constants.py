TOLERANCIA_PROXIMO_KM = 500
TOLERANCIA_PROXIMO_HORAS = 50
# ── Tolerância de vencimento ───────────────────────────────────────────────────
# Itens com diferença <= este valor são marcados como "PRÓXIMO" (revisão e lubrificação).
# Altere aqui para afetar todo o sistema simultaneamente.
TOLERANCIA_PADRAO = 10

STATUS_LABEL = {
    "SEM_BASE":  "🟣 Primeira troca",
    "VENCIDO":   "🔴 Vencido",
    "PROXIMO":   "🟡 Próximo",
    "EM DIA":    "🟢 Em dia",
    "REALIZADO": "✅ Realizado",
}

# Usado em global_search.py (nome ligeiramente diferente no original — unificado aqui)
STATUS_LABELS = STATUS_LABEL

STATUS_ORDEM = {
    "SEM_BASE":  0,
    "VENCIDO":   1,
    "PROXIMO":   2,
    "EM DIA":    3,
    "REALIZADO": 4,
}

STATUS_COR = {
    "SEM_BASE":  "#8b5cf6",
    "VENCIDO":   "#ef4444",
    "PROXIMO":   "#f59e0b",
    "EM DIA":    "#22c55e",
    "REALIZADO": "#3b82f6",
}

TIPOS_EQUIPAMENTO = [
    "Caminhão", "Trator", "Colheitadeira", "Pulverizador",
    "Implemento", "Máquina", "Outro",
]
