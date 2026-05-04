# Запуск ReFlex Калькулятора: гайд для команды

Время установки: **5–10 минут**. Требуется только папка с проектом и интернет.

---

## Шаг 0. Убедись, что установлен Python

Открой терминал (на Windows — PowerShell или CMD) и введи:

```
python3 --version
```

На Windows также попробуй:

```
python --version
```

Нужна версия **3.10 или выше**. Если Python не установлен или версия старше:

**macOS:**
Скачай с [python.org/downloads](https://www.python.org/downloads/) и установи. Или через Homebrew:
```
brew install python
```

**Windows:**
Скачай с [python.org/downloads](https://www.python.org/downloads/), запусти установщик.
> Важно: при установке поставь галочку **"Add Python to PATH"**.

---

## Шаг 1. Распакуй проект

Разархивируй полученный файл. Убедись, что папка называется `reflex-calculator` и внутри есть файл `app.py`.

---

## Шаг 2. Открой терминал в папке проекта

**macOS / Linux:**
```bash
cd /путь/до/reflex-calculator
```

Например:
```bash
cd ~/Downloads/reflex-calculator
```

**Windows (PowerShell):**
```powershell
cd C:\Users\Имя\Downloads\reflex-calculator
```

> Совет: можно открыть папку в Finder / Проводнике, кликнуть правой кнопкой и выбрать "Открыть в терминале".

---

## Шаг 3. Создай виртуальное окружение

Это изолированная среда — не будет конфликтов с другими проектами.

**macOS / Linux:**
```bash
python3 -m venv venv
```

**Windows:**
```powershell
python -m venv venv
```

После выполнения появится папка `venv/` внутри проекта.

---

## Шаг 4. Установи зависимости

**macOS / Linux:**
```bash
./venv/bin/pip install -r requirements.txt
```

**Windows:**
```powershell
venv\Scripts\pip install -r requirements.txt
```

Установка займёт 1–3 минуты. Будут скачаны: streamlit, plotly, pandas, numpy и др.

---

## Шаг 5. Запусти приложение

**macOS / Linux:**
```bash
./venv/bin/streamlit run app.py --server.headless true
```

**Windows:**
```powershell
venv\Scripts\streamlit run app.py --server.headless true
```

После запуска в терминале появится:

```
Local URL: http://localhost:8501
```

Открой [http://localhost:8501](http://localhost:8501) в браузере. Приложение готово.

---

## Первые шаги в приложении

1. В **левой панели** выбери бизнес-модель — начни с **Model B (B2B2C)**
2. Выбери **сценарий Base**
3. Смотри KPI-метрики вверху и график Cash Flow
4. Меняй параметры — графики обновляются автоматически
5. В конце страницы — кнопки экспорта в Excel / JSON

---

## Частые проблемы

**"python3: command not found" / "python is not recognized"**
→ Python не установлен или не добавлен в PATH. Повтори Шаг 0.

**"ModuleNotFoundError: No module named 'streamlit'"**
→ Зависимости не установлены или запускаешь не через venv. Повтори Шаги 3–4.

**"No such file or directory: config/defaults.json"**
→ Терминал открыт не в папке `reflex-calculator`. Повтори Шаг 2.

**Браузер не открылся автоматически**
→ Открой вручную: [http://localhost:8501](http://localhost:8501)

**Графики не отображаются**
→ Обнови plotly:

```bash
# macOS / Linux
./venv/bin/pip install --upgrade plotly

# Windows
venv\Scripts\pip install --upgrade plotly
```

---

## Как остановить приложение

В терминале нажми `Ctrl + C`.

---

## Следующие запуски

Виртуальное окружение и зависимости устанавливаются только один раз.
При следующих запусках достаточно:

**macOS / Linux:**
```bash
cd /путь/до/reflex-calculator
./venv/bin/streamlit run app.py --server.headless true
```

**Windows:**
```powershell
cd C:\путь\до\reflex-calculator
venv\Scripts\streamlit run app.py --server.headless true
```

---

По вопросам — пишите Антону.
