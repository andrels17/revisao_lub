from __future__ import annotations

from typing import Any


def _is_missing(valor: Any) -> bool:
    return valor is None or valor == ""


def format_int_br(valor: Any, default: str = "-") -> str:
    if _is_missing(valor):
        return default
    try:
        return f"{int(round(float(valor))):,}".replace(",", ".")
    except Exception:
        return default


def format_decimal_br(valor: Any, casas: int = 2, default: str = "-") -> str:
    if _is_missing(valor):
        return default
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return default


def format_percent_br(valor: Any, casas: int = 1, default: str = "-") -> str:
    if _is_missing(valor):
        return default
    try:
        return f"{float(valor):.{casas}f}".replace(".", ",") + "%"
    except Exception:
        return default


def format_moeda_br(valor: Any, casas: int = 2, default: str = "-") -> str:
    texto = format_decimal_br(valor, casas=casas, default=default)
    return default if texto == default else f"R$ {texto}"


def format_unidade_br(valor: Any, unidade: str, casas: int = 0, default: str = "-") -> str:
    if casas <= 0:
        texto = format_int_br(valor, default=default)
    else:
        texto = format_decimal_br(valor, casas=casas, default=default)
    return default if texto == default else f"{texto} {unidade}"
