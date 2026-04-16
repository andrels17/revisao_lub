try:
    from .formatters import (
        format_dataframe_br,
        format_decimal_br,
        format_int_br,
        format_medida_br,
        format_metric_value,
        format_numero_br,
        format_percent_br,
        install_streamlit_br_patch,
    )
except Exception:
    from .formatters import (
        format_dataframe_br,
        format_decimal_br,
        format_int_br,
        format_medida_br,
        format_metric_value,
        format_numero_br,
        format_percent_br,
    )

    def install_streamlit_br_patch(_st_module):
        return None

__all__ = [
    'format_dataframe_br',
    'format_decimal_br',
    'format_int_br',
    'format_medida_br',
    'format_metric_value',
    'format_numero_br',
    'format_percent_br',
    'install_streamlit_br_patch',
]
