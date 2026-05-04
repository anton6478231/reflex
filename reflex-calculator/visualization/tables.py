"""
Модуль для отображения детальных таблиц
"""
import streamlit as st
import pandas as pd
from typing import List, Dict
from utils.formatters import format_currency


def display_detailed_table(
    cash_flow_results: List[Dict],
    revenue_results: List[Dict],
    costs_results: List[Dict]
):
    """
    Отображение детальной таблицы расчетов (экспандируемая)
    """
    with st.expander("📋 Показать детальную таблицу расчетов"):
        st.caption(
            "**Сводная таблица по месяцам.** "
            "Revenue — суммарная выручка месяца. "
            "Fixed Costs — постоянные затраты (зарплаты, офис, инфраструктура). "
            "Variable Costs — переменные затраты (COGS устройств, логистика, поддержка, CAC). "
            "Total Costs = Fixed + Variable. "
            "Cash Flow = Revenue − Total Costs. "
            "Cumulative CF — нарастающим итогом: когда пересекает 0 снизу вверх — это точка безубыточности."
        )
        # Подготовка данных
        data = []

        has_active_clinics = any(r.get('active_clinics') is not None for r in revenue_results)
        has_patients = any(r.get('num_patients', 0) > 0 for r in revenue_results)

        for i, cf in enumerate(cash_flow_results):
            revenue = revenue_results[i]
            costs = costs_results[i]

            row = {
                'Месяц': cf['month'],
                'Revenue (₽)': cf['revenue'],
                'Fixed Costs (₽)': cf['fixed_costs'],
                'Variable Costs (₽)': cf['variable_costs'],
                'Total Costs (₽)': cf['total_costs'],
                'Cash Flow (₽)': cf['cash_flow'],
                'Cumulative CF (₽)': cf['cumulative_cash_flow'],
            }
            if has_active_clinics:
                row['Активных клиник'] = revenue.get('active_clinics', '')
            if has_patients:
                row['Пациентов (эфф.)'] = revenue.get('num_patients', 0)
                row['Устройств'] = revenue.get('devices_in_pool', 0)

            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Форматирование для отображения
        df_display = df.copy()
        for col in df_display.columns:
            if col != 'Месяц':
                df_display[col] = df_display[col].apply(lambda x: f"{x:,.0f}".replace(',', ' '))
        
        st.dataframe(df_display, use_container_width=True)
        
        # Кнопки экспорта
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Экспорт в CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Скачать CSV",
                data=csv,
                file_name="reflex_calculator_results.csv",
                mime="text/csv"
            )


def display_costs_breakdown(costs_results: List[Dict]):
    """
    Детализация затрат по категориям
    """
    with st.expander("💰 Детализация затрат по категориям"):
        st.caption(
            "**Fixed Costs** одинаковы каждый месяц независимо от числа пациентов и устройств: "
            "зарплаты команды, аренда офиса, инфраструктура (серверы, облако), юридика, прочее. "
            "**Variable Costs** растут вместе с бизнесом: COGS (себестоимость устройства при производстве), "
            "логистика (доставка пациенту), поддержка (ежемесячно на каждого активного пациента), "
            "CAC (привлечение клиник и пациентов, разово). "
            "Кастомные статьи (🔧) добавлены вами вручную."
        )
        for costs in costs_results:
            month = costs['month']
            st.markdown(f"#### Месяц {month}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Fixed Costs:**")
                st.markdown(f"- Команда: {format_currency(costs['fixed_costs']['team_salaries'])}")
                st.markdown(f"- Инфраструктура: {format_currency(costs['fixed_costs']['infrastructure_fixed'])}")
                st.markdown(f"- Офис: {format_currency(costs['fixed_costs']['office_rent'])}")
                st.markdown(f"- Юридика: {format_currency(costs['fixed_costs']['legal_services'])}")
                st.markdown(f"- Прочее: {format_currency(costs['fixed_costs']['other_fixed'])}")
                
                # Кастомные Fixed Costs
                if 'custom_breakdown' in costs['fixed_costs']:
                    for name, value in costs['fixed_costs']['custom_breakdown'].items():
                        if value > 0:
                            st.markdown(f"- 🔧 {name}: {format_currency(value)}")
                
                st.markdown(f"**Total Fixed:** {format_currency(costs['fixed_costs']['total'])}")
            
            with col2:
                st.markdown("**Variable Costs:**")
                st.markdown(f"- COGS: {format_currency(costs['variable_costs']['cogs'])}")
                st.markdown(f"- Логистика: {format_currency(costs['variable_costs']['logistics'])}")
                st.markdown(f"- Поддержка: {format_currency(costs['variable_costs']['support'])}")
                st.markdown(f"- CAC: {format_currency(costs['variable_costs']['cac'])}")
                st.markdown(f"- Инфраструктура: {format_currency(costs['variable_costs']['infrastructure_variable'])}")
                
                # Кастомные Variable Costs
                if 'custom_breakdown' in costs['variable_costs']:
                    for name, value in costs['variable_costs']['custom_breakdown'].items():
                        if value > 0:
                            st.markdown(f"- 🔧 {name}: {format_currency(value)}")
                
                st.markdown(f"**Total Variable:** {format_currency(costs['variable_costs']['total'])}")
            
            st.markdown("---")


def display_revenue_breakdown(revenue_results: List[Dict], model_type: str):
    """
    Детализация выручки по компонентам.
    Для Model A с per-batch трекингом показывает таблицу по пачкам клиник.
    """
    with st.expander("💵 Детализация выручки"):
        if model_type == 'model_a':
            st.caption(
                "**Model A (B2B).** Выручка состоит из двух частей: "
                "Setup Fee — разовый платёж клиники при покупке устройств (возникает в месяц первой продажи или расширения парка); "
                "Subscription — ежемесячный recurring revenue за каждое устройство в парке. "
                "Парк каждой «пачки» клиник независим: устройства одной пачки не используются другой. "
                "Рост пациентов стартует с месяца подключения пачки."
            )
        elif model_type == 'model_b':
            st.caption(
                "**Model B (B2B2C).** Пациент платит клинике за аренду устройства. "
                "Gross Revenue — полная арендная плата всех активных пациентов. "
                "Clinic Commission — доля, которую забирает клиника (задаётся в % от Gross). "
                "Net Revenue = Gross − Commission — деньги, которые остаются ReFlex. "
                "Именно Net Revenue формирует строку Revenue в Cash Flow."
            )
        elif model_type == 'model_ab':
            st.caption(
                "**Model A+B (Гибрид).** Клиника покупает парк устройств у ReFlex (Setup Fee + Subscription, как в A), "
                "а пациенты арендуют устройства у клиники. "
                "ReFlex получает долю от аренды (Net Rental = Gross Rental × (1 − Commission)). "
                "Итоговая выручка = Setup Fee + Subscription + Net Rental."
            )
        for revenue in revenue_results:
            month = revenue['month']
            st.markdown(f"#### Месяц {month}")

            if model_type == 'model_a':
                active_clinics = revenue.get('active_clinics')
                if active_clinics is not None:
                    st.caption(f"Активных клиник: **{active_clinics}**")

                st.markdown(
                    f"- Setup Fee (новые/расширения устройств): {format_currency(revenue.get('setup_revenue', 0))}"
                )
                st.markdown(
                    f"- Subscription (весь парк): {format_currency(revenue.get('subscription_revenue', 0))}"
                )
                st.markdown(
                    f"- Устройств в парке: **{revenue.get('devices_in_pool', revenue.get('num_devices', 0))}** "
                    f"(новых в этом месяце: {revenue.get('additional_devices', 0)})"
                )
                if revenue.get('num_patients', 0) > 0 or revenue.get('billable_patients', 0) > 0:
                    st.markdown(
                        f"- Пациентов (эффективных): **{revenue.get('num_patients', revenue.get('billable_patients', 0))}** "
                        f"| когорта: {revenue.get('cohort_active_patients', 0)} "
                        f"| после churn: {revenue.get('patients_after_churn', 0)}"
                    )

                # Детализация по пачкам
                batches = revenue.get('clinic_batches_detail', [])
                if batches:
                    st.markdown("**По пачкам клиник:**")
                    batch_data = []
                    for b in batches:
                        batch_data.append({
                            "Старт пачки (M)": b["batch_start_month"],
                            "Относит. M": b["relative_month"],
                            "Клиник": b["count"],
                            "Парк (кнт. мин.)": b["contractual_pool"],
                            "Парк (факт)": b["devices_in_pool"],
                            "Новых уст.": b["additional_devices"],
                            "Новых пац.": b["new_patients"],
                            "Когорта": b["cohort_active_patients"],
                            "После churn": b["patients_after_churn"],
                            "Эфф. пац.": b["billable_patients"],
                            "Setup (₽)": int(b["setup_revenue"]),
                            "Sub (₽)": int(b["subscription_revenue"]),
                        })
                    st.dataframe(pd.DataFrame(batch_data), use_container_width=True, hide_index=True)
                    st.caption(
                        "Каждая пачка — независимые когорты и парк. "
                        "Устройства одной пачки не доступны другой. "
                        "Рост пациентов считается от месяца старта пачки."
                    )

            elif model_type == 'model_b':
                st.markdown(f"- Gross Revenue: {format_currency(revenue.get('gross_revenue', 0))}")
                st.markdown(f"- Clinic Commission: {format_currency(revenue.get('clinic_commission', 0))}")
                st.markdown(f"- Net Revenue: {format_currency(revenue.get('net_revenue', 0))}")
                st.markdown(f"- Пациентов: {revenue.get('num_patients', 0)}")

            elif model_type == 'model_ab':
                st.markdown(f"- Setup Fee: {format_currency(revenue.get('setup_revenue', 0))}")
                st.markdown(f"- Subscription: {format_currency(revenue.get('subscription_revenue', 0))}")
                st.markdown(f"- Rental Net Revenue: {format_currency(revenue.get('rental_net_revenue', 0))}")
                st.markdown(f"- Устройств: {revenue.get('num_devices', 0)}")
                st.markdown(f"- Пациентов: {revenue.get('num_patients', 0)}")

            st.markdown(f"**Total Revenue:** {format_currency(revenue.get('total_revenue', 0))}")
            st.markdown("---")
