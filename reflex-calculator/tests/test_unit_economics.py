"""
Тесты для models/unit_economics.py — LTV, CAC, Payback Period.

Проверяемые инварианты:
  - LTV = profit_per_patient_per_month × avg_rental_duration
  - profit_per_patient_per_month = net_revenue_per_month − variable_costs_per_month
  - net_revenue_per_month = rental_price × (1 − commission)
  - LTV/CAC ratio: корректен для > 0 и = 0 значений CAC
  - Payback Period = CAC / profit_per_month; inf при отрицательной прибыли
  - calculate_unit_economics_from_params: только для model_b и model_ab
"""
import math
import pytest
from models.unit_economics import calculate_unit_economics, calculate_unit_economics_from_params


# ─── Базовые расчёты ─────────────────────────────────────────────────────────

class TestUnitEconomicsFormulas:
    """Проверка каждой формулы unit economics по отдельности."""

    def test_net_revenue_per_month_formula(self):
        """net_revenue = rental_price × (1 − commission)."""
        result = calculate_unit_economics(
            rental_price=5_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.20,
            variable_costs_per_patient_per_month=0,
            cac_per_patient=0,
        )
        # 5000 × 0.8 = 4000
        assert result['net_revenue_per_patient_per_month'] == 4_000

    def test_profit_per_month_formula(self):
        """profit = net_revenue − variable_costs."""
        result = calculate_unit_economics(
            rental_price=5_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.20,
            variable_costs_per_patient_per_month=500,
            cac_per_patient=0,
        )
        # net = 4000, profit = 4000 - 500 = 3500
        assert result['profit_per_patient_per_month'] == 3_500

    def test_ltv_formula(self):
        """LTV = profit_per_month × rehab_duration."""
        result = calculate_unit_economics(
            rental_price=3_000,
            avg_rental_duration=4,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=200,
            cac_per_patient=0,
        )
        # net = 3000, profit = 2800, LTV = 2800 × 4 = 11 200
        assert result['ltv'] == 11_200

    def test_ltv_scales_with_duration(self):
        """Удвоение срока реабилитации удваивает LTV."""
        base = dict(
            rental_price=3_000, clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=0, cac_per_patient=0,
        )
        r2 = calculate_unit_economics(**base, avg_rental_duration=2)
        r4 = calculate_unit_economics(**base, avg_rental_duration=4)
        assert r4['ltv'] == r2['ltv'] * 2


# ─── LTV / CAC ───────────────────────────────────────────────────────────────

class TestLTVtoCAC:
    """LTV/CAC ratio определяет привлекательность юнита."""

    def test_ltv_cac_ratio_calculation(self):
        """LTV=6 600, CAC=2 200 → ratio = 3.0."""
        result = calculate_unit_economics(
            rental_price=3_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.20,
            variable_costs_per_patient_per_month=200,
            cac_per_patient=2_200,
        )
        # net = 2400, profit = 2200, LTV = 6600
        assert abs(result['ltv'] - 6_600) < 1
        assert abs(result['ltv_cac_ratio'] - 3.0) < 0.001

    def test_cac_zero_gives_infinite_ratio_when_ltv_positive(self):
        """CAC = 0 при положительном LTV → ratio = ∞."""
        result = calculate_unit_economics(
            rental_price=3_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=0,
            cac_per_patient=0,
        )
        assert result['ltv_cac_ratio'] == float('inf')

    def test_ratio_above_3_is_healthy(self):
        """LTV/CAC > 3 — принято считать здоровым юнит-экономикой."""
        result = calculate_unit_economics(
            rental_price=5_000,
            avg_rental_duration=6,
            clinic_commission_rate=0.10,
            variable_costs_per_patient_per_month=100,
            cac_per_patient=1_000,
        )
        assert result['ltv_cac_ratio'] > 3

    def test_ratio_below_1_is_unprofitable(self):
        """LTV/CAC < 1 — юнит убыточен (CAC не окупается за срок реабилитации)."""
        result = calculate_unit_economics(
            rental_price=1_000,
            avg_rental_duration=1,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=0,
            cac_per_patient=5_000,
        )
        assert result['ltv_cac_ratio'] < 1


# ─── Payback Period ───────────────────────────────────────────────────────────

class TestPaybackPeriod:
    """Payback Period = сколько месяцев окупается CAC."""

    def test_payback_period_exact(self):
        """CAC=6 000, profit=3 000/мес → payback = 2 месяца."""
        result = calculate_unit_economics(
            rental_price=3_000,
            avg_rental_duration=6,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=0,
            cac_per_patient=6_000,
        )
        assert result['payback_months'] == 2.0

    def test_payback_infinite_when_profit_negative(self):
        """
        Если переменные затраты > net revenue → profit < 0 → payback = ∞.
        Юнит никогда не окупится.
        """
        result = calculate_unit_economics(
            rental_price=1_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=1_500,
            cac_per_patient=5_000,
        )
        assert result['profit_per_patient_per_month'] < 0
        assert result['payback_months'] == float('inf')

    def test_payback_zero_when_cac_zero(self):
        """CAC = 0 → payback = 0 (нет инвестиций для окупаемости)."""
        result = calculate_unit_economics(
            rental_price=3_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=500,
            cac_per_patient=0,
        )
        assert result['payback_months'] == 0.0


# ─── Отрицательный LTV ────────────────────────────────────────────────────────

class TestNegativeLTV:
    """Отрицательный LTV: затраты превышают доходы — юнит убыточен по определению."""

    def test_negative_ltv_when_variable_costs_exceed_revenue(self):
        """Переменные затраты > net revenue → profit < 0 → LTV < 0."""
        result = calculate_unit_economics(
            rental_price=1_000,
            avg_rental_duration=3,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=1_200,
            cac_per_patient=0,
        )
        assert result['profit_per_patient_per_month'] == -200
        assert result['ltv'] == -600  # -200 × 3

    def test_ltv_zero_at_exact_breakeven_per_unit(self):
        """profit = 0 (revenue == variable costs) → LTV = 0."""
        result = calculate_unit_economics(
            rental_price=2_000,
            avg_rental_duration=4,
            clinic_commission_rate=0.0,
            variable_costs_per_patient_per_month=2_000,
            cac_per_patient=0,
        )
        assert result['profit_per_patient_per_month'] == 0
        assert result['ltv'] == 0


# ─── calculate_unit_economics_from_params ─────────────────────────────────────

class TestUnitEconomicsFromParams:
    """Фасад поверх calculate_unit_economics — проверяем маппинг параметров."""

    def test_model_b_calculates_correctly(self):
        """Model B: корректный расчёт из словарей параметров."""
        result = calculate_unit_economics_from_params(
            model_type='model_b',
            revenue_params={
                'rental_price': 4_000,
                'avg_rental_duration': 3,
                'clinic_commission_rate': 0.10,
            },
            variable_params={
                'logistics_per_patient': 200,
                'support_per_patient_per_month': 100,
                'infrastructure_per_user': 50,
                'cac_patient': 1_000,
            },
        )
        # net = 4000 * 0.9 = 3600
        # variable_per_month = 200 + 100 + 50 = 350 (логистика учтена как per month в unit econ)
        # profit = 3600 - 350 = 3250
        # LTV = 3250 * 3 = 9750
        assert result['ltv'] == 9_750
        assert result['cac'] == 1_000
        assert result['ltv_cac_ratio'] == pytest.approx(9.75, rel=0.001)

    def test_model_a_returns_zeros(self):
        """Model A не поддерживает unit economics (нет пациентских платежей) → нули."""
        result = calculate_unit_economics_from_params(
            model_type='model_a',
            revenue_params={'rental_price': 5_000, 'avg_rental_duration': 3,
                            'clinic_commission_rate': 0.15},
            variable_params={'cac_patient': 500, 'support_per_patient_per_month': 100,
                             'logistics_per_patient': 200, 'infrastructure_per_user': 0},
        )
        assert result['ltv'] == 0
        assert result['cac'] == 0
        assert result['ltv_cac_ratio'] == 0

    def test_model_ab_calculates_same_as_model_b(self):
        """Model A+B использует те же формулы unit economics, что и Model B."""
        params_rev = {'rental_price': 3_000, 'avg_rental_duration': 4,
                      'clinic_commission_rate': 0.20}
        params_var = {'logistics_per_patient': 100, 'support_per_patient_per_month': 150,
                      'infrastructure_per_user': 50, 'cac_patient': 2_000}

        r_b = calculate_unit_economics_from_params('model_b', params_rev, params_var)
        r_ab = calculate_unit_economics_from_params('model_ab', params_rev, params_var)

        assert r_b['ltv'] == r_ab['ltv']
        assert r_b['ltv_cac_ratio'] == r_ab['ltv_cac_ratio']
        assert r_b['payback_months'] == r_ab['payback_months']
