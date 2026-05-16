# Сайт ReFlex max (GitHub Pages)

Лендинг стартап-проекта для отчёта по гранту «Студенческий стартап» (ТЗ п. 3.2б).

## Открыть локально

Из корня репозитория:

```bash
cd docs
python3 -m http.server 8080
```

В браузере: [http://localhost:8080](http://localhost:8080)

Остановить сервер: `Ctrl+C`.

Альтернатива (macOS): `open index.html` — откроется файл напрямую; для проверки путей к CSS лучше использовать `http.server` выше.

## GitHub Pages

1. Репозиторий на GitHub → **Settings** → **Pages**.
2. **Source:** Deploy from a branch → `main` → папка **`/docs`**.
3. После деплоя: `https://<username>.github.io/<repo>/`.

Свой домен: **Custom domain** в настройках Pages + DNS у регистратора (см. инструкции GitHub).

## Логотипы (обязательно для отчёта)

| Файл | Источник |
|------|----------|
| `assets/images/logo-putp.jpg` | Официальный пакет ПУТП ([брендбук PDF](https://univertechpred.ru/upload/pres/putp-bazoviy-paket-brendirovaniya-dlya-vuzov.pdf)) |
| `assets/images/logo-fasie.png` | Официальный логотип Фонда содействия инновациям |
| `assets/images/logo-reflex.svg` | Логотип проекта (при необходимости замените) |

Текст атрибуции на главной странице — дословно по договору (п. 7.2) и ТЗ (п. 3.2б).

## Контакты

В `index.html` замените `info@reflexmax.ru` на рабочий email перед сдачей отчёта.
