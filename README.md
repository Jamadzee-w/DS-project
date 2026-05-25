# EcoLogistic — Бородулин Владимир

Я отвечаю за два раздела:

1. **Анализ контрагентов** — поставщики и партнёры платформы, оценка надёжности, условий, рейтингов
2. **Анализ конкурентов** — сравнение транспортных компаний по тарифам, срокам доставки и покрытию

---

## Структура файлов
vladimir/
├── README.html   

├── parser.py

├── data/

│   ├── routes.csv

│   └── real_tariffs_export.csv

├── contractors/

│   └── contractor_analysis.ipynb

└── competitors/

    └── competitor_analysis.ipynb
    


## Источники данных

| # | Источник | Тип | Что брали |
|---|----------|-----|-----------|
| 1 | СДЭК API v2 | REST API (requests) | Тарифы доставки по маршрутам — цены и сроки |
| 2 | Возовоз (vozovoz.ru) | Динамический скрапинг (Playwright) | Котировки калькулятора доставки |
| 3 | Открытые данные Росстата | CSV с сайта Росстата | Число субъектов МСП по регионам |
| 4 | Опрос (Google Forms) | Открытый датасет / синтетика | Предпочтения малых производителей по доставке |

---

## Применённые темы курса

- **ООП** — классы `CDEKParser` и `VozovozScraper` в `parser.py`
- **API и HTTP-запросы** — авторизация OAuth2, POST к `/v2/calculator/tariff`
- **Веб-скрапинг** — Playwright + headless Chromium для динамических страниц
- **Pandas** — агрегация, фильтрация, экспорт результатов в CSV
- **Визуализация** — Plotly bar- и scatter-диаграммы внутри Streamlit-дашборда

```bash
pip install requests playwright pandas streamlit plotly python-dotenv
playwright install chromium

# собрать данные
python parser.py

# открыть дашборд
streamlit run app.py
```
