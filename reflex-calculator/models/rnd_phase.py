"""
Модуль R&D фазы: расходы до старта продаж, покрываемые из инвестиционного банка.

Логика:
  - R&D фаза предшествует рыночной (market) фазе.
  - В R&D нет выручки — только постоянные расходы.
  - Все расходы R&D списываются из банка инвестиций.
  - NPV продаж дисконтируется с учётом сдвига: месяц t рыночной фазы
    является месяцем (rnd_months + t) с момента инвестиций.

Ключевые типы:

RndCostCategory — {"name": str}  (редактируемое название статьи)

RndCostsMatrix  — dict[category_name -> list[float]]
    Ключ: название категории (строка, совпадает с RndCostCategory.name).
    Значение: список затрат длиной rnd_months (индекс = R&D месяц − 1).

RndMonthResult — результат одного R&D месяца, помечен phase="rnd".
"""

from __future__ import annotations

from typing import Dict, List


# ──────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────

RND_PHASE_LABEL = "rnd"
MARKET_PHASE_LABEL = "market"

MAX_RND_MONTHS = 24
DEFAULT_RND_CATEGORIES: List[str] = [
    "Зарплаты команды",
    "Оборудование и материалы",
    "Разработка и тестирование",
    "Аренда и инфраструктура",
    "Прочие расходы R&D",
]


# ──────────────────────────────────────────────────────────────
# Основные функции
# ──────────────────────────────────────────────────────────────

def calculate_rnd_cash_flows(
    rnd_months: int,
    costs_matrix: Dict[str, List[float]],
) -> List[Dict]:
    """
    Вычисляет денежный поток за каждый R&D месяц.

    Args:
        rnd_months: количество R&D месяцев (≥ 1).
        costs_matrix: {category_name: [cost_month_1, cost_month_2, ...]}.
            Длина каждого списка должна быть ≥ rnd_months; лишние элементы игнорируются,
            недостающие принимаются равными 0.

    Returns:
        Список словарей длиной rnd_months, каждый содержит:
            month        — порядковый номер R&D месяца (1-based)
            phase        — "rnd"
            cash_flow    — отрицательное число (суммарные расходы со знаком «−»)
            total_costs  — суммарные расходы месяца (положительное число)
            breakdown    — {category_name: cost} для данного месяца
    """
    results: List[Dict] = []
    cumulative = 0.0
    for m in range(1, rnd_months + 1):
        breakdown: Dict[str, float] = {}
        for cat, monthly_list in costs_matrix.items():
            idx = m - 1
            val = float(monthly_list[idx]) if idx < len(monthly_list) else 0.0
            breakdown[cat] = val
        total_costs = sum(breakdown.values())
        cf = -total_costs
        cumulative += cf
        results.append({
            "month": m,
            "phase": RND_PHASE_LABEL,
            "cash_flow": cf,
            "total_costs": total_costs,
            "cumulative_cash_flow": cumulative,
            "revenue": 0.0,
            "breakdown": breakdown,
        })
    return results


def get_total_rnd_cost(costs_matrix: Dict[str, List[float]], rnd_months: int) -> float:
    """
    Суммирует все расходы R&D за все месяцы.

    Args:
        costs_matrix: матрица расходов R&D.
        rnd_months: количество R&D месяцев.

    Returns:
        Общая сумма расходов R&D (₽).
    """
    total = 0.0
    for monthly_list in costs_matrix.values():
        for idx in range(rnd_months):
            total += float(monthly_list[idx]) if idx < len(monthly_list) else 0.0
    return total


def get_rnd_cost_by_month(costs_matrix: Dict[str, List[float]], rnd_months: int) -> List[float]:
    """
    Возвращает суммарные расходы R&D по каждому месяцу.

    Returns:
        Список длиной rnd_months с суммой расходов по всем категориям.
    """
    monthly_totals = []
    for m_idx in range(rnd_months):
        s = 0.0
        for monthly_list in costs_matrix.values():
            s += float(monthly_list[m_idx]) if m_idx < len(monthly_list) else 0.0
        monthly_totals.append(s)
    return monthly_totals


def validate_rnd_vs_bank(
    total_rnd_cost: float,
    initial_investment: float,
) -> Dict:
    """
    Проверяет, не превышает ли суммарный R&D расход банк инвестиций.

    Returns:
        dict с ключами:
            ok           — True, если расходы не превышают банк
            remaining    — остаток банка после R&D (₽)
            overflow     — сумма превышения (0 если ok)
            pct_used     — процент использования банка
            message      — человекочитаемое сообщение
    """
    remaining = initial_investment - total_rnd_cost
    overflow = max(0.0, -remaining)
    pct_used = (total_rnd_cost / initial_investment * 100) if initial_investment > 0 else 0.0
    ok = remaining >= 0.0

    if initial_investment <= 0:
        message = (
            "Банк инвестиций равен 0. Задайте «Начальные вложения» в разделе "
            "«Срок окупаемости», чтобы использовать R&D фазу."
        )
        return {"ok": False, "remaining": 0.0, "overflow": total_rnd_cost,
                "pct_used": 0.0, "message": message}

    if ok:
        message = (
            f"R&D расходы: {total_rnd_cost:,.0f} ₽ | "
            f"Остаток банка: {remaining:,.0f} ₽ ({100 - pct_used:.0f}% доступно)"
        )
    else:
        message = (
            f"Расходы R&D ({total_rnd_cost:,.0f} ₽) превышают банк инвестиций "
            f"({initial_investment:,.0f} ₽) на {overflow:,.0f} ₽. "
            "Уменьшите расходы или увеличьте начальные вложения."
        )

    return {
        "ok": ok,
        "remaining": max(0.0, remaining),
        "overflow": overflow,
        "pct_used": min(pct_used, 100.0),
        "message": message,
    }


def ensure_matrix_size(
    costs_matrix: Dict[str, List[float]],
    rnd_months: int,
) -> Dict[str, List[float]]:
    """
    Гарантирует, что каждый список в матрице имеет длину ровно rnd_months.
    Недостающие значения заполняются 0, лишние обрезаются.
    """
    result = {}
    for cat, vals in costs_matrix.items():
        padded = list(vals)
        while len(padded) < rnd_months:
            padded.append(0.0)
        result[cat] = padded[:rnd_months]
    return result


def build_empty_matrix(categories: List[str], rnd_months: int) -> Dict[str, List[float]]:
    """
    Создаёт пустую (нулевую) матрицу расходов R&D.
    """
    return {cat: [0.0] * rnd_months for cat in categories}


def rename_category(
    costs_matrix: Dict[str, List[float]],
    old_name: str,
    new_name: str,
) -> Dict[str, List[float]]:
    """
    Переименовывает категорию в матрице, сохраняя данные.
    """
    result = {}
    for cat, vals in costs_matrix.items():
        result[new_name if cat == old_name else cat] = vals
    return result
