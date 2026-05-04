"""
Интерактивный калькулятор финансово-экономической модели ReFlex

Точка входа и навигация (Streamlit 1.36+ new navigation API).
Весь код калькулятора — в pages/calculator.py
Страница бизнес-логики — в pages/business_logic.py
"""
import streamlit as st

st.set_page_config(
    page_title="ReFlex Калькулятор ФЭМ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page("pages/calculator.py", title="Калькулятор", icon="📊"),
        st.Page("pages/business_logic.py", title="Бизнес-логика", icon="📐"),
    ]
)
pg.run()
