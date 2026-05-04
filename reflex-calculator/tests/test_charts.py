from visualization.charts import (
    create_cohort_dynamics_chart,
    create_revenue_breakdown_chart,
)


def test_revenue_breakdown_uses_selected_month_for_model_a():
    revenue_results = [
        {"month": 1, "setup_revenue": 1000, "subscription_revenue": 100},
        {"month": 2, "setup_revenue": 0, "subscription_revenue": 300},
    ]

    fig = create_revenue_breakdown_chart(revenue_results, "model_a", selected_month=2)
    values = list(fig.data[0]["values"])

    assert values == [0, 300]
    assert "Месяц 2" in fig.layout.title.text


def test_revenue_breakdown_clamps_out_of_range_month():
    revenue_results = [
        {"month": 1, "net_revenue": 100, "clinic_commission": 20},
        {"month": 2, "net_revenue": 250, "clinic_commission": 50},
    ]

    fig = create_revenue_breakdown_chart(revenue_results, "model_b", selected_month=12)
    values = list(fig.data[0]["values"])

    assert values == [250, 50]
    assert "Месяц 2" in fig.layout.title.text


def test_cohort_chart_for_model_b_contains_expected_traces():
    revenue_results = [
        {
            "month": 1,
            "new_patients": 10,
            "cohort_active_patients": 10,
            "num_patients": 10,
            "released_patients": 0,
        },
        {
            "month": 2,
            "new_patients": 15,
            "cohort_active_patients": 25,
            "num_patients": 25,
            "released_patients": 0,
        },
        {
            "month": 3,
            "new_patients": 22,
            "cohort_active_patients": 47,
            "num_patients": 47,
            "released_patients": 0,
        },
    ]

    fig = create_cohort_dynamics_chart(revenue_results, "model_b")

    assert len(fig.data) == 4
    assert fig.data[0]["name"] == "Новая когорта (пациенты)"
    assert list(fig.data[0]["y"]) == [10, 15, 22]
    assert fig.data[1]["name"] == "Активные (сумма когорт, до churn)"
    assert list(fig.data[1]["y"]) == [10, 25, 47]
    assert fig.data[2]["name"] == "Эффективные (выручка/затраты)"
    assert list(fig.data[2]["y"]) == [10, 25, 47]


def test_cohort_chart_for_model_a_shows_annotation():
    fig = create_cohort_dynamics_chart([{"month": 1}], "model_a")

    assert len(fig.data) == 0
    assert len(fig.layout.annotations) == 1
