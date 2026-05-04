"""
__init__.py для visualization
"""
from .charts import (
    create_cash_flow_chart,
    create_revenue_breakdown_chart,
    create_costs_structure_chart,
    create_breakeven_chart,
    create_true_breakeven_chart,
    create_sensitivity_chart,
    create_unit_economics_chart,
    create_cohort_dynamics_chart,
)

from .kpi_cards import (
    display_kpi_cards,
    display_kpi_summary
)

from .tables import (
    display_detailed_table,
    display_costs_breakdown,
    display_revenue_breakdown
)

from .formula_panel import render_formula_auditor

__all__ = [
    'create_cash_flow_chart',
    'create_revenue_breakdown_chart',
    'create_costs_structure_chart',
    'create_breakeven_chart',
    'create_true_breakeven_chart',
    'create_sensitivity_chart',
    'create_unit_economics_chart',
    'create_cohort_dynamics_chart',
    'display_kpi_cards',
    'display_kpi_summary',
    'display_detailed_table',
    'display_costs_breakdown',
    'display_revenue_breakdown',
    'render_formula_auditor',
]
