"""
__init__.py для utils
"""
from .formatters import (
    format_currency,
    format_percent,
    format_number,
    format_ratio,
    format_months,
    get_color_for_value,
    get_metric_delta
)

from .validation import (
    validate_positive_number,
    validate_percent,
    validate_integer,
    validate_range,
    validate_revenue_params,
    validate_costs_params,
    validate_all_params
)

from .export import (
    export_to_excel,
    export_to_excel_with_formulas,
    export_to_json,
    create_detailed_table,
    build_bp04_fem_snapshot_markdown,
)
from .export_msp import export_to_msp_excel
from .config_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    build_config_snapshot,
    preflight_config_snapshot,
    apply_config_snapshot,
)

__all__ = [
    'format_currency',
    'format_percent',
    'format_number',
    'format_ratio',
    'format_months',
    'get_color_for_value',
    'get_metric_delta',
    'validate_positive_number',
    'validate_percent',
    'validate_integer',
    'validate_range',
    'validate_revenue_params',
    'validate_costs_params',
    'validate_all_params',
    'export_to_excel',
    'export_to_excel_with_formulas',
    'export_to_json',
    'create_detailed_table',
    'build_bp04_fem_snapshot_markdown',
    'export_to_msp_excel',
    'SNAPSHOT_SCHEMA_VERSION',
    'build_config_snapshot',
    'preflight_config_snapshot',
    'apply_config_snapshot',
]
