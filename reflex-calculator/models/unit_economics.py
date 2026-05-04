"""
Модуль расчета Unit Economics (LTV, CAC, Payback) для Model B
"""
from typing import Dict


def calculate_unit_economics(
    rental_price: float,
    avg_rental_duration: int,
    clinic_commission_rate: float,
    variable_costs_per_patient_per_month: float,
    cac_per_patient: float
) -> Dict[str, float]:
    """
    Расчет Unit Economics для Model B
    
    Returns:
        dict с ltv, cac, ltv_cac_ratio, payback_months, profit_per_patient_per_month
    """
    # Net Revenue на пациента в месяц (после комиссии)
    net_revenue_per_patient_per_month = rental_price * (1 - clinic_commission_rate)
    
    # Прибыль на пациента в месяц (после вычета переменных затрат)
    profit_per_patient_per_month = (
        net_revenue_per_patient_per_month - variable_costs_per_patient_per_month
    )
    
    # LTV (Lifetime Value)
    ltv = profit_per_patient_per_month * avg_rental_duration
    
    # LTV/CAC Ratio
    if cac_per_patient > 0:
        ltv_cac_ratio = ltv / cac_per_patient
    else:
        ltv_cac_ratio = float('inf') if ltv > 0 else 0
    
    # Payback Period (месяцы окупаемости CAC)
    if profit_per_patient_per_month > 0:
        payback_months = cac_per_patient / profit_per_patient_per_month
    else:
        payback_months = float('inf')
    
    return {
        'ltv': ltv,
        'cac': cac_per_patient,
        'ltv_cac_ratio': ltv_cac_ratio,
        'payback_months': payback_months,
        'profit_per_patient_per_month': profit_per_patient_per_month,
        'net_revenue_per_patient_per_month': net_revenue_per_patient_per_month
    }


def calculate_unit_economics_from_params(
    model_type: str,
    revenue_params: Dict,
    variable_params: Dict
) -> Dict[str, float]:
    """
    Расчет Unit Economics из параметров
    
    Работает только для model_b и model_ab
    """
    if model_type not in ['model_b', 'model_ab']:
        return {
            'ltv': 0,
            'cac': 0,
            'ltv_cac_ratio': 0,
            'payback_months': 0,
            'profit_per_patient_per_month': 0,
            'net_revenue_per_patient_per_month': 0
        }
    
    rental_price = revenue_params.get('rental_price', 0)
    avg_rental_duration = revenue_params.get('avg_rental_duration', 2)
    clinic_commission_rate = revenue_params.get('clinic_commission_rate', 0.15)
    
    variable_costs_per_patient = (
        variable_params.get('logistics_per_patient', 0) +
        variable_params.get('support_per_patient_per_month', 0) +
        variable_params.get('infrastructure_per_user', 0)
    )
    
    cac_per_patient = variable_params.get('cac_patient', 0)
    
    return calculate_unit_economics(
        rental_price=rental_price,
        avg_rental_duration=avg_rental_duration,
        clinic_commission_rate=clinic_commission_rate,
        variable_costs_per_patient_per_month=variable_costs_per_patient,
        cac_per_patient=cac_per_patient
    )
