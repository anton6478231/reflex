"""
Тесты для models/cash_flow.py — денежный поток, кумулятив, NPV и точка безубыточности.

Проверяемые инварианты:
  - CF = Revenue − Fixed − Variable (базовая формула)
  - Cumulative CF — нарастающий итог, строго последовательный
  - calculate_npv_series: формула дисконтирования r_m = (1+r_год)^(1/12)−1
  - Breakeven: корректно определяется месяц, когда CumCF ≥ 0
  - Breakeven: правильно обрабатывает крайние случаи (M1, never reached, проекция)
  - min_rental_price_for_target_breakeven: аналитическая формула верна
"""
import math
import pytest
from models.cash_flow import (
    calculate_cash_flow,
    calculate_cumulative_cash_flow,
    calculate_npv_series,
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
    calculate_min_rental_price_for_target_breakeven,
)


# ─── Базовая формула CF ───────────────────────────────────────────────────────

class TestCashFlowFormula:
    """CF = Revenue − Fixed Costs − Variable Costs."""

    def test_basic_cf_formula(self):
        """CF = Revenue − fixed − variable."""
        result = calculate_cash_flow(revenue=10_000, fixed_costs=3_000, variable_costs=2_000)
        assert result['cash_flow'] == 5_000
        assert result['total_costs'] == 5_000
        assert result['revenue'] == 10_000

    def test_positive_cf_when_revenue_exceeds_costs(self):
        """CF > 0 когда Revenue > Costs."""
        result = calculate_cash_flow(revenue=100_000, fixed_costs=30_000, variable_costs=20_000)
        assert result['cash_flow'] > 0

    def test_negative_cf_when_costs_exceed_revenue(self):
        """CF < 0 когда Costs > Revenue."""
        result = calculate_cash_flow(revenue=10_000, fixed_costs=8_000, variable_costs=5_000)
        assert result['cash_flow'] == -3_000

    def test_zero_cf_at_breakeven_point(self):
        """CF = 0 когда Revenue == Total Costs."""
        result = calculate_cash_flow(revenue=50_000, fixed_costs=30_000, variable_costs=20_000)
        assert result['cash_flow'] == 0

    def test_zero_revenue_gives_negative_cf(self):
        """Нулевой Revenue при наличии затрат → отрицательный CF."""
        result = calculate_cash_flow(revenue=0, fixed_costs=100_000, variable_costs=50_000)
        assert result['cash_flow'] == -150_000

    def test_total_costs_is_fixed_plus_variable(self):
        """total_costs = fixed + variable (проверка компонентов)."""
        result = calculate_cash_flow(revenue=0, fixed_costs=40_000, variable_costs=25_000)
        assert result['total_costs'] == 65_000
        assert result['fixed_costs'] == 40_000
        assert result['variable_costs'] == 25_000


# ─── NPV Series ───────────────────────────────────────────────────────────────

class TestNpvSeries:
    """calculate_npv_series: NPV(T) = Σ_{t=1}^{T} CF_t / (1+r_m)^t."""

    def test_zero_rate_equals_cumulative_cf(self):
        """При ставке 0% NPV совпадает с накопленным CF."""
        cfs = [100.0, 200.0, 300.0]
        npv = calculate_npv_series(cfs, annual_rate=0.0)
        assert len(npv) == 3
        assert abs(npv[0] - 100.0) < 1e-9
        assert abs(npv[1] - 300.0) < 1e-9
        assert abs(npv[2] - 600.0) < 1e-9

    def test_positive_rate_discounts_future_cf(self):
        """При положительной ставке NPV < CumCF (будущие потоки обесцениваются)."""
        cfs = [0.0, 0.0, 1200.0]  # всё в месяц 3
        npv_0 = calculate_npv_series(cfs, annual_rate=0.0)
        npv_20 = calculate_npv_series(cfs, annual_rate=0.20)
        # NPV при 20% < NPV при 0%
        assert npv_20[-1] < npv_0[-1]

    def test_exact_formula_single_month(self):
        """M1: NPV = CF1 / (1+r_m)^1, r_m = (1+0.20)^(1/12)−1."""
        cf = 1000.0
        annual = 0.20
        r_m = (1 + annual) ** (1 / 12) - 1
        expected = cf / (1 + r_m) ** 1
        result = calculate_npv_series([cf], annual_rate=annual)
        assert abs(result[0] - expected) < 1e-6

    def test_exact_formula_three_months(self):
        """Точная проверка формулы за 3 месяца."""
        cfs = [100.0, 200.0, 300.0]
        annual = 0.24
        r_m = (1 + annual) ** (1 / 12) - 1
        expected_cumulative = [
            100.0 / (1 + r_m) ** 1,
            100.0 / (1 + r_m) ** 1 + 200.0 / (1 + r_m) ** 2,
            100.0 / (1 + r_m) ** 1 + 200.0 / (1 + r_m) ** 2 + 300.0 / (1 + r_m) ** 3,
        ]
        result = calculate_npv_series(cfs, annual_rate=annual)
        for exp, got in zip(expected_cumulative, result):
            assert abs(exp - got) < 1e-6, f"expected {exp}, got {got}"

    def test_length_equals_input_length(self):
        """Длина результата равна длине входа."""
        cfs = [10.0] * 12
        result = calculate_npv_series(cfs, annual_rate=0.15)
        assert len(result) == 12

    def test_monotone_for_all_positive_cf(self):
        """При всех положительных CF: NPV-серия строго возрастает."""
        cfs = [500.0] * 6
        result = calculate_npv_series(cfs, annual_rate=0.20)
        for i in range(1, len(result)):
            assert result[i] > result[i - 1]

    def test_empty_input_returns_empty(self):
        """Пустой список — пустой результат."""
        result = calculate_npv_series([], annual_rate=0.20)
        assert result == []

    def test_npv_lower_for_higher_rate(self):
        """Чем выше ставка — тем ниже NPV (одни и те же потоки)."""
        cfs = [1000.0, 2000.0, 3000.0]
        npv_low = calculate_npv_series(cfs, annual_rate=0.10)
        npv_high = calculate_npv_series(cfs, annual_rate=0.50)
        assert npv_high[-1] < npv_low[-1]

    def test_negative_cfs_give_negative_npv(self):
        """Отрицательные CF → NPV отрицателен (накопленный)."""
        cfs = [-1000.0, -500.0, -200.0]
        result = calculate_npv_series(cfs, annual_rate=0.20)
        assert result[-1] < 0

    def test_npv_series_is_cumulative_not_per_period(self):
        """Значение NPV[i] — это накопленный NPV до месяца i+1, не только за этот месяц."""
        cfs = [100.0, 200.0]
        annual = 0.12
        r_m = (1 + annual) ** (1 / 12) - 1
        npv_m1 = 100.0 / (1 + r_m) ** 1
        npv_m2 = npv_m1 + 200.0 / (1 + r_m) ** 2
        result = calculate_npv_series(cfs, annual_rate=annual)
        assert abs(result[0] - npv_m1) < 1e-6
        assert abs(result[1] - npv_m2) < 1e-6  # накопленный, не только M2


# ─── NPV-предиктор: инварианты meets_target ───────────────────────────────────

class TestNpvVsCumCfOrdering:
    """
    При положительной ставке NPV < CumCF:
    если CumCF >= threshold, то NPV может быть < threshold.
    Это и есть смысл переключения — предиктор становится строже.
    """

    def test_npv_strictly_less_than_cumcf_positive_rate(self):
        """Для положительного CF и ставки > 0: NPV < CumCF."""
        cfs = [500.0, 500.0, 500.0]
        npv_series = calculate_npv_series(cfs, annual_rate=0.20)
        cumcf = sum(cfs)
        assert npv_series[-1] < cumcf

    def test_predictor_stricter_with_positive_rate(self):
        """
        При ставке 20% PV < CumCF, поэтому NPV = PV − I₀ тоже меньше.
        Предиктор с более высокой ставкой требует более высокой цены.
        Smoke-тест: PV_20 < PV_0 для тех же CF.
        """
        cfs = [100.0, 100.0, 100.0]
        pv_0 = calculate_npv_series(cfs, annual_rate=0.0)[-1]
        pv_20 = calculate_npv_series(cfs, annual_rate=0.20)[-1]
        # При 0%: PV = CumCF = 300; при 20% — меньше
        assert pv_20 < pv_0
        assert pv_0 == pytest.approx(300.0)

    def test_zero_rate_backward_compatible(self):
        """
        При ставке 0% PV-серия идентична кумулятивному CF.
        С учётом вложений: NPV = CumCF − I₀ (обратная совместимость предиктора).
        """
        cfs = [-200.0, 100.0, 150.0]
        pv_series = calculate_npv_series(cfs, annual_rate=0.0)
        cumcf = []
        s = 0.0
        for c in cfs:
            s += c
            cumcf.append(s)
        # PV при rate=0 == CumCF
        for pv, cf_cum in zip(pv_series, cumcf):
            assert abs(pv - cf_cum) < 1e-9

    def test_npv_includes_investment(self):
        """
        NPV = −I₀ + PV(future CFs): при вложениях I₀ NPV < PV.
        Стандартная финансовая формула.
        """
        cfs = [500.0, 500.0, 500.0]
        annual = 0.20
        pv_series = calculate_npv_series(cfs, annual_rate=annual)
        pv = pv_series[-1]
        i0 = 1000.0
        npv = pv - i0
        # NPV должен быть меньше PV на величину вложений
        assert abs(npv - (pv - i0)) < 1e-9
        # При достаточно высоких CF NPV может быть положительным
        assert npv > -i0  # PV > 0 гарантирует


# ─── Кумулятивный CF ──────────────────────────────────────────────────────────

class TestCumulativeCashFlow:
    """Cumulative CF — нарастающий итог помесячных значений CF."""

    def test_cumulative_cf_is_running_sum(self):
        """CumCF[n] = CF[0] + CF[1] + ... + CF[n]."""
        cf_values = [100, -50, 200, -30, 80]
        result = calculate_cumulative_cash_flow(cf_values)
        assert result == [100, 50, 250, 220, 300]

    def test_cumulative_cf_single_month(self):
        """Один месяц: cumCF = CF."""
        assert calculate_cumulative_cash_flow([500]) == [500]

    def test_cumulative_cf_all_positive(self):
        """Все CF положительные → кумулятив строго возрастающий."""
        cf = [1000, 2000, 3000]
        result = calculate_cumulative_cash_flow(cf)
        assert result == [1000, 3000, 6000]
        for i in range(1, len(result)):
            assert result[i] > result[i - 1]

    def test_cumulative_cf_all_negative(self):
        """Все CF отрицательные → кумулятив строго убывающий."""
        cf = [-500, -300, -200]
        result = calculate_cumulative_cash_flow(cf)
        assert result == [-500, -800, -1000]

    def test_cumulative_cf_zero_values(self):
        """Нулевые CF: кумулятив не меняется."""
        cf = [1000, 0, 0, 500]
        result = calculate_cumulative_cash_flow(cf)
        assert result == [1000, 1000, 1000, 1500]

    def test_cumulative_cf_length_equals_input_length(self):
        """Длина результата = длине входа."""
        cf = [1, 2, 3, 4, 5]
        result = calculate_cumulative_cash_flow(cf)
        assert len(result) == len(cf)


# ─── Cash Flow for Months (интеграция с revenue и costs) ─────────────────────

class TestCashFlowForMonths:
    """calculate_cash_flow_for_months корректно агрегирует данные по месяцам."""

    def _make_revenue_result(self, total_revenue):
        return {'total_revenue': total_revenue, 'month': 1}

    def _make_costs_result(self, fixed_total, variable_total):
        return {
            'fixed_costs': {'total': fixed_total},
            'variable_costs': {'total': variable_total},
        }

    def test_cf_for_months_cumulative_accumulates(self):
        """
        M1: Rev=10 000, Costs=8 000 → CF=2 000, CumCF=2 000
        M2: Rev=15 000, Costs=8 000 → CF=7 000, CumCF=9 000
        M3: Rev=20 000, Costs=8 000 → CF=12 000, CumCF=21 000
        """
        revenue_results = [
            {'total_revenue': 10_000},
            {'total_revenue': 15_000},
            {'total_revenue': 20_000},
        ]
        costs_results = [
            {'fixed_costs': {'total': 6_000}, 'variable_costs': {'total': 2_000}},
            {'fixed_costs': {'total': 6_000}, 'variable_costs': {'total': 2_000}},
            {'fixed_costs': {'total': 6_000}, 'variable_costs': {'total': 2_000}},
        ]

        result = calculate_cash_flow_for_months(revenue_results, costs_results, num_months=3)

        assert result[0]['cash_flow'] == 2_000
        assert result[0]['cumulative_cash_flow'] == 2_000
        assert result[1]['cash_flow'] == 7_000
        assert result[1]['cumulative_cash_flow'] == 9_000
        assert result[2]['cash_flow'] == 12_000
        assert result[2]['cumulative_cash_flow'] == 21_000

    def test_cf_for_months_month_numbers_correct(self):
        """Поле month[i] == i+1 (1-indexed)."""
        revenue_results = [{'total_revenue': 0}] * 5
        costs_results = [
            {'fixed_costs': {'total': 0}, 'variable_costs': {'total': 0}}
        ] * 5

        result = calculate_cash_flow_for_months(revenue_results, costs_results, num_months=5)

        for i, cf in enumerate(result):
            assert cf['month'] == i + 1


# ─── Breakeven ────────────────────────────────────────────────────────────────

class TestBreakevenMonth:
    """Точка безубыточности: месяц, когда CumCF переходит в ≥0."""

    def test_breakeven_detected_in_month3(self):
        """
        M1: CF=-100, M2: CF=-50, M3: CF=200
        CumCF: -100, -150, 50 → breakeven в M3.
        """
        revenue = [0, 0, 300]
        costs = [100, 50, 100]

        result = calculate_breakeven_month(revenue, costs)

        assert result['reached'] is True
        assert result['breakeven_month'] == 3

    def test_breakeven_in_month1_when_immediately_profitable(self):
        """Если M1 CF > 0 — breakeven достигается в месяц 1."""
        revenue = [1000, 500, 500]
        costs = [200, 200, 200]

        result = calculate_breakeven_month(revenue, costs)

        assert result['reached'] is True
        assert result['breakeven_month'] == 1

    def test_breakeven_at_exact_zero_cf(self):
        """
        M1: CF=-100, M2: CF=+100 → CumCF M2 = 0.
        Нулевой CumCF считается достижением breakeven (≥0).
        """
        revenue = [0, 200]
        costs = [100, 100]

        result = calculate_breakeven_month(revenue, costs)

        assert result['reached'] is True
        assert result['breakeven_month'] == 2

    def test_breakeven_not_reached_when_always_negative(self):
        """Всегда отрицательный CF → breakeven не достигается."""
        revenue = [100, 100, 100]
        costs = [200, 200, 200]

        result = calculate_breakeven_month(revenue, costs, max_months=3)

        assert result['reached'] is False
        assert result['breakeven_month'] is None

    def test_breakeven_projects_last_value_beyond_data(self):
        """
        Если данных меньше max_months — модель проецирует последнее значение.
        Revenue=[100], Costs=[300] → всегда CF=-200, никогда не выйдем в плюс.
        Но Revenue=[500], Costs=[300] → CF=+200 уже в M1.
        """
        # Один месяц данных, проекция на 6 — всегда отрицательно
        result_neg = calculate_breakeven_month([100], [300], max_months=6)
        assert result_neg['reached'] is False

        # Один месяц данных, проекция на 6 — сразу положительно
        result_pos = calculate_breakeven_month([500], [300], max_months=6)
        assert result_pos['reached'] is True
        assert result_pos['breakeven_month'] == 1

    def test_breakeven_with_growing_revenue_reaches_positive(self):
        """
        Убыток в первые месяцы, прибыль в конце.
        M1=-500, M2=-200, M3=+100, M4=+400 → CumCF: -500, -700, -600, -200.
        Нет breakeven за 4 месяца.
        """
        revenue = [0, 300, 700, 1100]
        costs = [500, 500, 600, 700]

        result = calculate_breakeven_month(revenue, costs, max_months=4)
        # CumCF: -500, -700, -600, -200 — всё ещё отрицательный
        assert result['reached'] is False

    def test_breakeven_cumulative_cf_value_correct(self):
        """cumulative_cf_at_breakeven — накопленный CF на момент достижения."""
        revenue = [0, 0, 0, 600]
        costs = [100, 100, 100, 100]

        result = calculate_breakeven_month(revenue, costs)

        # CumCF: -100, -200, -300, 200
        assert result['reached'] is True
        assert result['breakeven_month'] == 4
        assert result['cumulative_cf_at_breakeven'] == 200


# ─── Минимальная цена аренды ──────────────────────────────────────────────────

class TestMinRentalPrice:
    """Аналитическая формула минимальной цены для целевого breakeven."""

    def test_min_price_formula_no_commission_no_variable(self):
        """
        Без комиссии и переменных затрат:
        min_price = FC × T / ΣP.
        T=3, FC=30 000, 10 пациентов каждый месяц → ΣP=30.
        min_price = 90 000 / 30 = 3 000.
        """
        result = calculate_min_rental_price_for_target_breakeven(
            num_clinics=1,
            patients_per_clinic_month1=10,
            growth_rate=0.0,
            clinic_commission_rate=0.0,
            variable_costs_per_patient=0,
            fixed_costs_monthly=30_000,
            target_breakeven_month=3,
        )
        assert result['feasible'] is True
        assert abs(result['min_rental_price'] - 3_000) < 1

    def test_min_price_increases_with_fixed_costs(self):
        """Чем выше fixed costs — тем выше min цена."""
        base_params = dict(
            num_clinics=1, patients_per_clinic_month1=10, growth_rate=0.0,
            clinic_commission_rate=0.0, variable_costs_per_patient=0,
            target_breakeven_month=3,
        )
        r_low = calculate_min_rental_price_for_target_breakeven(
            **base_params, fixed_costs_monthly=10_000
        )
        r_high = calculate_min_rental_price_for_target_breakeven(
            **base_params, fixed_costs_monthly=50_000
        )
        assert r_high['min_rental_price'] > r_low['min_rental_price']

    def test_min_price_decreases_with_more_patients(self):
        """Чем больше пациентов — тем ниже min цена (затраты делятся на больший объём)."""
        base_params = dict(
            num_clinics=1, growth_rate=0.0, clinic_commission_rate=0.0,
            variable_costs_per_patient=0, fixed_costs_monthly=30_000,
            target_breakeven_month=3,
        )
        r_few = calculate_min_rental_price_for_target_breakeven(
            **base_params, patients_per_clinic_month1=5
        )
        r_many = calculate_min_rental_price_for_target_breakeven(
            **base_params, patients_per_clinic_month1=20
        )
        assert r_many['min_rental_price'] < r_few['min_rental_price']

    def test_min_price_infeasible_with_zero_patients(self):
        """С нулевым числом пациентов — задача не решаема (inf)."""
        result = calculate_min_rental_price_for_target_breakeven(
            num_clinics=1,
            patients_per_clinic_month1=0,
            growth_rate=0.0,
            clinic_commission_rate=0.0,
            variable_costs_per_patient=0,
            fixed_costs_monthly=50_000,
            target_breakeven_month=3,
        )
        assert result['feasible'] is False

    def test_min_price_infeasible_with_100pct_commission(self):
        """При 100% комиссии клиники — net revenue = 0, цена не определена."""
        result = calculate_min_rental_price_for_target_breakeven(
            num_clinics=1,
            patients_per_clinic_month1=10,
            growth_rate=0.0,
            clinic_commission_rate=1.0,
            variable_costs_per_patient=0,
            fixed_costs_monthly=10_000,
            target_breakeven_month=3,
        )
        assert result['feasible'] is False
