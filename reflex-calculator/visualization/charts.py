"""
Модуль для создания интерактивных графиков с Plotly
"""
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict
import pandas as pd


def create_cash_flow_chart(
    cash_flow_results: List[Dict],
    initial_investment: float = 0.0,
    npv_series: List[float] | None = None,
    annual_discount_rate: float = 0.0,
    rnd_results: List[Dict] | None = None,
    rnd_npv_series: List[float] | None = None,
) -> go.Figure:
    """
    График 1: Cash Flow по месяцам (основной line chart).

    Показывает Revenue, Total Costs, Cash Flow, Cumulative CF.
    Если rnd_results передан — в начале графика добавляется R&D фаза
    со своими барами и подсветкой фона. Ось X: «R&D N», «М1», «М2», ...
    Нумерация рыночных месяцев начинается с М1 (независимо от длины R&D).
    Если initial_investment > 0 — дополнительная пунктирная линия
    порога окупаемости (CumCF должен пересечь это значение).
    Если rnd_npv_series и/или npv_series переданы — рисует единую непрерывную
    линию NPV, начиная с первого R&D месяца (или M1, если R&D выключен).
    """
    rnd_count = len(rnd_results) if rnd_results else 0
    market_count = len(cash_flow_results)
    total_points = rnd_count + market_count

    # ── Строим единую ось X ─────────────────────────────────────────
    x_labels: List[str] = []
    for r in range(1, rnd_count + 1):
        x_labels.append(f"R&D {r}")
    for m in range(1, market_count + 1):
        x_labels.append(f"М{m}")

    # ── R&D серии ───────────────────────────────────────────────────
    rnd_costs = [abs(r["cash_flow"]) for r in (rnd_results or [])]
    rnd_cf = [r["cash_flow"] for r in (rnd_results or [])]
    rnd_cum = [r["cumulative_cash_flow"] for r in (rnd_results or [])]

    # ── Market серии ────────────────────────────────────────────────
    market_revenue = [cf["revenue"] for cf in cash_flow_results]
    market_costs = [cf["total_costs"] for cf in cash_flow_results]
    market_cf = [cf["cash_flow"] for cf in cash_flow_results]
    # Cumulative CF рыночных месяцев начинается от конца R&D кумулятивного CF
    rnd_cum_last = rnd_cum[-1] if rnd_cum else 0.0
    market_cum_raw = [cf["cumulative_cash_flow"] for cf in cash_flow_results]
    # Добавляем смещение: cumulative CF рыночной фазы = rnd_cum_last + рыночный накопленный CF
    market_cum = [rnd_cum_last + v for v in market_cum_raw]

    fig = go.Figure()

    # ── R&D фаза: затемнённый фон ───────────────────────────────────
    if rnd_count > 0:
        fig.add_vrect(
            x0=-0.5,
            x1=rnd_count - 0.5,
            fillcolor="#FEF3C7",
            opacity=0.35,
            layer="below",
            line_width=0,
        )
        # Вертикальная граница R&D / Market
        fig.add_vline(
            x=rnd_count - 0.5,
            line_dash="dash",
            line_color="#D97706",
            line_width=2,
            annotation_text="Выход на рынок",
            annotation_position="top right",
            annotation_font_color="#D97706",
            annotation_font_size=12,
        )

        # R&D Total Costs bar (столбчатый, оранжевый)
        fig.add_trace(go.Bar(
            x=x_labels[:rnd_count],
            y=rnd_costs,
            name="R&D Затраты",
            marker_color="#F59E0B",
            opacity=0.7,
            width=0.5,
        ))

        # R&D Cash Flow (negative)
        fig.add_trace(go.Scatter(
            x=x_labels[:rnd_count],
            y=rnd_cf,
            mode="lines+markers",
            name="R&D Cash Flow",
            line=dict(color="#D97706", width=2, dash="dot"),
            marker=dict(size=7, symbol="diamond"),
        ))

        # R&D Cumulative CF
        fig.add_trace(go.Scatter(
            x=x_labels[:rnd_count],
            y=rnd_cum,
            mode="lines+markers",
            name="R&D Cumulative CF",
            line=dict(color="#92400E", width=2, dash="dash"),
            marker=dict(size=6, symbol="diamond"),
        ))

    # ── Рыночная фаза: основные линии ───────────────────────────────
    fig.add_trace(go.Scatter(
        x=x_labels[rnd_count:], y=market_revenue,
        mode="lines+markers", name="Revenue",
        line=dict(color="#10B981", width=3), marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=x_labels[rnd_count:], y=market_costs,
        mode="lines+markers", name="Total Costs",
        line=dict(color="#EF4444", width=3), marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=x_labels[rnd_count:], y=market_cf,
        mode="lines+markers", name="Cash Flow",
        line=dict(color="#3B82F6", width=3), marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=x_labels[rnd_count:], y=market_cum,
        mode="lines+markers", name="Cumulative CF",
        line=dict(color="#8B5CF6", width=2, dash="dash"), marker=dict(size=6),
    ))

    # ── NPV: единая непрерывная линия от первого R&D (или M1) до конца ─
    _full_npv: List[float] = list(rnd_npv_series or []) + list(npv_series or [])
    if _full_npv:
        rate_pct = annual_discount_rate * 100
        _npv_x = x_labels[:len(_full_npv)]
        fig.add_trace(go.Scatter(
            x=_npv_x, y=_full_npv,
            mode="lines+markers",
            name=f"NPV = −I₀ + PV(CF) | {rate_pct:.0f}% год.",
            line=dict(color="#F59E0B", width=2, dash="dot"), marker=dict(size=5),
        ))

    # ── Вспомогательные линии ───────────────────────────────────────
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

    if initial_investment and initial_investment > 0:
        fig.add_hline(
            y=initial_investment,
            line_dash="dashdot",
            line_color="#F59E0B",
            opacity=0.8,
            annotation_text=f"Порог окупаемости (+{initial_investment:,.0f} ₽ вложений)",
            annotation_position="right",
            annotation_font_color="#F59E0B",
        )

    # Заголовок с учётом R&D
    title_text = "Cash Flow по месяцам"
    if rnd_count > 0:
        title_text = f"Cash Flow: R&D ({rnd_count} мес) + Рынок ({market_count} мес)"

    fig.update_layout(
        title=title_text,
        xaxis_title="Период",
        yaxis_title="Рубли (₽)",
        hovermode="x unified",
        template="plotly_white",
        height=520,
        barmode="overlay",
    )

    return fig


def create_revenue_breakdown_chart(
    revenue_results: List[Dict],
    model_type: str,
    selected_month: int = 1,
) -> go.Figure:
    """
    График 2: Структура Revenue (pie chart или stacked bar)
    """
    if not revenue_results:
        revenue_results = [{"month": 1}]
    month_idx = max(0, min(len(revenue_results) - 1, int(selected_month) - 1))
    revenue_for_month = revenue_results[month_idx]
    month_number = revenue_for_month.get("month", month_idx + 1)
    
    if model_type == 'model_a':
        labels = ['Setup Fee', 'Subscription']
        values = [
            revenue_for_month.get('setup_revenue', 0),
            revenue_for_month.get('subscription_revenue', 0)
        ]
        colors = ['#3B82F6', '#10B981']
        
    elif model_type == 'model_b':
        labels = ['Net Revenue (ReFlex)', 'Clinic Commission']
        values = [
            revenue_for_month.get('net_revenue', 0),
            revenue_for_month.get('clinic_commission', 0)
        ]
        colors = ['#10B981', '#F59E0B']
        
    elif model_type == 'model_ab':
        labels = ['Setup Fee', 'Subscription', 'Rental Net Revenue']
        values = [
            revenue_for_month.get('setup_revenue', 0),
            revenue_for_month.get('subscription_revenue', 0),
            revenue_for_month.get('rental_net_revenue', 0)
        ]
        colors = ['#3B82F6', '#10B981', '#8B5CF6']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hole=0.3,
        textinfo='label+percent',
        textposition='auto'
    )])
    
    fig.update_layout(
        title=f'Структура Revenue (Месяц {month_number})',
        template='plotly_white',
        height=400
    )
    
    return fig


def create_cohort_dynamics_chart(revenue_results: List[Dict], model_type: str) -> go.Figure:
    """
    График когорт: новые пациенты, сумма активных когорт и эффективная база (после churn и загрузки).
    Для Model A с per-batch трекингом добавляет trace «Активных клиник» (secondary y-axis)
    и вертикальные аннотации на месяцах старта новых пачек.
    """
    months = [row.get("month", idx + 1) for idx, row in enumerate(revenue_results)]

    has_flow = any(
        int(row.get("new_patients", 0) or 0) > 0 or int(row.get("cohort_active_patients", 0) or 0) > 0
        for row in revenue_results
    )
    if model_type not in ["model_b", "model_ab", "model_a"] or not has_flow:
        fig = go.Figure()
        fig.add_annotation(
            text=(
                "Нет потока пациентов: для A задайте «# новых пациентов/клинику (месяц 1)» > 0; "
                "для B / A+B параметры уже в Revenue."
            ),
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
        fig.update_layout(
            title="Когортная динамика пациентов",
            template="plotly_white",
            height=420,
        )
        return fig

    # Для model_a: есть ли per-batch данные (active_clinics из нескольких пачек)?
    has_multi_batch = model_type == "model_a" and any(
        row.get("active_clinics") is not None for row in revenue_results
    )

    # Используем secondary_y только для model_a с активными клиниками
    from plotly.subplots import make_subplots
    if has_multi_batch:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    new_patients = [row.get("new_patients", 0) for row in revenue_results]
    cohort_sum = [row.get("cohort_active_patients", row.get("num_patients", 0)) for row in revenue_results]
    effective = [row.get("num_patients", 0) for row in revenue_results]
    released_patients = [row.get("released_patients", 0) for row in revenue_results]

    _bar_kw = dict(secondary_y=False) if has_multi_batch else {}
    _line_kw = dict(secondary_y=False) if has_multi_batch else {}

    fig.add_trace(
        go.Bar(
            name="Новая когорта (пациенты)",
            x=months,
            y=new_patients,
            marker_color="#3B82F6",
        ),
        **_bar_kw,
    )
    fig.add_trace(
        go.Scatter(
            name="Активные (сумма когорт, до churn)",
            x=months,
            y=cohort_sum,
            mode="lines+markers",
            line=dict(color="#6366F1", width=2, dash="dash"),
            marker=dict(size=7),
        ),
        **_line_kw,
    )
    fig.add_trace(
        go.Scatter(
            name="Эффективные (выручка/затраты)",
            x=months,
            y=effective,
            mode="lines+markers",
            line=dict(color="#10B981", width=3),
            marker=dict(size=8),
        ),
        **_line_kw,
    )
    fig.add_trace(
        go.Scatter(
            name="Вышли из когорты",
            x=months,
            y=released_patients,
            mode="lines+markers",
            line=dict(color="#F59E0B", width=2, dash="dot"),
            marker=dict(size=7),
        ),
        **_line_kw,
    )

    # --- Model A per-batch: active_clinics + аннотации пачек ---
    if has_multi_batch:
        active_clinics = [row.get("active_clinics", 0) for row in revenue_results]
        fig.add_trace(
            go.Scatter(
                name="Активных клиник",
                x=months,
                y=active_clinics,
                mode="lines+markers",
                line=dict(color="#EC4899", width=2, dash="longdash"),
                marker=dict(size=7, symbol="diamond"),
            ),
            secondary_y=True,
        )

        # Находим месяцы старта новых пачек (когда active_clinics растёт)
        batch_start_months = []
        prev_clinics = 0
        for row in revenue_results:
            m = row.get("month", 0)
            c = row.get("active_clinics", 0) or 0
            if c > prev_clinics and m > 1:
                batch_start_months.append(m)
            prev_clinics = c

        shapes = []
        annotations = []
        for bm in batch_start_months:
            shapes.append(dict(
                type="line",
                x0=bm, x1=bm,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="#EC4899", width=1.5, dash="dot"),
            ))
            annotations.append(dict(
                x=bm, y=1.02,
                xref="x", yref="paper",
                text=f"Пачка M{bm}",
                showarrow=False,
                font=dict(size=10, color="#EC4899"),
                xanchor="center",
            ))
        fig.update_layout(shapes=shapes, annotations=annotations)
        fig.update_yaxes(title_text="Количество пациентов", secondary_y=False)
        fig.update_yaxes(title_text="Активных клиник", secondary_y=True)

    fig.update_layout(
        title="Когортная динамика пациентов" + (" + активные клиники" if has_multi_batch else ""),
        xaxis_title="Месяц",
        yaxis_title="Количество пациентов",
        template="plotly_white",
        height=460,
        hovermode="x unified",
    )
    return fig


def create_costs_structure_chart(costs_results: List[Dict]) -> go.Figure:
    """
    График 3: Структура Costs (stacked bar по месяцам)
    """
    months = [costs['month'] for costs in costs_results]
    
    # Fixed costs компоненты
    team_salaries = [costs['fixed_costs']['team_salaries'] for costs in costs_results]
    infrastructure = [costs['fixed_costs']['infrastructure_fixed'] for costs in costs_results]
    office = [costs['fixed_costs']['office_rent'] for costs in costs_results]
    legal = [costs['fixed_costs']['legal_services'] for costs in costs_results]
    other_fixed = [costs['fixed_costs']['other_fixed'] for costs in costs_results]
    
    # Variable costs компоненты
    cogs = [costs['variable_costs']['cogs'] for costs in costs_results]
    logistics = [costs['variable_costs']['logistics'] for costs in costs_results]
    support = [costs['variable_costs']['support'] for costs in costs_results]
    cac = [costs['variable_costs']['cac'] for costs in costs_results]
    
    fig = go.Figure()
    
    # Fixed costs
    fig.add_trace(go.Bar(name='Команда', x=months, y=team_salaries, marker_color='#EF4444'))
    fig.add_trace(go.Bar(name='Инфраструктура', x=months, y=infrastructure, marker_color='#F59E0B'))
    fig.add_trace(go.Bar(name='Офис', x=months, y=office, marker_color='#FCD34D'))
    fig.add_trace(go.Bar(name='Юридика', x=months, y=legal, marker_color='#FBBF24'))
    fig.add_trace(go.Bar(name='Прочее', x=months, y=other_fixed, marker_color='#FDE68A'))
    
    # Кастомные Fixed Costs
    if 'custom_breakdown' in costs_results[0]['fixed_costs']:
        for custom_name in costs_results[0]['fixed_costs']['custom_breakdown'].keys():
            custom_values = [
                costs['fixed_costs']['custom_breakdown'].get(custom_name, 0) 
                for costs in costs_results
            ]
            fig.add_trace(go.Bar(
                name=f'Custom: {custom_name}', 
                x=months, 
                y=custom_values, 
                marker_color='#FB923C'
            ))
    
    # Variable costs
    fig.add_trace(go.Bar(name='COGS', x=months, y=cogs, marker_color='#8B5CF6'))
    fig.add_trace(go.Bar(name='Логистика', x=months, y=logistics, marker_color='#A78BFA'))
    fig.add_trace(go.Bar(name='Поддержка', x=months, y=support, marker_color='#C4B5FD'))
    fig.add_trace(go.Bar(name='CAC', x=months, y=cac, marker_color='#DDD6FE'))
    
    # Кастомные Variable Costs
    if 'custom_breakdown' in costs_results[0]['variable_costs']:
        for custom_name in costs_results[0]['variable_costs']['custom_breakdown'].keys():
            custom_values = [
                costs['variable_costs']['custom_breakdown'].get(custom_name, 0) 
                for costs in costs_results
            ]
            fig.add_trace(go.Bar(
                name=f'Custom: {custom_name}', 
                x=months, 
                y=custom_values, 
                marker_color='#E0E7FF'
            ))
    
    fig.update_layout(
        title='Структура затрат по месяцам',
        xaxis_title='Месяц',
        yaxis_title='Рубли (₽)',
        barmode='stack',
        template='plotly_white',
        height=450
    )
    
    return fig


def create_breakeven_chart(cash_flow_results: List[Dict], breakeven_result: Dict) -> go.Figure:
    """
    График 4: Breakeven Analysis с проекцией за горизонт расчёта + 6 месяцев.
    """
    n = len(cash_flow_results)
    proj_total = max(n + 6, 12)  # показываем данные + не менее 6 месяцев проекции
    months = list(range(1, proj_total + 1))

    # Берем последний месяц CF для проекции
    last_cf = cash_flow_results[-1]['cash_flow']
    last_cumulative = cash_flow_results[-1]['cumulative_cash_flow']

    # Проекция cumulative CF
    cumulative_cf_projected = []
    current_cumulative = 0

    for i in range(1, proj_total + 1):
        if i <= n:
            current_cumulative = cash_flow_results[i - 1]['cumulative_cash_flow']
        else:
            # Проецируем с последним CF
            current_cumulative += last_cf

        cumulative_cf_projected.append(current_cumulative)

    fig = go.Figure()

    # Фактические данные (сплошная линия)
    fig.add_trace(go.Scatter(
        x=months[:n],
        y=cumulative_cf_projected[:n],
        mode='lines+markers',
        name='Cumulative Cash Flow',
        line=dict(color='#3B82F6', width=3),
        marker=dict(size=6)
    ))

    # Проекция (пунктир)
    if proj_total > n:
        fig.add_trace(go.Scatter(
            x=months[n - 1:],
            y=cumulative_cf_projected[n - 1:],
            mode='lines',
            name='Проекция',
            line=dict(color='#3B82F6', width=2, dash='dot'),
            showlegend=True
        ))

    # Нулевая линия (breakeven)
    fig.add_hline(y=0, line_dash="dash", line_color="green",
                  annotation_text="Breakeven", annotation_position="right")

    # Если breakeven достигнут, помечаем точку
    if breakeven_result['reached']:
        breakeven_month = breakeven_result['breakeven_month']
        if breakeven_month <= proj_total:
            fig.add_trace(go.Scatter(
                x=[breakeven_month],
                y=[0],
                mode='markers',
                name='Breakeven Point',
                marker=dict(size=15, color='green', symbol='star')
            ))
    
    fig.update_layout(
        title=f"Точка безубыточности {'достигнута через ' + str(breakeven_result['breakeven_month']) + ' мес' if breakeven_result['reached'] else 'не достигается'}",
        xaxis_title='Месяц',
        yaxis_title='Cumulative Cash Flow (₽)',
        template='plotly_white',
        height=450
    )
    
    return fig


def create_sensitivity_chart(sensitivity_results: List[Dict]) -> go.Figure:
    """
    График 5: Sensitivity Analysis (tornado chart)
    """
    # Берем топ-5 параметров по impact
    top_params = sensitivity_results[:5]
    
    parameters = [s['parameter'] for s in top_params]
    cf_increase = [s['cf_increase'] for s in top_params]
    cf_decrease = [-s['cf_decrease'] for s in top_params]  # Отрицательные для tornado
    
    fig = go.Figure()
    
    # Положительное влияние (увеличение параметра)
    fig.add_trace(go.Bar(
        name='Увеличение +20%',
        y=parameters,
        x=cf_increase,
        orientation='h',
        marker=dict(color='#10B981')
    ))
    
    # Отрицательное влияние (уменьшение параметра)
    fig.add_trace(go.Bar(
        name='Уменьшение -20%',
        y=parameters,
        x=cf_decrease,
        orientation='h',
        marker=dict(color='#EF4444')
    ))
    
    fig.update_layout(
        title='Анализ чувствительности (влияние на Cash Flow)',
        xaxis_title='Изменение Cash Flow (₽)',
        barmode='relative',
        template='plotly_white',
        height=400
    )
    
    return fig


def create_true_breakeven_chart(
    revenue_results: List[Dict],
    costs_results: List[Dict],
    model_type: str,
    selected_month: int,
) -> go.Figure:
    """
    График 4: Точка безубыточности (BEP).

    Для выбранного месяца строит:
      - Линию Revenue(N) — как растёт выручка при N активных юнитах
      - Линию Costs(N) = Fixed + Variable(N) — как растут затраты
      - Точку пересечения N* — собственно BEP
      - Зоны: красная (убыток, N < N*), зелёная (прибыль, N > N*)
      - Вертикальный маркер "as is" на фактическом N текущего месяца

    X-axis: количество активных «платящих» юнитов:
      - Model A: devices_in_pool (подписка идёт на весь парк)
      - Model B: billable_patients (аренда только с активных пациентов)
      - Model AB: devices_in_pool (оба потока зависят от парка)
    """
    month_idx = max(0, min(len(revenue_results) - 1, int(selected_month) - 1))
    rev = revenue_results[month_idx]
    cost = costs_results[month_idx]

    # Определяем N_actual в зависимости от модели
    if model_type == "model_b":
        N_actual = int(rev.get("billable_patients", rev.get("num_patients", 0)) or 0)
        x_label = "Активных пациентов"
    else:
        N_actual = int(rev.get("devices_in_pool", rev.get("num_devices", 0)) or 0)
        x_label = "Устройств в парке"

    R_actual = float(rev.get("total_revenue", 0.0))
    F_actual = float(cost["fixed_costs"]["total"])
    V_actual = float(cost["variable_costs"]["total"])

    # Средние на юнит (защита от деления на 0)
    if N_actual > 0:
        rev_per_unit = R_actual / N_actual
        var_per_unit = V_actual / N_actual
    else:
        # Fallback: нет данных — строим по минимальным ненулевым значениям
        rev_per_unit = 0.0
        var_per_unit = 0.0

    # Margin per unit
    margin_per_unit = rev_per_unit - var_per_unit

    # Точка безубыточности N*
    if margin_per_unit > 0:
        N_star = F_actual / margin_per_unit
    else:
        N_star = None  # BEP недостижим при таких ценах

    # Диапазон X для графика
    ref_n = max(N_actual, N_star if N_star else 0, 1)
    x_max = int(ref_n * 2.2) + 1
    x_range = list(range(0, x_max + 1))

    revenue_line = [rev_per_unit * n for n in x_range]
    costs_line = [F_actual + var_per_unit * n for n in x_range]

    fig = go.Figure()

    # Зона прибыли / убытка
    if N_star is not None:
        n_star_int = int(N_star)
        # Убыточная зона (левее N*)
        x_loss = list(range(0, min(n_star_int + 2, x_max + 1)))
        fig.add_trace(go.Scatter(
            x=x_loss + x_loss[::-1],
            y=[rev_per_unit * n for n in x_loss] + [F_actual + var_per_unit * n for n in x_loss[::-1]],
            fill='toself',
            fillcolor='rgba(239,68,68,0.08)',
            line=dict(color='rgba(0,0,0,0)'),
            showlegend=False,
            hoverinfo='skip',
            name='_loss_zone',
        ))
        # Прибыльная зона (правее N*)
        x_profit = list(range(n_star_int, x_max + 1))
        fig.add_trace(go.Scatter(
            x=x_profit + x_profit[::-1],
            y=[rev_per_unit * n for n in x_profit] + [F_actual + var_per_unit * n for n in x_profit[::-1]],
            fill='toself',
            fillcolor='rgba(16,185,129,0.08)',
            line=dict(color='rgba(0,0,0,0)'),
            showlegend=False,
            hoverinfo='skip',
            name='_profit_zone',
        ))

    # Линия Revenue
    fig.add_trace(go.Scatter(
        x=x_range, y=revenue_line,
        mode='lines',
        name='Выручка (Revenue)',
        line=dict(color='#10B981', width=3),
    ))

    # Линия Costs
    fig.add_trace(go.Scatter(
        x=x_range, y=costs_line,
        mode='lines',
        name='Затраты (Costs)',
        line=dict(color='#EF4444', width=3),
    ))

    # Точка BEP N*
    if N_star is not None:
        bep_y = F_actual + var_per_unit * N_star
        fig.add_trace(go.Scatter(
            x=[N_star], y=[bep_y],
            mode='markers',
            name=f'BEP: N* = {N_star:.1f}',
            marker=dict(size=14, color='#F59E0B', symbol='star'),
        ))
        fig.add_vline(
            x=N_star,
            line_dash="dash",
            line_color="#F59E0B",
            opacity=0.6,
            annotation_text=f"N* = {N_star:.0f}",
            annotation_position="top right",
            annotation_font_color="#F59E0B",
        )

    # Вертикальная линия "as is" (фактическое N)
    if N_actual > 0:
        current_cf = R_actual - F_actual - V_actual
        is_profitable = current_cf >= 0
        as_is_color = "#10B981" if is_profitable else "#EF4444"
        as_is_label = (
            f"As is: {N_actual} юн. | +{current_cf:,.0f} ₽"
            if is_profitable
            else f"As is: {N_actual} юн. | {current_cf:,.0f} ₽"
        )
        fig.add_vline(
            x=N_actual,
            line_dash="dot",
            line_color=as_is_color,
            opacity=0.9,
            annotation_text=as_is_label,
            annotation_position="top left",
            annotation_font_color=as_is_color,
        )
        # Точка as-is на линии Revenue
        fig.add_trace(go.Scatter(
            x=[N_actual], y=[R_actual],
            mode='markers',
            name='Текущая выручка (as is)',
            marker=dict(size=10, color=as_is_color, symbol='circle'),
        ))
        # Точка as-is на линии Costs
        fig.add_trace(go.Scatter(
            x=[N_actual], y=[F_actual + V_actual],
            mode='markers',
            name='Текущие затраты (as is)',
            marker=dict(size=10, color=as_is_color, symbol='square'),
        ))

    # Подпись зон
    if N_star is not None:
        zone_text = (
            "Вы правее BEP — в зоне прибыли" if N_actual >= N_star
            else f"Вы левее BEP — нужно ещё {N_star - N_actual:.0f} юн. для выхода в плюс"
        )
    elif N_actual == 0:
        zone_text = "Нет активных юнитов в выбранном месяце"
    else:
        zone_text = "BEP недостижим: выручка на юнит ≤ переменных затрат на юнит"

    # Пояснение к осям: что такое N для данной модели
    model_note = {
        "model_a": "Model A: X = устройства в парке клиники (подписка начисляется на весь парк, включая незанятые)",
        "model_b": "Model B: X = активных платящих пациентов (аренда только с занятых устройств)",
        "model_ab": "Model A+B: X = устройства в парке (подписка со всего парка + аренда пациентов)",
    }.get(model_type, "")

    fig.update_layout(
        title=f"Точка безубыточности (BEP) — Месяц {selected_month}",
        xaxis_title=x_label,
        yaxis_title="Рубли (₽)",
        template="plotly_white",
        height=500,
        hovermode="x unified",
        annotations=[
            dict(
                x=0.01, y=0.98,
                xref="paper", yref="paper",
                text=zone_text,
                showarrow=False,
                font=dict(size=13, color="#1F2937"),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#D1D5DB",
                borderwidth=1,
                xanchor="left",
                yanchor="top",
            )
        ],
    )

    # Добавляем model_note как caption через subtitle-аннотацию
    if model_note:
        existing = list(fig.layout.annotations)
        existing.append(dict(
            x=0.5, y=-0.14,
            xref="paper", yref="paper",
            text=model_note,
            showarrow=False,
            font=dict(size=11, color="#6B7280"),
            xanchor="center",
        ))
        fig.update_layout(annotations=existing)

    return fig


def create_unit_economics_chart(unit_economics: Dict) -> go.Figure:
    """
    График 6: Unit Economics (bar chart с метриками)
    """
    metrics = ['LTV', 'CAC', 'LTV/CAC Ratio', 'Payback (мес)']
    values = [
        unit_economics.get('ltv', 0),
        unit_economics.get('cac', 0),
        unit_economics.get('ltv_cac_ratio', 0),
        unit_economics.get('payback_months', 0)
    ]
    
    # Цвета: зеленый если хороший, красный если плохой
    colors = [
        '#10B981' if values[0] > 0 else '#EF4444',
        '#F59E0B',
        '#10B981' if values[2] > 3 else '#EF4444',
        '#10B981' if values[3] < 6 else '#EF4444'
    ]
    
    fig = go.Figure(data=[
        go.Bar(
            x=metrics,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        title='Unit Economics (Model B)',
        yaxis_title='Значение',
        template='plotly_white',
        height=400
    )
    
    return fig
