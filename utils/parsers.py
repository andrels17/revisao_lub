from __future__ import annotations

from typing import Any

import streamlit as st

from .formatters import format_decimal_br


def parse_numero_br(valor: Any) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return None

    texto = str(valor).strip()
    if not texto:
        return None

    texto = texto.replace(" ", "")
    texto = texto.replace("R$", "").replace("r$", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        partes = texto.split(".")
        if len(partes) > 2:
            texto = "".join(partes[:-1]) + "." + partes[-1]
        elif len(partes) == 2 and len(partes[1]) == 3 and partes[0].isdigit() and partes[1].isdigit():
            texto = "".join(partes)

    try:
        return float(texto)
    except Exception:
        return None


def parse_numero(valor: Any) -> float | None:
    return parse_numero_br(valor)


def numero_para_texto_input(valor: Any, casas: int = 2) -> str:
    numero = parse_numero_br(valor)
    if numero is None:
        return ""
    if casas <= 0:
        return format_decimal_br(numero, casas=0)
    return format_decimal_br(numero, casas=casas)


def numero_input_br(label: str, value: Any = None, *, key: str | None = None, placeholder: str = "Ex.: 1.234,56", help: str | None = None, disabled: bool = False, casas_preview: int = 2) -> float | None:
    valor_inicial = numero_para_texto_input(value, casas=casas_preview) if value is not None else ""
    texto = st.text_input(label, value=valor_inicial, key=key, placeholder=placeholder, help=help, disabled=disabled)
    if not str(texto).strip():
        return None
    numero = parse_numero_br(texto)
    if numero is None:
        st.error(f"Valor inválido em '{label}'. Use formato como 1.234,56 ou 1234.56.")
    else:
        st.caption(f"Valor interpretado: {format_decimal_br(numero, casas=casas_preview)}")
    return numero
