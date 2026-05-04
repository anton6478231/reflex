"""
Юнит-тесты для модуля revenue
"""
import pytest
from models.revenue import (
    calculate_revenue_model_a,
    calculate_revenue_model_b,
    calculate_revenue_model_ab,
    calculate_revenue_for_months
)


def test_model_a_month1():
    """Тест Model A: месяц 1 должен включать setup fee"""
    result = calculate_revenue_model_a(
        num_clinics=2,
        devices_per_clinic=10,
        setup_fee=50000,
        subscription_per_device=2000,
        month=1
    )
    
    # Setup fee = 2 × 10 × 50000 = 1,000,000
    # Subscription = 2 × 10 × 2000 = 40,000
    # Total = 1,040,000
    
    assert result['setup_revenue'] == 1_000_000
    assert result['subscription_revenue'] == 40_000
    assert result['total_revenue'] == 1_040_000


def test_model_a_month2():
    """Тест Model A: месяц 2 не должен включать setup fee"""
    result = calculate_revenue_model_a(
        num_clinics=2,
        devices_per_clinic=10,
        setup_fee=50000,
        subscription_per_device=2000,
        month=2
    )
    
    # Setup fee = 0 (только месяц 1)
    # Subscription = 2 × 10 × 2000 = 40,000
    
    assert result['setup_revenue'] == 0
    assert result['subscription_revenue'] == 40_000
    assert result['total_revenue'] == 40_000


def test_model_b_month1():
    """Тест Model B: месяц 1"""
    result = calculate_revenue_model_b(
        num_clinics=2,
        patients_per_clinic_month1=5,
        growth_rate=0.5,
        rental_price=6000,
        clinic_commission_rate=0.15,
        month=1
    )
    
    # Patients = 2 × 5 = 10
    # Gross revenue = 10 × 6000 = 60,000
    # Clinic commission = 60,000 × 0.15 = 9,000
    # Net revenue = 60,000 - 9,000 = 51,000
    
    assert result['num_patients'] == 10
    assert result['gross_revenue'] == 60_000
    assert result['clinic_commission'] == 9_000
    assert result['net_revenue'] == 51_000
    assert result['total_revenue'] == 51_000


def test_model_b_growth():
    """Тест Model B: рост новых пациентов + занятость парка по сроку реабилитации"""
    results = calculate_revenue_for_months(
        model_type='model_b',
        params={
            'num_clinics': 2,
            'patients_per_clinic_month1': 5,
            'growth_rate': 0.5,
            'rental_price': 6000,
            'clinic_commission_rate': 0.15,
            'rehab_duration_months': 3,
        },
        num_months=3,
        assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
    )
    
    # New patients:
    # M1 = 10, M2 = 15, M3 = 22
    # Active patients (занято в парке, duration=3):
    # M1 = 10, M2 = 10+15=25, M3 = 10+15+22=47
    assert results[0]['new_patients'] == 10
    assert results[1]['new_patients'] == 15
    assert results[2]['new_patients'] == 22
    assert results[0]['num_patients'] == 10
    assert results[1]['num_patients'] == 25
    assert results[2]['num_patients'] == 47


def test_model_b_churn_reduces_billable():
    """Churn снижает эффективных пациентов относительно когорты."""
    base = calculate_revenue_for_months(
        'model_b',
        {
            'num_clinics': 2,
            'patients_per_clinic_month1': 5,
            'growth_rate': 0.5,
            'rental_price': 6000,
            'clinic_commission_rate': 0.15,
            'rehab_duration_months': 3,
        },
        3,
        assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
    )
    churned = calculate_revenue_for_months(
        'model_b',
        {
            'num_clinics': 2,
            'patients_per_clinic_month1': 5,
            'growth_rate': 0.5,
            'rental_price': 6000,
            'clinic_commission_rate': 0.15,
            'rehab_duration_months': 3,
        },
        3,
        assumptions={'churn_rate': 0.2, 'utilization_rate': 1.0},
    )
    assert churned[2]['cohort_active_patients'] == base[2]['cohort_active_patients']
    assert churned[2]['num_patients'] < base[2]['num_patients']


def test_model_a_patient_flow_supports_costs_engine():
    """Model A: при заданном потоке пациентов num_patients > 0 для переменных затрат."""
    r = calculate_revenue_for_months(
        'model_a',
        {
            'num_clinics': 2,
            'devices_per_clinic': 10,
            'setup_fee': 50000,
            'subscription_per_device': 2000,
            'patients_per_clinic_month1': 5,
            'growth_rate': 0.5,
            'rehab_duration_months': 3,
        },
        2,
        assumptions={'churn_rate': 0.0, 'utilization_rate': 1.0},
    )
    assert r[0]['new_patients'] == 10
    assert r[0]['num_patients'] == 10
    assert r[0]['devices_in_pool'] == 20
    # Когорта 10+15=25 → докупка парка до 25, все пациенты обслужены
    assert r[1]['cohort_active_patients'] == 25
    assert r[1]['num_patients'] == 25
    assert r[1]['devices_in_pool'] == 25
    assert r[1]['additional_devices'] == 5
    assert r[1]['num_devices_produced'] == 5


def test_model_a_clinic_schedule_independent_pools():
    """
    Per-batch: парки двух пачек клиник независимы — не смешиваются.

    Пачка 1: старт M1, 2 клиники, 5 пациентов/клинику, growth=0, duration=3.
    Пачка 2: старт M2, 1 клиника,  5 пациентов/клинику, growth=0, duration=3.

    devices_per_clinic=10 (контрактный мин.), no churn, ut=1.

    Проверяем в M2:
    - active_clinics == 3  (2 + 1)
    - Парк пачки 1: min(contract=20, demand=10) = 20 — не меняется (demand=new_patients=10)
    - Парк пачки 2: min(contract=10, demand=5)  = 10 (новая пачка)
    - Суммарный devices_in_pool == 30
    - Суммарный new_patients == 10 + 5 = 15
    """
    r = calculate_revenue_for_months(
        "model_a",
        {
            "num_clinics": 2,
            "devices_per_clinic": 10,
            "setup_fee": 10000,
            "subscription_per_device": 1000,
            "patients_per_clinic_month1": 5,
            "growth_rate": 0.0,
            "rehab_duration_months": 3,
            "clinic_schedule": [{"month_start": 2, "count": 1}],
        },
        3,
        assumptions={"churn_rate": 0.0, "utilization_rate": 1.0},
    )
    # M1: только пачка 1
    assert r[0]["active_clinics"] == 2
    assert r[0]["devices_in_pool"] == 20  # контрактный минимум пачки 1 (demand=10 < 20)
    assert r[0]["new_patients"] == 10     # 2*5

    # M2: пачки 1 и 2 активны
    assert r[1]["active_clinics"] == 3
    # Пачка 1: pool уже 20, demand=10 -> pool=20; пачка 2: contract=10, demand=5 -> pool=10
    assert r[1]["devices_in_pool"] == 30
    assert r[1]["new_patients"] == 15  # 10 (пачка1) + 5 (пачка2)

    # Детализация по пачкам в M2
    batches = r[1]["clinic_batches_detail"]
    assert len(batches) == 2
    pools = sorted([b["devices_in_pool"] for b in batches])
    assert pools == [10, 20]

    # M3: обе пачки, пачка 1 relative=3, пачка 2 relative=2
    assert r[2]["active_clinics"] == 3
    # Пачка 1: cohort = 10+10+10=30 (duration=3, growth=0) → pool расширяется с 20 до 30
    # Пачка 2: cohort = 5+5=10 (relative M2) → pool=10 не меняется
    assert r[2]["devices_in_pool"] == 40


def test_model_a_clinic_schedule_growth_from_start_month():
    """
    Per-batch: рост пациентов в пачке идёт от ЕЁ месяца старта, а не от M1.

    Пачка 1: старт M1, 1 клиника, 10 пациентов, growth=100% (×2 каждый месяц).
    Пачка 2: старт M3, 1 клиника, 10 пациентов, growth=100%.

    devices_per_clinic=100 (очень большой контракт), duration=1, churn=0, ut=1.

    Ожидаем:
      M1: пачка1.new=10
      M2: пачка1.new=20 (рост от M1)
      M3: пачка1.new=40, пачка2.new=10 (пачка2 — первый месяц)
      M4: пачка1.new=80, пачка2.new=20 (пачка2 — второй месяц)
    """
    r = calculate_revenue_for_months(
        "model_a",
        {
            "num_clinics": 1,
            "devices_per_clinic": 100,
            "setup_fee": 0,
            "subscription_per_device": 0,
            "patients_per_clinic_month1": 10,
            "growth_rate": 1.0,
            "rehab_duration_months": 1,
            "clinic_schedule": [{"month_start": 3, "count": 1}],
        },
        4,
        assumptions={"churn_rate": 0.0, "utilization_rate": 1.0},
    )

    def _batch_new(month_idx: int, batch_start: int) -> int:
        batches = r[month_idx]["clinic_batches_detail"]
        for b in batches:
            if b["batch_start_month"] == batch_start:
                return b["new_patients"]
        raise AssertionError(f"Batch start={batch_start} not found in month_idx={month_idx}")

    assert r[0]["new_patients"] == 10   # M1: только пачка1
    assert r[1]["new_patients"] == 20   # M2: пачка1 рост
    # M3: пачка1=40, пачка2=10
    assert _batch_new(2, batch_start=1) == 40
    assert _batch_new(2, batch_start=3) == 10
    assert r[2]["new_patients"] == 50
    # M4: пачка1=80, пачка2=20
    assert _batch_new(3, batch_start=1) == 80
    assert _batch_new(3, batch_start=3) == 20
    assert r[3]["new_patients"] == 100


def test_model_ab():
    """Тест Model A+B (гибрид)"""
    result = calculate_revenue_model_ab(
        num_clinics=2,
        devices_per_clinic=10,
        setup_fee=50000,
        subscription_per_device=2000,
        patients_per_clinic_month1=5,
        growth_rate=0.5,
        rental_price=6000,
        clinic_commission_rate=0.15,
        month=1
    )
    
    # Model A часть:
    # Setup = 1,000,000
    # Subscription = 40,000
    # Total A = 1,040,000
    
    # Model B часть:
    # Net revenue = 51,000
    
    # Total = 1,040,000 + 51,000 = 1,091,000
    
    assert result['setup_revenue'] == 1_000_000
    assert result['subscription_revenue'] == 40_000
    assert result['rental_net_revenue'] == 51_000
    assert result['total_revenue'] == 1_091_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
