"""
Модуль «Инвестиционный банк» ReFlex.

Распределяет начальные инвестиции (I₀) по статьям затрат помесячно,
пока банк не исчерпается. Результат используется для:
  1. Отображения «runway» инвестиций в UI.
  2. Формирования листа «Грантовые расходы» при экспорте в Excel.

Логика не меняет NPV/CF — это параллельный трекер атрибуции.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────

# Стандартный порядок статей затрат при стратегии «priority»
_FIXED_PRIORITY: List[str] = [
    "team_salaries",
    "infrastructure_fixed",
    "office_rent",
    "legal_services",
    "other_fixed",
]
_VARIABLE_PRIORITY: List[str] = [
    "cogs",
    "logistics",
    "support",
    "infrastructure_variable",
    "cac",
]


def _extract_line_items(costs_result: Dict) -> List[Tuple[str, float]]:
    """
    Возвращает плоский список (название_статьи, сумма) из структуры одного месяца.

    Порядок: фиксированные стандартные → кастомные fixed → переменные стандартные
    → кастомные variable.
    """
    items: List[Tuple[str, float]] = []

    fc = costs_result.get("fixed_costs", {})
    for key in _FIXED_PRIORITY:
        val = fc.get(key, 0.0)
        if val > 0:
            items.append((key, val))

    for name, val in fc.get("custom_breakdown", {}).items():
        if val and val > 0:
            items.append((f"[fix] {name}", val))

    vc = costs_result.get("variable_costs", {})
    for key in _VARIABLE_PRIORITY:
        val = vc.get(key, 0.0)
        if val > 0:
            items.append((key, val))

    for name, val in vc.get("custom_breakdown", {}).items():
        if val and val > 0:
            items.append((f"[var] {name}", val))

    return items


def _allocate_proportional(
    line_items: List[Tuple[str, float]], bank: float, total: float
) -> Dict[str, Dict[str, float]]:
    """
    Пропорциональное распределение: каждая статья покрывается банком
    в той же доле, что bank/total (coverage_ratio ≤ 1).
    """
    ratio = min(bank / total, 1.0) if total > 0 else 0.0
    result: Dict[str, Dict[str, float]] = {}
    for name, amt in line_items:
        covered = round(amt * ratio, 2)
        result[name] = {
            "total": amt,
            "bank": covered,
            "own": round(amt - covered, 2),
        }
    return result


def _allocate_priority(
    line_items: List[Tuple[str, float]], bank: float
) -> Dict[str, Dict[str, float]]:
    """
    Приоритетное распределение: статьи покрываются по очереди до исчерпания банка.
    """
    result: Dict[str, Dict[str, float]] = {}
    remaining = bank
    for name, amt in line_items:
        covered = min(remaining, amt)
        result[name] = {
            "total": amt,
            "bank": round(covered, 2),
            "own": round(amt - covered, 2),
        }
        remaining = max(0.0, remaining - covered)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Основная функция
# ──────────────────────────────────────────────────────────────────────────────

def calculate_bank_allocation(
    costs_results: List[Dict],
    initial_investment: float,
    strategy: str = "proportional",
) -> List[Dict]:
    """
    Рассчитывает помесячное распределение инвестиционного банка по статьям затрат.

    Args:
        costs_results: список словарей из calculate_costs_for_months().
        initial_investment: размер банка на старте (I₀).
        strategy: «proportional» (по умолчанию) или «priority».

    Returns:
        Список словарей, по одному на каждый месяц::

            {
                "month":          int,
                "bank_at_start":  float,   # остаток на начало месяца
                "bank_used":      float,   # потрачено в этом месяце
                "bank_at_end":    float,   # остаток на конец месяца
                "fully_covered":  bool,    # банк покрыл все затраты месяца
                "coverage_ratio": float,   # bank_used / total_costs (0..1)
                "line_items": {
                    "<статья>": {
                        "total": float,   # итого по статье
                        "bank":  float,   # покрыто банком
                        "own":   float,   # собственные затраты (не из банка)
                    },
                    ...
                },
            }

    Для месяцев, в которых банк уже исчерпан, bank_used=0 и bank=0 по всем статьям.
    """
    bank = float(initial_investment)
    allocation: List[Dict] = []

    for costs_result in costs_results:
        month = costs_result.get("month", len(allocation) + 1)
        total_costs = costs_result.get("total_costs", 0.0)
        line_items = _extract_line_items(costs_result)

        bank_at_start = bank

        if bank <= 0 or total_costs <= 0:
            # Банк исчерпан или затрат нет
            line_alloc = {
                name: {"total": amt, "bank": 0.0, "own": amt}
                for name, amt in line_items
            }
            allocation.append(
                {
                    "month": month,
                    "bank_at_start": bank_at_start,
                    "bank_used": 0.0,
                    "bank_at_end": bank,
                    "fully_covered": False,
                    "coverage_ratio": 0.0,
                    "line_items": line_alloc,
                }
            )
            continue

        fully_covered = bank >= total_costs
        bank_used = min(bank, total_costs)

        if fully_covered:
            # Банк покрывает все затраты месяца полностью
            line_alloc = {
                name: {"total": amt, "bank": amt, "own": 0.0}
                for name, amt in line_items
            }
        elif strategy == "priority":
            line_alloc = _allocate_priority(line_items, bank)
        else:
            # proportional (default)
            line_alloc = _allocate_proportional(line_items, bank, total_costs)

        bank = max(0.0, bank - bank_used)

        allocation.append(
            {
                "month": month,
                "bank_at_start": bank_at_start,
                "bank_used": bank_used,
                "bank_at_end": bank,
                "fully_covered": fully_covered,
                "coverage_ratio": bank_used / total_costs if total_costs > 0 else 0.0,
                "line_items": line_alloc,
            }
        )

    return allocation


# ──────────────────────────────────────────────────────────────────────────────
# Хелперы для UI и экспорта
# ──────────────────────────────────────────────────────────────────────────────

def bank_exhausted_month(allocation: List[Dict]) -> int | None:
    """
    Возвращает номер месяца, в котором банк исчерпался (bank_at_end == 0),
    или None, если банк не был исчерпан за весь горизонт.
    """
    for entry in allocation:
        if entry["bank_at_end"] == 0 and entry["bank_used"] > 0:
            return entry["month"]
    return None


def months_covered_by_bank(allocation: List[Dict]) -> int:
    """
    Количество месяцев, в которых банк участвовал в покрытии затрат.
    """
    return sum(1 for e in allocation if e["bank_used"] > 0)


def bank_balance_series(allocation: List[Dict]) -> List[float]:
    """
    Список остатков банка на начало каждого месяца (для графика runway).
    """
    return [e["bank_at_start"] for e in allocation]


def all_line_names(allocation: List[Dict]) -> List[str]:
    """
    Уникальный упорядоченный список всех статей затрат, которые встречались
    в allocation (для заголовков таблицы/Excel).
    """
    seen: dict[str, int] = {}
    for entry in allocation:
        for name in entry["line_items"]:
            if name not in seen:
                seen[name] = len(seen)
    return sorted(seen, key=lambda n: seen[n])


def build_grant_matrix(
    allocation: List[Dict],
) -> Tuple[List[str], List[str], List[List[float]]]:
    """
    Строит матрицу «строка=статья, столбец=месяц» для листа «Грантовые расходы».

    Returns:
        (line_names, month_labels, matrix)

        - line_names: список названий статей
        - month_labels: ['Месяц 1', 'Месяц 2', ...]  (только активные месяцы)
        - matrix: list[list[float]] — matrix[i][j] = bank-покрытие статьи i в месяце j
    """
    # Берём только месяцы с ненулевым расходом банка
    active = [e for e in allocation if e["bank_used"] > 0]
    if not active:
        return [], [], []

    line_names = all_line_names(active)
    month_labels = [e.get("month_label", f"Месяц {e['month']}") for e in active]

    matrix: List[List[float]] = []
    for name in line_names:
        row = [e["line_items"].get(name, {}).get("bank", 0.0) for e in active]
        matrix.append(row)

    return line_names, month_labels, matrix
