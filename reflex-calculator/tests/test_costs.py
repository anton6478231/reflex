"""
Тесты для models/costs.py — проверка корректности атрибуции затрат.

Критические инварианты, которые здесь проверяются:
  - COGS       : только за НОВЫЕ устройства (num_devices_produced), не за весь парк
  - Логистика  : только за НОВЫХ пациентов (new_patients), не за активных
  - Поддержка  : за ВСЕХ активных пациентов ежемесячно (num_patients)
  - Fixed Costs: одинаковы каждый месяц; не зависят от объема
  - CAC model_a: начисляется в месяц подключения новых клиник (включая clinic_schedule)
  - CAC model_b: за каждого нового пациента каждый месяц
  - Единоразовые кастомные статьи: только в месяц 1
  - Ежемесячные кастомные статьи: каждый месяц
  - Кастомные переменные затраты: корректная разбивка по типу
"""
import pytest
from models.costs import calculate_costs_for_month


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _zero_fixed():
    """Нулевые фиксированные затраты для изоляции переменных."""
    return {
        'team_salaries': 0,
        'infrastructure_fixed': 0,
        'office_rent': 0,
        'legal_services': 0,
        'other_fixed': 0,
    }


def _zero_variable():
    """Нулевые переменные параметры — все статьи выключены."""
    return {
        'cogs_per_device': 0,
        'logistics_per_patient': 0,
        'support_per_patient_per_month': 0,
        'cac_clinic': 0,
        'cac_patient': 0,
        'infrastructure_per_user': 0,
        'num_clinics': 0,
    }


def _rev(**kw):
    """Минимальный revenue_result с нулевыми значениями по умолчанию."""
    defaults = {
        'new_patients': 0,
        'num_patients': 0,
        'num_devices_produced': 0,
        'num_clinics': 0,
    }
    defaults.update(kw)
    return defaults


# ─── COGS ────────────────────────────────────────────────────────────────────

class TestCOGS:
    """COGS должен начисляться только за произведённые (новые) устройства."""

    def test_cogs_charged_only_for_new_devices_not_total_pool(self):
        """
        В месяце 2: парк 25 устройств, но произведено только 5 новых.
        COGS = 5 × 10 000 = 50 000, а не 25 × 10 000 = 250 000.
        """
        var = _zero_variable() | {'cogs_per_device': 10_000}
        rev = _rev(num_devices_produced=5, num_patients=25)

        costs = calculate_costs_for_month('model_a', _zero_fixed(), var, rev, month=2)

        assert costs['variable_costs']['cogs'] == 50_000

    def test_cogs_zero_when_pool_not_expanded(self):
        """Если парк не расширялся — COGS = 0, даже если активных пациентов много."""
        var = _zero_variable() | {'cogs_per_device': 15_000}
        rev = _rev(num_devices_produced=0, num_patients=30)

        costs = calculate_costs_for_month('model_b', _zero_fixed(), var, rev, month=2)

        assert costs['variable_costs']['cogs'] == 0

    def test_cogs_scales_linearly_with_devices_produced(self):
        """COGS линейно масштабируется с количеством произведённых устройств."""
        cogs_unit = 8_000
        for n_devices in [1, 5, 10, 20]:
            var = _zero_variable() | {'cogs_per_device': cogs_unit}
            rev = _rev(num_devices_produced=n_devices)
            costs = calculate_costs_for_month('model_a', _zero_fixed(), var, rev, month=1)
            assert costs['variable_costs']['cogs'] == n_devices * cogs_unit


# ─── Логистика ────────────────────────────────────────────────────────────────

class TestLogistics:
    """Логистика — разовая доставка при начале реабилитации, только новым пациентам."""

    def test_logistics_charged_only_on_new_patients(self):
        """
        5 новых пациентов при 20 активных → логистика = 5 × 500 = 2 500.
        Не 20 × 500 = 10 000.
        """
        var = _zero_variable() | {'logistics_per_patient': 500}
        rev = _rev(new_patients=5, num_patients=20)

        costs = calculate_costs_for_month('model_b', _zero_fixed(), var, rev, month=2)

        assert costs['variable_costs']['logistics'] == 2_500

    def test_logistics_zero_when_no_new_patients(self):
        """Если новых пациентов нет — логистика = 0, даже если есть активные."""
        var = _zero_variable() | {'logistics_per_patient': 500}
        rev = _rev(new_patients=0, num_patients=15)

        costs = calculate_costs_for_month('model_b', _zero_fixed(), var, rev, month=3)

        assert costs['variable_costs']['logistics'] == 0


# ─── Поддержка ────────────────────────────────────────────────────────────────

class TestSupport:
    """Поддержка — ежемесячная, начисляется на всех активных пациентов."""

    def test_support_on_all_active_patients_not_only_new(self):
        """
        20 активных пациентов (5 новых + 15 старых).
        Поддержка = 20 × 200 = 4 000, а не 5 × 200 = 1 000.
        """
        var = _zero_variable() | {'support_per_patient_per_month': 200}
        rev = _rev(new_patients=5, num_patients=20)

        costs = calculate_costs_for_month('model_b', _zero_fixed(), var, rev, month=2)

        assert costs['variable_costs']['support'] == 4_000

    def test_support_charged_in_every_month(self):
        """Поддержка начисляется каждый месяц (не только в M1)."""
        var = _zero_variable() | {'support_per_patient_per_month': 150}
        rev = _rev(new_patients=0, num_patients=10)
        fixed = _zero_fixed()

        for month in [1, 2, 3, 6, 12]:
            costs = calculate_costs_for_month('model_b', fixed, var, rev, month=month)
            assert costs['variable_costs']['support'] == 1_500  # 10 × 150


# ─── Fixed Costs ─────────────────────────────────────────────────────────────

class TestFixedCosts:
    """Постоянные затраты не зависят от объёма и одинаковы каждый месяц."""

    def test_fixed_costs_identical_across_all_months(self):
        """Fixed Costs M1 = M2 = M3 — не зависят от месяца."""
        fixed = {
            'team_salaries': 500_000,
            'infrastructure_fixed': 20_000,
            'office_rent': 30_000,
            'legal_services': 10_000,
            'other_fixed': 10_000,
        }
        rev = _rev()
        var = _zero_variable()
        expected = 570_000  # сумма всех статей

        for month in [1, 2, 3, 6, 12]:
            costs = calculate_costs_for_month('model_b', fixed, var, rev, month=month)
            assert costs['fixed_costs']['total'] == expected

    def test_fixed_costs_not_affected_by_patient_volume(self):
        """Рост числа пациентов не меняет fixed costs."""
        fixed = {'team_salaries': 300_000, 'infrastructure_fixed': 0,
                 'office_rent': 0, 'legal_services': 0, 'other_fixed': 0}
        var = _zero_variable()

        for n_patients in [0, 10, 100, 1000]:
            rev = _rev(num_patients=n_patients, new_patients=n_patients)
            costs = calculate_costs_for_month('model_b', fixed, var, rev, month=1)
            assert costs['fixed_costs']['total'] == 300_000

    def test_fixed_costs_total_is_sum_of_components(self):
        """total = sum всех компонентов без custom."""
        fixed = {
            'team_salaries': 100_000,
            'infrastructure_fixed': 10_000,
            'office_rent': 20_000,
            'legal_services': 5_000,
            'other_fixed': 5_000,
        }
        costs = calculate_costs_for_month('model_b', fixed, _zero_variable(), _rev(), month=1)
        fc = costs['fixed_costs']
        component_sum = (
            fc['team_salaries'] + fc['infrastructure_fixed']
            + fc['office_rent'] + fc['legal_services'] + fc['other_fixed']
        )
        # custom = 0, поэтому total == component_sum
        assert fc['total'] == component_sum == 140_000


# ─── Кастомные затраты ────────────────────────────────────────────────────────

class TestCustomCosts:
    """Корректная логика кастомных fixed и variable статей."""

    def test_custom_fixed_onetime_only_in_month1(self):
        """Единоразовая custom fixed статья: M1=50 000, M2=0."""
        custom_fixed = {'Регистрация': {'value': 50_000, 'type': 'Единоразовая (месяц 1)'}}
        rev = _rev()
        var = _zero_variable()
        fixed = _zero_fixed()

        m1 = calculate_costs_for_month('model_b', fixed, var, rev, month=1,
                                        custom_fixed=custom_fixed)
        m2 = calculate_costs_for_month('model_b', fixed, var, rev, month=2,
                                        custom_fixed=custom_fixed)

        assert m1['fixed_costs']['total'] == 50_000
        assert m2['fixed_costs']['total'] == 0

    def test_custom_fixed_monthly_appears_every_month(self):
        """Ежемесячная custom fixed статья начисляется каждый месяц."""
        custom_fixed = {'Маркетинг': {'value': 20_000, 'type': 'Ежемесячная'}}
        rev = _rev()
        var = _zero_variable()
        fixed = _zero_fixed()

        for month in [1, 2, 3, 12]:
            costs = calculate_costs_for_month('model_b', fixed, var, rev, month=month,
                                              custom_fixed=custom_fixed)
            assert costs['fixed_costs']['total'] == 20_000

    def test_custom_variable_per_device_scales_with_production(self):
        """Custom variable 'На устройство (разово)' × num_devices_produced."""
        custom_variable = {'Калибровка': {'value': 1_000, 'type': 'На устройство (разово)'}}
        rev = _rev(num_devices_produced=7)
        var = _zero_variable()
        fixed = _zero_fixed()

        costs = calculate_costs_for_month('model_b', fixed, var, rev, month=1,
                                          custom_variable=custom_variable)
        assert costs['variable_costs']['custom'] == 7_000

    def test_custom_variable_per_patient_month_scales_with_active(self):
        """Custom variable 'На пациента/месяц' × num_patients (активных)."""
        custom_variable = {'Мониторинг': {'value': 50, 'type': 'На пациента/месяц'}}
        rev = _rev(new_patients=5, num_patients=20)
        var = _zero_variable()
        fixed = _zero_fixed()

        costs = calculate_costs_for_month('model_b', fixed, var, rev, month=2,
                                          custom_variable=custom_variable)
        # 20 активных × 50 = 1 000 (не 5 × 50 = 250)
        assert costs['variable_costs']['custom'] == 1_000

    def test_custom_variable_per_patient_onetime_scales_with_new(self):
        """Custom variable 'На пациента (разово)' × new_patients."""
        custom_variable = {'Анкетирование': {'value': 200, 'type': 'На пациента (разово)'}}
        rev = _rev(new_patients=8, num_patients=25)
        var = _zero_variable()
        fixed = _zero_fixed()

        costs = calculate_costs_for_month('model_b', fixed, var, rev, month=2,
                                          custom_variable=custom_variable)
        assert costs['variable_costs']['custom'] == 1_600  # 8 × 200


# ─── CAC ─────────────────────────────────────────────────────────────────────

class TestCAC:
    """Клиентские расходы на привлечение начисляются корректно для каждой модели."""

    def test_cac_model_a_charged_for_initial_clinics_in_month1(self):
        """Model A: 3 начальные клиники × 10 000₽ CAC = 30 000 в M1."""
        var = _zero_variable() | {'cac_clinic': 10_000, 'num_clinics': 3}
        rev = _rev(num_devices_produced=30)
        fixed = _zero_fixed()

        m1 = calculate_costs_for_month('model_a', fixed, var, rev, month=1)

        assert m1['variable_costs']['cac'] == 30_000

    def test_cac_model_a_zero_in_subsequent_months_without_new_clinics(self):
        """Model A: в M2 без новых клиник CAC = 0."""
        var = _zero_variable() | {'cac_clinic': 10_000, 'num_clinics': 3}
        rev = _rev(num_devices_produced=0)
        fixed = _zero_fixed()

        m2 = calculate_costs_for_month('model_a', fixed, var, rev, month=2)

        assert m2['variable_costs']['cac'] == 0

    def test_cac_model_a_charged_for_schedule_clinics_at_their_start_month(self):
        """
        Баг-фикс: при добавлении пачки клиник через clinic_schedule
        CAC должен начисляться в месяц подключения, а не только в M1.

        В M3 добавляется 1 клиника → CAC = 1 × 10 000 = 10 000.
        Передаём new_clinics_this_month=1 в revenue_result (как это делает
        _run_model_a_schedule после фикса).
        """
        var = _zero_variable() | {'cac_clinic': 10_000, 'num_clinics': 2}
        fixed = _zero_fixed()

        # M1: начальные 2 клиники
        rev_m1 = _rev(num_devices_produced=20, new_clinics_this_month=2)
        m1 = calculate_costs_for_month('model_a', fixed, var, rev_m1, month=1)
        assert m1['variable_costs']['cac'] == 20_000  # 2 × 10 000

        # M3: новая пачка 1 клиника через clinic_schedule
        rev_m3 = _rev(num_devices_produced=10, new_clinics_this_month=1)
        m3 = calculate_costs_for_month('model_a', fixed, var, rev_m3, month=3)
        assert m3['variable_costs']['cac'] == 10_000  # 1 × 10 000

    def test_cac_model_b_charged_per_new_patient_every_month(self):
        """Model B: CAC начисляется за каждого нового пациента каждый месяц."""
        var = _zero_variable() | {'cac_patient': 500}
        fixed = _zero_fixed()

        cases = [(1, 10), (2, 15), (3, 22)]
        for month, new_p in cases:
            rev = _rev(new_patients=new_p, num_patients=new_p + 10)
            costs = calculate_costs_for_month('model_b', fixed, var, rev, month=month)
            assert costs['variable_costs']['cac'] == new_p * 500, (
                f"Месяц {month}: ожидали CAC={new_p * 500}, получили {costs['variable_costs']['cac']}"
            )

    def test_cac_model_a_end_to_end_with_clinic_schedule(self):
        """
        Интеграционный тест: clinic_schedule вызывает начисление CAC
        в месяц подключения через _run_model_a_schedule + calculate_costs_for_months.
        """
        from models.revenue import calculate_revenue_for_months
        from models.costs import calculate_costs_for_months

        revenue_results = calculate_revenue_for_months(
            'model_a',
            {
                'num_clinics': 2,
                'devices_per_clinic': 5,
                'setup_fee': 0,
                'subscription_per_device': 0,
                'patients_per_clinic_month1': 5,
                'growth_rate': 0.0,
                'rehab_duration_months': 3,
                'clinic_schedule': [{'month_start': 3, 'count': 1}],
            },
            num_months=4,
            assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
        )

        fixed_params = _zero_fixed()
        variable_params = _zero_variable() | {'cac_clinic': 10_000, 'num_clinics': 2}

        costs_results = calculate_costs_for_months(
            'model_a', fixed_params, variable_params, revenue_results, num_months=4
        )

        # M1: 2 начальные клиники → CAC=20 000
        assert costs_results[0]['variable_costs']['cac'] == 20_000
        # M2: новых клиник нет → CAC=0
        assert costs_results[1]['variable_costs']['cac'] == 0
        # M3: добавляется 1 клиника через schedule → CAC=10 000
        assert costs_results[2]['variable_costs']['cac'] == 10_000
        # M4: новых клиник нет → CAC=0
        assert costs_results[3]['variable_costs']['cac'] == 0


# ─── Total Costs ─────────────────────────────────────────────────────────────

class TestTotalCosts:
    """total_costs = fixed_costs.total + variable_costs.total."""

    def test_total_costs_equals_fixed_plus_variable(self):
        """Контрольная сумма: total_costs = fixed + variable."""
        fixed = {
            'team_salaries': 100_000,
            'infrastructure_fixed': 5_000,
            'office_rent': 10_000,
            'legal_services': 2_000,
            'other_fixed': 3_000,
        }
        var = _zero_variable() | {
            'cogs_per_device': 5_000,
            'logistics_per_patient': 300,
            'support_per_patient_per_month': 100,
        }
        rev = _rev(num_devices_produced=3, new_patients=4, num_patients=10)

        costs = calculate_costs_for_month('model_b', fixed, var, rev, month=2)

        expected_fixed = 120_000  # 100+5+10+2+3 тыс
        expected_cogs = 15_000   # 3 × 5 000
        expected_log = 1_200     # 4 × 300
        expected_sup = 1_000     # 10 × 100
        expected_variable = expected_cogs + expected_log + expected_sup

        assert costs['fixed_costs']['total'] == expected_fixed
        assert costs['variable_costs']['cogs'] == expected_cogs
        assert costs['variable_costs']['logistics'] == expected_log
        assert costs['variable_costs']['support'] == expected_sup
        assert costs['total_costs'] == expected_fixed + expected_variable
