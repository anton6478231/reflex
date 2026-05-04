"""
Утилиты для форматирования чисел, валют и других данных
"""
from typing import Dict


def format_currency_compact(value: float, currency: str = '₽') -> str:
    """
    Компактное отображение для узких KPI: млн / тыс при больших суммах.
    Для подсказок с полной суммой используйте format_currency.
    """
    if value == float('inf'):
        return "∞"
    if value == float('-inf'):
        return "-∞"

    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.2f}".replace(".", ",")
        return f"{sign}{s} млн{currency}"
    if v >= 10_000:
        s = f"{v / 1_000:,.0f}".replace(",", " ")
        return f"{sign}{s} тыс{currency}"
    return format_currency(value, currency)


def format_currency(value: float, currency: str = '₽') -> str:
    """
    Форматирование валюты с разделителями
    
    Args:
        value: числовое значение
        currency: символ валюты
    
    Returns:
        Отформатированная строка (например, "1 234 567₽")
    """
    if value == float('inf'):
        return "∞"
    if value == float('-inf'):
        return "-∞"
    
    # Форматируем с пробелами как разделителями тысяч
    formatted = f"{value:,.0f}".replace(',', ' ')
    return f"{formatted}{currency}"


def format_percent(value: float) -> str:
    """
    Форматирование процентов
    
    Args:
        value: значение от 0 до 1 (например, 0.15 для 15%)
    
    Returns:
        Отформатированная строка (например, "15%")
    """
    return f"{value * 100:.1f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """
    Форматирование числа с разделителями тысяч
    
    Args:
        value: числовое значение
        decimals: количество знаков после запятой
    
    Returns:
        Отформатированная строка (например, "1 234")
    """
    if value == float('inf'):
        return "∞"
    if value == float('-inf'):
        return "-∞"
    
    if decimals > 0:
        formatted = f"{value:,.{decimals}f}".replace(',', ' ')
    else:
        formatted = f"{value:,.0f}".replace(',', ' ')
    
    return formatted


def format_ratio(value: float, decimals: int = 2) -> str:
    """
    Форматирование коэффициента (LTV/CAC и т.д.)
    """
    if value == float('inf'):
        return "∞"
    if value == float('-inf'):
        return "-∞"
    
    return f"{value:.{decimals}f}"


def format_months(value: float) -> str:
    """
    Форматирование месяцев
    """
    if value == float('inf'):
        return "Никогда"
    if value < 0:
        return "Отрицательный CF"
    
    return f"{value:.1f} мес"


def get_color_for_value(value: float, good_threshold: float = 0, reverse: bool = False) -> str:
    """
    Возвращает цвет в зависимости от значения
    
    Args:
        value: значение для проверки
        good_threshold: порог для "хорошего" значения
        reverse: если True, то меньше = лучше (для затрат)
    
    Returns:
        Цвет: 'green', 'red', 'orange'
    """
    if reverse:
        # Для затрат: меньше = лучше
        if value < good_threshold:
            return 'green'
        elif value < good_threshold * 1.2:
            return 'orange'
        else:
            return 'red'
    else:
        # Для доходов/прибыли: больше = лучше
        if value >= good_threshold:
            return 'green'
        elif value >= good_threshold * 0.5:
            return 'orange'
        else:
            return 'red'


def get_metric_delta(current: float, previous: float) -> Dict[str, any]:
    """
    Рассчитывает изменение метрики
    
    Returns:
        dict с ключами: delta, delta_percent, direction
    """
    delta = current - previous
    
    if previous != 0:
        delta_percent = (delta / abs(previous)) * 100
    else:
        delta_percent = 0 if delta == 0 else float('inf')
    
    direction = 'up' if delta > 0 else ('down' if delta < 0 else 'stable')
    
    return {
        'delta': delta,
        'delta_percent': delta_percent,
        'direction': direction
    }
