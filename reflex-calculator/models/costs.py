"""
Модуль расчета затрат (Fixed и Variable Costs) для ReFlex
"""
from typing import Dict, List


def calculate_fixed_costs(
    team_salaries: float,
    infrastructure_fixed: float,
    office_rent: float,
    legal_services: float,
    other_fixed: float
) -> Dict[str, float]:
    """
    Постоянные затраты (одинаковые каждый месяц)
    
    Returns:
        dict с breakdown по категориям и total
    """
    total = (
        team_salaries +
        infrastructure_fixed +
        office_rent +
        legal_services +
        other_fixed
    )
    
    return {
        'team_salaries': team_salaries,
        'infrastructure_fixed': infrastructure_fixed,
        'office_rent': office_rent,
        'legal_services': legal_services,
        'other_fixed': other_fixed,
        'total': total
    }


def calculate_variable_costs(
    num_devices_produced: int,
    cogs_per_device: float,
    num_patients_for_logistics: int,
    num_patients_for_support: int,
    logistics_per_patient: float,
    support_per_patient_per_month: float,
    num_active_users: int,
    infrastructure_per_user: float,
    num_new_customers: int,
    cac: float
) -> Dict[str, float]:
    """
    Переменные затраты (зависят от объема)
    
    Returns:
        dict с breakdown по категориям и total
    """
    # COGS (производство устройств)
    cogs_total = num_devices_produced * cogs_per_device
    
    # Логистика (доставка устройств новым пациентам; разовая на входе)
    logistics_total = num_patients_for_logistics * logistics_per_patient
    
    # Поддержка (ежемесячно по активным пациентам)
    support_total = num_patients_for_support * support_per_patient_per_month
    
    # Инфраструктура (переменная часть)
    infrastructure_variable = num_active_users * infrastructure_per_user
    
    # CAC (привлечение новых клиентов)
    cac_total = num_new_customers * cac
    
    total_variable_costs = (
        cogs_total +
        logistics_total +
        support_total +
        infrastructure_variable +
        cac_total
    )
    
    return {
        'cogs': cogs_total,
        'logistics': logistics_total,
        'support': support_total,
        'infrastructure_variable': infrastructure_variable,
        'cac': cac_total,
        'total': total_variable_costs
    }


def calculate_costs_for_month(
    model_type: str,
    fixed_params: Dict,
    variable_params: Dict,
    revenue_result: Dict,
    month: int,
    custom_fixed: Dict = None,
    custom_variable: Dict = None
) -> Dict[str, float]:
    """
    Расчет всех затрат для конкретного месяца
    
    Args:
        model_type: 'model_a', 'model_b', или 'model_ab'
        fixed_params: Параметры постоянных затрат
        variable_params: Параметры переменных затрат
        revenue_result: Результат расчета revenue для этого месяца
        month: Номер месяца
        custom_fixed: Кастомные fixed costs {name: {'value': float, 'type': str}}
        custom_variable: Кастомные variable costs {name: {'value': float, 'type': str}}
    
    Returns:
        dict с fixed_costs, variable_costs, total_costs
    """
    if custom_fixed is None:
        custom_fixed = {}
    if custom_variable is None:
        custom_variable = {}
    
    # Fixed costs одинаковые каждый месяц
    fixed_costs = calculate_fixed_costs(
        team_salaries=fixed_params.get('team_salaries', 0),
        infrastructure_fixed=fixed_params.get('infrastructure_fixed', 0),
        office_rent=fixed_params.get('office_rent', 0),
        legal_services=fixed_params.get('legal_services', 0),
        other_fixed=fixed_params.get('other_fixed', 0)
    )
    
    # Добавляем кастомные fixed costs
    custom_fixed_total = 0
    custom_fixed_breakdown = {}
    for name, data in custom_fixed.items():
        if data['type'] == "Единоразовая (месяц 1)" and month != 1:
            custom_fixed_breakdown[name] = 0
        else:
            custom_fixed_breakdown[name] = data['value']
            custom_fixed_total += data['value']
    
    fixed_costs['custom'] = custom_fixed_total
    fixed_costs['custom_breakdown'] = custom_fixed_breakdown
    fixed_costs['total'] += custom_fixed_total
    
    # Variable costs зависят от модели и объема
    if model_type == 'model_a':
        # Model A: COGS на докупку парка (каждый месяц, см. num_devices_produced в revenue)
        num_devices_produced = int(revenue_result.get('num_devices_produced', 0) or 0)
        num_patients_for_logistics = int(revenue_result.get('new_patients', 0) or 0)
        num_patients_for_support = int(revenue_result.get('num_patients', 0) or 0)
        num_active_users = num_patients_for_support
        # CAC начисляется за каждую новую клинику в месяц её подключения.
        # revenue_result['new_clinics_this_month'] устанавливается в _run_model_a_schedule;
        # fallback — num_clinics в M1 (обратная совместимость с тестами без расписания).
        default_cac_customers = int(variable_params.get('num_clinics', 0) or 0) if month == 1 else 0
        num_new_customers = int(revenue_result.get('new_clinics_this_month', default_cac_customers))
        cac = variable_params.get('cac_clinic', 0)
        
    elif model_type == 'model_b':
        # Model B: учитываем расширение парка при дефиците + когорты пациентов
        num_devices_produced = revenue_result.get('num_devices_produced', 0)
        num_patients_for_logistics = revenue_result.get('new_patients', revenue_result.get('num_patients', 0))
        num_patients_for_support = revenue_result.get('num_patients', 0)
        num_active_users = num_patients_for_support
        num_new_customers = revenue_result.get('new_patients', 0)
        cac = variable_params.get('cac_patient', 0)
        
    elif model_type == 'model_ab':
        # Гибрид: стартовый парк + допроизводство под рост пациентов
        num_devices_produced = revenue_result.get('num_devices_produced', 0)
        num_patients_for_logistics = revenue_result.get('new_patients', revenue_result.get('num_patients', 0))
        num_patients_for_support = revenue_result.get('num_patients', 0)
        num_active_users = num_patients_for_support
        num_new_customers = num_devices_produced
        cac = variable_params.get('cac_clinic', 0)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    variable_costs = calculate_variable_costs(
        num_devices_produced=num_devices_produced,
        cogs_per_device=variable_params.get('cogs_per_device', 0),
        num_patients_for_logistics=num_patients_for_logistics,
        num_patients_for_support=num_patients_for_support,
        logistics_per_patient=variable_params.get('logistics_per_patient', 0),
        support_per_patient_per_month=variable_params.get('support_per_patient_per_month', 0),
        num_active_users=num_active_users,
        infrastructure_per_user=variable_params.get('infrastructure_per_user', 0),
        num_new_customers=num_new_customers,
        cac=cac
    )
    
    # Добавляем кастомные variable costs
    custom_var_total = 0
    custom_var_breakdown = {}
    for name, data in custom_variable.items():
        value = data['value']
        var_type = data['type']
        
        if var_type == "На устройство (разово)":
            cost = num_devices_produced * value
        elif var_type == "На пациента (разово)":
            cost = num_patients_for_logistics * value
        elif var_type == "На пациента/месяц":
            cost = num_patients_for_support * value
        elif var_type == "На клинику (разово)":
            # В revenue_result ключ num_clinics обычно отсутствует, поэтому берем fallback из variable_params.
            num_clinics = revenue_result.get('num_clinics', variable_params.get('num_clinics', 0))
            cost = num_clinics * value if month == 1 else 0
        else:
            cost = 0
        
        custom_var_breakdown[name] = cost
        custom_var_total += cost
    
    variable_costs['custom'] = custom_var_total
    variable_costs['custom_breakdown'] = custom_var_breakdown
    variable_costs['total'] += custom_var_total
    
    return {
        'fixed_costs': fixed_costs,
        'variable_costs': variable_costs,
        'total_costs': fixed_costs['total'] + variable_costs['total']
    }


def calculate_costs_for_months(
    model_type: str,
    fixed_params: Dict,
    variable_params: Dict,
    revenue_results: List[Dict],
    num_months: int = 3,
    custom_fixed: Dict = None,
    custom_variable: Dict = None
) -> List[Dict[str, float]]:
    """
    Расчет затрат для всех месяцев
    
    Returns:
        Список словарей с затратами по месяцам
    """
    results = []
    
    for month in range(1, num_months + 1):
        revenue_result = revenue_results[month - 1]
        costs = calculate_costs_for_month(
            model_type, fixed_params, variable_params, 
            revenue_result, month, custom_fixed, custom_variable
        )
        costs['month'] = month
        results.append(costs)
    
    return results
