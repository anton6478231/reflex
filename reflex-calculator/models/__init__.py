"""
__init__.py для models
"""
from .revenue import (
    calculate_revenue_model_a,
    calculate_revenue_model_b,
    calculate_revenue_model_ab,
    calculate_revenue_for_months
)

from .costs import (
    calculate_fixed_costs,
    calculate_variable_costs,
    calculate_costs_for_month,
    calculate_costs_for_months
)

from .cash_flow import (
    calculate_cash_flow,
    calculate_cumulative_cash_flow,
    calculate_npv_series,
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
    calculate_min_rental_price_for_breakeven,
    calculate_min_rental_price_for_target_breakeven,
)

from .unit_economics import (
    calculate_unit_economics,
    calculate_unit_economics_from_params
)

from .sensitivity import (
    calculate_sensitivity,
    calculate_sensitivity_analysis
)

from .investment_bank import (
    calculate_bank_allocation,
    bank_exhausted_month,
    months_covered_by_bank,
    bank_balance_series,
    all_line_names,
    build_grant_matrix,
)

from .rnd_phase import (
    calculate_rnd_cash_flows,
    get_total_rnd_cost,
    get_rnd_cost_by_month,
    validate_rnd_vs_bank,
    ensure_matrix_size,
    build_empty_matrix,
    rename_category,
    DEFAULT_RND_CATEGORIES,
    MAX_RND_MONTHS,
    RND_PHASE_LABEL,
    MARKET_PHASE_LABEL,
)

__all__ = [
    'calculate_revenue_model_a',
    'calculate_revenue_model_b',
    'calculate_revenue_model_ab',
    'calculate_revenue_for_months',
    'calculate_fixed_costs',
    'calculate_variable_costs',
    'calculate_costs_for_month',
    'calculate_costs_for_months',
    'calculate_cash_flow',
    'calculate_cumulative_cash_flow',
    'calculate_npv_series',
    'calculate_cash_flow_for_months',
    'calculate_breakeven_month',
    'calculate_min_rental_price_for_breakeven',
    'calculate_min_rental_price_for_target_breakeven',
    'calculate_unit_economics',
    'calculate_unit_economics_from_params',
    'calculate_sensitivity',
    'calculate_sensitivity_analysis',
    'calculate_bank_allocation',
    'bank_exhausted_month',
    'months_covered_by_bank',
    'bank_balance_series',
    'all_line_names',
    'build_grant_matrix',
    'calculate_rnd_cash_flows',
    'get_total_rnd_cost',
    'get_rnd_cost_by_month',
    'validate_rnd_vs_bank',
    'ensure_matrix_size',
    'build_empty_matrix',
    'rename_category',
    'DEFAULT_RND_CATEGORIES',
    'MAX_RND_MONTHS',
    'RND_PHASE_LABEL',
    'MARKET_PHASE_LABEL',
]
