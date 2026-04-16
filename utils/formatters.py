from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd


NUMERIC_TYPES = (int, float, Decimal)


def _is_na(value: Any) -> bool:
    try:
        return pd.isna(value)
    except Exception:
        return value is None


def format_int_br(value: Any) -> str:
    if _is_na(value):
        return "-"
    try:
        return f"{int(round(float(value))):,}".replace(",", ".")
    except Exception:
        return str(value)


def format_decimal_br(value: Any, casas: int = 2) -> str:
    if _is_na(value):
        return "-"
    try:
        return f"{float(value):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def format_percent_br(value: Any, casas: int = 1) -> str:
    if _is_na(value):
        return "-"
    try:
        return f"{float(value):.{casas}f}".replace(".", ",") + "%"
    except Exception:
        return str(value)


def format_numero_br(value: Any, casas: int | None = None) -> str:
    if _is_na(value):
        return "-"
    try:
        number = float(value)
    except Exception:
        return str(value)
    if casas is None:
        casas = 0 if abs(number - round(number)) < 1e-9 else 2
    if casas <= 0:
        return format_int_br(number)
    return format_decimal_br(number, casas)


def format_medida_br(value: Any, unidade: str, casas: int | None = None) -> str:
    return f"{format_numero_br(value, casas)} {unidade}".strip()


_PERCENT_HINTS = (
    "percent", "%", "progresso", "conclus", "taxa", "efici", "saude", "saúde"
)
_INT_HINTS = (
    "qtd", "quant", "total", "cont", "pos", "posição", "dias", "alert", "venc", "prox", "pend", "parado"
)
_MEASURE_HINTS = ("km", "hora", "horí", "hori", "medidor", "intervalo", "atual", "vencimento", "falta", "atraso")


def _infer_casas(col_name: str, series: pd.Series) -> int:
    name = (col_name or "").lower()
    if any(h in name for h in _PERCENT_HINTS):
        return 1
    if pd.api.types.is_integer_dtype(series):
        return 0
    if pd.api.types.is_float_dtype(series):
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if vals.empty:
            return 0
        if (vals.round(0) == vals).all():
            return 0
        if any(h in name for h in _MEASURE_HINTS):
            return 0
        return 2
    return 0


def _should_format_column(col_name: str, series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series):
        return True
    name = (col_name or "").lower()
    if any(h in name for h in _PERCENT_HINTS + _INT_HINTS + _MEASURE_HINTS):
        coerced = pd.to_numeric(series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")
        return coerced.notna().mean() > 0.7 if len(series) else False
    return False


def format_dataframe_br(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        series = out[col]
        name = str(col)
        lower = name.lower()
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        if any(h in lower for h in _PERCENT_HINTS):
            nums = pd.to_numeric(series, errors="coerce")
            if nums.notna().any():
                out[col] = nums.map(lambda v: format_percent_br(v, 1) if not _is_na(v) else "-")
            continue
        if _should_format_column(name, series):
            nums = pd.to_numeric(series, errors="coerce")
            casas = _infer_casas(name, nums)
            out[col] = nums.map(lambda v: format_numero_br(v, casas) if not _is_na(v) else "-")
    return out


def format_metric_value(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, NUMERIC_TYPES):
        return format_numero_br(value)
    return value


_ORIG_ST_METRIC = None
_ORIG_ST_DATAFRAME = None
_ORIG_ST_DATA_EDITOR = None


def install_streamlit_br_patch(st_module) -> None:
    global _ORIG_ST_METRIC, _ORIG_ST_DATAFRAME, _ORIG_ST_DATA_EDITOR
    if getattr(st_module, "_br_patch_installed", False):
        return

    _ORIG_ST_METRIC = st_module.metric
    _ORIG_ST_DATAFRAME = st_module.dataframe
    _ORIG_ST_DATA_EDITOR = getattr(st_module, "data_editor", None)

    def metric(self_or_label, value=None, delta=None, *args, **kwargs):
        if isinstance(self_or_label, str):
            return _ORIG_ST_METRIC(self_or_label, format_metric_value(value), format_metric_value(delta), *args, **kwargs)
        self = self_or_label
        label = value
        real_value = delta
        real_delta = args[0] if args else None
        rest = args[1:] if args else ()
        return self._br_orig_metric(label, format_metric_value(real_value), format_metric_value(real_delta), *rest, **kwargs)

    def dataframe(self_or_data=None, *args, **kwargs):
        if isinstance(self_or_data, pd.DataFrame):
            return _ORIG_ST_DATAFRAME(format_dataframe_br(self_or_data), *args, **kwargs)
        self = self_or_data
        data = args[0] if args else None
        rest = args[1:] if args else ()
        if isinstance(data, pd.DataFrame):
            data = format_dataframe_br(data)
        return self._br_orig_dataframe(data, *rest, **kwargs)

    st_module.metric = lambda label, value=None, delta=None, *args, **kwargs: _ORIG_ST_METRIC(label, format_metric_value(value), format_metric_value(delta), *args, **kwargs)
    st_module.dataframe = lambda data=None, *args, **kwargs: _ORIG_ST_DATAFRAME(format_dataframe_br(data) if isinstance(data, pd.DataFrame) else data, *args, **kwargs)

    if _ORIG_ST_DATA_EDITOR is not None:
        st_module.data_editor = lambda data=None, *args, **kwargs: _ORIG_ST_DATA_EDITOR(format_dataframe_br(data) if isinstance(data, pd.DataFrame) else data, *args, **kwargs)

    try:
        from streamlit.delta_generator import DeltaGenerator
        DeltaGenerator._br_orig_metric = DeltaGenerator.metric
        DeltaGenerator._br_orig_dataframe = DeltaGenerator.dataframe
        DeltaGenerator.metric = metric
        DeltaGenerator.dataframe = dataframe
        if hasattr(DeltaGenerator, 'data_editor') and _ORIG_ST_DATA_EDITOR is not None:
            DeltaGenerator._br_orig_data_editor = DeltaGenerator.data_editor
            def dg_data_editor(self, data=None, *args, **kwargs):
                if isinstance(data, pd.DataFrame):
                    data = format_dataframe_br(data)
                return self._br_orig_data_editor(data, *args, **kwargs)
            DeltaGenerator.data_editor = dg_data_editor
    except Exception:
        pass

    st_module._br_patch_installed = True
