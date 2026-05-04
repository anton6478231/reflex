"""
Тесты для формульного аудита.
"""
from models.formula_trace import trace_revenue_month
from models.revenue import calculate_revenue_for_months


def _row_map(rows):
    return {title: (snippet, value, note) for title, snippet, value, note in rows}


def test_model_ab_trace_matches_dynamic_pool_logic():
    params = {
        "num_clinics": 2,
        "devices_per_clinic": 5,
        "setup_fee": 50_000,
        "subscription_per_device": 2_000,
        "patients_per_clinic_month1": 8,
        "growth_rate": 0.5,
        "rental_price": 6_000,
        "clinic_commission_rate": 0.15,
        "rehab_duration_months": 3,
    }

    revenue_results = calculate_revenue_for_months("model_ab", params, num_months=3)
    month3_actual = revenue_results[2]

    rows = trace_revenue_month(
        model_type="model_ab",
        params=params,
        month=3,
        prev_patients=revenue_results[1].get("num_patients"),
        actual=month3_actual,
    )
    row_values = _row_map(rows)

    assert "OK actual[setup_revenue]" in row_values["setup_revenue"][2]
    assert "OK actual[subscription_revenue]" in row_values["subscription_revenue"][2]
    assert "OK actual[additional_devices]" in row_values["additional_devices"][2]
    assert "OK actual[devices_in_pool]" in row_values["devices_in_pool"][2]
