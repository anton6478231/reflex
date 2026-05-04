"""
Панель аудита формул: пошаговые выражения и сверка с фактическими результатами расчёта.
"""
from __future__ import annotations

import streamlit as st

from models.formula_trace import (
    build_executable_snippet,
    trace_cash_flow_month,
    trace_revenue_month,
)


def render_formula_auditor(
    model_type: str,
    revenue_params: dict,
    num_months: int,
    revenue_results: list,
    costs_results: list,
    cash_flow_results: list,
    assumptions: dict | None = None,
) -> None:
    st.markdown("### 🔬 Аудит формул (живые вычисления)")
    st.caption(
        "Таблица повторяет логику `models/revenue.py` и `models/cash_flow.py`. "
        "Колонка «Сверка» сравнивает шаг с фактическим словарём результата. "
        "Ниже — готовый фрагмент на Python с подставленными числами: его можно скопировать и выполнить."
    )

    month_pick = st.selectbox(
        "Месяц для разбора",
        options=list(range(1, num_months + 1)),
        format_func=lambda m: f"Месяц {m}",
        key="formula_audit_month",
    )
    idx = month_pick - 1
    prev = None
    if idx > 0 and "num_patients" in revenue_results[idx - 1]:
        prev = int(revenue_results[idx - 1]["num_patients"])

    rev_actual = revenue_results[idx]
    cost_actual = costs_results[idx]
    cf_actual = cash_flow_results[idx]

    st.markdown("#### Revenue")
    rows = trace_revenue_month(
        model_type, revenue_params, month_pick, prev, rev_actual, assumptions=assumptions
    )
    for title, snippet, val, note in rows:
        with st.expander(f"{title} → **{_fmt_display(val)}**", expanded=False):
            st.code(snippet, language="python")
            st.caption(note)

    st.markdown("#### Cash flow (итог месяца)")
    rev_tot = float(rev_actual.get("total_revenue", rev_actual.get("net_revenue", 0)))
    ft = float(cost_actual["fixed_costs"]["total"])
    vt = float(cost_actual["variable_costs"]["total"])
    cf_rows = trace_cash_flow_month(rev_tot, ft, vt, cf_actual)
    for title, snippet, val, note in cf_rows:
        with st.expander(f"{title} → **{_fmt_display(val)}**", expanded=False):
            st.code(snippet, language="python")
            st.caption(note)

    snippet = build_executable_snippet(model_type, revenue_params, month_pick, prev)
    st.markdown("#### Копируемый фрагмент (все числа подставлены)")
    st.code(snippet, language="python")

    with st.expander("▶ Выполнить фрагмент внутри приложения (проверка)", expanded=False):
        if st.button("Запустить exec() этого кода", key="exec_formula_snippet"):
            try:
                loc: dict = {}
                builtins_safe = {"int": int, "float": float, "round": round, "abs": abs}
                exec(snippet, {"__builtins__": builtins_safe}, loc)
                st.success("Результат (локальные переменные после выполнения):")
                out = {}
                for k, v in loc.items():
                    if k.startswith("_"):
                        continue
                    if isinstance(v, (int, float)):
                        out[k] = float(v)
                    else:
                        out[k] = str(v)
                st.json(out)
                tr = float(loc.get("total_revenue", loc.get("net_revenue", 0)))
                if abs(tr - rev_tot) > 0.02:
                    st.warning(f"total_revenue из exec ({tr}) ≠ revenue в расчёте ({rev_tot}) — проверьте фрагмент.")
                else:
                    st.caption("Совпадает с выручкой месяца в расчёте.")
            except Exception as e:
                st.error(f"Ошибка выполнения: {e}")


def _fmt_display(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v)):,}".replace(",", " ") + " ₽"
    return f"{v:,.2f}".replace(",", " ") + " ₽"
