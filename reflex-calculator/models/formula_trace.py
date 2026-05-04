"""
Пошаговый аудит формул: те же вычисления, что в revenue/costs/cash_flow,
в виде выражений на Python и чисел — для сверки с результатами калькулятора.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

Row = Tuple[str, str, float, str]  # title, python_snippet, value, check_vs_actual


def trace_revenue_month(
    model_type: str,
    params: Dict[str, Any],
    month: int,
    prev_patients: Optional[int],
    actual: Dict[str, Any],
    assumptions: Optional[Dict[str, Any]] = None,
) -> List[Row]:
    """Сверка через то же ядро, что и основной расчёт (`calculate_revenue_for_months`)."""
    from models.revenue import calculate_revenue_for_months

    res = calculate_revenue_for_months(model_type, params, month, assumptions=assumptions)
    calc = res[-1]

    if model_type == "model_a":
        keys = [
            ("active_clinics (всего активных)", "active_clinics"),
            ("devices_in_pool (общий парк)", "devices_in_pool"),
            ("additional_devices (новых устройств)", "additional_devices"),
            ("setup_revenue", "setup_revenue"),
            ("subscription_revenue", "subscription_revenue"),
            ("total_revenue", "total_revenue"),
            ("new_patients (все пачки)", "new_patients"),
            ("cohort_active_patients", "cohort_active_patients"),
            ("patients_after_churn", "patients_after_churn"),
            ("num_patients (эффективные для затрат)", "num_patients"),
        ]
    elif model_type == "model_b":
        keys = [
            ("new_patients", "new_patients"),
            ("cohort_active_patients", "cohort_active_patients"),
            ("patients_after_churn", "patients_after_churn"),
            ("num_patients (эффективные для выручки)", "num_patients"),
            ("gross_revenue", "gross_revenue"),
            ("clinic_commission", "clinic_commission"),
            ("net_revenue", "net_revenue"),
            ("total_revenue", "total_revenue"),
            ("devices_in_pool", "devices_in_pool"),
        ]
    elif model_type == "model_ab":
        keys = [
            ("setup_revenue", "setup_revenue"),
            ("subscription_revenue", "subscription_revenue"),
            ("new_patients", "new_patients"),
            ("cohort_active_patients", "cohort_active_patients"),
            ("patients_after_churn", "patients_after_churn"),
            ("num_patients (аренда, эффективные)", "num_patients"),
            ("additional_devices", "additional_devices"),
            ("devices_in_pool", "devices_in_pool"),
            ("rental_net_revenue", "rental_net_revenue"),
            ("total_revenue", "total_revenue"),
        ]
    else:
        keys = []

    rows: List[Row] = []
    for title, key in keys:
        if key not in calc:
            continue
        val = float(calc[key])
        snippet = (
            f"from models.revenue import calculate_revenue_for_months\n"
            f"calc = calculate_revenue_for_months({model_type!r}, params, {month}, assumptions={assumptions!r})[-1]\n"
            f"{key} = calc[{key!r}]"
        )
        rows.append((title, snippet, val, key))

    # Сверка с фактическим словарём
    out: List[Row] = []
    for title, snippet, val, key in rows:
        if key and key in actual:
            av = float(actual[key])
            ok = abs(av - val) < 0.01
            note = f"OK actual[{key}]={av}" if ok else f"РАСХОЖДЕНИЕ actual[{key}]={av} vs trace={val}"
        else:
            note = "(нет ключа в actual)" if not key else ""
        out.append((title, snippet, val, note))
    return out


def trace_cash_flow_month(
    revenue_total: float,
    fixed_total: float,
    variable_total: float,
    actual_cf: Dict[str, Any],
) -> List[Row]:
    tc = fixed_total + variable_total
    cf = revenue_total - tc
    rows = [
        ("total_costs", f"total_costs = fixed_total + variable_total", float(tc), "total_costs"),
        ("cash_flow", f"cash_flow = revenue - total_costs  # {revenue_total} - {tc}", float(cf), "cash_flow"),
    ]
    out: List[Row] = []
    for title, snippet, val, key in rows:
        av = float(actual_cf.get(key, 0))
        ok = abs(av - val) < 0.01
        note = f"OK actual[{key}]={av}" if ok else f"РАСХОЖДЕНИЕ actual[{key}]={av}"
        out.append((title, snippet, val, note))
    return out


def build_executable_snippet(
    model_type: str,
    revenue_params: Dict[str, Any],
    month: int,
    prev_patients: Optional[int],
) -> str:
    """Один блок кода, который можно скопировать в REPL после присвоения params (опционально)."""
    if model_type == "model_b":
        nc = int(revenue_params["num_clinics"])
        p1 = int(revenue_params["patients_per_clinic_month1"])
        g = float(revenue_params["growth_rate"])
        rp = float(revenue_params["rental_price"])
        cc = float(revenue_params["clinic_commission_rate"])
        duration = int(revenue_params.get("rehab_duration_months", revenue_params.get("avg_rental_duration", 3)))
        body = (
            "new_counts=[]\n"
            f"duration={duration}\n"
            "prev_new=None\n"
            f"for _m in range(1, {month}+1):\n"
            f"    new_n = ({nc}*{p1}) if _m==1 else int(prev_new*(1+{g}))\n"
            "    new_counts.append(new_n)\n"
            "    prev_new=new_n\n"
            "num_patients = sum(new_counts[-duration:])\n"
        )
        return (
            f"# Месяц {month}, Model B\n"
            f"{body}"
            f"gross_revenue = num_patients * {rp}\n"
            f"clinic_commission = gross_revenue * {cc}\n"
            f"net_revenue = gross_revenue - clinic_commission\n"
            f"total_revenue = net_revenue\n"
        )
    if model_type == "model_a":
        nc = int(revenue_params["num_clinics"])
        dpc = int(revenue_params["devices_per_clinic"])
        sf = float(revenue_params["setup_fee"])
        sub = float(revenue_params["subscription_per_device"])
        p1 = int(revenue_params.get("patients_per_clinic_month1", 0) or 0)
        gr = float(revenue_params.get("growth_rate", 0.0))
        duration = int(revenue_params.get("rehab_duration_months", revenue_params.get("avg_rental_duration", 3)))
        schedule = list(revenue_params.get("clinic_schedule", []) or [])
        if p1 > 0:
            return (
                f"# Месяц {month}, Model A (per-batch, patients_per_clinic={p1})\n"
                f"# num_clinics={nc}, devices_per_clinic={dpc}, setup_fee={sf}, sub/dev={sub}\n"
                f"# growth_rate={gr}, rehab_duration={duration}\n"
                f"# clinic_schedule={schedule}\n"
                f"from models.revenue import calculate_revenue_for_months\n"
                f"params = {revenue_params!r}\n"
                f"results = calculate_revenue_for_months('model_a', params, {month})\n"
                f"# Результат месяца {month}:\n"
                f"r = results[-1]\n"
                f"active_clinics = r['active_clinics']\n"
                f"devices_in_pool = r['devices_in_pool']\n"
                f"setup_revenue = r['setup_revenue']\n"
                f"subscription_revenue = r['subscription_revenue']\n"
                f"total_revenue = r['total_revenue']\n"
                f"num_patients = r['num_patients']  # после churn и загрузки\n"
            )
        return (
            f"# Месяц {month}, Model A (статический парк)\n"
            f"setup_revenue = ({nc} * {dpc} * {sf}) if {month} == 1 else 0\n"
            f"subscription_revenue = {nc} * {dpc} * {sub}\n"
            f"total_revenue = setup_revenue + subscription_revenue\n"
        )
    if model_type == "model_ab":
        nc = int(revenue_params["num_clinics"])
        dpc = int(revenue_params["devices_per_clinic"])
        sf = float(revenue_params["setup_fee"])
        sub = float(revenue_params["subscription_per_device"])
        p1 = int(revenue_params["patients_per_clinic_month1"])
        g = float(revenue_params["growth_rate"])
        rp = float(revenue_params["rental_price"])
        cc = float(revenue_params["clinic_commission_rate"])
        duration = int(revenue_params.get("rehab_duration_months", revenue_params.get("avg_rental_duration", 3)))
        pblock = (
            "new_counts=[]\n"
            f"duration={duration}\n"
            "prev_new=None\n"
            f"for _m in range(1, {month}+1):\n"
            f"    new_n = ({nc}*{p1}) if _m==1 else int(prev_new*(1+{g}))\n"
            "    new_counts.append(new_n)\n"
            "    prev_new=new_n\n"
            "num_patients = sum(new_counts[-duration:])\n"
        )
        return (
            f"# Месяц {month}, Model A+B\n"
            f"{pblock}"
            f"base_devices = {nc} * {dpc}\n"
            f"pool = base_devices\n"
            "for _active in [sum(new_counts[max(0, i-duration+1):i+1]) for i in range(len(new_counts))]:\n"
            "    prev_pool = pool\n"
            "    additional_devices = max(0, _active - prev_pool)\n"
            "    pool = prev_pool + additional_devices\n"
            f"devices_in_pool = pool\n"
            f"setup_base = (base_devices * {sf}) if {month} == 1 else 0\n"
            f"setup_additional = additional_devices * {sf}\n"
            f"setup_revenue = setup_base + setup_additional\n"
            f"subscription_revenue = devices_in_pool * {sub}\n"
            f"gross_B = num_patients * {rp}\n"
            f"clinic_commission = gross_B * {cc}\n"
            f"rental_net_revenue = gross_B - clinic_commission\n"
            f"total_revenue = setup_revenue + subscription_revenue + rental_net_revenue\n"
        )
    return f"# Нет фрагмента для model_type={model_type!r}\n"
