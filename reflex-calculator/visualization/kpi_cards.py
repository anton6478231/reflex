"""
Модуль для создания KPI карточек (метрик)
"""
import streamlit as st
from typing import Dict, List
from utils.formatters import format_currency, format_currency_compact, format_ratio

# Узкие колонки Streamlit обрезают st.metric; перенос + компактные суммы
_KPI_METRIC_CSS = """
<style>
section.main div[data-testid="stMetric"] {
    min-width: 0;
    padding: 0.45rem 0.3rem;
}
section.main div[data-testid="stMetric"] label {
    white-space: normal !important;
    word-break: break-word;
    line-height: 1.25;
    font-size: 0.78rem;
}
section.main div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    white-space: normal !important;
    word-break: break-word;
    line-height: 1.2;
    font-size: clamp(0.85rem, 2.1vw, 1.15rem);
}
</style>
"""


def display_kpi_cards(
    cash_flow_results: List[Dict],
    breakeven_result: Dict,
    min_rental_price: float,
    unit_economics: Dict,
    num_months: int = 3,
    model_type: str = "model_b",
    mrr_model_a: float = 0.0,
    target_min_rental_price: float = 0.0,
    target_breakeven_month: int = 0,
):
    """
    Отображение 6 KPI карточек в верхней части дашборда
    
    Args:
        cash_flow_results: результаты расчета CF
        breakeven_result: результат breakeven analysis
        min_rental_price: минимальная цена для безубыточности
        unit_economics: метрики unit economics
        num_months: количество месяцев для расчета
    """
    # Рассчитываем метрики
    total_revenue = sum([cf['revenue'] for cf in cash_flow_results])
    total_costs = sum([cf['total_costs'] for cf in cash_flow_results])
    net_cash_flow = sum([cf['cash_flow'] for cf in cash_flow_results])
    
    breakeven_month = breakeven_result['breakeven_month'] if breakeven_result['reached'] else None
    ltv_cac_ratio = unit_economics.get('ltv_cac_ratio', 0)

    st.markdown(_KPI_METRIC_CSS, unsafe_allow_html=True)

    # Две строки по 3 метрики — в 2 раза шире ячейка, чем 6 колонок в ряд
    r1c1, r1c2, r1c3 = st.columns(3)
    r2c1, r2c2, r2c3 = st.columns(3)

    with r1c1:
        st.metric(
            label=f"Выручка ({num_months} мес)",
            value=format_currency_compact(total_revenue),
            delta=None,
            help=(
                f"Суммарная выручка (Revenue) за весь горизонт {num_months} мес: {format_currency(total_revenue)}. "
                "Включает все источники: Setup Fee (продажа устройств), Subscription (подписка ПО), "
                "Net Rental (аренда пациентами за вычетом комиссии). "
                "Растёт с количеством клиник, пациентов и устройств."
            ),
        )

    with r1c2:
        st.metric(
            label=f"Затраты ({num_months} мес)",
            value=format_currency_compact(total_costs),
            delta=None,
            help=(
                f"Суммарные затраты (Costs) за {num_months} мес: {format_currency(total_costs)}. "
                "Fixed Costs (зарплаты, офис, инфраструктура) постоянны каждый месяц. "
                "Variable Costs (COGS — себестоимость устройств, логистика, поддержка, CAC) "
                "растут пропорционально количеству устройств и пациентов."
            ),
        )

    with r1c3:
        st.metric(
            label=f"Чистый CF ({num_months} мес)",
            value=format_currency_compact(net_cash_flow),
            delta=None,
            help=(
                f"Чистый денежный поток (Net Cash Flow) за {num_months} мес: {format_currency(net_cash_flow)}. "
                "Формула: CF = Выручка − Затраты (по каждому месяцу, затем сумма). "
                "Отрицательный CF означает, что за период суммарно вложено больше, чем заработано. "
                "Цель — выйти в положительный накопленный CF как можно раньше."
            ),
        )

    with r2c1:
        if breakeven_month:
            st.metric(
                label="Breakeven",
                value=f"{breakeven_month} мес",
                delta=None,
                help=(
                    f"Точка безубыточности — месяц №{breakeven_month}, когда накопленный Cash Flow впервые стал ≥ 0. "
                    "До этого момента суммарные затраты превышали суммарную выручку. "
                    "После — проект начинает «отбивать» вложения. "
                    "Чем раньше — тем меньше требуется стартовое финансирование."
                ),
            )
        else:
            st.metric(
                label="Breakeven",
                value="—",
                delta=None,
                help=(
                    f"Безубыточность не достигается в горизонте {num_months} мес при текущих параметрах. "
                    "Попробуйте: увеличить цену аренды/подписки, добавить клиники/пациентов, "
                    "или сократить Fixed/Variable Costs. "
                    "Блок «Целевая безубыточность» поможет найти минимальную цену для нужного срока."
                ),
            )

    with r2c2:
        if model_type == "model_a":
            st.metric(
                label="MRR (подписка)",
                value=format_currency_compact(mrr_model_a),
                delta=None,
                help=(
                    f"Monthly Recurring Revenue от подписки на ПО: {format_currency(mrr_model_a)}. "
                    "Формула: Кол-во устройств в парке × Subscription per device. "
                    "Это ежемесячный стабильный доход — чем больше парк, тем выше MRR. "
                    "В модели A нет аренды пациентам, поэтому показатель «Мин. аренда» неприменим."
                ),
            )
        elif model_type in ["model_b", "model_ab"] and target_breakeven_month > 0 and target_min_rental_price < float('inf'):
            label = f"Мин. цена → мес {target_breakeven_month}"
            st.metric(
                label=label,
                value=format_currency_compact(target_min_rental_price),
                delta=None,
                help=(
                    f"Минимальная цена аренды, при которой выход в плюс достигается к месяцу {target_breakeven_month}: "
                    f"{format_currency(target_min_rental_price)}. "
                    "Рассчитывается бинарным поиском: модель симулируется многократно с разной ценой "
                    "до нахождения минимальной, при которой CumCF(N) ≥ 0. "
                    "Подробности — в блоке «Целевая безубыточность» ниже."
                ),
            )
        elif min_rental_price != float('inf'):
            st.metric(
                label="Мин. аренда",
                value=format_currency_compact(min_rental_price),
                delta=None,
                help=(
                    f"Минимальная цена аренды для достижения безубыточности: {format_currency(min_rental_price)}. "
                    "Ниже этой цены накопленный CF не выйдет в плюс в горизонте расчёта. "
                    "Для задания целевого срока — используйте ползунок «Целевая безубыточность» в сайдбаре."
                ),
            )
        else:
            st.metric(
                label="Мин. аренда",
                value="—",
                delta=None,
                help=(
                    "Не удалось рассчитать минимальную цену аренды. "
                    "Возможные причины: нулевое количество пациентов, 100% комиссия клиники, "
                    "или модель не использует аренду (Model A). Проверьте параметры выбранной модели."
                ),
            )

    with r2c3:
        if ltv_cac_ratio > 0 and ltv_cac_ratio != float('inf'):
            st.metric(
                label="LTV / CAC",
                value=format_ratio(ltv_cac_ratio),
                delta="OK" if ltv_cac_ratio > 3 else "Low",
                delta_color="normal" if ltv_cac_ratio > 3 else "inverse",
                help=(
                    "LTV (Lifetime Value) — сколько денег приносит один пациент за весь курс реабилитации. "
                    "CAC (Customer Acquisition Cost) — стоимость привлечения одного пациента. "
                    f"Отношение LTV/CAC = {format_ratio(ltv_cac_ratio)}. "
                    "Правило: > 3 — здоровая модель (на каждый рубль затрат на привлечение 3+ рубля дохода). "
                    "< 1 — привлечение обходится дороже, чем приносит пациент: нужно снижать CAC или повышать цену."
                ),
            )
        else:
            st.metric(
                label="LTV / CAC",
                value="—",
                delta=None,
                help=(
                    "Unit economics не рассчитаны. Для Model A LTV/CAC считается иначе (через MRR). "
                    "Для Model B/AB: убедитесь, что заданы CAC пациента и цена аренды > 0, "
                    "и горизонт расчёта > срока реабилитации."
                ),
            )


def display_kpi_summary(
    cash_flow_results: List[Dict],
    model_type: str,
    num_months: int = 3
):
    """
    Краткая сводка метрик в боковой панели
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Краткая сводка")
    
    total_revenue = sum([cf['revenue'] for cf in cash_flow_results])
    total_costs = sum([cf['total_costs'] for cf in cash_flow_results])
    net_cf = sum([cf['cash_flow'] for cf in cash_flow_results])
    
    st.sidebar.markdown(f"**Revenue ({num_months} мес):** {format_currency(total_revenue)}")
    st.sidebar.markdown(f"**Costs ({num_months} мес):** {format_currency(total_costs)}")
    
    if net_cf >= 0:
        st.sidebar.markdown(f"**Net CF:** :green[{format_currency(net_cf)}]")
    else:
        st.sidebar.markdown(f"**Net CF:** :red[{format_currency(net_cf)}]")
