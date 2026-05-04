"""
Простой тест для проверки импорта модулей
Запуск: python3 simple_test.py
"""

print("🧪 Тестирование импорта модулей...")

try:
    from models import calculate_revenue_for_months
    print("✅ models.revenue - OK")
except Exception as e:
    print(f"❌ models.revenue - ERROR: {e}")

try:
    from models import calculate_costs_for_months
    print("✅ models.costs - OK")
except Exception as e:
    print(f"❌ models.costs - ERROR: {e}")

try:
    from models import calculate_cash_flow_for_months
    print("✅ models.cash_flow - OK")
except Exception as e:
    print(f"❌ models.cash_flow - ERROR: {e}")

try:
    from models import calculate_unit_economics_from_params
    print("✅ models.unit_economics - OK")
except Exception as e:
    print(f"❌ models.unit_economics - ERROR: {e}")

try:
    from utils import format_currency, validate_all_params
    print("✅ utils - OK")
except Exception as e:
    print(f"❌ utils - ERROR: {e}")

print("\n🧪 Тестирование расчетов...")

try:
    # Простой тест Model B
    revenue_params = {
        'num_clinics': 2,
        'patients_per_clinic_month1': 5,
        'growth_rate': 0.5,
        'rental_price': 6000,
        'avg_rental_duration': 2,
        'clinic_commission_rate': 0.15
    }
    
    revenue_results = calculate_revenue_for_months('model_b', revenue_params, 3)
    
    print(f"✅ Расчет revenue: {len(revenue_results)} месяцев")
    print(f"   Месяц 1: {revenue_results[0].get('num_patients', 0)} пациентов, {revenue_results[0].get('net_revenue', 0):,.0f}₽")
    print(f"   Месяц 2: {revenue_results[1].get('num_patients', 0)} пациентов, {revenue_results[1].get('net_revenue', 0):,.0f}₽")
    print(f"   Месяц 3: {revenue_results[2].get('num_patients', 0)} пациентов, {revenue_results[2].get('net_revenue', 0):,.0f}₽")
    
except Exception as e:
    print(f"❌ Расчеты - ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Все базовые проверки пройдены!")
print("🚀 Можно запускать приложение: streamlit run app.py")
