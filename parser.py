"""
Статический парсер hh.ru для сбора данных о вакансиях в сфере логистики.
Используется для анализа рынка и целевой аудитории EcoLogistic.

Автор: Алимурадов Джамал
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os


class HHParser:
    """
    Парсер вакансий с hh.ru.
    Собирает название, компанию, зарплату и город по заданному запросу.
    """

    BASE_URL = "https://hh.ru/search/vacancy"

    def __init__(self, query, pages=3):
        self.query = query
        self.pages = pages
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self.data = []

    def _get_html(self, page):
        """Загружает HTML-страницу с результатами поиска."""
        params = {
            "text": self.query,
            "page": page,
            "per_page": 20,
            "area": 113,  # Россия
        }
        try:
            response = requests.get(
                self.BASE_URL, params=params, headers=self.headers, timeout=10
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Ошибка при загрузке страницы {page}: {e}")
            return None

    def _parse_page(self, html):
        """Парсит одну страницу и возвращает список вакансий."""
        soup = BeautifulSoup(html, "html.parser")
        vacancies = []

        # hh периодически меняет классы, ищем по data-атрибутам
        cards = soup.find_all("div", attrs={"data-qa": "vacancy-serp__vacancy"})

        for card in cards:
            try:
                title_tag = card.find("a", attrs={"data-qa": "serp-item__title"})
                title = title_tag.text.strip() if title_tag else "N/A"

                company_tag = card.find(
                    "a", attrs={"data-qa": "vacancy-serp__vacancy-employer"}
                )
                company = company_tag.text.strip() if company_tag else "N/A"

                salary_tag = card.find(
                    "span", attrs={"data-qa": "vacancy-serp__vacancy-compensation"}
                )
                salary = salary_tag.text.strip() if salary_tag else "Не указана"

                city_tag = card.find(
                    "div", attrs={"data-qa": "vacancy-serp__vacancy-address"}
                )
                city = city_tag.text.strip() if city_tag else "N/A"

                vacancies.append(
                    {
                        "title": title,
                        "company": company,
                        "salary": salary,
                        "city": city,
                    }
                )
            except Exception as e:
                # пропускаем карточку если что-то пошло не так
                continue

        return vacancies

    def scrape(self):
        """Запускает парсинг по всем страницам."""
        print(f"Начинаю парсинг hh.ru по запросу: '{self.query}'")

        for page in range(self.pages):
            print(f"  Страница {page + 1}/{self.pages}...")
            html = self._get_html(page)
            if html:
                page_data = self._parse_page(html)
                self.data.extend(page_data)
                print(f"  Собрано вакансий: {len(page_data)}")
            time.sleep(1.5)  # задержка чтобы не получить бан

        print(f"\nВсего собрано: {len(self.data)} вакансий")
        return self

    def to_dataframe(self):
        """Возвращает собранные данные в виде DataFrame."""
        return pd.DataFrame(self.data)

    def save_csv(self, path="data/hh_vacancies.csv"):
        """Сохраняет данные в CSV-файл."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df = self.to_dataframe()
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Данные сохранены в {path}")
        return df


if __name__ == "__main__":
    # Запрос 1: ищем компании в сфере доставки для малого бизнеса
    parser = HHParser(query="логистика доставка малый бизнес", pages=3)
    parser.scrape()
    df = parser.save_csv("data/hh_vacancies.csv")

    print("\nПервые 5 строк:")
    print(df.head())
    print(f"\nРаспределение по городам:\n{df['city'].value_counts().head(10)}")
