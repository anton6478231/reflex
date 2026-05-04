# ReFlex FEM Calculator - Summary

**Дата:** 2026-04-19  
**Статус:** актуальная версия  
**Версия:** v1.x

## Что важно в текущей версии

- Модели: `model_a`, `model_b`, `model_ab`
- Горизонт: `1..36` месяцев (единый для расчетов, графиков и sensitivity)
- Target pricing: автоподбор минимальной цены для цели по месяцу и марже
- Formula audit: трассировка формул синхронизирована с расчетным ядром
- Сценарии обновлены: убраны нереалистичные `COGS=0` в `model_b`

## Недавние фикс-пункты качества

- Исправлена трассировка `model_ab`:
  - подписка считается по фактическому пулу устройств
  - допродажа устройств учитывается при дефиците пула
- В `target pricing` для `model_ab` убран двойной учет `infrastructure_per_user`
- Sensitivity теперь считает на выбранный горизонт и с учетом кастомных затрат

## Файлы с ключевой логикой

- `app.py` - точка входа: `set_page_config` + `st.navigation` + `pg.run()`
- `pages/calculator.py` - весь UI калькулятора: параметры, target pricing, stage-gate, sensitivity, экспорт
- `pages/business_logic.py` - страница с объяснением бизнес-логики, формулами и глоссарием
- `models/revenue.py` - поток пациентов, пул устройств, per-batch когорты, выручка
- `models/costs.py` - fixed/variable и кастомные статьи
- `models/sensitivity.py` - анализ чувствительности
- `models/formula_trace.py` - проверка формул против фактических расчетов
- `config/defaults.json`, `config/scenarios.json` - базовые assumptions

## Быстрая проверка

```bash
cd "reflex-calculator"
python3 -m pytest tests/ -q
```
