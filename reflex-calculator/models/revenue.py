"""
Модуль расчета выручки (Revenue) для различных бизнес-моделей ReFlex

Model A (B2B) — per-clinic-batch tracking:
  Каждая «пачка» клиник (начальные + добавляемые по clinic_schedule) имеет независимый
  трекинг когорт пациентов и собственный парк устройств. Устройства одной пачки клиник
  не доступны другой. Рост пациентов считается от месяца старта пачки.

Model B / A+B — совокупный поток пациентов без per-clinic ownership.
"""
from typing import Dict, List, Optional


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# ---------------------------------------------------------------------------
# Model A — per-batch helper
# ---------------------------------------------------------------------------

def _calc_one_batch_month(
    batch_count: int,
    relative_month: int,
    devices_per_clinic: int,
    patients_per_clinic_month1: int,
    growth_rate: float,
    rehab_duration_months: int,
    churn_rate: float,
    utilization_rate: float,
    prev_new_patients: Optional[float],
    cohort_history: List[int],
    devices_in_pool_prev: int,
    setup_fee: float,
    subscription_per_device: float,
) -> Dict:
    """
    Рассчитывает показатели одной «пачки» клиник за один месяц.

    relative_month = абсолютный месяц − месяц старта пачки + 1:
      relative_month=1 → первый месяц работы пачки (cohort M1, закупка контрактного парка).

    Мутирует cohort_history: добавляет new_patients текущего месяца.

    prev_new_patients хранится как float для корректного компаундирования роста —
    int-усечение на каждом шаге приводило бы к потере роста при малых числах пациентов.

    Возвращает dict с полями:
      new_patients, new_patients_float, cohort_active_patients, patients_after_churn,
      billable_patients, released_patients, setup_revenue, subscription_revenue,
      total_revenue, devices_in_pool, additional_devices, contractual_pool.
    """
    contractual_pool = int(batch_count * devices_per_clinic)
    duration = max(1, int(rehab_duration_months))

    # --- Новые пациенты этой пачки в данном месяце ---
    if relative_month == 1:
        new_patients_float: float = float(batch_count * patients_per_clinic_month1)
    else:
        base_prev = prev_new_patients if prev_new_patients is not None else 0.0
        new_patients_float = float(base_prev) * (1.0 + growth_rate)
    new_patients = max(0, round(new_patients_float))

    # --- Когортная активность ---
    cohort_history.append(new_patients)
    cohort_active = int(sum(cohort_history[-duration:]))
    released = int(cohort_history[-duration - 1]) if len(cohort_history) > duration else 0

    # --- Churn + utilization ---
    cr = _clamp01(churn_rate)
    ur = _clamp01(utilization_rate) if utilization_rate > 0 else 1.0
    patients_after_churn = max(0, int(round(cohort_active * (1 - cr))))
    demand = patients_after_churn

    # --- Парк устройств: растёт при дефиците, не ниже контрактного минимума ---
    if devices_in_pool_prev <= 0:
        devices_in_pool = int(max(contractual_pool, demand))
    else:
        devices_in_pool = int(max(devices_in_pool_prev, demand, contractual_pool))
    additional_devices = int(devices_in_pool - devices_in_pool_prev)

    # --- Выручка ---
    setup_revenue = float(additional_devices * setup_fee)
    subscription_revenue = float(devices_in_pool * subscription_per_device)
    total_revenue = setup_revenue + subscription_revenue

    on_devices = min(demand, devices_in_pool)
    billable_patients = max(0, int(round(on_devices * ur)))

    return {
        "new_patients": new_patients,
        "new_patients_float": new_patients_float,  # float для корректного growth-трекинга
        "cohort_active_patients": cohort_active,
        "patients_after_churn": patients_after_churn,
        "billable_patients": billable_patients,
        "released_patients": released,
        "setup_revenue": setup_revenue,
        "subscription_revenue": subscription_revenue,
        "total_revenue": total_revenue,
        "devices_in_pool": devices_in_pool,
        "additional_devices": additional_devices,
        "contractual_pool": contractual_pool,
    }


def _run_model_a_schedule(
    num_clinics: int,
    devices_per_clinic: int,
    setup_fee: float,
    subscription_per_device: float,
    patients_per_clinic_month1: int,
    growth_rate: float,
    rehab_duration_months: int,
    churn_rate: float,
    utilization_rate: float,
    clinic_schedule: List[Dict],
    num_months: int,
    manual_new_patients_per_clinic: Optional[List[int]] = None,
) -> List[Dict]:
    """
    Полный цикл по месяцам для Model A с per-batch tracking.

    all_batches = [{month_start: 1, count: num_clinics}, ...clinic_schedule]
    Каждая пачка имеет собственное состояние: cohort_history, devices_pool, prev_new_patients.
    Результаты суммируются по всем активным пачкам; детализация per-batch сохраняется
    в clinic_batches_detail для отображения в UI.
    """
    # Строим полный список пачек (стартовые + расписание)
    all_batches: List[Dict] = [{"month_start": 1, "count": int(num_clinics)}]
    for entry in (clinic_schedule or []):
        ms = int(entry.get("month_start", 2))
        cnt = int(entry.get("count", 1))
        if ms >= 1 and cnt > 0:
            all_batches.append({"month_start": ms, "count": cnt})
    all_batches.sort(key=lambda b: b["month_start"])

    # Состояние каждой пачки: ключ = month_start (уникален по условию)
    # Если несколько пачек с одним month_start — объединяем их count
    merged: Dict[int, int] = {}
    for b in all_batches:
        merged[b["month_start"]] = merged.get(b["month_start"], 0) + b["count"]

    # batch_states: month_start → state dict
    batch_states: Dict[int, Dict] = {}

    # Manual mode overrides auto growth formula when provided and non-empty
    is_manual = (
        manual_new_patients_per_clinic is not None
        and len(manual_new_patients_per_clinic) > 0
    )
    has_patients = is_manual or (patients_per_clinic_month1 and patients_per_clinic_month1 > 0)

    results: List[Dict] = []

    for month in range(1, num_months + 1):
        # Инициализируем пачки, стартующие в этом месяце
        if month in merged:
            batch_states[month] = {
                "count": merged[month],
                "prev_new_patients": None,   # float: для корректного компаундирования
                "cohort_history": [],
                "devices_pool": 0,
            }

        # Если нет пациентов — классическая статическая модель (одна неявная пачка)
        if not has_patients:
            total_pool = sum(
                st["count"] * devices_per_clinic
                for ms, st in batch_states.items()
            )
            if month == 1:
                setup_revenue = float(total_pool * setup_fee)
            else:
                # Новые клиники, подключившиеся в этом месяце
                new_pool_this_month = sum(
                    st["count"] * devices_per_clinic
                    for ms, st in batch_states.items()
                    if ms == month
                )
                setup_revenue = float(new_pool_this_month * setup_fee)
            subscription_revenue = float(total_pool * subscription_per_device)
            total_revenue = setup_revenue + subscription_revenue

            active_clinics_count = sum(st["count"] for st in batch_states.values())
            result = {
                "setup_revenue": setup_revenue,
                "subscription_revenue": subscription_revenue,
                "total_revenue": total_revenue,
                "num_devices": total_pool,
                "devices_in_pool": total_pool,
                "additional_devices": int(setup_revenue / setup_fee) if setup_fee > 0 else 0,
                "num_devices_produced": int(setup_revenue / setup_fee) if setup_fee > 0 else 0,
                "active_clinics": active_clinics_count,
                "new_clinics_this_month": merged.get(month, 0),
                "new_patients": 0,
                "released_patients": 0,
                "cohort_active_patients": 0,
                "patients_after_churn": 0,
                "num_patients": 0,
                "billable_patients": 0,
                "clinic_batches_detail": [],
            }
            results.append(result)
            continue

        # --- Расчёт по активным пачкам с потоком пациентов ---
        totals: Dict = {
            "setup_revenue": 0.0,
            "subscription_revenue": 0.0,
            "total_revenue": 0.0,
            "new_patients": 0,
            "cohort_active_patients": 0,
            "patients_after_churn": 0,
            "billable_patients": 0,
            "released_patients": 0,
            "devices_in_pool": 0,
            "additional_devices": 0,
        }
        batches_detail = []

        for batch_start_month, state in batch_states.items():
            if batch_start_month > month:
                continue  # ещё не подключилась

            relative_month = month - batch_start_month + 1

            # In manual mode use the user-supplied per-clinic intake for this
            # relative month (0-based index). We pass it as patients_per_clinic_month1
            # with relative_month=1 so the branch always computes
            #   new_patients = batch_count * per_clinic_value.
            if is_manual:
                _rel_idx = relative_month - 1
                _per_clinic = (
                    int(manual_new_patients_per_clinic[_rel_idx])
                    if _rel_idx < len(manual_new_patients_per_clinic)
                    else 0
                )
                batch_result = _calc_one_batch_month(
                    batch_count=state["count"],
                    relative_month=1,
                    devices_per_clinic=devices_per_clinic,
                    patients_per_clinic_month1=_per_clinic,
                    growth_rate=0.0,
                    rehab_duration_months=rehab_duration_months,
                    churn_rate=churn_rate,
                    utilization_rate=utilization_rate,
                    prev_new_patients=None,
                    cohort_history=state["cohort_history"],
                    devices_in_pool_prev=state["devices_pool"],
                    setup_fee=setup_fee,
                    subscription_per_device=subscription_per_device,
                )
            else:
                batch_result = _calc_one_batch_month(
                    batch_count=state["count"],
                    relative_month=relative_month,
                    devices_per_clinic=devices_per_clinic,
                    patients_per_clinic_month1=patients_per_clinic_month1,
                    growth_rate=growth_rate,
                    rehab_duration_months=rehab_duration_months,
                    churn_rate=churn_rate,
                    utilization_rate=utilization_rate,
                    prev_new_patients=state["prev_new_patients"],
                    cohort_history=state["cohort_history"],
                    devices_in_pool_prev=state["devices_pool"],
                    setup_fee=setup_fee,
                    subscription_per_device=subscription_per_device,
                )

            # Обновляем состояние пачки (float для роста, int-pool для парка)
            state["prev_new_patients"] = batch_result["new_patients_float"]
            state["devices_pool"] = batch_result["devices_in_pool"]

            # Суммируем
            totals["setup_revenue"] += batch_result["setup_revenue"]
            totals["subscription_revenue"] += batch_result["subscription_revenue"]
            totals["total_revenue"] += batch_result["total_revenue"]
            totals["new_patients"] += batch_result["new_patients"]
            totals["cohort_active_patients"] += batch_result["cohort_active_patients"]
            totals["patients_after_churn"] += batch_result["patients_after_churn"]
            totals["billable_patients"] += batch_result["billable_patients"]
            totals["released_patients"] += batch_result["released_patients"]
            totals["devices_in_pool"] += batch_result["devices_in_pool"]
            totals["additional_devices"] += batch_result["additional_devices"]

            batches_detail.append({
                "batch_start_month": batch_start_month,
                "relative_month": relative_month,
                "count": state["count"],
                "contractual_pool": batch_result["contractual_pool"],
                "devices_in_pool": batch_result["devices_in_pool"],
                "additional_devices": batch_result["additional_devices"],
                "new_patients": batch_result["new_patients"],
                "cohort_active_patients": batch_result["cohort_active_patients"],
                "patients_after_churn": batch_result["patients_after_churn"],
                "billable_patients": batch_result["billable_patients"],
                "setup_revenue": batch_result["setup_revenue"],
                "subscription_revenue": batch_result["subscription_revenue"],
            })

        active_clinics_count = sum(
            st["count"] for ms, st in batch_states.items() if ms <= month
        )

        result = {
            "setup_revenue": totals["setup_revenue"],
            "subscription_revenue": totals["subscription_revenue"],
            "total_revenue": totals["total_revenue"],
            "num_devices": totals["devices_in_pool"],
            "devices_in_pool": totals["devices_in_pool"],
            "additional_devices": totals["additional_devices"],
            "num_devices_produced": totals["additional_devices"],
            "active_clinics": active_clinics_count,
            "new_clinics_this_month": merged.get(month, 0),
            "new_patients": totals["new_patients"],
            "released_patients": totals["released_patients"],
            "cohort_active_patients": totals["cohort_active_patients"],
            "patients_after_churn": totals["patients_after_churn"],
            "num_patients": totals["billable_patients"],
            "billable_patients": totals["billable_patients"],
            "clinic_batches_detail": batches_detail,
        }
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Public per-month functions (backward-compat API)
# ---------------------------------------------------------------------------

def calculate_revenue_model_a(
    num_clinics: int,
    devices_per_clinic: int,
    setup_fee: float,
    subscription_per_device: float,
    month: int,
    patients_per_clinic_month1: int = 0,
    growth_rate: float = 0.0,
    rehab_duration_months: int = 3,
    prev_new_patients: Optional[int] = None,
    cohort_new_patients: Optional[List[int]] = None,
    churn_rate: float = 0.0,
    utilization_rate: float = 1.0,
    devices_in_pool_prev: int = 0,
) -> Dict[str, float]:
    """
    Расчет выручки Model A для одного месяца (без per-batch трекинга).
    Используется тестами и formula_trace. Для полного горизонта с clinic_schedule
    используйте calculate_revenue_for_months().
    """
    base_contract_pool = int(num_clinics * devices_per_clinic)

    if not patients_per_clinic_month1 or patients_per_clinic_month1 <= 0:
        if month == 1:
            setup_revenue = float(base_contract_pool * setup_fee)
        else:
            setup_revenue = 0.0
        subscription_revenue = float(base_contract_pool * subscription_per_device)
        total_revenue = setup_revenue + subscription_revenue
        return {
            "setup_revenue": setup_revenue,
            "subscription_revenue": subscription_revenue,
            "total_revenue": total_revenue,
            "num_devices": base_contract_pool,
            "devices_in_pool": base_contract_pool,
            "additional_devices": base_contract_pool if month == 1 else 0,
            "num_devices_produced": base_contract_pool if month == 1 else 0,
            "active_clinics": num_clinics,
            "new_patients": 0,
            "released_patients": 0,
            "cohort_active_patients": 0,
            "patients_after_churn": 0,
            "num_patients": 0,
            "billable_patients": 0,
            "clinic_batches_detail": [],
        }

    history = list(cohort_new_patients or [])
    batch_result = _calc_one_batch_month(
        batch_count=num_clinics,
        relative_month=month,
        devices_per_clinic=devices_per_clinic,
        patients_per_clinic_month1=patients_per_clinic_month1,
        growth_rate=growth_rate,
        rehab_duration_months=rehab_duration_months,
        churn_rate=churn_rate,
        utilization_rate=utilization_rate,
        prev_new_patients=prev_new_patients,
        cohort_history=history,
        devices_in_pool_prev=devices_in_pool_prev,
        setup_fee=setup_fee,
        subscription_per_device=subscription_per_device,
    )

    return {
        "setup_revenue": batch_result["setup_revenue"],
        "subscription_revenue": batch_result["subscription_revenue"],
        "total_revenue": batch_result["total_revenue"],
        "num_devices": batch_result["devices_in_pool"],
        "devices_in_pool": batch_result["devices_in_pool"],
        "additional_devices": batch_result["additional_devices"],
        "num_devices_produced": batch_result["additional_devices"],
        "active_clinics": num_clinics,
        "new_patients": batch_result["new_patients"],
        "released_patients": batch_result["released_patients"],
        "cohort_active_patients": batch_result["cohort_active_patients"],
        "patients_after_churn": batch_result["patients_after_churn"],
        "num_patients": batch_result["billable_patients"],
        "billable_patients": batch_result["billable_patients"],
        "clinic_batches_detail": [],
    }


def calculate_revenue_model_b(
    num_clinics: int,
    patients_per_clinic_month1: int,
    growth_rate: float,
    rental_price: float,
    clinic_commission_rate: float,
    month: int,
    prev_patients: int = None,
    rehab_duration_months: int = 3,
    prev_new_patients: float = None,
    cohort_new_patients: List[int] = None,
    devices_in_pool_prev: int = 0,
    churn_rate: float = 0.0,
    utilization_rate: float = 1.0,
) -> Dict[str, float]:
    """
    Расчет выручки для Model B (B2B2C).

    Совокупный поток пациентов по всем клиникам. Парк устройств растёт при дефиците.

    prev_new_patients хранится как float для корректного компаундирования роста.
    """
    duration = max(1, int(rehab_duration_months))
    history = list(cohort_new_patients or [])

    if month == 1:
        new_patients_float: float = float(num_clinics * patients_per_clinic_month1)
    else:
        base_prev_new = (
            prev_new_patients if prev_new_patients is not None else (
                float(prev_patients) if prev_patients is not None
                else float(num_clinics * patients_per_clinic_month1)
            )
        )
        new_patients_float = float(base_prev_new) * (1.0 + growth_rate)
    new_patients = max(0, round(new_patients_float))

    history.append(new_patients)
    active_new_slice = history[-duration:]
    cohort_active_patients = int(sum(active_new_slice))
    released_patients = history[-duration - 1] if len(history) > duration else 0

    cr = _clamp01(churn_rate)
    ur = _clamp01(utilization_rate) if utilization_rate > 0 else 1.0

    patients_after_churn = int(round(cohort_active_patients * (1 - cr)))
    patients_after_churn = max(0, patients_after_churn)

    demand_devices = patients_after_churn
    additional_devices = max(0, demand_devices - devices_in_pool_prev)
    devices_in_pool = devices_in_pool_prev + additional_devices

    on_devices = min(demand_devices, devices_in_pool)
    billable_patients = max(0, int(round(on_devices * ur)))

    gross_revenue = billable_patients * rental_price
    clinic_commission = gross_revenue * clinic_commission_rate
    net_revenue = gross_revenue - clinic_commission
    total_revenue = net_revenue

    return {
        "new_patients": new_patients,
        "new_patients_float": new_patients_float,  # float для корректного growth-трекинга
        "released_patients": released_patients,
        "cohort_active_patients": cohort_active_patients,
        "patients_after_churn": patients_after_churn,
        "num_patients": billable_patients,
        "billable_patients": billable_patients,
        "gross_revenue": gross_revenue,
        "clinic_commission": clinic_commission,
        "net_revenue": net_revenue,
        "total_revenue": total_revenue,
        "devices_in_pool": devices_in_pool,
        "additional_devices": additional_devices,
        "num_devices": devices_in_pool,
        "num_devices_produced": additional_devices,
    }


def calculate_revenue_model_ab(
    num_clinics: int,
    devices_per_clinic: int,
    setup_fee: float,
    subscription_per_device: float,
    patients_per_clinic_month1: int,
    growth_rate: float,
    rental_price: float,
    clinic_commission_rate: float,
    month: int,
    prev_patients: int = None,
    rehab_duration_months: int = 3,
    prev_new_patients: float = None,
    cohort_new_patients: List[int] = None,
    devices_in_pool_prev: int = None,
    churn_rate: float = 0.0,
    utilization_rate: float = 1.0,
) -> Dict[str, float]:
    """
    Расчет выручки для Model A+B (Гибрид).
    Клиника покупает парк устройств + ReFlex получает подписку +
    клиника сдает в аренду пациентам.
    """
    base_initial_devices = num_clinics * devices_per_clinic
    if devices_in_pool_prev is None:
        devices_in_pool_prev = base_initial_devices

    model_b = calculate_revenue_model_b(
        num_clinics, patients_per_clinic_month1, growth_rate,
        rental_price, clinic_commission_rate, month, prev_patients,
        rehab_duration_months=rehab_duration_months,
        prev_new_patients=prev_new_patients,
        cohort_new_patients=cohort_new_patients,
        devices_in_pool_prev=devices_in_pool_prev,
        churn_rate=churn_rate,
        utilization_rate=utilization_rate,
    )

    additional_devices = model_b["additional_devices"]

    setup_revenue_base = base_initial_devices * setup_fee if month == 1 else 0
    setup_revenue_additional = additional_devices * setup_fee
    setup_revenue = setup_revenue_base + setup_revenue_additional

    subscription_devices = model_b["devices_in_pool"]
    subscription_revenue = subscription_devices * subscription_per_device

    total_revenue = setup_revenue + subscription_revenue + model_b["net_revenue"]

    return {
        "setup_revenue": setup_revenue,
        "setup_revenue_base": setup_revenue_base,
        "setup_revenue_additional": setup_revenue_additional,
        "subscription_revenue": subscription_revenue,
        "rental_net_revenue": model_b["net_revenue"],
        "rental_gross_revenue": model_b["gross_revenue"],
        "clinic_commission": model_b["clinic_commission"],
        "total_revenue": total_revenue,
        "num_devices": subscription_devices,
        "num_patients": model_b["num_patients"],
        "new_patients": model_b["new_patients"],
        "new_patients_float": model_b.get("new_patients_float", float(model_b["new_patients"])),
        "released_patients": model_b["released_patients"],
        "cohort_active_patients": model_b.get("cohort_active_patients", 0),
        "patients_after_churn": model_b.get("patients_after_churn", 0),
        "devices_in_pool": model_b["devices_in_pool"],
        "additional_devices": additional_devices,
        "num_devices_produced": base_initial_devices + additional_devices if month == 1 else additional_devices,
    }


def calculate_revenue_for_months(
    model_type: str,
    params: Dict,
    num_months: int = 3,
    assumptions: Optional[Dict] = None,
    manual_new_patients_per_clinic: Optional[List[int]] = None,
    manual_active_patients_per_clinic: Optional[List[int]] = None,
) -> List[Dict[str, float]]:
    """
    Расчет выручки для всех месяцев.

    Model A использует _run_model_a_schedule() с per-batch трекингом:
      - params["num_clinics"] — начальные клиники (старт в месяц 1)
      - params["clinic_schedule"] — список дополнительных пачек:
          [{"month_start": 3, "count": 1}, {"month_start": 5, "count": 2}, ...]
      Каждая пачка: свои когорты, свой парк устройств.

    Args:
        model_type: 'model_a', 'model_b', или 'model_ab'
        params: Словарь с параметрами revenue
        num_months: Количество месяцев для расчета
        assumptions: Словарь с churn_rate, utilization_rate
        manual_new_patients_per_clinic: 1D список новых пациентов на клинику (legacy, Model A)
        manual_active_patients_per_clinic: 1D список СУММАРНЫХ активных пациентов на клинику
            по месяцам (из 2D матрицы когорт). Когда задан, напрямую переопределяет
            billable_patients для Model B и Model AB.

    Returns:
        Список словарей с выручкой по месяцам
    """
    a = assumptions or {}
    churn_rate = _clamp01(float(a.get("churn_rate", 0.0)))
    utilization_rate = float(a.get("utilization_rate", 1.0))
    if utilization_rate <= 0:
        utilization_rate = 1.0
    utilization_rate = _clamp01(utilization_rate)

    if model_type == "model_a":
        raw = _run_model_a_schedule(
            num_clinics=int(params["num_clinics"]),
            devices_per_clinic=int(params["devices_per_clinic"]),
            setup_fee=float(params["setup_fee"]),
            subscription_per_device=float(params["subscription_per_device"]),
            patients_per_clinic_month1=int(params.get("patients_per_clinic_month1", 0) or 0),
            growth_rate=float(params.get("growth_rate", 0.0)),
            rehab_duration_months=int(
                params.get("rehab_duration_months", params.get("avg_rental_duration", 3))
            ),
            churn_rate=churn_rate,
            utilization_rate=utilization_rate,
            clinic_schedule=list(params.get("clinic_schedule", []) or []),
            num_months=num_months,
            manual_new_patients_per_clinic=manual_new_patients_per_clinic,
        )
        for i, r in enumerate(raw):
            r["month"] = i + 1
        return raw

    results = []
    prev_patients = None
    prev_new_patients: Optional[float] = None  # float для корректного компаундирования
    cohort_new_patients: List[int] = []
    devices_in_pool_prev = 0

    is_manual_bc = (
        manual_new_patients_per_clinic is not None
        and len(manual_new_patients_per_clinic) > 0
    )
    # manual_active_patients_per_clinic (из 2D матрицы): прямой override billable_patients
    is_manual_active = (
        manual_active_patients_per_clinic is not None
        and len(manual_active_patients_per_clinic) > 0
    )

    for month in range(1, num_months + 1):
        # In manual mode compute total new patients directly from the manual table
        # (manual values are per-clinic; multiply by num_clinics for Model B/AB).
        if is_manual_bc:
            _man_idx = month - 1
            _per_clinic = (
                int(manual_new_patients_per_clinic[_man_idx])
                if _man_idx < len(manual_new_patients_per_clinic)
                else 0
            )
            # Override p_m1 each month; use month=1 branch → new = num_clinics * p_m1
            _eff_p_m1_bc = _per_clinic
            _eff_growth_bc = 0.0
            _eff_prev_bc: Optional[float] = None
            _eff_month_bc = 1  # force M1 branch every iteration
        else:
            _eff_p_m1_bc = params.get("patients_per_clinic_month1", 1)
            _eff_growth_bc = params.get("growth_rate", 0.0)
            _eff_prev_bc = prev_new_patients
            _eff_month_bc = month

        if model_type == "model_b":
            result = calculate_revenue_model_b(
                num_clinics=params["num_clinics"],
                patients_per_clinic_month1=_eff_p_m1_bc,
                growth_rate=_eff_growth_bc,
                rental_price=params["rental_price"],
                clinic_commission_rate=params["clinic_commission_rate"],
                month=_eff_month_bc,
                prev_patients=prev_patients if not is_manual_bc else None,
                rehab_duration_months=params.get("rehab_duration_months", params.get("avg_rental_duration", 3)),
                prev_new_patients=_eff_prev_bc,
                cohort_new_patients=cohort_new_patients,
                devices_in_pool_prev=devices_in_pool_prev,
                churn_rate=churn_rate,
                utilization_rate=utilization_rate,
            )
            # Override с матрицей: суммарные активные пациенты задаются напрямую
            if is_manual_active:
                _active_per_clinic = (
                    int(manual_active_patients_per_clinic[month - 1])
                    if month - 1 < len(manual_active_patients_per_clinic)
                    else 0
                )
                _n_clinics = int(params["num_clinics"])
                _total_active = _active_per_clinic * _n_clinics
                _rental = float(params["rental_price"])
                _comm = float(params.get("clinic_commission_rate", 0.0))
                result["num_patients"] = _total_active
                result["billable_patients"] = _total_active
                result["cohort_active_patients"] = _total_active
                result["total_revenue"] = _total_active * _rental * (1.0 - _comm)
            prev_patients = result["num_patients"]
            prev_new_patients = result.get("new_patients_float", float(result.get("new_patients", 0)))
            cohort_new_patients.append(result.get("new_patients", 0))
            devices_in_pool_prev = result.get("devices_in_pool", devices_in_pool_prev)

        elif model_type == "model_ab":
            if month == 1 and devices_in_pool_prev == 0:
                devices_in_pool_prev = params["num_clinics"] * params["devices_per_clinic"]
            result = calculate_revenue_model_ab(
                num_clinics=params["num_clinics"],
                devices_per_clinic=params["devices_per_clinic"],
                setup_fee=params["setup_fee"],
                subscription_per_device=params["subscription_per_device"],
                patients_per_clinic_month1=_eff_p_m1_bc,
                growth_rate=_eff_growth_bc,
                rental_price=params["rental_price"],
                clinic_commission_rate=params["clinic_commission_rate"],
                month=_eff_month_bc,
                prev_patients=prev_patients if not is_manual_bc else None,
                rehab_duration_months=params.get("rehab_duration_months", params.get("avg_rental_duration", 3)),
                prev_new_patients=_eff_prev_bc,
                cohort_new_patients=cohort_new_patients,
                devices_in_pool_prev=devices_in_pool_prev,
                churn_rate=churn_rate,
                utilization_rate=utilization_rate,
            )
            # Override с матрицей: суммарные активные пациенты задаются напрямую
            if is_manual_active:
                _active_per_clinic = (
                    int(manual_active_patients_per_clinic[month - 1])
                    if month - 1 < len(manual_active_patients_per_clinic)
                    else 0
                )
                _n_clinics = int(params["num_clinics"])
                _total_active = _active_per_clinic * _n_clinics
                _rental = float(params["rental_price"])
                _comm = float(params.get("clinic_commission_rate", 0.0))
                _rental_rev = _total_active * _rental * (1.0 - _comm)
                result["num_patients"] = _total_active
                result["billable_patients"] = _total_active
                result["cohort_active_patients"] = _total_active
                result["rental_revenue"] = _rental_rev
                result["total_revenue"] = result.get("setup_revenue", 0.0) + result.get("subscription_revenue", 0.0) + _rental_rev
            prev_patients = result.get("num_patients")
            prev_new_patients = result.get("new_patients_float", float(result.get("new_patients", 0)))
            cohort_new_patients.append(result.get("new_patients", 0))
            devices_in_pool_prev = result.get("devices_in_pool", devices_in_pool_prev)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

        result["month"] = month
        results.append(result)

    return results
