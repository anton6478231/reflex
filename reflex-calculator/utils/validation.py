"""
Утилиты для валидации входных данных
"""
from typing import Tuple


def validate_positive_number(value: float, name: str) -> Tuple[bool, str]:
    """
    Проверка, что значение положительное
    
    Returns:
        (is_valid, error_message)
    """
    if value < 0:
        return False, f"{name} должно быть положительным числом"
    return True, ""


def validate_percent(value: float, name: str) -> Tuple[bool, str]:
    """
    Проверка, что значение в диапазоне 0-1 (процент)
    """
    if value < 0 or value > 1:
        return False, f"{name} должно быть в диапазоне 0-100%"
    return True, ""


def validate_integer(value: float, name: str) -> Tuple[bool, str]:
    """
    Проверка, что значение целое число
    """
    if not isinstance(value, int) and value != int(value):
        return False, f"{name} должно быть целым числом"
    return True, ""


def validate_range(value: float, name: str, min_val: float, max_val: float) -> Tuple[bool, str]:
    """
    Проверка, что значение в заданном диапазоне
    """
    if value < min_val or value > max_val:
        return False, f"{name} должно быть в диапазоне {min_val}-{max_val}"
    return True, ""


def validate_revenue_params(model_type: str, params: dict) -> Tuple[bool, str]:
    """
    Валидация параметров revenue в зависимости от модели
    """
    if model_type == 'model_a':
        required = ['num_clinics', 'devices_per_clinic', 'setup_fee', 'subscription_per_device']
    elif model_type == 'model_b':
        required = ['num_clinics', 'patients_per_clinic_month1', 'growth_rate', 
                   'rental_price', 'clinic_commission_rate']
    elif model_type == 'model_ab':
        required = ['num_clinics', 'devices_per_clinic', 'setup_fee', 'subscription_per_device',
                   'patients_per_clinic_month1', 'growth_rate', 'rental_price', 'clinic_commission_rate']
    else:
        return False, f"Неизвестный тип модели: {model_type}"
    
    for key in required:
        if key not in params:
            return False, f"Отсутствует обязательный параметр: {key}"
        
        value = params[key]
        
        # Проверяем положительность
        if key not in ['growth_rate', 'clinic_commission_rate']:
            is_valid, error = validate_positive_number(value, key)
            if not is_valid:
                return is_valid, error
        
        # Проверяем проценты
        if key in ['growth_rate', 'clinic_commission_rate']:
            is_valid, error = validate_percent(value, key)
            if not is_valid:
                return is_valid, error

    if model_type == "model_a" and "new_clinics_per_month" in params:
        ncm = params["new_clinics_per_month"]
        if isinstance(ncm, (int, float)) and ncm < 0:
            return False, "new_clinics_per_month не может быть отрицательным"
    
    return True, ""


def validate_costs_params(params: dict) -> Tuple[bool, str]:
    """
    Валидация параметров затрат
    """
    for key, value in params.items():
        is_valid, error = validate_positive_number(value, key)
        if not is_valid:
            return is_valid, error
    
    return True, ""


def validate_all_params(model_type: str, all_params: dict) -> Tuple[bool, str]:
    """
    Полная валидация всех параметров
    """
    # Проверяем revenue
    is_valid, error = validate_revenue_params(model_type, all_params['revenue'])
    if not is_valid:
        return is_valid, f"Revenue: {error}"
    
    # Проверяем fixed costs
    is_valid, error = validate_costs_params(all_params['fixed_costs'])
    if not is_valid:
        return is_valid, f"Fixed Costs: {error}"
    
    # Проверяем variable costs
    is_valid, error = validate_costs_params(all_params['variable_costs'])
    if not is_valid:
        return is_valid, f"Variable Costs: {error}"
    
    return True, ""
