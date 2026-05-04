"""
Модуль расчета денежного потока (Cash Flow) и точки безубыточности (Breakeven)
"""
from typing import Dict, List


def calculate_cash_flow(
    revenue: float,
    fixed_costs: float,
    variable_costs: float
) -> Dict[str, float]:
    """
    Расчет денежного потока
    
    Returns:
        dict с revenue, costs, cash_flow
    """
    total_costs = fixed_costs + variable_costs
    cash_flow = revenue - total_costs
    
    return {
        'revenue': revenue,
        'fixed_costs': fixed_costs,
        'variable_costs': variable_costs,
        'total_costs': total_costs,
        'cash_flow': cash_flow
    }


def calculate_npv_series(
    cash_flows: List[float],
    annual_rate: float,
    month_offset: int = 0,
) -> List[float]:
    """
    Кумулятивный NPV по месяцам.

    Месячная ставка: r_m = (1 + annual_rate)^(1/12) - 1
    NPV(T) = Σ_{t=1}^{T} CF_t / (1 + r_m)^(t + month_offset)

    Args:
        cash_flows: список CF по месяцам [CF1, CF2, ...]
        annual_rate: годовая ставка дисконтирования (напр. 0.20 = 20%)
        month_offset: сдвиг дисконтирования — количество месяцев R&D
            перед началом продаж.  При R&D фазе из N месяцев рыночный
            месяц t дисконтируется как (1+r_m)^(t + N), потому что деньги
            получены позже момента инвестиций.  По умолчанию 0 (нет R&D).

    Returns:
        список накопленных дисконтированных CF по месяцам
    """
    if annual_rate <= -1.0:
        annual_rate = 0.0
    r_m = (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0
    npv_series: List[float] = []
    cumulative_npv = 0.0
    for t, cf in enumerate(cash_flows, start=1):
        exponent = t + int(month_offset)
        if r_m > -1.0:
            discounted = cf / (1.0 + r_m) ** exponent
        else:
            discounted = cf
        cumulative_npv += discounted
        npv_series.append(cumulative_npv)
    return npv_series


def calculate_cumulative_cash_flow(cash_flows: List[float]) -> List[float]:
    """
    Кумулятивный Cash Flow (накопленный)
    
    Args:
        cash_flows: список CF по месяцам [CF1, CF2, CF3]
    
    Returns:
        список кумулятивных CF [CF1, CF1+CF2, CF1+CF2+CF3]
    """
    cumulative = []
    total = 0
    for cf in cash_flows:
        total += cf
        cumulative.append(total)
    return cumulative


def calculate_cash_flow_for_months(
    revenue_results: List[Dict],
    costs_results: List[Dict],
    num_months: int = 3
) -> List[Dict[str, float]]:
    """
    Расчет Cash Flow для всех месяцев
    
    Returns:
        Список словарей с CF по месяцам
    """
    results = []
    cumulative_cf = 0
    
    for month in range(1, num_months + 1):
        revenue_result = revenue_results[month - 1]
        costs_result = costs_results[month - 1]
        
        revenue = revenue_result.get('total_revenue', 0)
        fixed_costs = costs_result['fixed_costs']['total']
        variable_costs = costs_result['variable_costs']['total']
        
        cf = calculate_cash_flow(revenue, fixed_costs, variable_costs)
        cumulative_cf += cf['cash_flow']
        
        cf['month'] = month
        cf['cumulative_cash_flow'] = cumulative_cf
        
        results.append(cf)
    
    return results


def calculate_breakeven_month(
    revenue_per_month: List[float],
    costs_per_month: List[float],
    max_months: int = 24,
    initial_investment: float = 0.0,
) -> Dict[str, any]:
    """
    Расчет месяца достижения точки окупаемости.

    Args:
        revenue_per_month: список Revenue по месяцам (может быть проецирован на 24 мес)
        costs_per_month: список Costs по месяцам
        max_months: максимум месяцев для проекции
        initial_investment: начальные вложения (₽), которые нужно отбить до выхода в плюс.
            При 0 — классическая безубыточность (CumCF >= 0).
            При > 0 — срок окупаемости: CumCF >= initial_investment.

    Returns:
        dict с ключами: breakeven_month, cumulative_cf_at_breakeven, reached
    """
    cumulative_cf = 0.0
    threshold = float(initial_investment)

    for month in range(1, max_months + 1):
        revenue = revenue_per_month[min(month - 1, len(revenue_per_month) - 1)]
        costs = costs_per_month[min(month - 1, len(costs_per_month) - 1)]

        cf_month = revenue - costs
        cumulative_cf += cf_month

        if cumulative_cf >= threshold:
            return {
                'breakeven_month': month,
                'cumulative_cf_at_breakeven': cumulative_cf,
                'reached': True,
                'initial_investment': threshold,
            }

    return {
        'breakeven_month': None,
        'cumulative_cf_at_breakeven': cumulative_cf,
        'reached': False,
        'initial_investment': threshold,
    }


def calculate_min_rental_price_for_target_breakeven(
    num_clinics: int,
    patients_per_clinic_month1: int,
    growth_rate: float,
    clinic_commission_rate: float,
    variable_costs_per_patient: float,
    fixed_costs_monthly: float,
    target_breakeven_month: int,
) -> Dict:
    """
    Минимальная цена аренды (₽/пациент/мес) для выхода накопленного CF в плюс
    к целевому месяцу T, с учётом роста пациентов.

    Вывод формулы:
      CumCF(T) = price × (1−commission) × ΣP − var × ΣP − T × FC ≥ 0
      ⟹ price_min = (var × ΣP + T × FC) / ((1−commission) × ΣP)

    где ΣP = Σ_{m=1..T} patients(m)

    Returns dict с полями:
      min_rental_price, total_patient_months, avg_patients_per_month,
      feasible (bool), formula_breakdown
    """
    if target_breakeven_month < 1:
        return {'min_rental_price': float('inf'), 'feasible': False,
                'total_patient_months': 0, 'avg_patients_per_month': 0,
                'formula_breakdown': {}}

    # Рассчитываем количество пациентов по месяцам (зеркало revenue.py)
    patient_counts: List[int] = []
    prev = None
    for m in range(1, target_breakeven_month + 1):
        if m == 1:
            n = num_clinics * patients_per_clinic_month1
        else:
            n = int(prev * (1 + growth_rate))
        patient_counts.append(n)
        prev = n

    total_patient_months = sum(patient_counts)
    avg_patients = total_patient_months / target_breakeven_month

    if total_patient_months == 0:
        return {'min_rental_price': float('inf'), 'feasible': False,
                'total_patient_months': 0, 'avg_patients_per_month': 0,
                'formula_breakdown': {}}

    net_factor = 1.0 - clinic_commission_rate
    if net_factor <= 0:
        return {'min_rental_price': float('inf'), 'feasible': False,
                'total_patient_months': total_patient_months,
                'avg_patients_per_month': avg_patients,
                'formula_breakdown': {}}

    total_var_cost = variable_costs_per_patient * total_patient_months
    total_fixed_cost = fixed_costs_monthly * target_breakeven_month
    numerator = total_var_cost + total_fixed_cost
    denominator = net_factor * total_patient_months

    min_price = numerator / denominator

    breakdown = {
        'patient_counts': patient_counts,
        'total_patient_months': total_patient_months,
        'total_variable_costs': total_var_cost,
        'total_fixed_costs': total_fixed_cost,
        'numerator': numerator,
        'denominator_factor': net_factor,
        'denominator': denominator,
    }

    return {
        'min_rental_price': min_price,
        'feasible': True,
        'total_patient_months': total_patient_months,
        'avg_patients_per_month': avg_patients,
        'formula_breakdown': breakdown,
    }


def calculate_min_rental_price_for_breakeven(
    fixed_costs_monthly: float,
    variable_costs_per_patient: float,
    num_patients_monthly: int,
    clinic_commission_rate: float,
    desired_margin: float
) -> float:
    """
    Расчет минимальной цены аренды для достижения безубыточности
    
    Формула:
    min_price = (Fixed Costs + Variable Costs × num_patients) / 
                (num_patients × (1 - clinic_commission - desired_margin))
    """
    if num_patients_monthly == 0:
        return float('inf')
    
    total_costs = fixed_costs_monthly + (variable_costs_per_patient * num_patients_monthly)
    
    denominator = num_patients_monthly * (1 - clinic_commission_rate - desired_margin)
    
    if denominator <= 0:
        return float('inf')  # Невозможно достичь безубыточности
    
    min_price = total_costs / denominator
    
    return min_price
