"""
Модуль анализа чувствительности (Sensitivity Analysis)
"""
from typing import Dict, List, Callable, Optional


def calculate_sensitivity(
    base_cash_flow: float,
    parameter_name: str,
    parameter_value: float,
    variation_percent: float,
    recalculate_func: Callable
) -> Dict[str, any]:
    """
    Анализ чувствительности: как изменение параметра влияет на Cash Flow
    
    Args:
        base_cash_flow: базовый CF при текущих параметрах
        parameter_name: название параметра (например, "rental_price")
        parameter_value: текущее значение параметра
        variation_percent: процент изменения (например, 0.2 = ±20%)
        recalculate_func: функция для пересчета CF при новом значении параметра
    
    Returns:
        dict с ключами: parameter, base_value, increased_value, decreased_value,
                       cf_increase, cf_decrease, impact
    """
    # Увеличенное значение параметра
    increased_value = parameter_value * (1 + variation_percent)
    cf_increased = recalculate_func(increased_value)
    cf_increase = cf_increased - base_cash_flow
    
    # Уменьшенное значение параметра
    decreased_value = parameter_value * (1 - variation_percent)
    cf_decreased = recalculate_func(decreased_value)
    cf_decrease = base_cash_flow - cf_decreased
    
    # Impact (абсолютное изменение CF)
    impact = max(abs(cf_increase), abs(cf_decrease))
    
    return {
        'parameter': parameter_name,
        'base_value': parameter_value,
        'increased_value': increased_value,
        'decreased_value': decreased_value,
        'cf_increase': cf_increase,
        'cf_decrease': cf_decrease,
        'impact': impact
    }


def calculate_sensitivity_analysis(
    model_type: str,
    all_params: Dict,
    base_total_cf: float,
    variation_percent: float = 0.20,
    num_months: int = 3,
    custom_fixed_costs: Optional[Dict] = None,
    custom_variable_costs: Optional[Dict] = None,
) -> List[Dict[str, any]]:
    """
    Полный анализ чувствительности для ключевых параметров
    
    Args:
        model_type: тип модели
        all_params: все параметры (revenue, fixed_costs, variable_costs)
        base_total_cf: базовый total CF за выбранный горизонт
        variation_percent: процент вариации (по умолчанию 20%)
        num_months: горизонт расчета sensitivity
        custom_fixed_costs: кастомные fixed статьи
        custom_variable_costs: кастомные variable статьи
    
    Returns:
        Список результатов sensitivity для каждого параметра, 
        отсортированный по убыванию impact
    """
    from models.revenue import calculate_revenue_for_months
    from models.costs import calculate_costs_for_months
    from models.cash_flow import calculate_cash_flow_for_months
    
    results = []
    
    # Параметры для анализа зависят от модели
    if model_type == 'model_b':
        params_to_test = [
            ('rental_price', all_params['revenue']['rental_price'], 'revenue'),
            ('patients_per_clinic_month1', all_params['revenue']['patients_per_clinic_month1'], 'revenue'),
            ('clinic_commission_rate', all_params['revenue']['clinic_commission_rate'], 'revenue'),
            ('team_salaries', all_params['fixed_costs']['team_salaries'], 'fixed_costs'),
            ('logistics_per_patient', all_params['variable_costs']['logistics_per_patient'], 'variable_costs'),
        ]
    elif model_type == 'model_a':
        params_to_test = [
            ('setup_fee', all_params['revenue']['setup_fee'], 'revenue'),
            ('subscription_per_device', all_params['revenue']['subscription_per_device'], 'revenue'),
            ('num_clinics', all_params['revenue']['num_clinics'], 'revenue'),
            ('devices_per_clinic', all_params['revenue']['devices_per_clinic'], 'revenue'),
            ('team_salaries', all_params['fixed_costs']['team_salaries'], 'fixed_costs'),
            ('cogs_per_device', all_params['variable_costs']['cogs_per_device'], 'variable_costs'),
        ]
    else:  # model_ab
        params_to_test = [
            ('rental_price', all_params['revenue']['rental_price'], 'revenue'),
            ('setup_fee', all_params['revenue']['setup_fee'], 'revenue'),
            ('subscription_per_device', all_params['revenue']['subscription_per_device'], 'revenue'),
            ('patients_per_clinic_month1', all_params['revenue']['patients_per_clinic_month1'], 'revenue'),
            ('team_salaries', all_params['fixed_costs']['team_salaries'], 'fixed_costs'),
        ]
    
    # Для каждого параметра рассчитываем влияние
    for param_name, param_value, param_category in params_to_test:
        def recalculate_cf(new_value):
            # Копируем параметры
            test_params = {
                'revenue': all_params['revenue'].copy(),
                'fixed_costs': all_params['fixed_costs'].copy(),
                'variable_costs': all_params['variable_costs'].copy(),
                'assumptions': all_params.get('assumptions', {}).copy()
            }
            
            # Обновляем тестируемый параметр
            test_params[param_category][param_name] = new_value
            
            # Пересчитываем CF
            revenue_results = calculate_revenue_for_months(
                model_type,
                test_params['revenue'],
                num_months,
                assumptions=test_params.get('assumptions'),
            )
            costs_results = calculate_costs_for_months(
                model_type, test_params['fixed_costs'], 
                test_params['variable_costs'], revenue_results, num_months,
                custom_fixed_costs or {}, custom_variable_costs or {}
            )
            cf_results = calculate_cash_flow_for_months(revenue_results, costs_results, num_months)
            
            # Возвращаем total CF за выбранный горизонт
            return sum([cf['cash_flow'] for cf in cf_results])
        
        sensitivity = calculate_sensitivity(
            base_cash_flow=base_total_cf,
            parameter_name=param_name,
            parameter_value=param_value,
            variation_percent=variation_percent,
            recalculate_func=recalculate_cf
        )
        
        results.append(sensitivity)
    
    # Сортируем по убыванию impact
    results.sort(key=lambda x: x['impact'], reverse=True)
    
    return results
