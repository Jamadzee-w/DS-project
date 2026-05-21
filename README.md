# EcoLogistic — Ветка Алимурадова Джамала



Я отвечаю за два раздела:
1. **Анализ целевой аудитории** — кто будет пользоваться платформой, портреты ЦА
2. **Маркетинговая кампания** — как будем привлекать первых клиентов, бюджет, KPI

## Структура файлов

```
jamal/
├── README.md                      
├── parser.py                      
├── data/
│   └── hh_vacancies_sample.csv      
├── target_audience/
│   └── target_audience_analysis.ipynb  
└── marketing/
    └── marketing_campaign.ipynb     
```



| # | Источник | Тип | Что брали |
|---|----------|-----|-----------|
| 1 | hh.ru | Статический парсинг (BeautifulSoup) | Вакансии по логистике — понять спрос на рынке |
| 2 | Опрос (Google Forms) | Открытый датасет / синтетика | Предпочтения малых производителей по доставке |
| 3 | Открытые данные Росстата | CSV с сайта Росстата | Число субъектов МСП по регионам |

## Применённые темы курса

-  **ООП** — класс `HHParser` в `parser.py`



```bash
pip install requests beautifulsoup4 pandas matplotlib
python parser.py          # собрать данные с hh.ru
# потом открыть .ipynb в Jupyter
```
