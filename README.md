# EcoLogistic — Бородулин Владимир

Я отвечаю за два раздела:

1. **Анализ контрагентов** — поставщики и партнёры платформы, оценка надёжности, условий, рейтингов
2. **Анализ конкурентов** — сравнение транспортных компаний по тарифам, срокам доставки и покрытию

---

## Структура файлов
vladimir/

├── README.md

├── parser.py

├── data/

├── routes.csv    
└── real_tariffs_export.csv

├── contractors/                
  └── contractor_analysis.ipynb    
└── competitors/
        └── competitor_analysis.ipynb

    



---

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
# установка зависимостей
pip install requests playwright pandas streamlit plotly python-dotenv
playwright install chromium

# собрать данные (СДЭК API + Возовоз scraper)
python parser.py

# открыть дашборд с анализом конкурентов
streamlit run app.py

# потом открыть .ipynb в Jupyter
# competitors/competitor_analysis.ipynb
# contractors/contractor_analysis.ipynb
```

---

## Пример кода — класс CDEKParser

```python
class CDEKParser:
    """Получает тарифы через официальный СДЭК API v2."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    def _authenticate(self) -> str:
        resp = requests.post(CDEK_AUTH_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def get_tariff(self, origin_code, dest_code, weight_kg) -> dict | None:
        if not self._token:
            self._token = self._authenticate()
        # POST к /v2/calculator/tariff — возвращает price + period_min/max
```
