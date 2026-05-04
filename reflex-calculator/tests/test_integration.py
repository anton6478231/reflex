"""
Интеграционные тесты — полный pipeline Revenue → Costs → Cash Flow.

Проверяет, что все три модели (A, B, A+B) работают корректно как система:
  - Рост пациентов отражается одновременно в Revenue И Costs
  - 100% Churn → 0 выручки, но fixed costs остаются
  - 0 пациентов → 0 переменных затрат на пациентов
  - Парк устройств растёт только при дефиците (не сжимается)
  - Breakeven достижим при достаточном росте
  - Анализ чувствительности правильно направлен (±доход, ±затраты)
  - Все числа в pipeline логически согласованы между модулями
"""
import pytest
from models.revenue import calculate_revenue_for_months
from models.costs import calculate_costs_for_months, calculate_costs_for_month
from models.cash_flow import (
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
)
from models.sensitivity import calculate_sensitivity_analysis


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _zero_fixed():
    return {
        'team_salaries': 0,
        'infrastructure_fixed': 0,
        'office_rent': 0,
        'legal_services': 0,
        'other_fixed': 0,
    }


def _full_pipeline(model_type, revenue_params, fixed_params, variable_params,
                   num_months=6, assumptions=None):
    """Полный pipeline: revenue → costs → CF."""
    rev = calculate_revenue_for_months(model_type, revenue_params, num_months, assumptions)
    costs = calculate_costs_for_months(model_type, fixed_params, variable_params, rev, num_months)
    cf = calculate_cash_flow_for_months(rev, costs, num_months)
    return rev, costs, cf


# ─── Model B: сквозные числа ──────────────────────────────────────────────────

class TestModelBPipeline:
    """End-to-end тесты для Model B (B2B2C)."""

    # Базовые параметры для группы тестов
    REV_PARAMS = {
        'num_clinics': 1,
        'patients_per_clinic_month1': 10,
        'growth_rate': 0.0,       # без роста: 10 пациентов каждый месяц
        'rental_price': 1_000,
        'clinic_commission_rate': 0.0,
        'rehab_duration_months': 1,  # пациенты уходят через 1 мес → когорта = новые
    }

    def test_revenue_equals_patients_times_price(self):
        """Выручка = активные пациенты × rental_price (без комиссии)."""
        rev, _, _ = _full_pipeline(
            'model_b',
            self.REV_PARAMS,
            _zero_fixed(),
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=3,
        )
        # Каждый месяц: 10 пациентов × 1000 = 10 000
        for r in rev:
            assert r['total_revenue'] == 10_000

    def test_support_costs_track_active_patients(self):
        """
        Затраты на поддержку = активные пациенты × cost_per_month.
        duration=3: M1=10, M2=20, M3=30 активных пациентов (когорта накапливается).
        """
        params = self.REV_PARAMS | {'rehab_duration_months': 3}
        var = {'cogs_per_device': 0, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 100, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0}

        rev, costs, _ = _full_pipeline('model_b', params, _zero_fixed(), var, num_months=3)

        assert costs[0]['variable_costs']['support'] == 10 * 100   # M1: 10 активных
        assert costs[1]['variable_costs']['support'] == 20 * 100   # M2: 20 активных
        assert costs[2]['variable_costs']['support'] == 30 * 100   # M3: 30 активных

    def test_fixed_costs_constant_variable_costs_grow(self):
        """
        Fixed costs постоянны, переменные растут вместе с когортой.
        При росте когорты total_costs увеличивается.
        """
        params = self.REV_PARAMS | {'rehab_duration_months': 3}
        var = {'cogs_per_device': 0, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 200, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0}
        fixed = _zero_fixed() | {'team_salaries': 50_000}

        _, costs, _ = _full_pipeline('model_b', params, fixed, var, num_months=3)

        fixed_vals = [c['fixed_costs']['total'] for c in costs]
        var_vals = [c['variable_costs']['total'] for c in costs]

        # Fixed не меняется
        assert fixed_vals[0] == fixed_vals[1] == fixed_vals[2] == 50_000
        # Variable растёт (когорта накапливается)
        assert var_vals[0] < var_vals[1] < var_vals[2]

    def test_100pct_churn_zeroes_revenue(self):
        """
        100% churn → 0 активных пациентов → 0 выручки во все месяцы.
        Fixed costs остаются → CF = −Fixed_Costs.
        """
        rev, costs, cf = _full_pipeline(
            'model_b',
            self.REV_PARAMS | {'rehab_duration_months': 3},
            _zero_fixed() | {'team_salaries': 30_000},
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=3,
            assumptions={'churn_rate': 1.0, 'utilization_rate': 1.0},
        )
        for r in rev:
            assert r['total_revenue'] == 0
        for c in cf:
            assert c['cash_flow'] == -30_000  # только fixed costs

    def test_zero_patients_zero_patient_variable_costs(self):
        """
        0 пациентов → COGS, логистика, поддержка = 0.
        (Модель с 0 клиниками.)
        """
        params = self.REV_PARAMS | {'num_clinics': 0}
        var = {'cogs_per_device': 5_000, 'logistics_per_patient': 500,
               'support_per_patient_per_month': 200, 'cac_clinic': 0,
               'cac_patient': 1_000, 'infrastructure_per_user': 0}

        rev, costs, _ = _full_pipeline('model_b', params, _zero_fixed(), var, num_months=3)

        for c in costs:
            assert c['variable_costs']['cogs'] == 0
            assert c['variable_costs']['logistics'] == 0
            assert c['variable_costs']['support'] == 0
            assert c['variable_costs']['cac'] == 0

    def test_more_patients_more_revenue_and_more_variable_costs(self):
        """
        Удвоение числа пациентов → вдвое больше выручки И переменных затрат.
        (При duration=1: когорта == новые пациенты каждый месяц.)
        """
        var = {'cogs_per_device': 0, 'logistics_per_patient': 300,
               'support_per_patient_per_month': 150, 'cac_clinic': 0,
               'cac_patient': 500, 'infrastructure_per_user': 0}

        def run(n_patients):
            p = self.REV_PARAMS | {'patients_per_clinic_month1': n_patients}
            _, costs, cf = _full_pipeline('model_b', p, _zero_fixed(), var, num_months=1)
            return costs[0]['variable_costs']['total']

        var_costs_10 = run(10)
        var_costs_20 = run(20)
        assert var_costs_20 == var_costs_10 * 2

    def test_breakeven_reachable_with_sufficient_margin(self):
        """
        При высоком рентном доходе и низких затратах breakeven достигается.
        1 клиника, 50 пациентов, rental=2000, fixed=50000, нет переменных.
        CF = 50*2000 - 50000 = 50000 > 0 → breakeven M1.
        """
        rev, costs, cf = _full_pipeline(
            'model_b',
            {
                'num_clinics': 1,
                'patients_per_clinic_month1': 50,
                'growth_rate': 0.0,
                'rental_price': 2_000,
                'clinic_commission_rate': 0.0,
                'rehab_duration_months': 1,
            },
            _zero_fixed() | {'team_salaries': 50_000},
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=3,
        )
        revenue_list = [r['total_revenue'] for r in rev]
        costs_list = [c['total_costs'] for c in costs]
        be = calculate_breakeven_month(revenue_list, costs_list)

        assert be['reached'] is True
        assert be['breakeven_month'] == 1

    def test_breakeven_not_reached_when_always_unprofitable(self):
        """При очень высоких fixed costs и малом потоке breakeven не достигается."""
        rev, costs, _ = _full_pipeline(
            'model_b',
            {
                'num_clinics': 1,
                'patients_per_clinic_month1': 2,
                'growth_rate': 0.0,
                'rental_price': 500,
                'clinic_commission_rate': 0.0,
                'rehab_duration_months': 1,
            },
            _zero_fixed() | {'team_salaries': 500_000},
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=6,
        )
        revenue_list = [r['total_revenue'] for r in rev]
        costs_list = [c['total_costs'] for c in costs]
        be = calculate_breakeven_month(revenue_list, costs_list, max_months=6)

        assert be['reached'] is False


# ─── Model A: сквозные числа ──────────────────────────────────────────────────

class TestModelAPipeline:
    """End-to-end тесты для Model A (B2B)."""

    def test_model_a_no_patients_subscription_only(self):
        """
        Model A без пациентов: только subscription revenue.
        Нет COGS после M1, нет логистики, нет поддержки.
        """
        rev_params = {
            'num_clinics': 2,
            'devices_per_clinic': 10,
            'setup_fee': 50_000,
            'subscription_per_device': 2_000,
            'patients_per_clinic_month1': 0,
            'growth_rate': 0.0,
            'rehab_duration_months': 3,
        }
        var = {'cogs_per_device': 5_000, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 0, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0, 'num_clinics': 2}

        rev, costs, _ = _full_pipeline(
            'model_a', rev_params, _zero_fixed(), var, num_months=3
        )

        # M1: setup_fee для 20 устройств + subscription
        assert rev[0]['setup_revenue'] == 20 * 50_000
        assert rev[0]['subscription_revenue'] == 20 * 2_000
        # M2, M3: только subscription, нет setup, нет COGS
        assert rev[1]['setup_revenue'] == 0
        assert rev[2]['setup_revenue'] == 0
        assert costs[1]['variable_costs']['cogs'] == 0
        assert costs[2]['variable_costs']['cogs'] == 0

    def test_model_a_pool_expands_only_when_needed(self):
        """
        Парк устройств расширяется только при дефиците.
        devices_per_clinic=10, 2 клиники → контрактный минимум 20.
        Если спрос ≤ 20 — парк остаётся 20, COGS в M2 = 0.
        """
        rev_params = {
            'num_clinics': 2,
            'devices_per_clinic': 10,
            'setup_fee': 50_000,
            'subscription_per_device': 2_000,
            'patients_per_clinic_month1': 5,   # 10 пациентов — меньше 20
            'growth_rate': 0.0,
            'rehab_duration_months': 3,
        }
        var = {'cogs_per_device': 5_000, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 0, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0, 'num_clinics': 2}

        rev, costs, _ = _full_pipeline(
            'model_a', rev_params, _zero_fixed(), var, num_months=3,
            assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
        )

        # Спрос M1=10, M2=10+10=20, M3=30 (duration=3 накапливает)
        # Pool M1=20 (контракт), M2=20 (спрос 20=контракт), M3=30 (спрос 30 > 20)
        assert rev[0]['devices_in_pool'] == 20
        assert rev[1]['devices_in_pool'] == 20
        assert costs[1]['variable_costs']['cogs'] == 0   # нет новых устройств в M2
        assert rev[2]['devices_in_pool'] == 30
        assert costs[2]['variable_costs']['cogs'] == 5_000 * 10  # 10 новых в M3

    def test_model_a_cac_with_clinic_schedule(self):
        """
        CAC начисляется в M1 за начальные клиники и в M3 за клиники из расписания.
        (Использует фикс new_clinics_this_month в revenue.py + costs.py)
        """
        rev_params = {
            'num_clinics': 2,
            'devices_per_clinic': 5,
            'setup_fee': 0,
            'subscription_per_device': 0,
            'patients_per_clinic_month1': 3,
            'growth_rate': 0.0,
            'rehab_duration_months': 3,
            'clinic_schedule': [{'month_start': 3, 'count': 2}],
        }
        var = {'cogs_per_device': 0, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 0, 'cac_clinic': 10_000,
               'cac_patient': 0, 'infrastructure_per_user': 0, 'num_clinics': 2}

        rev, costs, _ = _full_pipeline(
            'model_a', rev_params, _zero_fixed(), var, num_months=4,
            assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
        )

        # M1: 2 начальные клиники
        assert costs[0]['variable_costs']['cac'] == 20_000
        # M2: новых клиник нет
        assert costs[1]['variable_costs']['cac'] == 0
        # M3: 2 новые клиники через schedule
        assert costs[2]['variable_costs']['cac'] == 20_000
        # M4: новых клиник нет
        assert costs[3]['variable_costs']['cac'] == 0


# ─── Model A+B: сквозные числа ────────────────────────────────────────────────

class TestModelABPipeline:
    """End-to-end тесты для Model A+B (Гибрид)."""

    BASE_REV = {
        'num_clinics': 1,
        'devices_per_clinic': 10,
        'setup_fee': 20_000,
        'subscription_per_device': 1_000,
        'patients_per_clinic_month1': 5,
        'growth_rate': 0.0,
        'rental_price': 2_000,
        'clinic_commission_rate': 0.0,
        'rehab_duration_months': 3,
    }

    def test_total_revenue_is_sum_of_components(self):
        """
        total_revenue = setup_revenue + subscription_revenue + rental_net_revenue.
        """
        rev, _, _ = _full_pipeline(
            'model_ab',
            self.BASE_REV,
            _zero_fixed(),
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=3,
        )
        for r in rev:
            component_sum = (
                r['setup_revenue'] + r['subscription_revenue'] + r['rental_net_revenue']
            )
            assert abs(r['total_revenue'] - component_sum) < 1, (
                f"M{r['month']}: total_revenue={r['total_revenue']}, "
                f"components sum={component_sum}"
            )

    def test_setup_fee_only_in_month1_for_initial_pool(self):
        """Setup fee за начальный парк начисляется только в M1."""
        rev, _, _ = _full_pipeline(
            'model_ab',
            self.BASE_REV | {'growth_rate': 0.0},
            _zero_fixed(),
            {'cogs_per_device': 0, 'logistics_per_patient': 0,
             'support_per_patient_per_month': 0, 'cac_clinic': 0,
             'cac_patient': 0, 'infrastructure_per_user': 0},
            num_months=3,
        )
        # M1: setup за initial pool (10 устройств)
        assert rev[0]['setup_revenue'] >= 10 * 20_000
        # M2, M3: setup_revenue_base = 0
        assert rev[1].get('setup_revenue_base', 0) == 0
        assert rev[2].get('setup_revenue_base', 0) == 0


# ─── Анализ чувствительности ─────────────────────────────────────────────────

class TestSensitivityAnalysis:
    """Sensitivity analysis: направление влияния параметров корректно."""

    def _base_all_params(self):
        return {
            'revenue': {
                'num_clinics': 2,
                'patients_per_clinic_month1': 10,
                'growth_rate': 0.2,
                'rental_price': 3_000,
                'clinic_commission_rate': 0.15,
                'rehab_duration_months': 3,
            },
            'fixed_costs': {
                'team_salaries': 100_000,
                'infrastructure_fixed': 10_000,
                'office_rent': 20_000,
                'legal_services': 5_000,
                'other_fixed': 5_000,
            },
            'variable_costs': {
                'cogs_per_device': 5_000,
                'logistics_per_patient': 300,
                'support_per_patient_per_month': 150,
                'cac_clinic': 0,
                'cac_patient': 500,
                'infrastructure_per_user': 0,
            },
            'assumptions': {'churn_rate': 0.0, 'utilization_rate': 1.0},
        }

    def _compute_base_cf(self, all_params, num_months=3):
        rev = calculate_revenue_for_months(
            'model_b', all_params['revenue'], num_months,
            assumptions=all_params.get('assumptions'),
        )
        costs = calculate_costs_for_months(
            'model_b', all_params['fixed_costs'],
            all_params['variable_costs'], rev, num_months,
        )
        cf = calculate_cash_flow_for_months(rev, costs, num_months)
        return sum(c['cash_flow'] for c in cf)

    def test_increasing_rental_price_increases_total_cf(self):
        """Рост rental_price → больший total CF (выручка растёт, затраты не меняются)."""
        all_params = self._base_all_params()
        base_cf = self._compute_base_cf(all_params)

        all_params['revenue']['rental_price'] *= 1.5
        higher_cf = self._compute_base_cf(all_params)

        assert higher_cf > base_cf

    def test_increasing_team_salaries_decreases_total_cf(self):
        """Рост ФОТ → меньший total CF (затраты растут, выручка не меняется)."""
        all_params = self._base_all_params()
        base_cf = self._compute_base_cf(all_params)

        all_params['fixed_costs']['team_salaries'] *= 2
        lower_cf = self._compute_base_cf(all_params)

        assert lower_cf < base_cf

    def test_sensitivity_results_sorted_by_impact(self):
        """Sensitivity analysis возвращает результаты, отсортированные по impact (desc)."""
        all_params = self._base_all_params()
        base_cf = self._compute_base_cf(all_params)

        results = calculate_sensitivity_analysis('model_b', all_params, base_cf,
                                                  variation_percent=0.20, num_months=3)
        impacts = [r['impact'] for r in results]
        assert impacts == sorted(impacts, reverse=True), "Результаты не отсортированы по impact"

    def test_sensitivity_rental_price_is_most_impactful_param(self):
        """
        Для модели B rental_price ожидаемо является самым чувствительным параметром:
        изменение цены прямо пропорционально влияет на revenue.
        """
        all_params = self._base_all_params()
        base_cf = self._compute_base_cf(all_params)

        results = calculate_sensitivity_analysis('model_b', all_params, base_cf,
                                                  variation_percent=0.20, num_months=3)
        top_param = results[0]['parameter']
        # rental_price или patients_per_clinic_month1 — оба прямо влияют на выручку
        assert top_param in ('rental_price', 'patients_per_clinic_month1'), (
            f"Ожидали revenue-параметр в топе, получили: {top_param}"
        )


# ─── Согласованность полей между модулями ─────────────────────────────────────

class TestFieldConsistency:
    """Проверяет, что поля результатов модулей согласованы между собой."""

    def test_revenue_num_patients_matches_costs_support_patients(self):
        """
        revenue['num_patients'] (billable) = основа для costs support.
        При support_per_month=100: costs.support = num_patients × 100.
        """
        rev_params = {
            'num_clinics': 2,
            'patients_per_clinic_month1': 8,
            'growth_rate': 0.5,
            'rental_price': 2_000,
            'clinic_commission_rate': 0.0,
            'rehab_duration_months': 3,
        }
        var = {'cogs_per_device': 0, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 100, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0}
        assumptions = {'churn_rate': 0.0, 'utilization_rate': 1.0}

        rev, costs, _ = _full_pipeline('model_b', rev_params, _zero_fixed(), var,
                                        num_months=3, assumptions=assumptions)

        for i in range(3):
            expected_support = rev[i]['num_patients'] * 100
            actual_support = costs[i]['variable_costs']['support']
            assert actual_support == expected_support, (
                f"M{i+1}: num_patients={rev[i]['num_patients']}, "
                f"support={actual_support}, expected={expected_support}"
            )

    def test_revenue_new_patients_matches_costs_logistics(self):
        """
        revenue['new_patients'] = основа для costs logistics.
        При logistics_per_patient=500: costs.logistics = new_patients × 500.
        """
        rev_params = {
            'num_clinics': 1,
            'patients_per_clinic_month1': 5,
            'growth_rate': 1.0,
            'rental_price': 1_000,
            'clinic_commission_rate': 0.0,
            'rehab_duration_months': 6,
        }
        var = {'cogs_per_device': 0, 'logistics_per_patient': 500,
               'support_per_patient_per_month': 0, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0}
        assumptions = {'churn_rate': 0.0, 'utilization_rate': 1.0}

        rev, costs, _ = _full_pipeline('model_b', rev_params, _zero_fixed(), var,
                                        num_months=4, assumptions=assumptions)

        for i in range(4):
            expected_logistics = rev[i]['new_patients'] * 500
            actual_logistics = costs[i]['variable_costs']['logistics']
            assert actual_logistics == expected_logistics, (
                f"M{i+1}: new_patients={rev[i]['new_patients']}, "
                f"logistics={actual_logistics}, expected={expected_logistics}"
            )

    def test_cf_revenue_matches_revenue_module_output(self):
        """
        В cash_flow_results['revenue'] == revenue_results['total_revenue'].
        Промежуточных трансформаций не должно быть.
        """
        rev_params = {
            'num_clinics': 1,
            'patients_per_clinic_month1': 10,
            'growth_rate': 0.3,
            'rental_price': 1_500,
            'clinic_commission_rate': 0.10,
            'rehab_duration_months': 2,
        }
        var = {'cogs_per_device': 0, 'logistics_per_patient': 0,
               'support_per_patient_per_month': 0, 'cac_clinic': 0,
               'cac_patient': 0, 'infrastructure_per_user': 0}

        rev, costs, cf = _full_pipeline('model_b', rev_params, _zero_fixed(), var, num_months=4)

        for i in range(4):
            assert cf[i]['revenue'] == rev[i]['total_revenue'], (
                f"M{i+1}: cf.revenue={cf[i]['revenue']} != rev.total={rev[i]['total_revenue']}"
            )
