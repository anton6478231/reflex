"""
Интерактивный калькулятор финансово-экономической модели ReFlex

Главное приложение на Streamlit
"""
import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import date

# Импорт модулей проекта
from models import (
    calculate_revenue_for_months,
    calculate_costs_for_months,
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
    calculate_min_rental_price_for_breakeven,
    calculate_unit_economics_from_params,
    calculate_sensitivity_analysis,
    calculate_npv_series,
    calculate_bank_allocation,
    bank_exhausted_month,
    months_covered_by_bank,
    bank_balance_series,
    build_grant_matrix,
    calculate_rnd_cash_flows,
    get_total_rnd_cost,
    get_rnd_cost_by_month,
    validate_rnd_vs_bank,
    ensure_matrix_size,
    build_empty_matrix,
    DEFAULT_RND_CATEGORIES,
    MAX_RND_MONTHS,
)

from visualization import (
    create_cash_flow_chart,
    create_revenue_breakdown_chart,
    create_cohort_dynamics_chart,
    create_costs_structure_chart,
    create_breakeven_chart,
    create_true_breakeven_chart,
    create_sensitivity_chart,
    create_unit_economics_chart,
    display_kpi_cards,
    display_kpi_summary,
    display_detailed_table,
    display_costs_breakdown,
    display_revenue_breakdown,
    render_formula_auditor,
)

from utils import (
    format_currency,
    validate_all_params,
    export_to_excel,
    export_to_excel_with_formulas,
    export_to_json,
    build_bp04_fem_snapshot_markdown,
    export_to_msp_excel,
    SNAPSHOT_SCHEMA_VERSION,
    build_config_snapshot,
    preflight_config_snapshot,
    apply_config_snapshot,
)

MAX_MONTHS = 36  # максимальный горизонт планирования

# Настройка страницы
# Заголовок
st.title("📊 Калькулятор финансово-экономической модели ReFlex")
st.markdown("Интерактивное моделирование финансов от 1 до 36 месяцев")

toolbar_left, toolbar_right = st.columns([0.62, 0.38], gap="small")
with toolbar_left:
    st.markdown("")
config_actions_placeholder = toolbar_right.container(key="config_actions_top")

# Информационный блок
with st.expander("ℹ️ Новые возможности калькулятора"):
    st.markdown("""
    ### Что нового:
    
    1. **Сохранение настроек** — при переключении между моделями A/B/A+B настройки сохраняются
    2. **Выбор горизонта** — можно выбрать от 1 до 36 месяцев для расчетов
    3. **Кастомные параметры** — добавляйте свои статьи затрат в Fixed и Variable Costs
    4. **Гибкие графики** — каждый график можно свернуть/развернуть
    5. **ФЭМ с формулами** — экспорт в Excel с живыми формулами (можно менять параметры прямо в Excel)
    6. **Ручной ввод клиентской базы** — задавайте поток пациентов вручную по когортам (новое!)
    
    ### Ручной ввод клиентской базы (новая функция):
    
    В разделе **«Поток пациентов»** для каждой модели появился переключатель:
    - **Автоматический** — поток рассчитывается по формуле роста (существующее поведение)
    - **Ручной ввод** — вы задаёте число новых пациентов на клинику для каждого месяца
    
    Нажмите кнопку **«Ручной ввод клиентской базы»** / **«Посмотреть клиентскую базу»**:
    - Открывается таблица когорт: строки = когорты (по месяцу старта), столбцы = месяцы M1..Mn
    - Длина цветного блока когорты = **«Срок занятости устройства пациентом»** (действует в обоих режимах)
    - В ручном режиме: задаёте кол-во пациентов на клинику для каждой когорты
    - Введённые значения применяются ко всем клиникам одинаково (со сдвигом для пачек, стартующих позже)
    - В автоматическом режиме: таблица только для просмотра, данные вычислены из параметров роста
    
    ### Как добавить свою статью затрат:
    
    1. В левой панели найдите раздел **"💰 Fixed Costs"** или **"📦 Variable Costs"**
    2. Нажмите на **"➕ Свои статьи..."** (раскрывается список)
    3. Заполните форму: название, сумма, тип
    4. Нажмите **"➕ Добавить"**
    5. Статья автоматически учтется во всех расчетах и графиках!
    
    ### Подсказки:
    - Наведите курсор на вопросительный знак рядом с любым параметром для пояснения
    - Кастомные параметры сохраняются отдельно для каждой модели
    - При экспорте в Excel все кастомные параметры включаются автоматически
    """)

st.markdown("---")

# Загрузка конфигураций
@st.cache_data
def load_config():
    """Загрузка дефолтных параметров и сценариев"""
    config_path = Path(__file__).parent.parent / "config"
    
    with open(config_path / "defaults.json", "r", encoding="utf-8") as f:
        defaults = json.load(f)
    
    with open(config_path / "scenarios.json", "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    
    return defaults, scenarios

defaults, scenarios = load_config()

# Справка по бизнес-моделям (для сайдбара и основной области)
MODEL_DESCRIPTIONS = {
    "model_a": {
        "tagline": "B2B: клиника — покупатель парка устройств, ReFlex — вендор оборудования и ПО.",
        "body": """
**Кто платит:** клиника (единоразово за устройства + ежемесячная подписка за ПО на устройство).

**Поток выручки:** каждая «пачка» клиник полностью независима — собственная когортная история пациентов, собственный парк устройств. Устройства клиники 1 не доступны клинике 2. Старт пачки = первый месяц её работы: продаётся контрактный парк (setup + COGS), начинается когорта пациентов. Далее парк расширяется только при дефиците (спрос > парк). Подписка начисляется на весь накопленный парк.

**Расписание клиник:** добавляйте пачки с любого месяца через «🏥 Расписание подключения клиник» в сайдбаре. Рост пациентов в пачке считается от её месяца старта.

**Переменные затраты:** COGS на произведённые устройства (докупка при росте); при потоке пациентов — логистика/поддержка/инфра на эффективных пациентов (когорты + churn + загрузка).

**Когда выбирать:** переговоры с ЛПР клиники про закупку парка, грант/тендер на оборудование, «клиника владеет устройствами».

**Риски / нюансы:** длинный цикл сделки; выручка «ступенькой» при подключении новой пачки; нужно явно договариваться про MRR от подписки.
        """.strip(),
    },
    "model_b": {
        "tagline": "B2B2C: пациент платит за аренду, клиника — канал и получает комиссию.",
        "body": """
**Кто платит:** пациент (аренда в месяц). **Клиника** получает долю от gross (комиссия), **ReFlex** — net после комиссии.

**Поток выручки:** считается от **числа активных пациентов в месяц** × цена аренды × (1 − комиссия клиники). Пациенты могут **расти** от месяца к месяцу по заданному %.

**Переменные затраты:** логистика и поддержка **на пациента**, инфраструктура на пользователя, CAC пациента (если задан).

**Когда выбирать:** пилоты через клинику как канал, подписка/аренда «с полки», гибрид с частичной нагрузкой на клинику.

**Риски / нюансы:** чувствительность к цене аренды и комиссии; нужны unit economics (LTV/CAC) — см. карточки и график 6.
        """.strip(),
    },
    "model_ab": {
        "tagline": "Гибрид: клиника покупает парк (как в A) + монетизация с пациентов через аренду (как в B).",
        "body": """
**Кто платит:** клиника — за парк и подписку ReFlex; пациент — за аренду (часть остаётся клинике как комиссия, часть — в выручке ReFlex по логике B).

**Поток выручки:** **месяц 1** — setup + подписка + rental net; далее — подписка + rental net с ростом пациентов.

**Переменные затраты:** **COGS** на парк в месяце 1 + переменные **на пациентов** (логистика, поддержка и т.д.).

**Когда выбирать:** клиника хочет владеть активом, но выводить пациентов на платную домашнюю реабилитацию; сочетание capex-клиники и consumer-платежей.

**Риски / нюансы:** двойная операционка (B2B + B2B2C); аккуратно разделять, что остаётся клинике vs ReFlex в договоре — в калькуляторе заложена упрощённая формула.
        """.strip(),
    },
}

ASSUMPTION_IDS = ("A01", "A02", "A03", "A04")
ASSUMPTION_LABELS = {
    "A01": "A01: WTP пациентов S1",
    "A02": "A02: GTM сценарий A (клиника покупает парк)",
    "A03": "A03: GTM сценарий B (клиника канал, пациент платит)",
    "A04": "A04: Профили клиник для пилота",
}
ASSUMPTION_STATUS_OPTIONS = {
    "hypothesis": "гипотеза",
    "in_validation": "в валидации",
    "validated": "validated",
}
ASSUMPTION_IMPACT_METRICS = {
    "A01": ["Выручка", "Cash Flow", "LTV/CAC"],
    "A02": ["Выручка", "Breakeven"],
    "A03": ["Выручка", "Cash Flow", "Breakeven"],
    "A04": ["Выручка", "Активные пациенты"],
}
def _clear_param_widget_state(base_keys: list[str]) -> int:
    """Удаляет session_state ключи переключаемых виджетов (режим/значение), чтобы сброс реально обновил UI."""
    suffixes = ("_mode", "_value", "_slider_widget", "_manual_widget")
    removed = 0
    for base in base_keys:
        for suf in suffixes:
            k = f"{base}{suf}"
            if k in st.session_state:
                del st.session_state[k]
                removed += 1
    return removed


def _compute_core_metrics(
    model_type: str,
    revenue_results: list[dict],
    costs_results: list[dict],
    cash_flow_results: list[dict],
    revenue_params: dict,
    variable_costs_params: dict,
    assumptions_params: dict,
) -> dict:
    unit_economics = calculate_unit_economics_from_params(model_type, revenue_params, variable_costs_params)
    breakeven = calculate_breakeven_month(
        [row["revenue"] for row in cash_flow_results],
        [row["total_costs"] for row in cash_flow_results],
        24,
    )
    return {
        "total_revenue": sum(row.get("total_revenue", 0.0) for row in revenue_results),
        "total_cash_flow": sum(row.get("cash_flow", 0.0) for row in cash_flow_results),
        "ltv_cac_ratio": float(unit_economics.get("ltv_cac_ratio", 0.0)),
        "breakeven_month": float(breakeven.get("breakeven_month") or 0),
        "active_patients_last_month": float(revenue_results[-1].get("num_patients", 0)) if revenue_results else 0.0,
        "desired_margin": float(assumptions_params.get("desired_margin", 0.0)),
    }


def _build_assumption_what_if(
    assumption_id: str,
    model_type: str,
    revenue_params: dict,
    fixed_costs_params: dict,
    variable_costs_params: dict,
    assumptions_params: dict,
    num_months: int,
    custom_fixed_costs: dict,
    custom_variable_costs: dict,
    base_metrics: dict,
) -> dict:
    scenario_revenue = revenue_params.copy()
    scenario_variable = variable_costs_params.copy()
    scenario_assumptions = assumptions_params.copy()
    note = "Влияние считается как what-if на бизнес-параметрах."

    if assumption_id == "A01":
        if "rental_price" in scenario_revenue:
            scenario_revenue["rental_price"] *= 1.1
            note = "A01: +10% к цене аренды как проверка WTP."
        elif "subscription_per_device" in scenario_revenue:
            scenario_revenue["subscription_per_device"] *= 1.1
            note = "A01: +10% к подписке как прокси WTP."
    elif assumption_id == "A02":
        if model_type in ["model_a", "model_ab"]:
            scenario_revenue["num_clinics"] = int(max(1, round(scenario_revenue.get("num_clinics", 1) * 1.15)))
            note = "A02: +15% к числу клиник как усиление GTM A."
    elif assumption_id == "A03":
        if "clinic_commission_rate" in scenario_revenue:
            scenario_revenue["clinic_commission_rate"] = max(
                0.0, scenario_revenue["clinic_commission_rate"] - 0.05
            )
        if "growth_rate" in scenario_revenue:
            scenario_revenue["growth_rate"] *= 1.1
        note = "A03: -5 п.п. комиссия +10% рост пациентов как прокси GTM B."
    elif assumption_id == "A04":
        if "patients_per_clinic_month1" in scenario_revenue:
            scenario_revenue["patients_per_clinic_month1"] = int(
                max(1, round(scenario_revenue["patients_per_clinic_month1"] * 1.15))
            )
        note = "A04: +15% пациентов в M1 как эффект лучшего ICP/профиля клиники."

    scenario_revenue_results = calculate_revenue_for_months(
        model_type, scenario_revenue, num_months, assumptions=scenario_assumptions
    )
    scenario_costs_results = calculate_costs_for_months(
        model_type,
        fixed_costs_params,
        scenario_variable,
        scenario_revenue_results,
        num_months,
        custom_fixed_costs,
        custom_variable_costs,
    )
    scenario_cash_flow = calculate_cash_flow_for_months(scenario_revenue_results, scenario_costs_results, num_months)
    scenario_metrics = _compute_core_metrics(
        model_type,
        scenario_revenue_results,
        scenario_costs_results,
        scenario_cash_flow,
        scenario_revenue,
        scenario_variable,
        scenario_assumptions,
    )
    deltas = {k: scenario_metrics[k] - base_metrics[k] for k in base_metrics}
    return {"deltas": deltas, "note": note}

# Инициализация session state (должна быть ДО использования)
if 'num_months' not in st.session_state:
    st.session_state.num_months = 12

if 'saved_params' not in st.session_state:
    st.session_state.saved_params = {
        'model_a': defaults['model_a']['parameters'].copy(),
        'model_b': defaults['model_b']['parameters'].copy(),
        'model_ab': defaults['model_ab']['parameters'].copy()
    }

# Кастомные параметры для каждой модели
if 'custom_fixed_costs' not in st.session_state:
    st.session_state.custom_fixed_costs = {
        'model_a': {},
        'model_b': {},
        'model_ab': {}
    }

if 'custom_variable_costs' not in st.session_state:
    st.session_state.custom_variable_costs = {
        'model_a': {},
        'model_b': {},
        'model_ab': {}
    }

if 'custom_revenue' not in st.session_state:
    st.session_state.custom_revenue = {
        'model_a': {},
        'model_b': {},
        'model_ab': {}
    }

# clinic_schedule: список пачек клиник [{month_start, count}] для Model A
if 'clinic_schedule_model_a' not in st.session_state:
    st.session_state.clinic_schedule_model_a = [
        {"month_start": 3, "count": 1},
        {"month_start": 4, "count": 2},
        {"month_start": 5, "count": 2},
        {"month_start": 6, "count": 2},
        {"month_start": 7, "count": 2},
        {"month_start": 8, "count": 3},
        {"month_start": 9, "count": 4},
        {"month_start": 10, "count": 3},
        {"month_start": 11, "count": 3},
        {"month_start": 12, "count": 3},
    ]

# Дефолтная матрица пациентов для model_a (ручной ввод, 36×36)
_DEFAULT_MATRIX_MODEL_A = [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]
_DEFAULT_MATRIX_MODEL_A[0][0] = 10; _DEFAULT_MATRIX_MODEL_A[0][1] = 10; _DEFAULT_MATRIX_MODEL_A[0][2] = 10
_DEFAULT_MATRIX_MODEL_A[3][3] = 10; _DEFAULT_MATRIX_MODEL_A[3][4] = 10; _DEFAULT_MATRIX_MODEL_A[3][5] = 10
_DEFAULT_MATRIX_MODEL_A[4][4] = 2;  _DEFAULT_MATRIX_MODEL_A[4][5] = 2;  _DEFAULT_MATRIX_MODEL_A[4][6] = 2
_DEFAULT_MATRIX_MODEL_A[5][5] = 5;  _DEFAULT_MATRIX_MODEL_A[5][6] = 5;  _DEFAULT_MATRIX_MODEL_A[5][7] = 5
_DEFAULT_MATRIX_MODEL_A[6][6] = 8;  _DEFAULT_MATRIX_MODEL_A[6][7] = 8;  _DEFAULT_MATRIX_MODEL_A[6][8] = 8
_DEFAULT_MATRIX_MODEL_A[7][7] = 10; _DEFAULT_MATRIX_MODEL_A[7][8] = 10; _DEFAULT_MATRIX_MODEL_A[7][9] = 10
_DEFAULT_MATRIX_MODEL_A[8][8] = 15; _DEFAULT_MATRIX_MODEL_A[8][9] = 15; _DEFAULT_MATRIX_MODEL_A[8][10] = 15
_DEFAULT_MATRIX_MODEL_A[9][9] = 17; _DEFAULT_MATRIX_MODEL_A[9][10] = 17; _DEFAULT_MATRIX_MODEL_A[9][11] = 17
_DEFAULT_MATRIX_MODEL_A[10][10] = 20; _DEFAULT_MATRIX_MODEL_A[10][11] = 20
_DEFAULT_MATRIX_MODEL_A[11][11] = 25

# patient_mode: "auto" | "manual" — режим потока пациентов (отдельно для каждой модели)
_DEFAULT_PATIENT_MODES = {'model_a': 'manual', 'model_b': 'auto', 'model_ab': 'auto'}
_DEFAULT_PATIENT_MATRICES = {
    'model_a': _DEFAULT_MATRIX_MODEL_A,
    'model_b': [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)],
    'model_ab': [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)],
}
for _m in ('model_a', 'model_b', 'model_ab'):
    if f'patient_mode_{_m}' not in st.session_state:
        st.session_state[f'patient_mode_{_m}'] = _DEFAULT_PATIENT_MODES[_m]
    # manual_patients: список новых пациентов на клинику по месяцам (0-based) [legacy compat]
    if f'manual_patients_{_m}' not in st.session_state:
        st.session_state[f'manual_patients_{_m}'] = [0] * MAX_MONTHS
    # manual_patients_matrix: 2D матрица [когорта][месяц], MAX_MONTHS x MAX_MONTHS
    # matrix[i][j] = активных пациентов из когорты i в месяце j (0-based)
    if f'manual_patients_matrix_{_m}' not in st.session_state:
        st.session_state[f'manual_patients_matrix_{_m}'] = _DEFAULT_PATIENT_MATRICES[_m]

# Флаг открытия модального окна таблицы пациентов
if 'show_patient_table' not in st.session_state:
    st.session_state.show_patient_table = False

# ── R&D фаза ──────────────────────────────────────────────────
if 'rnd_enabled' not in st.session_state:
    st.session_state.rnd_enabled = False
if 'rnd_months' not in st.session_state:
    st.session_state.rnd_months = 2
if 'rnd_cost_categories' not in st.session_state:
    st.session_state.rnd_cost_categories = list(DEFAULT_RND_CATEGORIES)
if 'rnd_costs_matrix' not in st.session_state:
    st.session_state.rnd_costs_matrix = {
        "Зарплаты команды": [200000.0, 200000.0],
        "Оборудование и материалы": [150000.0, 20000.0],
        "Разработка и тестирование": [100000.0, 0.0],
        "Аренда и инфраструктура": [0.0, 0.0],
        "Прочие расходы R&D": [0.0, 0.0],
    }
if 'show_rnd_table' not in st.session_state:
    st.session_state.show_rnd_table = False

# ── Predictor defaults (срок окупаемости) ─────────────────────
_PREDICTOR_DEFAULTS = {
    'model_a': {'initial_investment': 1_000_000, 'target_breakeven': 12, 'target_margin_rate': 0.0},
    'model_b': {'initial_investment': 0, 'target_breakeven': 3, 'target_margin_rate': 0.25},
    'model_ab': {'initial_investment': 0, 'target_breakeven': 3, 'target_margin_rate': 0.25},
}
for _pm in ('model_a', 'model_b', 'model_ab'):
    if f'{_pm}_initial_investment_value' not in st.session_state:
        st.session_state[f'{_pm}_initial_investment_value'] = _PREDICTOR_DEFAULTS[_pm]['initial_investment']
    if f'{_pm}_target_breakeven_value' not in st.session_state:
        st.session_state[f'{_pm}_target_breakeven_value'] = _PREDICTOR_DEFAULTS[_pm]['target_breakeven']
    if f'{_pm}_target_margin_rate_value' not in st.session_state:
        st.session_state[f'{_pm}_target_margin_rate_value'] = _PREDICTOR_DEFAULTS[_pm]['target_margin_rate']

# Применяем отложенный импорт слепка (до рендера любых виджетов).
# Кнопки "Применить" кладут payload в _pending_snapshot_payload + rerun();
# здесь он применяется, пока ни один виджет ещё не инициализирован.
if '_pending_snapshot_payload' in st.session_state:
    _pending_payload = st.session_state.pop('_pending_snapshot_payload')
    apply_config_snapshot(
        session_state=st.session_state,
        normalized_payload=_pending_payload,
        assumption_ids=ASSUMPTION_IDS,
    )
    st.rerun()

# ========== SIDEBAR ==========
st.sidebar.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("🔧 Настройки")


def slider_with_manual_int(
    key: str,
    label: str,
    slider_min: int,
    slider_max: int,
    default_value: int,
    step: int = 1,
    help_text: str | None = None,
) -> int:
    """Переключаемый ввод int: слайдер или ручной."""
    mode_key = f"{key}_mode"
    last_mode_key = f"{key}_last_mode"
    value_key = f"{key}_value"
    slider_widget_key = f"{key}_slider_widget"
    manual_widget_key = f"{key}_manual_widget"

    if value_key not in st.session_state:
        st.session_state[value_key] = int(default_value)
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "slider"
    if last_mode_key not in st.session_state:
        st.session_state[last_mode_key] = st.session_state[mode_key]

    mode = st.sidebar.radio(
        f"{label}: режим ввода",
        options=["slider", "manual"],
        format_func=lambda m: "Слайдер" if m == "slider" else "Ручной ввод",
        key=mode_key,
        horizontal=True,
    )
    mode_changed = st.session_state[last_mode_key] != mode

    if mode == "slider":
        current_for_slider = int(min(max(st.session_state[value_key], slider_min), slider_max))
        if slider_widget_key not in st.session_state or mode_changed:
            st.session_state[slider_widget_key] = current_for_slider
        final_value = st.sidebar.slider(
            label,
            min_value=slider_min,
            max_value=slider_max,
            step=step,
            key=slider_widget_key,
            help=help_text,
        )
        final_value = int(final_value)
    else:
        if manual_widget_key not in st.session_state or mode_changed:
            st.session_state[manual_widget_key] = int(st.session_state[value_key])
        final_value = st.sidebar.number_input(
            label,
            step=step,
            key=manual_widget_key,
            help="Ручной ввод без ограничений диапазона слайдера",
        )
        final_value = int(final_value)
    st.session_state[value_key] = final_value
    st.session_state[last_mode_key] = mode
    return final_value


def slider_with_manual_float(
    key: str,
    label: str,
    slider_min: float,
    slider_max: float,
    default_value: float,
    step: float = 1.0,
    help_text: str | None = None,
) -> float:
    """Переключаемый ввод float: слайдер или ручной."""
    mode_key = f"{key}_mode"
    last_mode_key = f"{key}_last_mode"
    value_key = f"{key}_value"
    slider_widget_key = f"{key}_slider_widget"
    manual_widget_key = f"{key}_manual_widget"

    if value_key not in st.session_state:
        st.session_state[value_key] = float(default_value)
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "slider"
    if last_mode_key not in st.session_state:
        st.session_state[last_mode_key] = st.session_state[mode_key]

    mode = st.sidebar.radio(
        f"{label}: режим ввода",
        options=["slider", "manual"],
        format_func=lambda m: "Слайдер" if m == "slider" else "Ручной ввод",
        key=mode_key,
        horizontal=True,
    )
    mode_changed = st.session_state[last_mode_key] != mode

    if mode == "slider":
        current_for_slider = float(min(max(st.session_state[value_key], slider_min), slider_max))
        if slider_widget_key not in st.session_state or mode_changed:
            st.session_state[slider_widget_key] = current_for_slider
        final_value = st.sidebar.slider(
            label,
            min_value=slider_min,
            max_value=slider_max,
            step=step,
            key=slider_widget_key,
            help=help_text,
        )
        final_value = float(final_value)
    else:
        if manual_widget_key not in st.session_state or mode_changed:
            st.session_state[manual_widget_key] = float(st.session_state[value_key])
        final_value = st.sidebar.number_input(
            label,
            step=step,
            key=manual_widget_key,
            help="Ручной ввод без ограничений диапазона слайдера",
        )
        final_value = float(final_value)
    st.session_state[value_key] = final_value
    st.session_state[last_mode_key] = mode
    return final_value


def slider_with_manual_percent(
    key: str,
    label: str,
    slider_min_pct: int,
    slider_max_pct: int,
    default_fraction: float,
    help_text: str | None = None,
) -> float:
    default_pct = int(default_fraction * 100)
    pct = slider_with_manual_int(
        key=key,
        label=label,
        slider_min=slider_min_pct,
        slider_max=slider_max_pct,
        default_value=default_pct,
        step=1,
        help_text=help_text,
    )
    return pct / 100.0


def _project_patient_counts(
    num_clinics: int,
    patients_per_clinic_month1: int,
    growth_rate: float,
    target_month: int,
    rehab_duration_months: int,
) -> tuple[list[int], list[int]]:
    new_counts: list[int] = []
    active_counts: list[int] = []
    prev_new = None
    rehab_duration = max(1, int(rehab_duration_months))
    for m in range(1, target_month + 1):
        if m == 1:
            new_n = num_clinics * patients_per_clinic_month1
        else:
            new_n = int(prev_new * (1 + growth_rate))
        new_counts.append(new_n)
        active_counts.append(sum(new_counts[-rehab_duration:]))
        prev_new = new_n
    return new_counts, active_counts


def _calc_target_pricing_predictor(
    model_type: str,
    revenue_params: dict,
    fixed_costs_params: dict,
    variable_costs_params: dict,
    target_month: int,
    desired_margin: float,
    model_ab_mode: str = "rental_only",
    custom_fixed_costs: dict | None = None,
    custom_variable_costs: dict | None = None,
    assumptions_for_revenue: dict | None = None,
    initial_investment: float = 0.0,
    manual_new_patients_per_clinic: list | None = None,
    manual_active_patients_per_clinic: list | None = None,
    discount_rate_annual: float = 0.0,
) -> dict:
    """
    Возвращает требуемую цену(ы), чтобы к target_month выполнилось условие по NPV:

      NPV(N) = −I₀ + Σ_{t=1}^{N} CF_t / (1 + r_m)^t  ≥  desired_margin × TotalCosts(1..N)

    где r_m = (1 + discount_rate_annual)^(1/12) - 1 — месячная ставка дисконтирования,
    I₀ = initial_investment — начальные вложения, уже включены в NPV со знаком «−».

    При discount_rate_annual = 0 условие эквивалентно CumCF(N) − I₀ >= desired_margin × TotalCosts,
    что совпадает со старой формулой (обратная совместимость).

    Интерпретация:
      initial_investment = 0, desired_margin = 0  → NPV(N) >= 0 (операционный плюс)
      initial_investment > 0, desired_margin = 0  → вложения отбиты в дисконтированных деньгах
      desired_margin > 0                           → дополнительный запас над нулём NPV

    Расчет выполняется через тот же движок revenue/costs/cash-flow, что и основной дашборд.
    """
    if target_month < 1:
        return {"feasible": False, "reason": "target_month < 1"}

    custom_fixed_costs = custom_fixed_costs or {}
    custom_variable_costs = custom_variable_costs or {}
    _initial_inv = float(initial_investment)
    _discount_rate = float(discount_rate_annual)

    def _run_projection(test_revenue_params: dict) -> dict:
        _rev = calculate_revenue_for_months(
            model_type,
            test_revenue_params,
            target_month,
            assumptions=assumptions_for_revenue,
            manual_new_patients_per_clinic=manual_new_patients_per_clinic,
            manual_active_patients_per_clinic=manual_active_patients_per_clinic,
        )
        _costs = calculate_costs_for_months(
            model_type,
            fixed_costs_params,
            variable_costs_params,
            _rev,
            target_month,
            custom_fixed_costs,
            custom_variable_costs,
        )
        _cf = calculate_cash_flow_for_months(_rev, _costs, target_month)
        total_revenue = sum([r.get("total_revenue", 0.0) for r in _rev])
        total_costs = sum([c.get("total_costs", 0.0) for c in _costs])
        cumulative_cf = _cf[-1]["cumulative_cash_flow"] if _cf else 0.0
        # NPV включает начальные вложения со знаком «−»:
        #   NPV(N) = −I₀ + Σ CF_t / (1+r_m)^t
        # При ставке 0% это эквивалентно CumCF(N) − I₀ (обратная совместимость).
        _cf_monthly = [row["cash_flow"] for row in _cf]
        _pv_series = calculate_npv_series(_cf_monthly, _discount_rate)
        pv_of_flows = _pv_series[-1] if _pv_series else 0.0
        npv_cumulative = pv_of_flows - _initial_inv
        target_profit = desired_margin * total_costs
        # Порог: только запас над затратами (вложения уже учтены в npv_cumulative)
        threshold = target_profit
        return {
            "revenue_results": _rev,
            "costs_results": _costs,
            "cash_flow_results": _cf,
            "total_revenue": total_revenue,
            "total_costs": total_costs,
            "target_profit": target_profit,
            "target_revenue_required": total_costs + target_profit + _initial_inv,
            "cumulative_cf": cumulative_cf,
            "pv_of_flows": pv_of_flows,
            "npv_cumulative": npv_cumulative,
            # meets_target: NPV(N) = −I₀ + PV(CF) >= запас × TotalCosts
            "meets_target": npv_cumulative >= threshold,
        }

    def _find_min_value(base_params: dict, field_name: str) -> float:
        current_value = float(base_params.get(field_name, 0.0))
        lo = 0.0
        hi = max(1.0, current_value if current_value > 0 else 1.0)
        max_hi = 1e7

        test_params = base_params.copy()
        test_params[field_name] = hi
        sim_hi = _run_projection(test_params)
        while (not sim_hi["meets_target"]) and hi < max_hi:
            hi *= 2.0
            test_params[field_name] = hi
            sim_hi = _run_projection(test_params)

        if not sim_hi["meets_target"]:
            return float("inf")

        for _ in range(45):
            mid = (lo + hi) / 2.0
            test_params[field_name] = mid
            sim_mid = _run_projection(test_params)
            if sim_mid["meets_target"]:
                hi = mid
            else:
                lo = mid
        return hi

    def _build_single_price_result(price_kind: str, field_name: str) -> dict:
        current_value = float(revenue_params.get(field_name, 0.0))
        required_price = _find_min_value(revenue_params, field_name)

        params_current = revenue_params.copy()
        params_required = revenue_params.copy()
        params_current[field_name] = current_value
        params_required[field_name] = required_price if required_price != float("inf") else current_value

        sim_current = _run_projection(params_current)
        sim_required = _run_projection(params_required)

        coeff = 0.0
        if required_price != float("inf") and abs(required_price - current_value) > 1e-9:
            coeff = (
                (sim_required["total_revenue"] - sim_current["total_revenue"])
                / (required_price - current_value)
            )

        already_meets = bool(sim_current["meets_target"])
        headroom = current_value - required_price if required_price != float("inf") else float("-inf")
        trivial_floor = required_price != float("inf") and required_price < 1e-3

        return {
            "feasible": required_price != float("inf"),
            "model_type": model_type,
            "price_kind": price_kind,
            "required_price": required_price,
            "current_price": current_value,
            "target_month": target_month,
            "target_revenue_required": sim_required["target_revenue_required"],
            "base_revenue": sim_current["total_revenue"] - coeff * current_value,
            "coeff": coeff,
            "already_meets_target": already_meets,
            "headroom_price": headroom,
            "trivial_min_price": trivial_floor,
            "meta": {
                "current_cumulative_cf": sim_current["cumulative_cf"],
                "required_cumulative_cf": sim_required["cumulative_cf"],
                "current_npv": sim_current["npv_cumulative"],
                "required_npv": sim_required["npv_cumulative"],
                "target_profit": sim_required["target_profit"],
                "discount_rate_annual": _discount_rate,
            },
        }

    if model_type == "model_a":
        return _build_single_price_result("subscription_per_device", "subscription_per_device")

    if model_type == "model_b":
        return _build_single_price_result("rental_price", "rental_price")

    # model_ab
    if model_ab_mode == "subscription_only":
        return _build_single_price_result("subscription_per_device", "subscription_per_device")

    if model_ab_mode == "both_scaled":
        s0 = float(revenue_params.get("subscription_per_device", 0.0))
        r0 = float(revenue_params.get("rental_price", 0.0))
        lo = 0.0
        hi = 1.0
        max_hi = 1e4

        def _sim_by_scale(k: float) -> dict:
            p = revenue_params.copy()
            p["subscription_per_device"] = s0 * k
            p["rental_price"] = r0 * k
            return _run_projection(p)

        sim_hi = _sim_by_scale(hi)
        while (not sim_hi["meets_target"]) and hi < max_hi:
            hi *= 2.0
            sim_hi = _sim_by_scale(hi)

        if not sim_hi["meets_target"]:
            return {"feasible": False, "reason": "target not reachable for both_scaled"}

        for _ in range(45):
            mid = (lo + hi) / 2.0
            sim_mid = _sim_by_scale(mid)
            if sim_mid["meets_target"]:
                hi = mid
            else:
                lo = mid

        req_sim = _sim_by_scale(hi)
        cur_sim = _sim_by_scale(1.0)
        already_meets = bool(cur_sim["meets_target"])
        return {
            "feasible": True,
            "model_type": model_type,
            "price_kind": "both_scaled",
            "required_subscription": s0 * hi,
            "required_rental": r0 * hi,
            "scale_factor": hi,
            "current_subscription": s0,
            "current_rental": r0,
            "target_month": target_month,
            "target_revenue_required": req_sim["target_revenue_required"],
            "base_revenue": cur_sim["total_revenue"],
            "coeff": (req_sim["total_revenue"] - cur_sim["total_revenue"]) / max(hi - 1.0, 1e-9),
            "already_meets_target": already_meets,
            "headroom_scale_factor": hi,
            "trivial_min_price": hi < 1e-6,
            "meta": {
                "current_cumulative_cf": cur_sim["cumulative_cf"],
                "required_cumulative_cf": req_sim["cumulative_cf"],
                "current_npv": cur_sim["npv_cumulative"],
                "required_npv": req_sim["npv_cumulative"],
                "target_profit": req_sim["target_profit"],
                "discount_rate_annual": _discount_rate,
            },
        }

    # default: rental_only
    return _build_single_price_result("rental_price", "rental_price")

# ========== HELPERS: COHORT TABLE ==========

def _compute_cohort_active_per_month(
    values: list,
    num_months: int,
    rehab_duration: int,
) -> list:
    """
    Вычисляет суммарное число активных пациентов по месяцам (1D режим, авто).

    values[i] = новые пациенты на клинику, стартующие в месяц i+1 (0-based).
    Когорта i+1 активна в месяцах i+1 .. min(i+rehab_duration, num_months).
    """
    totals = [0] * num_months
    for i in range(num_months):
        cohort_val = int(values[i]) if i < len(values) else 0
        for j in range(i, min(i + rehab_duration, num_months)):
            totals[j] += cohort_val
    return totals


def _compute_cohort_active_from_matrix(
    matrix: list,
    num_months: int,
    rehab_duration: int,
) -> list:
    """
    Вычисляет суммарное число активных пациентов по месяцам из 2D матрицы.

    matrix[i][j] = активных пациентов из когорты i в месяце j (0-based).
    Только ячейки внутри активного окна [i .. i+rehab_duration-1] учитываются.
    """
    totals = [0] * num_months
    for i in range(num_months):
        for j in range(i, min(i + rehab_duration, num_months)):
            val = matrix[i][j] if i < len(matrix) and j < len(matrix[i]) else 0
            totals[j] += int(val)
    return totals


def _render_cohort_table_html(
    values: list,
    num_months: int,
    rehab_duration: int,
) -> str:
    """
    Генерирует HTML-таблицу когорт для АВТО-режима (только просмотр).

    Строки = когорты (по одной на каждый месяц горизонта).
    Столбцы = месяцы M1..Mn.
    """
    totals = _compute_cohort_active_per_month(values, num_months, rehab_duration)

    # Высококонтрастные цвета когорт (чередуем два оттенка)
    color_a = "#1e4d8c"   # насыщенный синий
    color_b = "#15397a"   # чуть темнее
    border_color = "#5b9bd5"

    th_style = (
        "padding:6px 10px;text-align:center;font-weight:600;"
        "background:#0d1b2a;color:#d0e4f7;border:1px solid #2a4a6b;white-space:nowrap;"
    )
    td_base = "padding:5px 8px;text-align:center;border:1px solid #2a4a6b;font-size:0.85rem;"
    td_empty = td_base + "background:#0d1b2a;color:#3a5070;"
    td_total_style = (
        "padding:6px 10px;text-align:center;font-weight:700;"
        "background:#0a2540;color:#4dd9d9;border:1px solid #2a4a6b;"
    )
    row_label_style = (
        "padding:5px 10px;text-align:left;font-weight:500;white-space:nowrap;"
        "background:#0d1b2a;color:#7eb8e0;border:1px solid #2a4a6b;font-size:0.82rem;"
    )

    lines = [
        '<div style="overflow-x:auto;margin:8px 0;">',
        '<table style="border-collapse:collapse;min-width:100%;font-family:monospace;">',
    ]

    lines.append("<thead><tr>")
    lines.append(f'<th style="{th_style}">Когорта</th>')
    for j in range(1, num_months + 1):
        lines.append(f'<th style="{th_style}">М{j}</th>')
    lines.append("</tr></thead>")

    lines.append("<tbody>")

    # Строка суммарных клиентов
    lines.append("<tr>")
    lines.append(f'<td style="{td_total_style}">Суммарно</td>')
    for j in range(num_months):
        val = totals[j]
        disp = str(val) if val > 0 else "—"
        lines.append(f'<td style="{td_total_style}">{disp}</td>')
    lines.append("</tr>")

    # Строки когорт
    for i in range(1, num_months + 1):
        cohort_val = int(values[i - 1]) if (i - 1) < len(values) else 0
        bg = color_a if i % 2 == 1 else color_b
        active_start = i
        active_end = min(i + rehab_duration - 1, num_months)

        lines.append("<tr>")
        lines.append(f'<td style="{row_label_style}">Когорта {i} (М{i})</td>')

        for j in range(1, num_months + 1):
            if active_start <= j <= active_end:
                is_first = j == active_start
                is_last = j == active_end
                border_left = f"2px solid {border_color}" if is_first else f"1px solid {border_color}"
                border_right = f"2px solid {border_color}" if is_last else f"1px solid {border_color}"
                cell_style = (
                    f"padding:5px 8px;text-align:center;font-size:0.85rem;"
                    f"background:{bg};color:#ffffff;font-weight:700;"
                    f"border-left:{border_left};border-right:{border_right};"
                    f"border-top:2px solid {border_color};border-bottom:2px solid {border_color};"
                )
                disp = str(cohort_val) if cohort_val > 0 else "0"
                lines.append(f'<td style="{cell_style}">{disp}</td>')
            else:
                lines.append(f'<td style="{td_empty}"></td>')

        lines.append("</tr>")

    lines.append("</tbody></table></div>")
    return "\n".join(lines)



@st.dialog("Клиентская база — поток пациентов по когортам", width="large")
def _show_patient_table_dialog(
    model_type: str,
    num_months: int,
    rehab_duration: int,
    auto_values: list | None = None,
) -> None:
    """
    Модальное окно для просмотра/редактирования клиентской базы.

    В автоматическом режиме — HTML-таблица (только просмотр).
    В ручном режиме — st.data_editor: редактирование прямо в ячейках таблицы когорт.
    Каждая строка = когорта, каждый столбец = месяц.
    Ячейки вне активного окна когорты отображаются пустыми и игнорируются.
    """
    patient_mode = st.session_state.get(f'patient_mode_{model_type}', 'auto')
    is_manual = patient_mode == 'manual'
    matrix_key = f'manual_patients_matrix_{model_type}'

    if is_manual:
        st.markdown(
            "**Ручной ввод — редактируйте значения прямо в ячейках таблицы.** "
            "Каждая строка = когорта пациентов, стартующих в соответствующем месяце. "
            "Цветные ячейки = активное окно когорты (ширина = срок занятости устройства). "
            "Пустые ячейки вне окна игнорируются."
        )
    else:
        st.markdown(
            "**Автоматический режим** (только просмотр). Значения рассчитаны из параметров "
            "«# новых пациентов/клинику в M1» и «Рост потока новых пациентов/мес (%)». "
            "Переключитесь в ручной режим для редактирования."
        )

    st.info(
        f"Срок занятости устройства: **{rehab_duration} мес** — ширина активного окна каждой когорты. "
        "Суммарно = сумма активных пациентов по всем когортам в данном месяце.",
        icon="ℹ️",
    )

    if is_manual:
        # Инициализируем матрицу, если нужно
        matrix = st.session_state.get(matrix_key, None)
        if matrix is None or len(matrix) < MAX_MONTHS:
            matrix = [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]
            st.session_state[matrix_key] = matrix

        new_matrix = [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]

        # Заголовок столбцов (месяцы)
        _lw = 1.6  # ширина колонки-лейбла
        _header_cols = st.columns([_lw] + [1.0] * num_months)
        _header_cols[0].markdown("**Когорта**")
        for _j in range(num_months):
            _header_cols[_j + 1].markdown(f"**М{_j + 1}**")

        # Строки когорт — number_input в каждой активной ячейке
        # Инициализируем ключи из матрицы (только если ключ ещё не существует)
        for _i in range(num_months):
            for _j in range(num_months):
                _k = f"coh_{model_type}_{_i}_{_j}"
                if _k not in st.session_state:
                    st.session_state[_k] = int(matrix[_i][_j]) if _i < len(matrix) and _j < len(matrix[_i]) else 0

        for _i in range(num_months):
            _active_start = _i
            _active_end = min(_i + rehab_duration - 1, num_months - 1)
            _row_cols = st.columns([_lw] + [1.0] * num_months)
            _row_cols[0].markdown(f"<small>К{_i + 1}&nbsp;(М{_i + 1})</small>", unsafe_allow_html=True)
            for _j in range(num_months):
                if _active_start <= _j <= _active_end:
                    _v = _row_cols[_j + 1].number_input(
                        f"К{_i + 1} М{_j + 1}",
                        min_value=0,
                        max_value=9999,
                        step=1,
                        key=f"coh_{model_type}_{_i}_{_j}",
                        label_visibility="collapsed",
                    )
                    new_matrix[_i][_j] = int(_v)

        st.session_state[matrix_key] = new_matrix

        # Синхронизируем legacy 1D
        _legacy_key = f'manual_patients_{model_type}'
        _legacy = list(st.session_state.get(_legacy_key, [0] * MAX_MONTHS))
        while len(_legacy) < MAX_MONTHS:
            _legacy.append(0)
        for _ci in range(num_months):
            _legacy[_ci] = new_matrix[_ci][_ci]
        st.session_state[_legacy_key] = _legacy

        # Суммарно
        totals = _compute_cohort_active_from_matrix(new_matrix, num_months, rehab_duration)
        st.markdown("---")
        st.caption("**Суммарно активных пациентов на клинику по месяцам:**")
        _tot_cols = st.columns([_lw] + [1.0] * num_months)
        _tot_cols[0].markdown("**∑**")
        for _j in range(num_months):
            _tot_cols[_j + 1].metric(f"М{_j + 1}", totals[_j], label_visibility="collapsed")

        st.caption("Значения применяются ко всем клиникам одинаково.")

    else:
        # Авто-режим: HTML-таблица (только просмотр)
        values = list(auto_values or [0] * num_months)
        while len(values) < num_months:
            values.append(0)
        values = values[:num_months]
        st.html(_render_cohort_table_html(values, num_months, rehab_duration))

    _, _btn_close = st.columns([3, 1])
    with _btn_close:
        if st.button("Закрыть", use_container_width=True, type="primary"):
            st.rerun()


@st.dialog("Расходы R&D по месяцам", width="large")
def _show_rnd_table_dialog(rnd_months: int, categories: list, initial_investment: float) -> None:
    """
    Модальное окно для заполнения расходов R&D по месяцам.

    Строки = категории расходов (редактируемые названия).
    Столбцы = R&D месяцы (R1..RN).
    Все расходы списываются из банка инвестиций.
    """
    st.markdown(
        "Заполните расходы для каждого месяца R&D фазы. "
        "Нет выручки — только постоянные затраты из банка инвестиций."
    )

    # Инициализируем/нормализуем матрицу под текущий набор категорий и месяцев
    current_matrix = st.session_state.rnd_costs_matrix
    normalized: dict = {}
    for cat in categories:
        vals = current_matrix.get(cat, [0.0] * rnd_months)
        while len(vals) < rnd_months:
            vals = list(vals) + [0.0]
        normalized[cat] = vals[:rnd_months]

    # Считаем текущую сумму для live-проверки банка
    def _live_total(matrix_state):
        return sum(
            float(matrix_state.get(cat, [0.0] * rnd_months)[m])
            for cat in categories
            for m in range(rnd_months)
        )

    month_labels = [f"R&D {m + 1}" for m in range(rnd_months)]

    # Заголовок: статья / месяцы
    hdr_cols = st.columns([2] + [1] * rnd_months + [1])
    hdr_cols[0].markdown("**Статья расходов**")
    for j, lbl in enumerate(month_labels):
        hdr_cols[j + 1].markdown(f"**{lbl}**")
    hdr_cols[-1].markdown("**Итого**")

    new_matrix = {}
    for cat in categories:
        row_cols = st.columns([2] + [1] * rnd_months + [1])
        row_cols[0].markdown(cat)
        row_vals = []
        for m in range(rnd_months):
            v = row_cols[m + 1].number_input(
                label=f"{cat} / R&D {m + 1}",
                min_value=0,
                value=int(normalized[cat][m]),
                step=5000,
                label_visibility="collapsed",
                key=f"rnd_cell_{cat}_{m}",
            )
            row_vals.append(float(v))
        row_total = sum(row_vals)
        row_cols[-1].markdown(f"**{row_total:,.0f} ₽**")
        new_matrix[cat] = row_vals

    # Итоговая строка
    st.markdown("---")
    total_cols = st.columns([2] + [1] * rnd_months + [1])
    total_cols[0].markdown("**ИТОГО**")
    month_totals = []
    for m in range(rnd_months):
        mt = sum(new_matrix[cat][m] for cat in categories)
        month_totals.append(mt)
        total_cols[m + 1].markdown(f"**{mt:,.0f} ₽**")
    grand_total = sum(month_totals)
    total_cols[-1].markdown(f"**{grand_total:,.0f} ₽**")

    # Валидация банка
    validation = validate_rnd_vs_bank(grand_total, initial_investment)
    if validation["ok"]:
        st.success(validation["message"])
    else:
        st.error(validation["message"])

    btn_cols = st.columns([3, 1])
    with btn_cols[1]:
        if st.button(
            "Сохранить",
            use_container_width=True,
            type="primary",
            disabled=not validation["ok"],
        ):
            st.session_state.rnd_costs_matrix = new_matrix
            st.rerun()
    with btn_cols[0]:
        if st.button("Отмена", use_container_width=True):
            st.rerun()


# 1. Выбор бизнес-модели
st.sidebar.markdown("### Бизнес-модель")
model_type = st.sidebar.radio(
    "Выберите модель:",
    options=["model_a", "model_b", "model_ab"],
    format_func=lambda x: defaults[x]["name"],
    help="Кратко: A — клиника покупает парк; B — пациент арендует, клиника с комиссией; A+B — гибрид. Подробности — в раскрывающихся блоках ниже («Что означает эта модель», «Сравнить все 3 модели»).",
)

# 1.5 Количество месяцев для расчета
st.sidebar.markdown("### Горизонт планирования")
num_months = st.sidebar.slider(
    "Количество месяцев:",
    min_value=1,
    max_value=36,
    value=st.session_state.num_months,
    help="Выберите, на сколько месяцев вперед рассчитывать модель"
)
st.session_state.num_months = num_months

# 2. Выбор сценария
st.sidebar.markdown("### Сценарий")
scenario_options = ["custom"] + list(scenarios.keys())
scenario_names = {
    "custom": "Custom (настроить вручную)",
    "conservative": "Conservative (минимальный)",
    "base": "Base (базовый)",
    "optimistic": "Optimistic (оптимистичный)"
}

selected_scenario = st.sidebar.selectbox(
    "Выберите сценарий:",
    options=scenario_options,
    format_func=lambda x: scenario_names.get(x, x),
    help=(
        "Custom — задаёте все параметры вручную (сохраняются между переключениями). "
        "Conservative — пессимистичные значения для стресс-теста. "
        "Base — средние ожидаемые значения. "
        "Optimistic — лучший сценарий при благоприятных условиях."
    ),
)

# Загрузка параметров из сценария или дефолтов
if selected_scenario == "custom":
    # Используем дефолты для выбранной модели
    current_params = defaults[model_type]["parameters"]
else:
    # Загружаем из готового сценария
    scenario_data = scenarios[selected_scenario]
    current_params = scenario_data["parameters"]
    # Обновляем модель из сценария
    model_type = scenario_data.get("model", model_type)

# Загружаем сохраненные параметры для текущей модели или из сценария
if selected_scenario == "custom":
    # Используем сохраненные параметры для текущей модели
    current_params = st.session_state.saved_params[model_type]
else:
    # Используем параметры из сценария
    current_params = scenario_data["parameters"]

# Описание текущей модели (после финального model_type и сценария)
_desc = MODEL_DESCRIPTIONS.get(model_type, {})
st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Что означает эта модель?", expanded=False):
    st.caption(_desc.get("tagline", defaults[model_type].get("description", "")))
    st.markdown(_desc.get("body", ""))
with st.sidebar.expander("📑 Сравнить все 3 модели", expanded=False):
    for mid in ("model_a", "model_b", "model_ab"):
        st.markdown(f"**{defaults[mid]['name']}**")
        st.caption(MODEL_DESCRIPTIONS[mid]["tagline"])
        st.markdown("---")

st.sidebar.markdown("---")
stage_gate_statuses = {}
with st.sidebar.expander("✅ Stage-gate допущений (БП_01)", expanded=False):
    for assumption_id in ASSUMPTION_IDS:
        key = f"assumption_status_{assumption_id}"
        if key not in st.session_state:
            st.session_state[key] = "hypothesis"
        stage_gate_statuses[assumption_id] = st.selectbox(
            ASSUMPTION_LABELS[assumption_id],
            options=list(ASSUMPTION_STATUS_OPTIONS.keys()),
            format_func=lambda x: ASSUMPTION_STATUS_OPTIONS[x],
            key=key,
            help="Используется как confidence marker для интерпретации pricing/GTM расчетов.",
        )

# ========== ПАРАМЕТРЫ REVENUE ==========
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Revenue Parameters")

revenue_params = {}

if model_type == "model_a":
    revenue_params['num_clinics'] = slider_with_manual_int(
        key="model_a_num_clinics",
        label="# стартовых клиник (M1)",
        slider_min=1,
        slider_max=20,
        default_value=current_params['revenue'].get('num_clinics', 2),
        help_text=(
            "Начальное число клиник, подключённых на месяце 1. "
            "Каждая пачка клиник работает независимо: собственный парк устройств и собственная история когорт пациентов. "
            "Устройства клиники 1 недоступны клинике 2. "
            "Дополнительные клиники (в другие месяцы) задаются в разделе «Расписание клиник» ниже."
        ),
    )
    revenue_params['devices_per_clinic'] = slider_with_manual_int(
        key="model_a_devices_per_clinic",
        label="# устройств/клинику (контрактный минимум)",
        slider_min=1,
        slider_max=30,
        default_value=current_params['revenue'].get('devices_per_clinic', 10),
        help_text=(
            "Контрактный минимум парка на одну клинику. "
            "В первый месяц работы клиники производится и продаётся этот парк (setup fee + COGS). "
            "Парк не уменьшается: если спрос пациентов превысит контрактный минимум — парк расширяется автоматически."
        ),
    )
    revenue_params['setup_fee'] = st.sidebar.number_input(
        "Setup Fee (₽/устройство)",
        min_value=0,
        max_value=500000,
        value=current_params['revenue'].get('setup_fee', 50000),
        step=5000,
        key="model_a_setup_fee",
        help=(
            "Разовая выручка ReFlex с каждого проданного устройства. "
            "Начисляется при появлении новой клиники (весь контрактный парк) "
            "и при расширении парка клиники из-за роста спроса пациентов (дополнительные устройства). "
            "Соответствует COGS в затратах."
        ),
    )
    revenue_params['subscription_per_device'] = slider_with_manual_int(
        key="model_a_subscription_per_device",
        label="Подписка/устройство (₽/мес)",
        slider_min=100,
        slider_max=10000,
        default_value=current_params['revenue'].get('subscription_per_device', 2000),
        step=100,
        help_text=(
            "Ежемесячный recurring revenue за ПО/сервис на каждое устройство в парке клиники. "
            "Начисляется на весь накопленный парк (не только занятые устройства). "
            "Это основной источник MRR в Model A."
        ),
    )

    # --- Параметры потока пациентов ---
    st.sidebar.markdown("**Поток пациентов (Model A)**")
    st.sidebar.info(
        "При `# пациентов/клинику > 0` (авто) или при ручном вводе модель отслеживает когорты "
        "пациентов по каждой пачке клиник независимо. Это влияет на динамику парка устройств "
        "(расширение при дефиците) и переменные затраты (логистика, поддержка)."
    )

    _patient_mode_a = st.sidebar.radio(
        "Режим потока пациентов",
        options=["auto", "manual"],
        format_func=lambda m: "Автоматический" if m == "auto" else "Ручной ввод",
        key="patient_mode_model_a",
        horizontal=True,
        help=(
            "Автоматический: поток рассчитывается по формуле роста (задаёте стартовое число и % роста). "
            "Ручной: вы вводите число новых пациентов на клинику для каждого месяца вручную."
        ),
    )

    if _patient_mode_a == "auto":
        revenue_params['patients_per_clinic_month1'] = slider_with_manual_int(
            key="model_a_patients_per_clinic_month1",
            label="# новых пациентов/клинику в M1 пачки",
            slider_min=0,
            slider_max=30,
            default_value=int(current_params['revenue'].get('patients_per_clinic_month1', 0) or 0),
            help_text=(
                "Количество новых пациентов, стартующих с устройством, в первый месяц работы клиники. "
                "0 — поток пациентов не моделируется (статическая модель). "
                ">0 — включает когортный трекинг, churn, загрузку и переменные затраты на пациентов. "
                "Применяется к каждой пачке клиник независимо от месяца её старта."
            ),
        )
        revenue_params['growth_rate'] = slider_with_manual_percent(
            key="model_a_growth_rate",
            label="Рост потока новых пациентов/мес (%)",
            slider_min_pct=0,
            slider_max_pct=200,
            default_fraction=float(current_params['revenue'].get('growth_rate', 0.5)),
            help_text=(
                "Каждый месяц новых пациентов становится на X% больше, чем в предыдущем. "
                "Применяется к каждой пачке клиник независимо, начиная с её второго месяца работы. "
                "Например: M1=10 пациентов, рост 50% → M2=15, M3=23, M4=34..."
            ),
        )
    else:
        # В ручном режиме параметры роста не нужны; задаём нейтральные значения
        revenue_params['patients_per_clinic_month1'] = 1  # ненулевое для активации когорт
        revenue_params['growth_rate'] = 0.0

    revenue_params['rehab_duration_months'] = slider_with_manual_int(
        key="model_a_rehab_duration_months",
        label="Срок занятости устройства пациентом (мес)",
        slider_min=1,
        slider_max=12,
        default_value=int(
            current_params['revenue'].get(
                'rehab_duration_months',
                current_params['revenue'].get('avg_rental_duration', 3),
            )
        ),
        help_text=(
            "Сколько месяцев устройство закреплено за одним пациентом до освобождения слота. "
            "Действует в обоих режимах (авто и ручной). "
            "Влияет на ширину когортного блока в таблице клиентской базы."
        ),
    )
    revenue_params['avg_rental_duration'] = revenue_params['rehab_duration_months']

    _btn_label_a = (
        "Ручной ввод клиентской базы" if _patient_mode_a == "manual"
        else "Посмотреть клиентскую базу"
    )
    if st.sidebar.button(
        _btn_label_a, key="open_patient_table_a", use_container_width=True,
        help=(
            "Открыть таблицу когорт пациентов. "
            "В ручном режиме — редактировать кол-во пациентов на клинику по месяцам. "
            "В автоматическом — только просмотр вычисленных значений."
        ),
    ):
        st.session_state.show_patient_table = True

    # --- Расписание подключения клиник ---
    st.sidebar.markdown("---")
    with st.sidebar.expander("🏥 Расписание подключения клиник", expanded=False):
        st.info(
            "**Как это работает:**\n\n"
            "Здесь задаётся расписание подключения дополнительных пачек клиник после месяца 1. "
            "Каждая пачка полностью независима:\n"
            "- собственная история когорт пациентов (старт с месяца подключения)\n"
            "- собственный парк устройств (не шарится с другими клиниками)\n"
            "- рост пациентов считается от месяца старта пачки\n\n"
            "**Пример:** Клиника 1 (M1, 10 пациентов) → к M3 растёт до 23; "
            "новая Клиника 2 (M3, 10 пациентов) → своя когорта с M3, к M4 = 15."
        )

        # Синхронизируем clinic_schedule из saved_params при смене сценария
        _saved_schedule = current_params['revenue'].get('clinic_schedule', [])
        if 'clinic_schedule_model_a_initialized' not in st.session_state:
            st.session_state.clinic_schedule_model_a = list(_saved_schedule)
            st.session_state.clinic_schedule_model_a_initialized = True

        # Показываем текущие пачки
        schedule = st.session_state.clinic_schedule_model_a
        if schedule:
            st.markdown("**Добавленные пачки клиник:**")
            for i, entry in enumerate(list(schedule)):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.markdown(
                        f"**Месяц {entry['month_start']}** — {entry['count']} клин."
                    )
                with col_del:
                    if st.button("🗑️", key=f"del_clinic_batch_{i}"):
                        st.session_state.clinic_schedule_model_a.pop(i)
                        st.rerun()
        else:
            st.caption("Дополнительных пачек нет. Все клиники стартуют в M1.")

        # Форма добавления пачки
        st.markdown("**Добавить пачку:**")
        with st.form("add_clinic_batch", clear_on_submit=True):
            col_ms, col_cnt = st.columns(2)
            with col_ms:
                new_ms = st.number_input(
                    "Месяц старта",
                    min_value=2,
                    max_value=num_months,
                    value=2,
                    step=1,
                    help="С какого месяца подключается эта пачка клиник (минимум 2).",
                )
            with col_cnt:
                new_cnt = st.number_input(
                    "Клиник в пачке",
                    min_value=1,
                    max_value=20,
                    value=1,
                    step=1,
                    help="Сколько клиник подключается в этот месяц.",
                )
            if st.form_submit_button("➕ Добавить пачку"):
                existing = next(
                    (e for e in st.session_state.clinic_schedule_model_a if e["month_start"] == int(new_ms)),
                    None,
                )
                if existing:
                    existing["count"] += int(new_cnt)
                else:
                    st.session_state.clinic_schedule_model_a.append(
                        {"month_start": int(new_ms), "count": int(new_cnt)}
                    )
                    st.session_state.clinic_schedule_model_a.sort(key=lambda x: x["month_start"])
                st.rerun()

    revenue_params['clinic_schedule'] = list(st.session_state.clinic_schedule_model_a)

elif model_type == "model_b":
    revenue_params['num_clinics'] = slider_with_manual_int(
        key="model_b_num_clinics",
        label="# клиник-партнеров",
        slider_min=1,
        slider_max=10,
        default_value=current_params['revenue'].get('num_clinics', 2),
        help_text="Количество клиник-партнеров, через которые пациенты арендуют устройства",
    )

    _patient_mode_b = st.sidebar.radio(
        "Режим потока пациентов",
        options=["auto", "manual"],
        format_func=lambda m: "Автоматический" if m == "auto" else "Ручной ввод",
        key="patient_mode_model_b",
        horizontal=True,
        help=(
            "Автоматический: поток рассчитывается по формуле роста. "
            "Ручной: вы вводите число новых пациентов на клинику для каждого месяца вручную."
        ),
    )

    if _patient_mode_b == "auto":
        revenue_params['patients_per_clinic_month1'] = slider_with_manual_int(
            key="model_b_patients_per_clinic_month1",
            label="# пациентов/клинику (месяц 1)",
            slider_min=1,
            slider_max=20,
            default_value=current_params['revenue'].get('patients_per_clinic_month1', 5),
            help_text="Сколько новых пациентов начинают аренду через одну клинику в первом месяце",
        )
        revenue_params['growth_rate'] = slider_with_manual_percent(
            key="model_b_growth_rate",
            label="Рост пациентов/месяц (%)",
            slider_min_pct=0,
            slider_max_pct=100,
            default_fraction=current_params['revenue'].get('growth_rate', 0.5),
            help_text="На сколько % растет количество пациентов каждый месяц (50% = в 1.5 раза)",
        )
    else:
        revenue_params['patients_per_clinic_month1'] = 1
        revenue_params['growth_rate'] = 0.0

    revenue_params['rental_price'] = slider_with_manual_int(
        key="model_b_rental_price",
        label="Цена аренды/месяц (₽)",
        slider_min=1000,
        slider_max=15000,
        default_value=current_params['revenue'].get('rental_price', 6000),
        step=500,
        help_text="Сколько платит пациент за аренду устройства в месяц",
    )
    revenue_params['rehab_duration_months'] = slider_with_manual_int(
        key="model_b_rehab_duration_months",
        label="Срок реабилитации / занятости устройства (мес)",
        slider_min=1,
        slider_max=12,
        default_value=current_params['revenue'].get('rehab_duration_months', current_params['revenue'].get('avg_rental_duration', 3)),
        help_text=(
            "Сколько месяцев устройство закреплено за пациентом до освобождения. "
            "Действует в обоих режимах (авто и ручной). "
            "Определяет ширину когортного блока в таблице клиентской базы."
        ),
    )
    revenue_params['avg_rental_duration'] = revenue_params['rehab_duration_months']
    revenue_params['clinic_commission_rate'] = slider_with_manual_percent(
        key="model_b_clinic_commission_rate",
        label="Комиссия клиники (%)",
        slider_min_pct=0,
        slider_max_pct=30,
        default_fraction=current_params['revenue'].get('clinic_commission_rate', 0.15),
        help_text="Какой % от платежа пациента получает клиника (остальное идет ReFlex)",
    )

    _btn_label_b = (
        "Ручной ввод клиентской базы" if _patient_mode_b == "manual"
        else "Посмотреть клиентскую базу"
    )
    if st.sidebar.button(
        _btn_label_b, key="open_patient_table_b", use_container_width=True,
        help=(
            "Открыть таблицу когорт пациентов. "
            "В ручном режиме — редактировать кол-во пациентов на клинику по месяцам. "
            "В автоматическом — только просмотр вычисленных значений."
        ),
    ):
        st.session_state.show_patient_table = True

elif model_type == "model_ab":
    revenue_params['num_clinics'] = slider_with_manual_int(
        key="model_ab_num_clinics",
        label="# клиник",
        slider_min=1,
        slider_max=10,
        default_value=current_params['revenue'].get('num_clinics', 2),
        help_text="Количество клиник, которые покупают парк устройств",
    )
    revenue_params['devices_per_clinic'] = slider_with_manual_int(
        key="model_ab_devices_per_clinic",
        label="# устройств/клинику",
        slider_min=5,
        slider_max=20,
        default_value=current_params['revenue'].get('devices_per_clinic', 10),
        help_text="Сколько устройств покупает каждая клиника",
    )
    revenue_params['setup_fee'] = st.sidebar.number_input(
        "Setup Fee (₽)", 0, 200000,
        current_params['revenue'].get('setup_fee', 50000),
        step=5000,
        key="model_ab_setup_fee",
        help="Разовая цена продажи устройства клинике"
    )
    revenue_params['subscription_per_device'] = slider_with_manual_int(
        key="model_ab_subscription_per_device",
        label="Подписка/устройство (₽/мес)",
        slider_min=500,
        slider_max=5000,
        default_value=current_params['revenue'].get('subscription_per_device', 2000),
        step=100,
        help_text="Ежемесячная подписка ReFlex за ПО на устройство",
    )

    _patient_mode_ab = st.sidebar.radio(
        "Режим потока пациентов",
        options=["auto", "manual"],
        format_func=lambda m: "Автоматический" if m == "auto" else "Ручной ввод",
        key="patient_mode_model_ab",
        horizontal=True,
        help=(
            "Автоматический: поток рассчитывается по формуле роста. "
            "Ручной: вы вводите число новых пациентов на клинику для каждого месяца вручную."
        ),
    )

    if _patient_mode_ab == "auto":
        revenue_params['patients_per_clinic_month1'] = slider_with_manual_int(
            key="model_ab_patients_per_clinic_month1",
            label="# пациентов/клинику (месяц 1)",
            slider_min=1,
            slider_max=20,
            default_value=current_params['revenue'].get('patients_per_clinic_month1', 5),
            help_text="Сколько пациентов клиника сдает в аренду в первом месяце",
        )
        revenue_params['growth_rate'] = slider_with_manual_percent(
            key="model_ab_growth_rate",
            label="Рост пациентов/месяц (%)",
            slider_min_pct=0,
            slider_max_pct=100,
            default_fraction=current_params['revenue'].get('growth_rate', 0.5),
            help_text="На сколько % растет количество арендаторов каждый месяц",
        )
    else:
        revenue_params['patients_per_clinic_month1'] = 1
        revenue_params['growth_rate'] = 0.0

    revenue_params['rental_price'] = slider_with_manual_int(
        key="model_ab_rental_price",
        label="Цена аренды/месяц (₽)",
        slider_min=1000,
        slider_max=15000,
        default_value=current_params['revenue'].get('rental_price', 6000),
        step=500,
        help_text="Цена, которую пациент платит клинике за аренду",
    )
    revenue_params['rehab_duration_months'] = slider_with_manual_int(
        key="model_ab_rehab_duration_months",
        label="Срок реабилитации / занятости устройства (мес)",
        slider_min=1,
        slider_max=12,
        default_value=current_params['revenue'].get('rehab_duration_months', current_params['revenue'].get('avg_rental_duration', 3)),
        help_text=(
            "Сколько месяцев устройство закреплено за пациентом до освобождения. "
            "Действует в обоих режимах (авто и ручной). "
            "Определяет ширину когортного блока в таблице клиентской базы."
        ),
    )
    revenue_params['avg_rental_duration'] = revenue_params['rehab_duration_months']
    revenue_params['clinic_commission_rate'] = slider_with_manual_percent(
        key="model_ab_clinic_commission_rate",
        label="Комиссия клиники (%)",
        slider_min_pct=0,
        slider_max_pct=30,
        default_fraction=current_params['revenue'].get('clinic_commission_rate', 0.15),
        help_text="% от аренды, который остается клинике",
    )

    _btn_label_ab = (
        "Ручной ввод клиентской базы" if _patient_mode_ab == "manual"
        else "Посмотреть клиентскую базу"
    )
    if st.sidebar.button(
        _btn_label_ab, key="open_patient_table_ab", use_container_width=True,
        help=(
            "Открыть таблицу когорт пациентов. "
            "В ручном режиме — редактировать кол-во пациентов на клинику по месяцам. "
            "В автоматическом — только просмотр вычисленных значений."
        ),
    ):
        st.session_state.show_patient_table = True

# ---- Срок окупаемости (все модели) ----
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Срок окупаемости")

initial_investment = slider_with_manual_int(
    key=f"{model_type}_initial_investment",
    label="Начальные вложения (₽)",
    slider_min=0,
    slider_max=10_000_000,
    default_value=0,
    step=50_000,
    help_text=(
        "Инвестиции, вложенные в проект до старта (гранты, собственные средства, займы). "
        "Срок окупаемости считается как момент, когда накопленный Cash Flow превысит эту сумму. "
        "При 0 — классический выход в операционный плюс (CumCF >= 0)."
    ),
)

target_breakeven_month = slider_with_manual_int(
    key=f"{model_type}_target_breakeven",
    label="Выйти в плюс к месяцу",
    slider_min=1,
    slider_max=24,
    default_value=3,
    help_text=(
        "Целевой месяц окупаемости: накопленный CF должен превысить начальные вложения к этому месяцу. "
        "Справа будет рассчитана минимально достаточная цена для выбранной модели."
    ),
)

target_margin_rate = slider_with_manual_percent(
    key=f"{model_type}_target_margin_rate",
    label="Запас над окупаемостью (% к суммарным затратам)",
    slider_min_pct=0,
    slider_max_pct=50,
    default_fraction=assumptions_params['desired_margin'] if 'assumptions_params' in locals() else 0.25,
    help_text=(
        "Это не «прибыль в P&L», а дополнительный запас относительно суммарных затрат за месяцы 1..N "
        "(N — «Выйти в плюс к месяцу»).\n\n"
        "0%: чистая окупаемость — CumCF(N) >= Начальные вложения.\n"
        "X%: требуется CumCF(N) >= Вложения + (X/100) × сумма Costs_m за 1..N.\n\n"
        "Отдельно: «Желаемая маржа (%)» в блоке Assumptions влияет на другие расчёты (например, мин. аренда в KPI) "
        "и не совпадает с этим ползунком."
    ),
)

# ---- Ставка дисконтирования (NPV) — глобальная, не зависит от модели ----
st.sidebar.markdown("---")
st.sidebar.markdown("### 📉 NPV (ставка дисконтирования)")

discount_rate_annual = slider_with_manual_percent(
    key="global_discount_rate",
    label="Годовая ставка дисконтирования (%)",
    slider_min_pct=0,
    slider_max_pct=100,
    default_fraction=st.session_state.get("discount_rate_annual", 0.20),
    help_text=(
        "Годовая ставка дисконтирования для расчёта NPV (чистой приведённой стоимости).\n\n"
        "Месячная ставка: r_m = (1 + r_год)^(1/12) − 1\n\n"
        "NPV(T) = Σ CF_t / (1 + r_m)^t — дисконтированный накопленный CF: "
        "показывает, сколько «сегодняшних рублей» стоит будущий Cash Flow с учётом стоимости денег во времени. "
        "Чем выше ставка — тем сильнее обесцениваются дальние денежные потоки. "
        "Ориентир для российского рынка: ключевая ставка + премия за риск (20–35%)."
    ),
)
st.session_state["discount_rate_annual"] = discount_rate_annual

# ========== R&D ФАЗА ==========
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔬 R&D фаза")

_rnd_enabled_new = st.sidebar.toggle(
    "Включить R&D фазу перед продажами",
    value=st.session_state.rnd_enabled,
    key="rnd_enabled_toggle",
    help=(
        "Добавляет период исследований и разработки до старта продаж. "
        "Расходы R&D списываются из банка инвестиций. "
        "Нумерация рыночных месяцев на других графиках не изменяется. "
        "NPV дисконтируется с учётом реального времени от инвестиций."
    ),
)
st.session_state.rnd_enabled = _rnd_enabled_new

if st.session_state.rnd_enabled:
    with st.sidebar.expander("⚙️ Настройки R&D фазы", expanded=True):
        rnd_months_val = st.slider(
            "Длительность R&D (мес)",
            min_value=1,
            max_value=MAX_RND_MONTHS,
            value=st.session_state.rnd_months,
            key="rnd_months_slider",
            help="Сколько месяцев длится фаза R&D до выхода на рынок.",
        )
        if rnd_months_val != st.session_state.rnd_months:
            st.session_state.rnd_months = rnd_months_val
            # Обнуляем матрицу расходов при изменении длительности
            old_matrix = st.session_state.rnd_costs_matrix
            new_matrix = {}
            for cat in st.session_state.rnd_cost_categories:
                old_vals = old_matrix.get(cat, [])
                padded = list(old_vals)
                while len(padded) < rnd_months_val:
                    padded.append(0.0)
                new_matrix[cat] = padded[:rnd_months_val]
            st.session_state.rnd_costs_matrix = new_matrix

        st.markdown("**Категории расходов R&D** (редактируемые названия):")
        new_categories = []
        for i, cat in enumerate(st.session_state.rnd_cost_categories):
            edited = st.text_input(
                f"Статья {i + 1}",
                value=cat,
                key=f"rnd_cat_{i}",
                label_visibility="collapsed",
            )
            if edited and edited != cat:
                # Переименовываем в матрице
                old_matrix = st.session_state.rnd_costs_matrix
                if cat in old_matrix:
                    old_matrix[edited] = old_matrix.pop(cat)
                    st.session_state.rnd_costs_matrix = old_matrix
            new_categories.append(edited if edited else cat)
        st.session_state.rnd_cost_categories = new_categories

        # Кнопки добавления/удаления категорий
        _cat_cols = st.columns(2)
        with _cat_cols[0]:
            if st.button("＋ Добавить статью", use_container_width=True,
                         help="Добавить ещё одну категорию расходов R&D"):
                st.session_state.rnd_cost_categories.append(f"Расход R&D {len(st.session_state.rnd_cost_categories) + 1}")
                st.rerun()
        with _cat_cols[1]:
            if len(st.session_state.rnd_cost_categories) > 1:
                if st.button("－ Удалить последнюю", use_container_width=True,
                             help="Удалить последнюю категорию расходов R&D"):
                    removed = st.session_state.rnd_cost_categories.pop()
                    st.session_state.rnd_costs_matrix.pop(removed, None)
                    st.rerun()

        # Кнопка открытия таблицы расходов
        st.markdown("---")
        # Live-сводка расходов R&D
        _rnd_total_live = get_total_rnd_cost(
            st.session_state.rnd_costs_matrix, st.session_state.rnd_months
        )
        _rnd_validation_live = validate_rnd_vs_bank(_rnd_total_live, initial_investment)
        if _rnd_total_live > 0:
            if _rnd_validation_live["ok"]:
                st.info(f"Расходы R&D: **{_rnd_total_live:,.0f} ₽** | Остаток банка: {_rnd_validation_live['remaining']:,.0f} ₽")
            else:
                st.error(_rnd_validation_live["message"])
        else:
            st.caption("Расходы R&D не заданы. Откройте таблицу для ввода.")

        if st.button(
            "📋 Заполнить расходы R&D по месяцам",
            use_container_width=True,
            type="primary",
            help="Открывает таблицу: строки = категории затрат, столбцы = R&D месяцы",
        ):
            _show_rnd_table_dialog(
                rnd_months=st.session_state.rnd_months,
                categories=st.session_state.rnd_cost_categories,
                initial_investment=initial_investment,
            )

    # Итоговые переменные R&D для использования ниже
    rnd_enabled = True
    rnd_months = st.session_state.rnd_months
    # Нормализуем матрицу под текущее число месяцев и категорий
    _rnd_matrix_normalized = {
        cat: (
            (st.session_state.rnd_costs_matrix.get(cat, []) + [0.0] * rnd_months)[:rnd_months]
        )
        for cat in st.session_state.rnd_cost_categories
    }
    rnd_results = calculate_rnd_cash_flows(rnd_months, _rnd_matrix_normalized)
    rnd_total_cost = get_total_rnd_cost(_rnd_matrix_normalized, rnd_months)
    rnd_validation = validate_rnd_vs_bank(rnd_total_cost, initial_investment)
else:
    rnd_enabled = False
    rnd_months = 0
    rnd_results = []
    rnd_total_cost = 0.0
    rnd_validation = {"ok": True, "remaining": initial_investment, "overflow": 0.0, "pct_used": 0.0, "message": ""}

model_ab_pricing_mode = "rental_only"
if model_type == "model_ab":
    model_ab_pricing_mode = st.sidebar.selectbox(
        "Что прогнозировать в A+B:",
        options=["rental_only", "subscription_only", "both_scaled"],
        format_func=lambda x: {
            "rental_only": "Только аренду пациенту (подписка фиксирована)",
            "subscription_only": "Только подписку клинике (аренда фиксирована)",
            "both_scaled": "И подписку, и аренду пропорционально",
        }[x],
        help="Выберите, какой ценовой рычаг менять для достижения цели.",
    )

# ========== ПАРАМЕТРЫ FIXED COSTS ==========
st.sidebar.markdown("---")
st.sidebar.markdown("### 💰 Fixed Costs")

fixed_costs_params = {
    'team_salaries': st.sidebar.number_input(
        "Зарплаты команды (₽/мес)", 0, 2000000,
        current_params['fixed_costs'].get('team_salaries', 500000),
        step=50000,
        key=f"{model_type}_fixed_team_salaries",
        help="Общий фонд оплаты труда команды в месяц (постоянные затраты)"
    ),
    'infrastructure_fixed': st.sidebar.number_input(
        "Инфраструктура (₽/мес)", 0, 100000,
        current_params['fixed_costs'].get('infrastructure_fixed', 20000),
        step=5000,
        key=f"{model_type}_fixed_infrastructure_fixed",
        help="Постоянные расходы на серверы, облако, лицензии (не зависят от количества пользователей)"
    ),
    'office_rent': st.sidebar.number_input(
        "Офис/коворкинг (₽/мес)", 0, 200000,
        current_params['fixed_costs'].get('office_rent', 30000),
        step=5000,
        key=f"{model_type}_fixed_office_rent",
        help="Аренда офиса или коворкинга в месяц"
    ),
    'legal_services': st.sidebar.number_input(
        "Юридические услуги (₽/мес)", 0, 100000,
        current_params['fixed_costs'].get('legal_services', 10000),
        step=5000,
        key=f"{model_type}_fixed_legal_services",
        help="Юридическое сопровождение, договоры, консультации (ежемесячные расходы)"
    ),
    'other_fixed': st.sidebar.number_input(
        "Прочее (₽/мес)", 0, 50000,
        current_params['fixed_costs'].get('other_fixed', 10000),
        step=5000,
        key=f"{model_type}_fixed_other_fixed",
        help="Бухгалтерия, подписки на ПО, прочие постоянные расходы"
    )
}

# Кастомные Fixed Costs
st.sidebar.markdown("#### ➕ Свои статьи Fixed Costs")
with st.sidebar.expander("Добавить/редактировать"):
    # Форма добавления новой статьи
    with st.form("add_custom_fixed", clear_on_submit=True):
        new_fixed_name = st.text_input(
            "Название статьи",
            placeholder="Например: Маркетинг",
            help="Произвольное название — появится в расчётах и экспорте.",
        )
        new_fixed_value = st.number_input(
            "Сумма (₽/мес)",
            min_value=0,
            value=0,
            step=1000,
            help="Ежемесячная сумма в рублях (для единоразовых — только в месяц 1).",
        )
        new_fixed_type = st.selectbox(
            "Тип",
            ["Ежемесячная", "Единоразовая (месяц 1)"],
            help="Ежемесячная — учитывается каждый месяц. Единоразовая — только в первый месяц (запуск, регистрация и т.п.).",
        )
        
        if st.form_submit_button("➕ Добавить"):
            if new_fixed_name:
                st.session_state.custom_fixed_costs[model_type][new_fixed_name] = {
                    'value': new_fixed_value,
                    'type': new_fixed_type
                }
                st.success(f"✅ Добавлено: {new_fixed_name}")
                st.rerun()
    
    # Список существующих кастомных статей
    if st.session_state.custom_fixed_costs[model_type]:
        st.markdown("**Текущие кастомные статьи:**")
        for name, data in list(st.session_state.custom_fixed_costs[model_type].items()):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{name}: {data['value']:,} ₽")
                st.caption(data['type'])
            with col2:
                if st.button("🗑️", key=f"del_fixed_{name}"):
                    del st.session_state.custom_fixed_costs[model_type][name]
                    st.rerun()

# Добавляем кастомные fixed costs в общий словарь
for name, data in st.session_state.custom_fixed_costs[model_type].items():
    fixed_costs_params[f"custom_fixed_{name}"] = data['value']

# ========== ПАРАМЕТРЫ VARIABLE COSTS ==========
st.sidebar.markdown("---")
st.sidebar.markdown("### 📦 Variable Costs")

variable_costs_params = {
    'cogs_per_device': st.sidebar.number_input(
        "COGS (себестоимость устройства, ₽)", 0, 100000,
        current_params['variable_costs'].get('cogs_per_device', 15000),
        step=1000,
        key=f"{model_type}_var_cogs_per_device",
        help="Себестоимость производства одного устройства (плата только при изготовлении новых устройств)"
    ),
    'logistics_per_patient': st.sidebar.number_input(
        "Логистика/пациента (₽)", 0, 5000,
        current_params['variable_costs'].get('logistics_per_patient', 500),
        step=100,
        key=f"{model_type}_var_logistics_per_patient",
        help="Доставка устройства пациенту туда-обратно (единоразово на пациента)"
    ),
    'support_per_patient_per_month': st.sidebar.number_input(
        "Поддержка/пациента/мес (₽)", 0, 2000,
        current_params['variable_costs'].get('support_per_patient_per_month', 200),
        step=50,
        key=f"{model_type}_var_support_per_patient_per_month",
        help="Техническая поддержка одного пациента в месяц (растет с количеством пациентов)"
    ),
    'cac_clinic': st.sidebar.number_input(
        "CAC (привлечение клиники, ₽)", 0, 100000,
        current_params['variable_costs'].get('cac_clinic', 10000),
        step=1000,
        key=f"{model_type}_var_cac_clinic",
        help="Customer Acquisition Cost - затраты на привлечение одной клиники (маркетинг, продажи)"
    ),
    'cac_patient': st.sidebar.number_input(
        "CAC (привлечение пациента, ₽)", 0, 5000,
        current_params['variable_costs'].get('cac_patient', 0),
        step=100,
        key=f"{model_type}_var_cac_patient",
        help="Затраты на привлечение одного пациента напрямую (если есть прямой канал)"
    ),
    'infrastructure_per_user': st.sidebar.number_input(
        "Инфраструктура/пользователя (₽/мес)", 0, 500,
        current_params['variable_costs'].get('infrastructure_per_user', 50),
        step=10,
        key=f"{model_type}_var_infrastructure_per_user",
        help="Переменные расходы на инфраструктуру на одного активного пользователя (облако, трафик)"
    )
}
# Нужен для custom variable типа "На клинику (разово)" в модели затрат.
variable_costs_params['num_clinics'] = revenue_params.get('num_clinics', 0)

# Кастомные Variable Costs
st.sidebar.markdown("#### ➕ Свои статьи Variable Costs")
with st.sidebar.expander("Добавить/редактировать"):
    # Форма добавления новой статьи
    with st.form("add_custom_variable", clear_on_submit=True):
        new_var_name = st.text_input(
            "Название статьи",
            placeholder="Например: Упаковка",
            help="Произвольное название — появится в расчётах и экспорте.",
        )
        new_var_value = st.number_input(
            "Сумма (₽)",
            min_value=0,
            value=0,
            step=100,
            help="Сумма за одну единицу привязки (устройство, пациент или клиника).",
        )
        new_var_type = st.selectbox(
            "Привязка",
            [
                "На устройство (разово)",
                "На пациента (разово)",
                "На пациента/месяц",
                "На клинику (разово)",
            ],
            help=(
                "На устройство — умножается на кол-во произведённых устройств в месяц. "
                "На пациента (разово) — один раз при появлении нового пациента. "
                "На пациента/месяц — каждый месяц на каждого активного пациента. "
                "На клинику (разово) — один раз при подключении клиники."
            ),
        )
        
        if st.form_submit_button("➕ Добавить"):
            if new_var_name:
                st.session_state.custom_variable_costs[model_type][new_var_name] = {
                    'value': new_var_value,
                    'type': new_var_type
                }
                st.success(f"✅ Добавлено: {new_var_name}")
                st.rerun()
    
    # Список существующих кастомных статей
    if st.session_state.custom_variable_costs[model_type]:
        st.markdown("**Текущие кастомные статьи:**")
        for name, data in list(st.session_state.custom_variable_costs[model_type].items()):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{name}: {data['value']:,} ₽")
                st.caption(data['type'])
            with col2:
                if st.button("🗑️", key=f"del_var_{name}"):
                    del st.session_state.custom_variable_costs[model_type][name]
                    st.rerun()

# Добавляем кастомные variable costs в общий словарь
for name, data in st.session_state.custom_variable_costs[model_type].items():
    variable_costs_params[f"custom_var_{name}"] = data['value']

# ========== ASSUMPTIONS ==========
st.sidebar.markdown("---")
with st.sidebar.expander("🎯 Assumptions", expanded=False):
    assumptions_params = {
        'amortization_months': slider_with_manual_int(
            key="assumptions_amortization_months",
            label="Срок амортизации (мес)",
            slider_min=12,
            slider_max=36,
            default_value=current_params.get('assumptions', {}).get('amortization_months', 24),
            help_text="За сколько месяцев окупается стоимость устройства при аренде. Используется в what-if оценке допущений.",
        ),
        'utilization_rate': slider_with_manual_percent(
            key="assumptions_utilization_rate",
            label="Загрузка устройств (%)",
            slider_min_pct=30,
            slider_max_pct=100,
            default_fraction=current_params.get('assumptions', {}).get('utilization_rate', 0.60),
            help_text=(
                "Доля слотов парка, по которым считается эффективная нагрузка (выручка B/B2C и пациенты в A при потоке >0). "
                "В модели A ограничивает число одновременных пациентов сверху: не больше парк × загрузка."
            ),
        ),
        'churn_rate': slider_with_manual_percent(
            key="assumptions_churn_rate",
            label="Churn пациентов (%)",
            slider_min_pct=0,
            slider_max_pct=50,
            default_fraction=current_params.get('assumptions', {}).get('churn_rate', 0.20),
            help_text=(
                "Доля активных пациентов (после когортного суммирования), «отваливающая» до выручки: "
                "эффективные пациенты = max(0, round(актив_когорта × (1 − churn))). Учитывается во всех трёх моделях."
            ),
        ),
        'desired_margin': slider_with_manual_percent(
            key="assumptions_desired_margin",
            label="Желаемая маржа (%)",
            slider_min_pct=10,
            slider_max_pct=50,
            default_fraction=current_params.get('assumptions', {}).get('desired_margin', 0.25),
            help_text="Какую маржу закладывать при расчете целевой цены.",
        )
    }

# Собираем все параметры
all_params = {
    'revenue': revenue_params,
    'fixed_costs': fixed_costs_params,
    'variable_costs': variable_costs_params,
    'assumptions': assumptions_params,
    'custom_fixed_costs': st.session_state.custom_fixed_costs[model_type],
    'custom_variable_costs': st.session_state.custom_variable_costs[model_type]
}

# Автосохранение базовых настроек текущей модели
_revenue_to_save = revenue_params.copy()
if model_type == 'model_a':
    _revenue_to_save['clinic_schedule'] = list(st.session_state.get('clinic_schedule_model_a', []))
st.session_state.saved_params[model_type] = {
    'revenue': _revenue_to_save,
    'fixed_costs': fixed_costs_params.copy(),
    'variable_costs': variable_costs_params.copy(),
    'assumptions': assumptions_params.copy(),
}

with config_actions_placeholder:
    st.markdown("### ⚙️ Действия с конфигурацией")
    with st.expander("💾 Слепок конфигурации", expanded=False):
        snapshot_saved_params = {
            'model_a': st.session_state.saved_params.get('model_a', defaults['model_a']['parameters']).copy(),
            'model_b': st.session_state.saved_params.get('model_b', defaults['model_b']['parameters']).copy(),
            'model_ab': st.session_state.saved_params.get('model_ab', defaults['model_ab']['parameters']).copy(),
        }
        _vc_for_snapshot = {k: v for k, v in variable_costs_params.items() if k != 'num_clinics'}
        snapshot_saved_params[model_type] = {
            'revenue': revenue_params.copy(),
            'fixed_costs': fixed_costs_params.copy(),
            'variable_costs': _vc_for_snapshot,
            'assumptions': assumptions_params.copy(),
        }

        snapshot_state = {
            'num_months': st.session_state.num_months,
            'discount_rate_annual': float(st.session_state.get('discount_rate_annual', 0.20)),
            'saved_params': snapshot_saved_params,
            'custom_fixed_costs': st.session_state.custom_fixed_costs,
            'custom_variable_costs': st.session_state.custom_variable_costs,
            'custom_revenue': st.session_state.custom_revenue,
            'patient_mode_model_a': st.session_state.get('patient_mode_model_a', 'auto'),
            'patient_mode_model_b': st.session_state.get('patient_mode_model_b', 'auto'),
            'patient_mode_model_ab': st.session_state.get('patient_mode_model_ab', 'auto'),
            'manual_patients_matrix_model_a': st.session_state.get('manual_patients_matrix_model_a', [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]),
            'manual_patients_matrix_model_b': st.session_state.get('manual_patients_matrix_model_b', [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]),
            'manual_patients_matrix_model_ab': st.session_state.get('manual_patients_matrix_model_ab', [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)]),
            'clinic_schedule_model_a': list(st.session_state.get('clinic_schedule_model_a', [])),
            # R&D phase
            'rnd_enabled': st.session_state.get('rnd_enabled', False),
            'rnd_months': st.session_state.get('rnd_months', 3),
            'rnd_cost_categories': list(st.session_state.get('rnd_cost_categories', [])),
            'rnd_costs_matrix': dict(st.session_state.get('rnd_costs_matrix', {})),
        }

        _predictor_settings_for_snapshot = {
            m: {
                "initial_investment": st.session_state.get(f"{m}_initial_investment_value", 0),
                "target_breakeven_month": st.session_state.get(f"{m}_target_breakeven_value", 3),
                "target_margin_rate": st.session_state.get(f"{m}_target_margin_rate_value", 0.25),
            }
            for m in ("model_a", "model_b", "model_ab")
        }
        snapshot = build_config_snapshot(
            session_state=snapshot_state,
            defaults=defaults,
            assumption_ids=ASSUMPTION_IDS,
            app_version="v1.0",
            predictor_settings=_predictor_settings_for_snapshot,
        )
        snapshot_name = f"reflex_config_snapshot_{date.today().isoformat()}.json"
        st.download_button(
            label="⬇️ Скачать слепок конфигурации",
            data=json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=snapshot_name,
            mime="application/json",
            help="Содержит все сохраненные параметры моделей, кастомные статьи и stage-gate статусы.",
        )

        uploaded_snapshot = st.file_uploader(
            "Загрузить слепок конфигурации (.json)",
            type=["json"],
            key="config_snapshot_uploader",
            help="Импортирует настройки со всех моделей с учетом совместимости версий.",
        )

        if uploaded_snapshot is not None:
            try:
                uploaded_data = json.loads(uploaded_snapshot.getvalue().decode("utf-8"))
            except Exception as exc:
                st.error(f"Не удалось прочитать JSON: {exc}")
                uploaded_data = None

            if uploaded_data is not None:
                preflight = preflight_config_snapshot(
                    snapshot_data=uploaded_data,
                    defaults=defaults,
                    assumption_ids=ASSUMPTION_IDS,
                )
                if not preflight["valid"]:
                    st.error("Файл конфигурации невалиден.")
                    for err in preflight["errors"]:
                        st.caption(f"- {err}")
                else:
                    meta = preflight["meta"]
                    st.caption(
                        f"schema_version: {meta.get('schema_version', 'unknown')} "
                        f"(поддерживаемая: {SNAPSHOT_SCHEMA_VERSION})"
                    )
                    if meta.get("exported_at"):
                        st.caption(f"exported_at: {meta['exported_at']}")
                    if meta.get("app_version"):
                        st.caption(f"app_version: {meta['app_version']}")

                    if preflight["missing_fields"]:
                        st.info(
                            "В слепке отсутствуют новые параметры текущей версии. "
                            "Они будут заполнены 0 или дефолтным значением."
                        )
                        st.caption(
                            "Отсутствующие поля: "
                            + ", ".join(preflight["missing_fields"][:8])
                            + (" ..." if len(preflight["missing_fields"]) > 8 else "")
                        )

                    for warn in preflight["warnings"]:
                        st.warning(warn)

                    st.caption("Текущие локальные настройки будут перезаписаны.")
                    unknown_fields = preflight["unknown_fields"]
                    if unknown_fields:
                        st.error(
                            "В слепке найдены параметры, которых нет в этой версии калькулятора."
                        )
                        st.caption(
                            "Неизвестные поля: "
                            + ", ".join(unknown_fields[:8])
                            + (" ..." if len(unknown_fields) > 8 else "")
                        )
                        col_ignore, col_cancel = st.columns(2)
                        with col_ignore:
                            if st.button("Игнорировать и применить", key="apply_snapshot_ignore_unknown"):
                                st.session_state['_pending_snapshot_payload'] = preflight["normalized_payload"]
                                st.rerun()
                        with col_cancel:
                            if st.button("Отменить импорт", key="cancel_snapshot_import"):
                                st.info("Импорт отменен. Текущие настройки сохранены.")
                    else:
                        if st.button("Применить конфигурацию", key="apply_snapshot_config"):
                            st.session_state['_pending_snapshot_payload'] = preflight["normalized_payload"]
                            st.rerun()

    if st.button("🔄 Сбросить к дефолтным", help="Вернуть параметры к значениям по умолчанию для этой модели"):
        st.session_state.saved_params[model_type] = defaults[model_type]['parameters'].copy()
        st.session_state.custom_fixed_costs[model_type] = {}
        st.session_state.custom_variable_costs[model_type] = {}
        if model_type == "model_a":
            st.session_state.clinic_schedule_model_a = []
            # сбрасываем флаг инициализации, чтобы при следующем рендере подхватился дефолт
            if 'clinic_schedule_model_a_initialized' in st.session_state:
                del st.session_state['clinic_schedule_model_a_initialized']
        common_keys = [
            f"{model_type}_target_breakeven",
            f"{model_type}_target_margin_rate",
            f"{model_type}_initial_investment",
            "assumptions_amortization_months",
            "assumptions_utilization_rate",
            "assumptions_churn_rate",
            "assumptions_desired_margin",
        ]
        model_keys: list[str] = []
        if model_type == "model_a":
            model_keys = [
                "model_a_num_clinics",
                "model_a_devices_per_clinic",
                "model_a_subscription_per_device",
                "model_a_patients_per_clinic_month1",
                "model_a_growth_rate",
                "model_a_rehab_duration_months",
            ]
        elif model_type == "model_b":
            model_keys = [
                "model_b_num_clinics",
                "model_b_patients_per_clinic_month1",
                "model_b_growth_rate",
                "model_b_rental_price",
                "model_b_rehab_duration_months",
                "model_b_clinic_commission_rate",
            ]
        else:
            model_keys = [
                "model_ab_num_clinics",
                "model_ab_devices_per_clinic",
                "model_ab_subscription_per_device",
                "model_ab_patients_per_clinic_month1",
                "model_ab_growth_rate",
                "model_ab_rental_price",
                "model_ab_rehab_duration_months",
                "model_ab_clinic_commission_rate",
            ]
        removed = _clear_param_widget_state(model_keys + common_keys)
        st.rerun()

# Валидация
is_valid, error_message = validate_all_params(model_type, all_params)
if not is_valid:
    st.sidebar.error(f"Ошибка валидации: {error_message}")
    st.stop()

# ========== ДИАЛОГ КЛИЕНТСКОЙ БАЗЫ ==========
# Вызываем модальное окно, если пользователь нажал кнопку
if st.session_state.get('show_patient_table', False):
    _rehab_dur = int(revenue_params.get('rehab_duration_months', 3))
    # Вычисляем авто-значения (новых пациентов на клинику по месяцам) для режима просмотра
    _auto_new, _ = _project_patient_counts(
        num_clinics=1,  # per-clinic: делим на 1
        patients_per_clinic_month1=int(revenue_params.get('patients_per_clinic_month1', 0) or 0),
        growth_rate=float(revenue_params.get('growth_rate', 0.0)),
        target_month=num_months,
        rehab_duration_months=_rehab_dur,
    )
    _show_patient_table_dialog(model_type, num_months, _rehab_dur, auto_values=_auto_new)
    st.session_state.show_patient_table = False

# Убеждаемся, что manual_patients_{model} достаточной длины для горизонта
_mp_key = f'manual_patients_{model_type}'
_mp_list = list(st.session_state.get(_mp_key, []))
while len(_mp_list) < num_months:
    _mp_list.append(0)
st.session_state[_mp_key] = _mp_list

# Получаем ручные данные в зависимости от модели и режима
_patient_mode = st.session_state.get(f'patient_mode_{model_type}', 'auto')
_matrix_key = f'manual_patients_matrix_{model_type}'
_matrix = st.session_state.get(_matrix_key, [[0] * MAX_MONTHS for _ in range(MAX_MONTHS)])
_rehab_dur_calc = int(revenue_params.get('rehab_duration_months', revenue_params.get('avg_rental_duration', 3)))

_manual_patients: list | None = None
_manual_active_patients: list | None = None

if _patient_mode == 'manual':
    if model_type == 'model_a':
        # Model A: передаём диагональ матрицы (новые пациенты по когортам)
        _manual_patients = [
            int(_matrix[i][i]) if i < len(_matrix) and i < len(_matrix[i]) else 0
            for i in range(num_months)
        ]
    else:
        # Model B / AB: передаём суммарные активные пациенты на клинику по месяцам
        _manual_active_patients = _compute_cohort_active_from_matrix(
            _matrix, num_months, _rehab_dur_calc
        )

# ========== РАСЧЕТЫ ==========
# Вычисляем все метрики
revenue_results = calculate_revenue_for_months(
    model_type, revenue_params, num_months,
    assumptions=assumptions_params,
    manual_new_patients_per_clinic=_manual_patients,
    manual_active_patients_per_clinic=_manual_active_patients,
)
costs_results = calculate_costs_for_months(
    model_type, fixed_costs_params, variable_costs_params, revenue_results, num_months,
    st.session_state.custom_fixed_costs[model_type],
    st.session_state.custom_variable_costs[model_type]
)
cash_flow_results = calculate_cash_flow_for_months(revenue_results, costs_results, num_months)

# Инвестиционный банк
_bank_strategy = st.session_state.get("bank_allocation_strategy", "proportional")
# R&D расходы покрываются банком до старта рынка; рыночная фаза начинается с остатка.
_remaining_for_market = max(0.0, initial_investment - rnd_total_cost) if rnd_enabled else initial_investment
bank_allocation = calculate_bank_allocation(
    costs_results, _remaining_for_market, strategy=_bank_strategy
)

# ── Синтетические записи R&D для инвестиционного банка ──────────────────────
# Все расходы R&D покрываются банком на 100%; строим записи в том же формате,
# что и calculate_bank_allocation, для использования в KPI, графике и экспорте.
rnd_bank_entries: list = []
if rnd_enabled and rnd_results:
    _rnd_bank = float(initial_investment)
    for _r in rnd_results:
        _cost = _r["total_costs"]
        _used = min(_rnd_bank, _cost)
        _end = max(0.0, _rnd_bank - _used)
        rnd_bank_entries.append({
            "month": f"R&D {_r['month']}",
            "month_label": f"R&D {_r['month']}",
            "bank_at_start": _rnd_bank,
            "bank_used": _used,
            "bank_at_end": _end,
            "fully_covered": _rnd_bank >= _cost,
            "coverage_ratio": (_used / _cost) if _cost > 0 else 1.0,
            "line_items": {
                cat: {"total": v, "bank": v, "own": 0.0}
                for cat, v in _r["breakdown"].items()
            },
        })
        _rnd_bank = _end

# Объединённое распределение: R&D месяцы (из банка) + рыночные месяцы
combined_bank_allocation = rnd_bank_entries + bank_allocation

# NPV: единая серия от первого R&D месяца до конца рыночного горизонта.
# R&D CFs (отрицательные) + рыночные CFs дисконтируются без сдвига (month_offset=0),
# что корректно отражает временну́ю стоимость денег от момента инвестиций.
_cf_monthly = [cf['cash_flow'] for cf in cash_flow_results]
_rnd_cf_monthly = [r['cash_flow'] for r in rnd_results]   # пусто если R&D выключен
_combined_cf = _rnd_cf_monthly + _cf_monthly               # R&D + рыночные

_pv_combined = calculate_npv_series(_combined_cf, discount_rate_annual, month_offset=0)
_npv_combined = [pv - initial_investment for pv in _pv_combined]

# Разделяем обратно для графика и для остальных расчётов
rnd_npv_series = _npv_combined[:len(_rnd_cf_monthly)]     # часть R&D (может быть пустой)
npv_series = _npv_combined[len(_rnd_cf_monthly):]          # часть рынка (как раньше)

# Breakeven / payback analysis
revenue_monthly = [cf['revenue'] for cf in cash_flow_results]
costs_monthly = [cf['total_costs'] for cf in cash_flow_results]
breakeven_result = calculate_breakeven_month(
    revenue_monthly, costs_monthly, 24,
    initial_investment=initial_investment,
)

# Переменные затраты на пациента (общие для всех расчётов B/AB)
_var_per_patient = (
    variable_costs_params['logistics_per_patient']
    + variable_costs_params['support_per_patient_per_month']
    + variable_costs_params['infrastructure_per_user']
)
_avg_fixed_costs = sum([c['fixed_costs']['total'] for c in costs_results]) / max(num_months, 1)

# Старый "среднемесячный" расчёт мин. цены (для KPI-карточки и model_ab)
if model_type in ['model_b', 'model_ab']:
    avg_patients = sum([r.get('num_patients', 0) for r in revenue_results]) / max(num_months, 1)
    min_rental_price = calculate_min_rental_price_for_breakeven(
        fixed_costs_monthly=_avg_fixed_costs,
        variable_costs_per_patient=_var_per_patient,
        num_patients_monthly=int(avg_patients),
        clinic_commission_rate=revenue_params.get('clinic_commission_rate', 0.15),
        desired_margin=assumptions_params['desired_margin']
    )
else:
    min_rental_price = float('inf')

# Универсальный предиктор цены под целевой месяц безубыточности (A / B / A+B)
target_pricing_result = _calc_target_pricing_predictor(
    model_type=model_type,
    revenue_params=revenue_params,
    fixed_costs_params=fixed_costs_params,
    variable_costs_params=variable_costs_params,
    target_month=target_breakeven_month,
    desired_margin=target_margin_rate,
    model_ab_mode=model_ab_pricing_mode,
    custom_fixed_costs=st.session_state.custom_fixed_costs[model_type],
    custom_variable_costs=st.session_state.custom_variable_costs[model_type],
    assumptions_for_revenue=assumptions_params,
    initial_investment=initial_investment,
    manual_new_patients_per_clinic=_manual_patients,
    manual_active_patients_per_clinic=_manual_active_patients,
    discount_rate_annual=discount_rate_annual,
)
# Unit Economics
unit_economics = calculate_unit_economics_from_params(model_type, revenue_params, variable_costs_params)
base_metrics = _compute_core_metrics(
    model_type,
    revenue_results,
    costs_results,
    cash_flow_results,
    revenue_params,
    variable_costs_params,
    assumptions_params,
)
assumption_impact_results = {}
for assumption_id in ASSUMPTION_IDS:
    assumption_impact_results[assumption_id] = _build_assumption_what_if(
        assumption_id=assumption_id,
        model_type=model_type,
        revenue_params=revenue_params,
        fixed_costs_params=fixed_costs_params,
        variable_costs_params=variable_costs_params,
        assumptions_params=assumptions_params,
        num_months=num_months,
        custom_fixed_costs=st.session_state.custom_fixed_costs[model_type],
        custom_variable_costs=st.session_state.custom_variable_costs[model_type],
        base_metrics=base_metrics,
    )

# Sensitivity Analysis (может быть долгим, делаем опционально)
total_cf = sum([cf['cash_flow'] for cf in cash_flow_results])

# ========== MAIN AREA ==========

# Описание модели над дашбордом (текущий расчёт)
_md = MODEL_DESCRIPTIONS.get(model_type, {})
with st.expander(f"📘 Модель в расчёте: {defaults[model_type]['name']}", expanded=False):
    st.markdown(f"**Кратко:** {_md.get('tagline', defaults[model_type].get('description', ''))}")
    st.markdown(_md.get("body", ""))
    st.caption(
        "Если выбран готовый сценарий, тип модели может подставиться из сценария — проверьте блок слева «Бизнес-модель» и этот текст."
    )

pending_stage_gates = [
    aid for aid, status in stage_gate_statuses.items() if status != "validated"
]
if pending_stage_gates:
    markers = ", ".join([f"{aid}={ASSUMPTION_STATUS_OPTIONS[stage_gate_statuses[aid]]}" for aid in ASSUMPTION_IDS])
    st.warning(
        "Stage-gate активен: A01-A04 не закрыты полностью. "
        "Используйте target pricing и sensitivity как рабочие гипотезы, а не финальное коммерческое решение.\n\n"
        f"Текущие confidence markers: {markers}"
    )
else:
    st.success("Stage-gate пройден: A01-A04 отмечены как validated.")

with st.expander("🧪 Влияние допущений (mini what-if)", expanded=False):
    st.info(
        "**Что такое «допущения» и зачем их отслеживать?**\n\n"
        "Финансовая модель строится на гипотезах — предположениях о поведении рынка (WTP пациентов, "
        "готовность клиник платить и т.д.). Пока гипотеза не проверена интервью или пилотом, "
        "её статус — «гипотеза» (🟠). После валидации — «validated» (🟢).\n\n"
        "Этот блок показывает: **на сколько рублей изменится выручка и Cash Flow**, "
        "если допущение A01–A04 окажется хуже или лучше ожидаемого. "
        "Смотрите на Δ, чтобы понять, какие гипотезы критичны для бизнес-плана."
    )
    st.caption("Показывает численную дельту метрик при тестовом изменении гипотезы A01-A04.")
    for aid in ASSUMPTION_IDS:
        status = stage_gate_statuses[aid]
        status_label = ASSUMPTION_STATUS_OPTIONS[status]
        deltas = assumption_impact_results[aid]["deltas"]
        note = assumption_impact_results[aid]["note"]
        mark = "🟢" if status == "validated" else "🟠"
        st.markdown(f"**{mark} {ASSUMPTION_LABELS[aid]}** — статус: `{status_label}`")
        st.caption(f"Связанные метрики: {', '.join(ASSUMPTION_IMPACT_METRICS.get(aid, []))}")
        st.caption(note)
        col1, col2, col3 = st.columns(3)
        col1.metric("Δ Выручка", format_currency(deltas["total_revenue"]))
        col2.metric("Δ Cash Flow", format_currency(deltas["total_cash_flow"]))
        col3.metric("Δ Breakeven (мес)", f"{deltas['breakeven_month']:+.1f}")
        st.caption(
            f"Δ LTV/CAC: {deltas['ltv_cac_ratio']:+.2f} | "
            f"Δ Активные пациенты (последний месяц): {deltas['active_patients_last_month']:+.0f}"
        )
        st.markdown("---")

with st.expander("🔬 Аудит формул: шаги вычисления и проверка в Python", expanded=False):
    st.info(
        "**Для кого этот блок?** Для тех, кто хочет убедиться в корректности расчётов или воспроизвести их в своей среде.\n\n"
        "Здесь показаны: пошаговые значения промежуточных переменных за конкретный месяц, "
        "и готовый Python-сниппет, который можно скопировать и запустить локально — "
        "он воспроизведёт ровно те же числа, что вы видите на дашборде. "
        "Никакие параметры в основной расчёт не меняются — это только «чтение»."
    )
    render_formula_auditor(
        model_type=model_type,
        revenue_params=revenue_params,
        num_months=num_months,
        revenue_results=revenue_results,
        costs_results=costs_results,
        cash_flow_results=cash_flow_results,
        assumptions=assumptions_params,
    )

# KPI Cards
mrr_model_a = (
    revenue_params.get('num_clinics', 0)
    * revenue_params.get('devices_per_clinic', 0)
    * revenue_params.get('subscription_per_device', 0)
    if model_type == 'model_a' else 0.0
)
_target_min_price = (
    target_pricing_result.get('required_price', float('inf'))
    if target_pricing_result.get('feasible', False) and target_pricing_result.get('price_kind') in ['rental_price', 'subscription_per_device']
    else float('inf')
)
display_kpi_cards(
    cash_flow_results, breakeven_result, min_rental_price, unit_economics,
    num_months,
    model_type=model_type,
    mrr_model_a=mrr_model_a,
    target_min_rental_price=_target_min_price,
    target_breakeven_month=target_breakeven_month or 0,
)

st.markdown("---")

# ========== Панель: Целевая безубыточность (все модели) ==========
_payback_label = (
    f"🎯 Срок окупаемости: выход в плюс к месяцу {target_breakeven_month}"
    + (f" (вложения: {initial_investment:,.0f} ₽)" if initial_investment > 0 else "")
)
with st.expander(_payback_label, expanded=True):
    if not target_pricing_result.get("feasible", False):
        st.error("Невозможно рассчитать предиктор с текущими параметрами. Проверьте объем и комиссии.")
    else:
        col_left, col_right = st.columns([1, 1])
        pk = target_pricing_result.get("price_kind")
        _n_goal = int(target_breakeven_month)
        _m_goal = float(target_margin_rate)
        _trr_goal = float(target_pricing_result.get("target_revenue_required") or 0.0)
        _sigma_costs = _trr_goal / (1.0 + _m_goal) if abs(1.0 + _m_goal) > 1e-12 else 0.0
        _cumcf_floor = _m_goal * _sigma_costs
        # NPV-специфичные переменные (нужны в обеих колонках)
        _r_pct = discount_rate_annual * 100
        _uses_npv = discount_rate_annual > 0
        _metric_name = f"NPV({_n_goal})" if _uses_npv else f"CumCF({_n_goal})"
        _meta = target_pricing_result.get("meta", {})
        _cur_npv = _meta.get("current_npv", _meta.get("current_cumulative_cf", 0.0))
        _req_npv = _meta.get("required_npv", _meta.get("required_cumulative_cf", 0.0))

        with col_left:
            if pk in ["rental_price", "subscription_per_device"]:
                req = float(target_pricing_result["required_price"])
                cur = float(target_pricing_result["current_price"])
                already = bool(target_pricing_result.get("already_meets_target", cur + 1e-9 >= req))
                headroom = max(0.0, float(target_pricing_result.get("headroom_price", cur - req)))
                trivial = bool(target_pricing_result.get("trivial_min_price", False))
                label = "₽ / пациент / мес" if pk == "rental_price" else "₽ / устройство / мес"
                metric_name = "Минимальная цена аренды" if pk == "rental_price" else "Минимальная цена подписки"
                st.markdown(f"#### {metric_name}")
                _metric_label_help = f"NPV({_n_goal})" if _uses_npv else f"CumCF({_n_goal})"
                metric_help = (
                    f"Цель к месяцу {_n_goal}.\n"
                    f"Если запас {_m_goal * 100:.1f}%: нужно {_metric_label_help} >= ({_m_goal:.4f}) × сумма Costs за 1..{_n_goal}.\n"
                    f"Если запас 0%: {_metric_label_help} >= 0 (дисконтированный накопленный CF).\n"
                    + (f"Ставка дисконтирования: {_r_pct:.0f}% годовых (r_m = (1+{_r_pct:.0f}%)^(1/12)−1).\n\n" if _uses_npv else "\n")
                    + "Минимальная цена — нижняя граница по выбранному рычагу: ниже условие к сроку "
                    "перестаёт выполняться. Считается симуляцией 1..N и бинарным поиском (тот же движок, что дашборд).\n\n"
                    "Подробная расшифровка условия и чисел — в блоке справа."
                )
                metric_val = format_currency(req)
                if already and headroom > 1e-6:
                    delta_txt = f"+{format_currency(headroom)} над минимумом"
                    delta_col = "normal"
                elif already and trivial:
                    delta_txt = "нижняя граница ≈ 0"
                    delta_col = "off"
                elif already:
                    delta_txt = "на уровне минимума"
                    delta_col = "off"
                else:
                    delta_txt = f"{format_currency(cur - req)} vs текущая"
                    delta_col = "inverse"
                st.metric(
                    label=f"{label} — для выхода в плюс к месяцу {target_breakeven_month}",
                    value=metric_val,
                    delta=delta_txt,
                    delta_color=delta_col,
                    help=metric_help,
                )
                if trivial:
                    st.caption("≈ 0 ₽\nнижняя граница модели (пояснение вынесено отдельно)")
                if already:
                    if trivial:
                        st.info(
                            f"Пограничный случай: при нулевой (или пренебрежимо малой) цене условие к месяцу {target_breakeven_month} "
                            "в расчёте всё равно выполняется — проверьте объёмы, комиссию и статьи затрат "
                            "(возможна выручка не только от этой цены или заниженные cost)."
                        )
                    elif headroom > 1e-6:
                        st.success(
                            f"Цель к месяцу {target_breakeven_month} уже выполняется. "
                            f"Минимально достаточная цена ≈ {format_currency(req)}; текущая выше на "
                            f"{format_currency(headroom)} — запас к «граничной» цене; при прочих равных цену можно снизить, "
                            f"но не ниже {format_currency(req)} (иначе цель может перестать выполняться)."
                        )
                    else:
                        st.success(
                            f"Цель к месяцу {target_breakeven_month} выполняется; текущая цена около минимально достаточной "
                            f"({format_currency(req)})."
                        )
                else:
                    st.warning(f"Нужно повысить цену минимум на {format_currency(req - cur)}.")
            else:
                req_s = float(target_pricing_result["required_subscription"])
                req_r = float(target_pricing_result["required_rental"])
                cur_s = float(target_pricing_result["current_subscription"])
                cur_r = float(target_pricing_result["current_rental"])
                k_req = float(target_pricing_result.get("scale_factor", 1.0))
                already_ab = bool(target_pricing_result.get("already_meets_target", False))
                trivial_ab = bool(target_pricing_result.get("trivial_min_price", False))
                st.markdown("#### Требуемые цены (A+B, масштабирование)")
                headroom_s = max(0.0, cur_s - req_s)
                headroom_r = max(0.0, cur_r - req_r)
                ok_s = cur_s + 1e-9 >= req_s
                ok_r = cur_r + 1e-9 >= req_r
                _ab_metric_label = f"NPV({_n_goal})" if _uses_npv else f"CumCF({_n_goal})"
                _ab_metric_condition = (
                    f"{_ab_metric_label}≥0 (ставка {_r_pct:.0f}%)" if _uses_npv
                    else f"{_ab_metric_label}≥0"
                )
                st.metric(
                    label="Подписка клинике (₽/устройство/мес)",
                    value=format_currency(req_s) if req_s >= 1e-3 else "≈ 0 ₽",
                    delta=(
                        f"+{format_currency(headroom_s)} над минимумом"
                        if already_ab and ok_s and headroom_s > 1e-6
                        else (f"{format_currency(cur_s - req_s)} vs текущая" if not ok_s else "на уровне минимума")
                    ),
                    delta_color="normal" if ok_s and (headroom_s > 1e-6 or trivial_ab) else ("inverse" if not ok_s else "off"),
                    help=(
                        f"Цель к месяцу {_n_goal}: {_ab_metric_condition} "
                        f"(запас {_m_goal * 100:.1f}%). "
                        "Минимально достаточная подписка при масштабировании A+B; симуляция + бинарный поиск."
                    ),
                )
                st.metric(
                    label="Аренда пациенту (₽/мес)",
                    value=format_currency(req_r) if req_r >= 1e-3 else "≈ 0 ₽",
                    delta=(
                        f"+{format_currency(headroom_r)} над минимумом"
                        if already_ab and ok_r and headroom_r > 1e-6
                        else (f"{format_currency(cur_r - req_r)} vs текущая" if not ok_r else "на уровне минимума")
                    ),
                    delta_color="normal" if ok_r and (headroom_r > 1e-6 or trivial_ab) else ("inverse" if not ok_r else "off"),
                    help=(
                        f"Цель к месяцу {_n_goal}: {_ab_metric_condition} "
                        f"(запас {_m_goal * 100:.1f}%). "
                        "Минимально достаточная аренда при масштабировании A+B; симуляция + бинарный поиск."
                    ),
                )
                if already_ab:
                    if trivial_ab:
                        st.info(
                            f"Пограничный случай: масштаб цен к нулю всё ещё даёт выполнение цели к месяцу {target_breakeven_month} — "
                            "проверьте допущения (выручка setup и др.)."
                        )
                    elif k_req < 1.0 - 1e-9:
                        pct = (1.0 - k_req) * 100.0
                        st.success(
                            f"Цель к месяцу {target_breakeven_month} уже выполняется. Достаточно масштаба цен ≈ "
                            f"{k_req:.3f}× от текущих; запас по «границе» около {pct:.1f}% "
                            f"(подписку и аренду можно пропорционально снизить примерно на эту долю, не ниже указанных минимумов)."
                        )
                    elif k_req > 1.0 + 1e-9:
                        st.warning(
                            f"Нужно поднять обе цены пропорционально: коэффициент не ниже {k_req:.3f}× к текущим значениям."
                        )
                    else:
                        st.success(
                            f"Цель к месяцу {target_breakeven_month} выполняется при текущем масштабе цен (≈1.0×)."
                        )
                else:
                    st.warning(
                        f"Нужно поднять обе цены пропорционально: коэффициент не ниже {k_req:.3f}× к текущим значениям."
                    )

        with col_right:
            st.markdown("#### Условие цели: окупаемость и запас")
            _inv_str = f"{initial_investment:,.0f} ₽" if initial_investment > 0 else "0"
            _rate_note = (
                f"где `r_m = (1 + {_r_pct:.0f}%)^(1/12) − 1` — месячная ставка дисконтирования."
                if _uses_npv else
                "_При ставке 0%: NPV = CumCF − I₀ (стандартный накопленный CF за вычетом вложений)._"
            )
            _inv_note = (
                f"Начальные вложения **{format_currency(initial_investment)}** вычтены из NPV: "
                f"NPV > 0 означает, что проект полностью отбил вложения в дисконтированных деньгах."
                if initial_investment > 0 else
                f"При вложениях = 0: NPV({_n_goal}) ≥ 0 — дисконтированный CF вышел в плюс."
            )
            st.markdown(
                f"""
**1) NPV с учётом начальных вложений:**

```
NPV({_n_goal}) = −{_inv_str} + Σ CF_t / (1 + r_m)^t
```

{_rate_note}

{_inv_note}

---

**2) Условие окупаемости + запас:**

если запас **{_m_goal * 100:.1f}%**, полное условие:

```
NPV({_n_goal})  ≥  ({_m_goal:.4f}) × Σ Costs_m   (m = 1..{_n_goal})
```

- При **0%** запаса: `NPV({_n_goal}) ≥ 0` — вложения отбиты в дисконтированных деньгах.
- При **>0%**: NPV должен перекрыть ещё и запас над затратами.

---

**3) Как получается «минимальная цена»**

1. Прогоняем `revenue → costs → cash flow` до месяца **{_n_goal}**.
2. Считаем `NPV({_n_goal}) = −I₀ + Σ CF_t / (1+r_m)^t`.
3. Бинарным поиском ищем **минимальную** цену, при которой NPV ≥ запас.

Это **сценарный инструмент**: «какая цена нужна, чтобы NPV вышел в ≥ 0 к сроку».
"""
            )

            if _cur_npv is not None:
                _cur_npv_display = _meta.get("current_npv", None)
                _req_npv_display = _meta.get("required_npv", None)
                if _cur_npv_display is not None:
                    st.markdown(
                        f"**Числа прогона:** текущая цена → NPV = `{_cur_npv_display:,.0f} ₽`, "
                        f"граничная цена → NPV = `{_req_npv_display:,.0f} ₽`"
                    )

            st.markdown("#### Числа текущего прогона (на граничной цене)")
            _threshold_display = initial_investment + _cumcf_floor
            st.markdown(
                f"""
| Показатель | Значение |
|---|---|
| Модель | `{model_type}` |
| Горизонт **N** | **{_n_goal}** мес |
| Начальные вложения | **{format_currency(initial_investment)}** |
| Запас (ползунок) | **{_m_goal * 100:.1f}%** |
| ΣCosts(1..N) (оценка) | **{format_currency(_sigma_costs)}** |
| Запас × ΣCosts | **{format_currency(_cumcf_floor)}** |
| Итоговый порог для CumCF(N) | **{format_currency(_threshold_display)}** (вложения + запас) |
"""
            )
            with st.expander("Технические поля линеаризации (для отладки)", expanded=False):
                st.markdown(
                    f"`base_revenue` = {format_currency(target_pricing_result['base_revenue'])}  \n"
                    f"`coeff` = {target_pricing_result['coeff']:,.2f}"
                )

st.markdown("---")

# График 1: Cash Flow (основной)
with st.expander("📈 График 1: Cash Flow по месяцам", expanded=True):
    st.plotly_chart(
        create_cash_flow_chart(
            cash_flow_results,
            initial_investment=initial_investment,
            npv_series=npv_series if discount_rate_annual > 0 else None,
            annual_discount_rate=discount_rate_annual,
            rnd_results=rnd_results if rnd_enabled else None,
            rnd_npv_series=rnd_npv_series if (rnd_enabled and discount_rate_annual > 0) else None,
        ),
        use_container_width=True,
    )
    _cf1_caption = (
        "**Как читать:** линия «Revenue» — выручка, «Total Costs» — суммарные затраты каждого месяца. "
        "«Cash Flow» = Выручка − Затраты за месяц: положительная — прибыльный месяц. "
        "«Cumulative CF» суммирует всё с нарастающим итогом."
    )
    if discount_rate_annual > 0:
        _npv_final = npv_series[-1] if npv_series else 0.0
        _r_pct_lbl = discount_rate_annual * 100
        _npv_label = f"NPV ({_r_pct_lbl:.0f}% год.)"
        _cf1_caption += (
            f" **«{_npv_label}»** = −Вложения + Σ CF_t/(1+r_m)^t: "
            f"пересечение нуля — момент когда дисконтированные доходы покрыли начальные вложения "
            f"(r_m = (1+{_r_pct_lbl:.0f}%)^(1/12)−1). "
            f"Итоговый NPV: **{_npv_final:,.0f} ₽**."
        )
    if initial_investment and initial_investment > 0:
        _cf1_caption += (
            f" Жёлтая пунктирная линия — порог окупаемости: Cumulative CF должен пересечь "
            f"{initial_investment:,.0f} ₽ (начальные вложения)."
        )
    else:
        _cf1_caption += " Пересечение нуля — операционная безубыточность."
    st.caption(_cf1_caption)

# Графики 2-3: Revenue + Costs (2 колонки)
col1, col2 = st.columns(2)
with col1:
    with st.expander("📊 График 2: Структура Revenue", expanded=True):
        selected_month_for_revenue_chart = st.slider(
            "Выберите месяц для структуры Revenue",
            min_value=1,
            max_value=max(1, num_months),
            value=1,
            key="revenue_breakdown_month_selector",
            help=(
                "Выберите конкретный месяц, чтобы увидеть из каких источников состоит выручка. "
                "В модели A: Setup Fee (разовая продажа устройств) + Subscription (ежемесячная подписка на ПО). "
                "В модели B: Gross Revenue от пациентов − Комиссия клиники = Net Revenue. "
                "В гибридной модели: все три компонента."
            ),
        )
        st.plotly_chart(
            create_revenue_breakdown_chart(
                revenue_results,
                model_type,
                selected_month=selected_month_for_revenue_chart,
            ),
            use_container_width=True,
        )
        st.caption(
            "**Структура выручки выбранного месяца.** "
            "Setup Fee — разовый платёж клиники за устройства (только при первой продаже или расширении парка). "
            "Subscription — ежемесячный recurring revenue за ПО на каждое устройство. "
            "Net Rental — выручка ReFlex от аренды пациентами за вычетом комиссии клиники."
        )
with col2:
    with st.expander("💰 График 3: Структура Costs", expanded=True):
        st.plotly_chart(create_costs_structure_chart(costs_results), use_container_width=True)
        st.caption(
            "**Структура затрат по месяцам.** "
            "Fixed Costs (зарплаты, офис, инфраструктура, юридика) — постоянны вне зависимости от объёма продаж. "
            "Variable Costs (COGS, логистика, поддержка, CAC) — растут с количеством устройств и пациентов. "
            "Высокая доля Fixed в первые месяцы — нормально: они «размываются» при росте выручки."
        )

# График 4: Точка безубыточности (BEP)
with st.expander("🎯 График 4: Точка безубыточности (BEP)", expanded=True):
    _bep_x_hint = {
        "model_a": "устройств в парке",
        "model_b": "активных пациентов",
        "model_ab": "устройств в парке",
    }.get(model_type, "юнитов")
    selected_month_bep = st.slider(
        f"Выберите месяц для BEP-анализа (ось X — количество {_bep_x_hint})",
        min_value=1,
        max_value=max(1, num_months),
        value=1,
        key="bep_month_selector",
        help=(
            "График показывает, при каком количестве активных юнитов выручка покрывает затраты в выбранном месяце. "
            "Зелёная зона — прибыль, красная — убыток. Вертикальная линия «as is» — фактическое положение."
        ),
    )
    st.plotly_chart(
        create_true_breakeven_chart(
            revenue_results=revenue_results,
            costs_results=costs_results,
            model_type=model_type,
            selected_month=selected_month_bep,
        ),
        use_container_width=True,
    )
    st.caption(
        "**Как читать:** ось X — количество активных юнитов (устройств или пациентов) в выбранном месяце. "
        "**Зелёная линия** — выручка: растёт пропорционально числу юнитов (подписка/аренда + доля от продаж). "
        "**Красная линия** — затраты: начинается с уровня фиксированных расходов и растёт с каждым юнитом. "
        "**N\\*** — точка пересечения (BEP): здесь выручка = затратам. "
        "Слева от N\\* — убыток, справа — прибыль. "
        "Синяя пунктирная линия «as is» — фактическое число юнитов в этом месяце."
    )

# График 4b: Когорты
with st.expander("👥 График: Когортная динамика", expanded=False):
    st.plotly_chart(create_cohort_dynamics_chart(revenue_results, model_type), use_container_width=True)
    st.caption(
        "**Динамика когорт пациентов.** "
        "Столбцы — новые пациенты, впервые взявшие устройство в данном месяце. "
        "«Активные (до churn)» — сумма пациентов всех когорт, срок реабилитации которых ещё не истёк. "
        "«Эффективные» — после вычета churn (отказавшихся) и загрузки (utilization): именно с ними считается выручка и переменные затраты. "
        "«Вышли из когорты» — пациенты, завершившие курс и освободившие устройство."
    )

# Детальная таблица
display_detailed_table(cash_flow_results, revenue_results, costs_results)

# Детализация выручки и затрат
display_revenue_breakdown(revenue_results, model_type)
display_costs_breakdown(costs_results)

# ──────────────────────────────────────────────────────────────────────────────
# Инвестиционный банк
# ──────────────────────────────────────────────────────────────────────────────
if initial_investment and initial_investment > 0:
    with st.expander("🏦 Инвестиционный банк: распределение по затратам", expanded=True):

        # Стратегия распределения (сохраняется в session_state)
        _strat_labels = {"proportional": "Пропорционально (рекомендуется)", "priority": "По приоритету (сверху вниз)"}
        _strat_keys = list(_strat_labels.keys())
        _cur_strat = st.session_state.get("bank_allocation_strategy", "proportional")
        _strat_idx = _strat_keys.index(_cur_strat) if _cur_strat in _strat_keys else 0
        _selected_strat = st.radio(
            "Стратегия распределения банка",
            options=_strat_keys,
            format_func=lambda k: _strat_labels[k],
            index=_strat_idx,
            horizontal=True,
            key="bank_strategy_radio",
            help=(
                "**Пропорционально** — каждая статья затрат покрывается банком в одинаковой доле. "
                "Лучше для грантовой отчётности: сумма по каждой статье легко объясняется. "
                "**По приоритету** — статьи покрываются по порядку (зарплаты → инфраструктура → …) "
                "пока банк не исчерпается."
            ),
        )
        if _selected_strat != _cur_strat:
            st.session_state["bank_allocation_strategy"] = _selected_strat
            # Пересчитываем с новой стратегией немедленно
            bank_allocation = calculate_bank_allocation(
                costs_results, _remaining_for_market, strategy=_selected_strat
            )
            combined_bank_allocation = rnd_bank_entries + bank_allocation

        # ── KPI cards ──
        _exhausted_m = bank_exhausted_month(combined_bank_allocation)
        _covered_months = months_covered_by_bank(combined_bank_allocation)
        _total_bank_used = sum(e["bank_used"] for e in combined_bank_allocation)
        _bank_remaining = max(0.0, initial_investment - _total_bank_used)

        _kpi_cols = st.columns(4)
        with _kpi_cols[0]:
            st.metric("Начальный банк", f"{initial_investment:,.0f} ₽".replace(",", " "))
        with _kpi_cols[1]:
            st.metric("Потрачено из банка", f"{_total_bank_used:,.0f} ₽".replace(",", " "))
        with _kpi_cols[2]:
            if _exhausted_m:
                st.metric("Банк исчерпан в месяце", str(_exhausted_m))
            elif _bank_remaining > 0:
                st.metric("Остаток банка", f"{_bank_remaining:,.0f} ₽".replace(",", " "))
            else:
                st.metric("Банк исчерпан в месяце", "—")
        with _kpi_cols[3]:
            st.metric("Месяцев покрытия", str(_covered_months))

        st.markdown("---")

        # ── График: runway банка ──
        import plotly.graph_objects as go

        _balance_series = bank_balance_series(combined_bank_allocation)
        _months_axis = [e["month"] for e in combined_bank_allocation]
        _bank_used_series = [e["bank_used"] for e in combined_bank_allocation]
        _bank_end_series = [e["bank_at_end"] for e in combined_bank_allocation]

        _fig_bank = go.Figure()
        _fig_bank.add_trace(go.Bar(
            x=_months_axis,
            y=_bank_used_series,
            name="Потрачено из банка",
            marker_color="#EF553B",
            opacity=0.75,
        ))
        _fig_bank.add_trace(go.Scatter(
            x=_months_axis,
            y=_balance_series,
            mode="lines+markers",
            name="Остаток банка (начало месяца)",
            line=dict(color="#636EFA", width=2),
            marker=dict(size=6),
        ))
        _fig_bank.update_layout(
            title="Расход инвестиционного банка по месяцам",
            xaxis_title="Месяц",
            yaxis_title="Сумма (₽)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=340,
            yaxis=dict(tickformat=",.0f"),
        )
        st.plotly_chart(_fig_bank, use_container_width=True)
        st.caption(
            "**Красные столбцы** — сколько денег из банка потрачено в каждом месяце. "
            "**Синяя линия** — остаток банка на начало месяца. "
            "Когда линия достигает нуля, банк исчерпан и затраты переходят на операционный CF."
        )

        st.markdown("---")

        # ── Таблица атрибуции по статьям ──
        _line_names, _month_labels, _matrix = build_grant_matrix(combined_bank_allocation)

        if _line_names and _month_labels:
            st.markdown("##### Детализация: на что потрачен банк")

            _LABEL_MAP = {
                "team_salaries": "Зарплаты команды",
                "infrastructure_fixed": "Инфраструктура (fixed)",
                "office_rent": "Аренда офиса",
                "legal_services": "Юридические услуги",
                "other_fixed": "Прочие постоянные",
                "cogs": "COGS (производство)",
                "logistics": "Логистика",
                "support": "Поддержка",
                "infrastructure_variable": "Инфраструктура (variable)",
                "cac": "CAC (привлечение)",
            }

            def _pretty_name(n: str) -> str:
                return _LABEL_MAP.get(n, n)

            _pretty_rows = [_pretty_name(n) for n in _line_names]

            # Строим DataFrame: строки = статьи, столбцы = месяцы
            _df_grant = pd.DataFrame(
                _matrix,
                index=_pretty_rows,
                columns=_month_labels,
            )
            # Добавляем итоговый столбец
            _df_grant["ИТОГО"] = _df_grant.sum(axis=1)

            # Добавляем итоговую строку
            _total_row = _df_grant.sum(axis=0)
            _total_row.name = "ИТОГО"
            _df_grant = pd.concat([_df_grant, _total_row.to_frame().T])

            # Форматируем числа
            def _fmt(v):
                if isinstance(v, (int, float)) and v > 0:
                    return f"{v:,.0f} ₽".replace(",", " ")
                return "—"

            st.dataframe(
                _df_grant.map(_fmt),
                use_container_width=True,
            )
            st.caption(
                "Таблица показывает, сколько из инвестиционного банка ушло на каждую статью затрат "
                "в каждом месяце. Используйте для заполнения грантовой отчётности."
            )
        else:
            st.info("Инвестиционный банк не расходуется: либо вложения равны нулю, либо затрат нет.")

# График 5: Sensitivity Analysis (опционально)
with st.expander("📈 График 5: Анализ чувствительности"):
    st.info(
        "**Анализ чувствительности** показывает, как изменится итоговый Cash Flow за весь горизонт, "
        "если каждый параметр в отдельности сдвинуть на ±20% при прочих равных. "
        "Длинная полоса = сильный рычаг: небольшое изменение этого параметра сильно влияет на финансовый результат. "
        "Используйте для приоритизации: на каких параметрах фокусироваться в переговорах."
    )
    with st.spinner("Расчет sensitivity analysis..."):
        sensitivity_results = calculate_sensitivity_analysis(
            model_type=model_type,
            all_params=all_params,
            base_total_cf=total_cf,
            variation_percent=0.20,
            num_months=num_months,
            custom_fixed_costs=st.session_state.custom_fixed_costs[model_type],
            custom_variable_costs=st.session_state.custom_variable_costs[model_type],
        )
        st.plotly_chart(create_sensitivity_chart(sensitivity_results), use_container_width=True)
        st.caption(
            "Каждая полоса = изменение суммарного CF при сдвиге параметра на +20% (правая) или −20% (левая) "
            "относительно базового значения. Параметры отсортированы по абсолютному влиянию."
        )

# График 6: Unit Economics (только для model_b/ab)
if model_type in ['model_b', 'model_ab'] and unit_economics.get('ltv', 0) > 0:
    with st.expander("💵 График 6: Unit Economics", expanded=True):
        st.plotly_chart(create_unit_economics_chart(unit_economics), use_container_width=True)
        st.caption(
            "**Unit Economics — экономика одного пациента.** "
            "LTV (Lifetime Value) — сколько денег приносит один пациент за весь срок реабилитации (за вычетом комиссии клиники). "
            "CAC (Customer Acquisition Cost) — затраты на привлечение одного пациента. "
            "LTV/CAC > 3 — общепринятый ориентир «здоровой» модели: на каждый рубль привлечения зарабатывается минимум 3 рубля."
        )

# ========== ЭКСПОРТ ==========
st.markdown("---")
st.markdown("### 📥 Экспорт результатов")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("📊 ФЭМ с формулами (Excel)", help="Полная интерактивная модель с формулами - можно менять параметры прямо в Excel!"):
        with st.spinner("Создание Excel файла с формулами..."):
            # Подготавливаем all_params с кастомными параметрами для экспорта
            export_params = {
                'revenue': revenue_params,
                'fixed_costs': {k: v for k, v in fixed_costs_params.items() if not k.startswith('custom_')},
                'variable_costs': {k: v for k, v in variable_costs_params.items() if not k.startswith('custom_')},
                'assumptions': assumptions_params,
                'custom_fixed_costs': st.session_state.custom_fixed_costs[model_type],
                'custom_variable_costs': st.session_state.custom_variable_costs[model_type]
            }
            
            filename = export_to_excel_with_formulas(
                model_type, export_params, num_months,
                bank_allocation=combined_bank_allocation,
                rnd_results=rnd_results if rnd_enabled else None,
            )
            if filename.endswith('.xlsx'):
                st.success(f"✅ Файл создан: {filename}")
                st.info("💡 В этом файле можно менять параметры и все пересчитается автоматически!")
                st.info("🔧 Включены все кастомные параметры!")
                
                # Кнопка скачивания
                with open(filename, 'rb') as f:
                    st.download_button(
                        label="⬇️ Скачать файл",
                        data=f,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.error(filename)

with col2:
    if st.button("📄 Данные (Excel)", help="Простой экспорт текущих данных без формул"):
        with st.spinner("Создание Excel файла..."):
            filename = export_to_excel(
                cash_flow_results, revenue_results, costs_results,
                unit_economics, all_params,
                bank_allocation=combined_bank_allocation,
                rnd_results=rnd_results if rnd_enabled else None,
            )
            if filename.endswith('.xlsx'):
                st.success(f"✅ Файл создан: {filename}")
                
                with open(filename, 'rb') as f:
                    st.download_button(
                        label="⬇️ Скачать файл",
                        data=f,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.error(filename)

with col3:
    if st.button("📋 JSON", help="Экспорт в JSON формате для разработчиков"):
        with st.spinner("Создание JSON файла..."):
            filename = export_to_json(
                cash_flow_results, revenue_results, costs_results,
                unit_economics, all_params
            )
            if filename.endswith('.json'):
                st.success(f"✅ Файл создан: {filename}")
                
                with open(filename, 'r', encoding='utf-8') as f:
                    st.download_button(
                        label="⬇️ Скачать файл",
                        data=f,
                        file_name=filename,
                        mime="application/json"
                    )
            else:
                st.error(filename)

with col4:
    st.markdown("**Для БП_04**")
    md_name = f"reflex_fem_bp04_snapshot_{date.today().isoformat()}.md"
    md_body = build_bp04_fem_snapshot_markdown(
        model_type=model_type,
        model_display_name=defaults[model_type]["name"],
        scenario_label=scenario_names.get(selected_scenario, selected_scenario),
        num_months=num_months,
        all_params=all_params,
        cash_flow_results=cash_flow_results,
        revenue_results=revenue_results,
        unit_economics=unit_economics,
        breakeven_result=breakeven_result,
        min_rental_price=min_rental_price,
        rnd_results=rnd_results if rnd_enabled else None,
    )
    st.download_button(
        label="📑 Снимок для БП_04 (.md)",
        data=md_body.encode("utf-8"),
        file_name=md_name,
        mime="text/markdown",
        help="Скачай и прикрепи к чату в Cursor: попроси обновить БП_04 по этому снимку",
    )

with col5:
    st.markdown("**Конкурс МСП**")
    if st.button(
        "🏆 БП МСП",
        help="Экспорт финансовой модели в формате конкурса МСП / Студенческий стартап. "
             "Содержит: Титульный лист, БДДС, Инвест, Графики CF, Точку безубыточности, "
             "Когорты, Клиники и автогенерированную Бизнес-логику.",
        use_container_width=True,
    ):
        with st.spinner("Формирование пакета документов БП МСП..."):
            _msp_clinic_schedule = list(st.session_state.get("clinic_schedule_model_a", []))
            _msp_filename = f"ReFlex_BP_MSP_{model_type}_{date.today().isoformat()}.xlsx"

            result = export_to_msp_excel(
                model_type=model_type,
                all_params=all_params,
                num_months=num_months,
                revenue_results=revenue_results,
                costs_results=costs_results,
                cash_flow_results=cash_flow_results,
                bank_allocation=combined_bank_allocation,
                breakeven_result=breakeven_result,
                unit_economics=unit_economics,
                initial_investment=initial_investment,
                discount_rate_annual=discount_rate_annual,
                clinic_schedule=_msp_clinic_schedule,
                filename=_msp_filename,
                rnd_results=rnd_results if rnd_enabled else None,
            )

            if result.endswith(".xlsx"):
                st.success("Файл готов!")
                with open(result, "rb") as _f:
                    st.download_button(
                        label="⬇️ Скачать БП МСП",
                        data=_f,
                        file_name=_msp_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_msp_excel",
                    )
            else:
                st.error(result)

# Краткая сводка в sidebar
display_kpi_summary(cash_flow_results, model_type, num_months)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**ReFlex Calculator v1.0**")
st.sidebar.markdown("© 2026 ReFlex")
