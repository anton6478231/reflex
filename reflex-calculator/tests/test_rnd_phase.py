"""
Тесты для модуля R&D фазы (models/rnd_phase.py) и связанных изменений.
"""

import pytest
from models.rnd_phase import (
    calculate_rnd_cash_flows,
    get_total_rnd_cost,
    get_rnd_cost_by_month,
    validate_rnd_vs_bank,
    ensure_matrix_size,
    build_empty_matrix,
    rename_category,
    DEFAULT_RND_CATEGORIES,
    RND_PHASE_LABEL,
    MARKET_PHASE_LABEL,
)
from models.cash_flow import calculate_npv_series


# ──────────────────────────────────────────────────────────────
# calculate_rnd_cash_flows
# ──────────────────────────────────────────────────────────────

class TestCalculateRndCashFlows:
    def test_single_month_single_category(self):
        matrix = {"Зарплата": [100_000.0]}
        results = calculate_rnd_cash_flows(1, matrix)
        assert len(results) == 1
        r = results[0]
        assert r["month"] == 1
        assert r["phase"] == RND_PHASE_LABEL
        assert r["total_costs"] == 100_000.0
        assert r["cash_flow"] == -100_000.0
        assert r["revenue"] == 0.0
        assert r["cumulative_cash_flow"] == -100_000.0

    def test_multiple_months_multiple_categories(self):
        matrix = {
            "Зарплата": [100_000.0, 120_000.0, 110_000.0],
            "Оборудование": [50_000.0, 0.0, 30_000.0],
        }
        results = calculate_rnd_cash_flows(3, matrix)
        assert len(results) == 3

        expected_totals = [150_000.0, 120_000.0, 140_000.0]
        cumulative = 0.0
        for i, r in enumerate(results):
            assert r["total_costs"] == pytest.approx(expected_totals[i])
            assert r["cash_flow"] == pytest.approx(-expected_totals[i])
            cumulative += -expected_totals[i]
            assert r["cumulative_cash_flow"] == pytest.approx(cumulative)

    def test_empty_matrix_gives_zero_costs(self):
        results = calculate_rnd_cash_flows(3, {})
        for r in results:
            assert r["total_costs"] == 0.0
            assert r["cash_flow"] == 0.0

    def test_breakdown_keys_correct(self):
        matrix = {"A": [10.0], "B": [20.0]}
        results = calculate_rnd_cash_flows(1, matrix)
        assert results[0]["breakdown"]["A"] == 10.0
        assert results[0]["breakdown"]["B"] == 20.0

    def test_matrix_shorter_than_rnd_months_padded_with_zero(self):
        matrix = {"Кат": [5_000.0]}  # только 1 значение, но просим 3 месяца
        results = calculate_rnd_cash_flows(3, matrix)
        assert results[0]["total_costs"] == 5_000.0
        assert results[1]["total_costs"] == 0.0
        assert results[2]["total_costs"] == 0.0

    def test_phase_label_is_rnd(self):
        matrix = {"X": [1.0, 2.0]}
        results = calculate_rnd_cash_flows(2, matrix)
        for r in results:
            assert r["phase"] == "rnd"


# ──────────────────────────────────────────────────────────────
# get_total_rnd_cost
# ──────────────────────────────────────────────────────────────

class TestGetTotalRndCost:
    def test_basic(self):
        matrix = {"A": [10_000.0, 20_000.0], "B": [5_000.0, 5_000.0]}
        total = get_total_rnd_cost(matrix, 2)
        assert total == pytest.approx(40_000.0)

    def test_empty_matrix(self):
        assert get_total_rnd_cost({}, 3) == 0.0

    def test_rnd_months_limits_sum(self):
        matrix = {"A": [10_000.0, 10_000.0, 10_000.0]}
        total = get_total_rnd_cost(matrix, 2)  # берём только первые 2
        assert total == pytest.approx(20_000.0)


# ──────────────────────────────────────────────────────────────
# get_rnd_cost_by_month
# ──────────────────────────────────────────────────────────────

class TestGetRndCostByMonth:
    def test_basic(self):
        matrix = {"A": [10_000.0, 20_000.0], "B": [5_000.0, 5_000.0]}
        monthly = get_rnd_cost_by_month(matrix, 2)
        assert monthly == [15_000.0, 25_000.0]

    def test_empty_matrix(self):
        assert get_rnd_cost_by_month({}, 3) == [0.0, 0.0, 0.0]


# ──────────────────────────────────────────────────────────────
# validate_rnd_vs_bank
# ──────────────────────────────────────────────────────────────

class TestValidateRndVsBank:
    def test_ok_when_within_budget(self):
        result = validate_rnd_vs_bank(500_000.0, 1_000_000.0)
        assert result["ok"] is True
        assert result["remaining"] == pytest.approx(500_000.0)
        assert result["overflow"] == 0.0
        assert result["pct_used"] == pytest.approx(50.0)

    def test_error_when_exceeds_budget(self):
        result = validate_rnd_vs_bank(1_200_000.0, 1_000_000.0)
        assert result["ok"] is False
        assert result["overflow"] == pytest.approx(200_000.0)
        assert result["remaining"] == 0.0

    def test_zero_bank_gives_error(self):
        result = validate_rnd_vs_bank(100_000.0, 0.0)
        assert result["ok"] is False

    def test_zero_cost_ok(self):
        result = validate_rnd_vs_bank(0.0, 1_000_000.0)
        assert result["ok"] is True
        assert result["remaining"] == pytest.approx(1_000_000.0)

    def test_exactly_equals_bank(self):
        result = validate_rnd_vs_bank(1_000_000.0, 1_000_000.0)
        assert result["ok"] is True
        assert result["remaining"] == 0.0
        assert result["pct_used"] == pytest.approx(100.0)


# ──────────────────────────────────────────────────────────────
# ensure_matrix_size
# ──────────────────────────────────────────────────────────────

class TestEnsureMatrixSize:
    def test_pads_short_lists(self):
        matrix = {"A": [1.0]}
        result = ensure_matrix_size(matrix, 3)
        assert result["A"] == [1.0, 0.0, 0.0]

    def test_truncates_long_lists(self):
        matrix = {"A": [1.0, 2.0, 3.0, 4.0, 5.0]}
        result = ensure_matrix_size(matrix, 3)
        assert result["A"] == [1.0, 2.0, 3.0]

    def test_exact_length_unchanged(self):
        matrix = {"A": [1.0, 2.0, 3.0]}
        result = ensure_matrix_size(matrix, 3)
        assert result["A"] == [1.0, 2.0, 3.0]


# ──────────────────────────────────────────────────────────────
# build_empty_matrix
# ──────────────────────────────────────────────────────────────

class TestBuildEmptyMatrix:
    def test_creates_correct_shape(self):
        cats = ["A", "B", "C"]
        matrix = build_empty_matrix(cats, 4)
        assert set(matrix.keys()) == set(cats)
        for cat in cats:
            assert matrix[cat] == [0.0, 0.0, 0.0, 0.0]


# ──────────────────────────────────────────────────────────────
# rename_category
# ──────────────────────────────────────────────────────────────

class TestRenameCategory:
    def test_renames_correctly(self):
        matrix = {"Old": [1.0, 2.0], "Keep": [3.0, 4.0]}
        result = rename_category(matrix, "Old", "New")
        assert "New" in result
        assert "Old" not in result
        assert result["New"] == [1.0, 2.0]
        assert result["Keep"] == [3.0, 4.0]

    def test_nonexistent_key_has_no_effect(self):
        matrix = {"A": [1.0]}
        result = rename_category(matrix, "X", "Y")
        assert "A" in result
        assert "X" not in result
        assert "Y" not in result


# ──────────────────────────────────────────────────────────────
# calculate_npv_series with month_offset
# ──────────────────────────────────────────────────────────────

class TestNpvSeriesWithOffset:
    def test_offset_zero_equals_no_offset(self):
        cash_flows = [10_000.0, 15_000.0, 20_000.0]
        rate = 0.20
        npv_without = calculate_npv_series(cash_flows, rate)
        npv_with_zero = calculate_npv_series(cash_flows, rate, month_offset=0)
        assert npv_without == pytest.approx(npv_with_zero)

    def test_offset_increases_discount(self):
        """С ненулевым offset NPV должен быть меньше (больший дисконт)."""
        cash_flows = [100_000.0, 200_000.0]
        rate = 0.20
        npv_no_offset = calculate_npv_series(cash_flows, rate, month_offset=0)
        npv_with_offset = calculate_npv_series(cash_flows, rate, month_offset=3)
        # С бо́льшим дисконтом PV ниже
        assert npv_with_offset[-1] < npv_no_offset[-1]

    def test_offset_formula_correctness(self):
        """Вручную проверяем формулу для 1 месяца с offset=2 и ставкой 0%."""
        # При нулевой ставке дисконтирования offset не влияет
        cash_flows = [10_000.0]
        npv_no_offset = calculate_npv_series(cash_flows, 0.0, month_offset=0)
        npv_with_offset = calculate_npv_series(cash_flows, 0.0, month_offset=2)
        assert npv_no_offset[-1] == pytest.approx(10_000.0)
        assert npv_with_offset[-1] == pytest.approx(10_000.0)

    def test_offset_with_nonzero_rate(self):
        """Проверяем конкретные цифры: CF=12000, r=0.20/год, offset=6."""
        import math
        cf = 12_000.0
        annual = 0.20
        offset = 6
        r_m = (1 + annual) ** (1 / 12) - 1
        expected_pv = cf / (1 + r_m) ** (1 + offset)

        result = calculate_npv_series([cf], annual, month_offset=offset)
        assert result[0] == pytest.approx(expected_pv, rel=1e-6)

    def test_cumulative_with_offset(self):
        """Кумулятивный NPV с offset = сумма дисконтированных CF."""
        cash_flows = [5_000.0, 10_000.0, 8_000.0]
        annual = 0.15
        offset = 3
        r_m = (1 + annual) ** (1 / 12) - 1

        expected_series = []
        cumsum = 0.0
        for t, cf in enumerate(cash_flows, start=1):
            cumsum += cf / (1 + r_m) ** (t + offset)
            expected_series.append(cumsum)

        result = calculate_npv_series(cash_flows, annual, month_offset=offset)
        for i in range(len(cash_flows)):
            assert result[i] == pytest.approx(expected_series[i], rel=1e-6)


# ──────────────────────────────────────────────────────────────
# DEFAULT_RND_CATEGORIES
# ──────────────────────────────────────────────────────────────

class TestDefaultCategories:
    def test_is_nonempty_list(self):
        assert isinstance(DEFAULT_RND_CATEGORIES, list)
        assert len(DEFAULT_RND_CATEGORIES) > 0

    def test_all_strings(self):
        for cat in DEFAULT_RND_CATEGORIES:
            assert isinstance(cat, str)


# ──────────────────────────────────────────────────────────────
# Integration: R&D + NPV offset
# ──────────────────────────────────────────────────────────────

class TestRndNpvIntegration:
    def test_rnd_costs_reduce_bank_balance(self):
        """validate_rnd_vs_bank корректно учитывает суммарные расходы R&D."""
        matrix = {
            "Зарплата": [200_000.0, 200_000.0],
            "Оборудование": [100_000.0, 50_000.0],
        }
        total = get_total_rnd_cost(matrix, 2)
        assert total == pytest.approx(550_000.0)
        result = validate_rnd_vs_bank(total, 600_000.0)
        assert result["ok"] is True
        assert result["remaining"] == pytest.approx(50_000.0)

    def test_rnd_results_have_zero_revenue(self):
        """В R&D фазе нет выручки."""
        matrix = {"A": [50_000.0]}
        results = calculate_rnd_cash_flows(1, matrix)
        assert results[0]["revenue"] == 0.0

    def test_npv_offset_matches_rnd_months(self):
        """
        Если R&D = 3 месяца, NPV рыночных CF дисконтируется со сдвигом 3.
        Проверяем, что для рыночного месяца 1 показатель < без сдвига.
        """
        market_cf = [100_000.0]
        annual = 0.24
        rnd_months = 3

        pv_no_rnd = calculate_npv_series(market_cf, annual, month_offset=0)
        pv_with_rnd = calculate_npv_series(market_cf, annual, month_offset=rnd_months)

        assert pv_with_rnd[-1] < pv_no_rnd[-1]

    def test_combined_npv_length(self):
        """
        Объединённый NPV (R&D + рынок) должен иметь длину rnd_months + num_months.
        Моделируем логику calculator.py: _combined_cf = rnd_cf + market_cf,
        npv_combined = calculate_npv_series(_combined_cf, rate, month_offset=0).
        """
        rnd_months = 3
        num_months = 12
        annual = 0.20

        matrix = {"R&D расходы": [50_000.0] * rnd_months}
        rnd_results = calculate_rnd_cash_flows(rnd_months, matrix)
        rnd_cf = [r["cash_flow"] for r in rnd_results]

        market_cf = [80_000.0] * num_months

        combined_cf = rnd_cf + market_cf
        pv_combined = calculate_npv_series(combined_cf, annual, month_offset=0)
        initial_investment = 200_000.0
        npv_combined = [pv - initial_investment for pv in pv_combined]

        assert len(npv_combined) == rnd_months + num_months

        # Разбивка обратно
        rnd_npv = npv_combined[:rnd_months]
        market_npv = npv_combined[rnd_months:]
        assert len(rnd_npv) == rnd_months
        assert len(market_npv) == num_months
