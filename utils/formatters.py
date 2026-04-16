from __future__ import annotations

import datetime as _dt
import math
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _to_float(value: Any) -> float | None:
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(value)
        except Exception:
            return None
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return None
        # já formatado no padrão brasileiro
        if txt.count(',') == 1 and ('.' in txt or txt.replace(',', '').replace('-', '').isdigit()):
            txt = txt.replace('.', '').replace(',', '.')
        else:
            txt = txt.replace(',', '')
        try:
            return float(txt)
        except Exception:
            return None
    return None


def format_int_br(value: Any, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    return f"{int(round(num)):,}".replace(',', '.')



def format_decimal_br(value: Any, casas: int = 2, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    fmt = f"{{:,.{casas}f}}".format(num)
    return fmt.replace(',', 'X').replace('.', ',').replace('X', '.')



def format_percent_br(value: Any, casas: int = 1, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    return f"{format_decimal_br(num, casas=casas, default=default)}%"



def format_moeda_br(value: Any, casas: int = 2, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    return f"R$ {format_decimal_br(num, casas=casas, default=default)}"



def format_unidade_br(value: Any, unidade: str = '', casas: int = 0, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    base = format_decimal_br(num, casas=casas, default=default) if casas > 0 else format_int_br(num, default=default)
    return f"{base} {unidade}".strip()



def format_numero_auto(value: Any, default: str = '-') -> str:
    num = _to_float(value)
    if num is None:
        return default
    if math.isfinite(num) and float(num).is_integer():
        return format_int_br(num, default=default)
    return format_decimal_br(num, casas=2, default=default)



def format_datetime_br(value: Any, include_time: bool | None = None, default: str = '-') -> str:
    if _is_null(value):
        return default
    try:
        dt = pd.to_datetime(value)
    except Exception:
        return str(value)
    if pd.isna(dt):
        return default
    try:
        if getattr(dt, 'tzinfo', None) is not None:
            dt = dt.tz_localize(None)
    except Exception:
        pass
    if include_time is None:
        include_time = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)
    return dt.strftime('%d/%m/%Y %H:%M' if include_time else '%d/%m/%Y')



def parse_decimal_br(value: Any, default: float | None = None) -> float | None:
    num = _to_float(value)
    return default if num is None else num



def _col_prefers_decimal(col_name: str) -> bool:
    name = (col_name or '').strip().lower()
    return any(token in name for token in ['percent', 'percentual', 'progresso', 'score', 'cobertura', 'média', 'media', 'razão', 'razao'])



def _col_is_date(col_name: str) -> bool:
    name = (col_name or '').strip().lower()
    return any(token in name for token in ['data', 'dt_', 'criado', 'created', 'ultima leitura', 'última leitura', 'gerado em', 'fechado em'])



def _format_cell(value: Any, col_name: str = '') -> Any:
    if _is_null(value):
        return '-'
    if isinstance(value, (pd.Timestamp, _dt.datetime, _dt.date)):
        return format_datetime_br(value)
    num = _to_float(value)
    if num is None or isinstance(value, str) and any(ch.isalpha() for ch in value):
        if _col_is_date(col_name):
            return format_datetime_br(value)
        return value
    if _col_prefers_decimal(col_name):
        return format_decimal_br(num, casas=1)
    if float(num).is_integer():
        return format_int_br(num)
    return format_decimal_br(num, casas=2)



def format_dataframe_br(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df
    base = df.copy()
    for col in base.columns:
        serie = base[col]
        if pd.api.types.is_datetime64_any_dtype(serie) or pd.api.types.is_datetime64tz_dtype(serie):
            base[col] = serie.map(lambda v: format_datetime_br(v, include_time=True))
            continue
        if pd.api.types.is_numeric_dtype(serie):
            if _col_prefers_decimal(str(col)):
                base[col] = serie.map(lambda v: format_decimal_br(v, casas=1))
            else:
                if pd.api.types.is_float_dtype(serie) and not serie.dropna().empty and not (serie.dropna() % 1 == 0).all():
                    base[col] = serie.map(lambda v: format_decimal_br(v, casas=2))
                else:
                    base[col] = serie.map(format_int_br)
            continue
        if pd.api.types.is_object_dtype(serie) and _col_is_date(str(col)):
            base[col] = serie.map(lambda v: format_datetime_br(v))
            continue
        if pd.api.types.is_object_dtype(serie):
            base[col] = serie.map(lambda v: _format_cell(v, str(col)))
    return base



def patch_streamlit_br() -> None:
    if getattr(st, '_ptbr_patched', False):
        return

    original_metric = st.metric
    original_dataframe = st.dataframe

    def metric_br(label, value, delta=None, *args, **kwargs):
        display_value = format_numero_auto(value) if isinstance(value, (int, float, Decimal)) else value
        display_delta = format_numero_auto(delta) if isinstance(delta, (int, float, Decimal)) else delta
        return original_metric(label, display_value, display_delta, *args, **kwargs)

    def dataframe_br(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame):
            data = format_dataframe_br(data)
        return original_dataframe(data, *args, **kwargs)

    st.metric = metric_br
    st.dataframe = dataframe_br
    st._ptbr_patched = True
