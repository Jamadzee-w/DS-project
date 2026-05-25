import time
import re
import sys
import os
import requests
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CDEK_CLIENT_ID     = os.getenv("CDEK_CLIENT_ID",     "EMscd6r9JnFiQ3bLoyjJY6eM78JrJceI")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "PjLZkKBHEiLK3YsjtNrt3TGNG0ahs3kG")
CDEK_AUTH_URL      = "https://api.cdek.ru/v2/oauth/token"
CDEK_CALC_URL      = "https://api.cdek.ru/v2/calculator/tariff"
ROUTES_CSV         = "data/routes.csv"
EXPORT_CSV         = "data/real_tariffs_export.csv"

MOCK_DATA = [
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Казань",          "weight_kg": 5, "price_rub": 1240, "delivery_days_min": 2, "delivery_days_max": 3},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Екатеринбург",    "weight_kg": 5, "price_rub": 1580, "delivery_days_min": 3, "delivery_days_max": 4},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Новосибирск",     "weight_kg": 5, "price_rub": 1950, "delivery_days_min": 4, "delivery_days_max": 5},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Краснодар",       "weight_kg": 5, "price_rub": 1380, "delivery_days_min": 3, "delivery_days_max": 4},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Санкт-Петербург", "weight_kg": 5, "price_rub":  980, "delivery_days_min": 2, "delivery_days_max": 3},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Самара",          "weight_kg": 5, "price_rub": 1120, "delivery_days_min": 2, "delivery_days_max": 3},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Ростов-на-Дону",  "weight_kg": 5, "price_rub": 1450, "delivery_days_min": 3, "delivery_days_max": 4},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Уфа",             "weight_kg": 5, "price_rub": 1680, "delivery_days_min": 3, "delivery_days_max": 5},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Пермь",           "weight_kg": 5, "price_rub": 1520, "delivery_days_min": 3, "delivery_days_max": 4},
    {"company_name": "СДЭК", "origin": "Москва", "destination": "Воронеж",         "weight_kg": 5, "price_rub":  890, "delivery_days_min": 1, "delivery_days_max": 2},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Казань",          "weight_kg": 5, "price_rub": 1090, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Екатеринбург",    "weight_kg": 5, "price_rub": 1320, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Новосибирск",     "weight_kg": 5, "price_rub": 1780, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Краснодар",       "weight_kg": 5, "price_rub": 1210, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Санкт-Петербург", "weight_kg": 5, "price_rub":  850, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Самара",          "weight_kg": 5, "price_rub":  990, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Ростов-на-Дону",  "weight_kg": 5, "price_rub": 1290, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Уфа",             "weight_kg": 5, "price_rub": 1540, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Пермь",           "weight_kg": 5, "price_rub": 1380, "delivery_days_min": None, "delivery_days_max": None},
    {"company_name": "Возовоз", "origin": "Москва", "destination": "Воронеж",         "weight_kg": 5, "price_rub":  780, "delivery_days_min": None, "delivery_days_max": None},
]


# ════════════════════════════════════════════════════════
#  КЛАСС 1 — СДЭК (REST API)
# ════════════════════════════════════════════════════════

class CDEKParser:
    """Получает тарифы через официальный СДЭК API v2."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self._token        = None

    def _authenticate(self) -> str:
        resp = requests.post(CDEK_AUTH_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def get_tariff(self, origin_code, dest_code, weight_kg, origin="", destination=""):
        if not self._token:
            self._token = self._authenticate()
        payload = {
            "type": 1,
            "tariff_code": 480,
            "from_location": {"code": origin_code},
            "to_location":   {"code": dest_code},
            "packages": [{"weight": int(weight_kg * 1000), "length": 10, "width": 10, "height": 10}],
        }
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        try:
            resp = requests.post(CDEK_CALC_URL, json=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            data  = resp.json()
            price = data.get("delivery_sum") or data.get("total_sum")
            if price is None:
                print(f"[СДЭК] нет цены {origin}→{destination}: {data}", file=sys.stderr)
                return None
            print(f"[СДЭК] {origin}→{destination} | {float(price):.0f}₽ | {data.get('period_min')}-{data.get('period_max')} дн.")
            return {
                "company_name": "СДЭК",
                "origin":       origin or str(origin_code),
                "destination":  destination or str(dest_code),
                "weight_kg":    weight_kg,
                "price_rub":    float(price),
                "delivery_days_min": data.get("period_min"),
                "delivery_days_max": data.get("period_max"),
            }
        except Exception as e:
            print(f"[СДЭК] ошибка {origin}→{destination}: {e}", file=sys.stderr)
            return None


# ════════════════════════════════════════════════════════
#  КЛАСС 2 — Возовоз (Playwright scraper)
# ════════════════════════════════════════════════════════

class VozovozScraper:
    """Парсит калькулятор vozovoz.ru через headless Chromium."""

    def get_tariff(self, origin, destination, weight_kg):
        from playwright.sync_api import sync_playwright
        print(f"[Возовоз] {origin}→{destination} {weight_kg}кг ...")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page()
            try:
                page.goto("https://vozovoz.ru/order/create/", wait_until="domcontentloaded", timeout=30_000)
                page.locator("div.dp-input-icon-padding input").nth(0).click()
                page.locator("div.dp-input-icon-padding input").nth(0).fill(origin)
                page.wait_for_timeout(1000)
                page.locator("div.dp-menu-min-width div[role='option']").first.click()
                page.wait_for_timeout(1000)
                page.locator("div.dp-input-icon-padding input").nth(1).click()
                page.locator("div.dp-input-icon-padding input").nth(1).fill(destination)
                page.wait_for_timeout(1000)
                page.locator("div.dp-menu-min-width div[role='option']").first.click()
                page.wait_for_timeout(1000)
                page.get_by_placeholder("Вес").click()
                page.get_by_placeholder("Вес").fill(str(weight_kg))
                page.get_by_text("Рассчитать").click()
                page.wait_for_timeout(2500)
                raw     = page.locator(".total-price-value, span:has-text('Всего') + span").first.inner_text()
                cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
                price   = float(cleaned)
                print(f"[Возовоз] {origin}→{destination} | {price:.0f}₽")
                return {
                    "company_name": "Возовоз",
                    "origin":       origin,
                    "destination":  destination,
                    "weight_kg":    weight_kg,
                    "price_rub":    price,
                    "delivery_days_min": None,
                    "delivery_days_max": None,
                }
            except Exception as e:
                print(f"[Возовоз] ошибка {origin}→{destination}: {e}", file=sys.stderr)
                return None
            finally:
                browser.close()


# ════════════════════════════════════════════════════════
#  MOCK-режим
# ════════════════════════════════════════════════════════

def run_mock(log_fn=print):
    """Симулирует парсинг — сохраняет тестовые данные без реальных запросов."""
    log_fn("─" * 50)
    log_fn("MOCK-режим: загружаем тестовые данные...")
    log_fn("─" * 50)
    for r in MOCK_DATA:
        days = f"{r['delivery_days_min']}-{r['delivery_days_max']} дн." if r["delivery_days_min"] else "—"
        log_fn(f"✓ {r['company_name']}  {r['origin']}→{r['destination']} | {r['price_rub']} ₽  {days}")
        time.sleep(0.05)
    _save(MOCK_DATA, log_fn)


# ════════════════════════════════════════════════════════
#  LIVE-режим
# ════════════════════════════════════════════════════════

def run_live(log_fn=print):
    """Реальный парсинг: СДЭК API + Возовоз scraper."""
    if not os.path.exists(ROUTES_CSV):
        log_fn(f"✗ Файл {ROUTES_CSV} не найден.")
        return
    routes  = pd.read_csv(ROUTES_CSV).to_dict("records")
    results = []
    cdek    = CDEKParser(CDEK_CLIENT_ID, CDEK_CLIENT_SECRET)
    voz     = VozovozScraper()

    log_fn("─" * 50)
    log_fn("СДЭК API...")
    for r in routes:
        rec = cdek.get_tariff(
            r["origin_code"], r["dest_code"], r["weight_kg"],
            r["origin"], r["destination"]
        )
        if rec:
            results.append(rec)
            log_fn(f"✓ СДЭК  {r['origin']}→{r['destination']} | {rec['price_rub']} ₽")
        else:
            log_fn(f"✗ СДЭК  {r['origin']}→{r['destination']} | нет данных")
        time.sleep(1.5)

    log_fn("─" * 50)
    log_fn("Возовоз scraper...")
    for r in routes:
        rec = voz.get_tariff(r["origin"], r["destination"], r["weight_kg"])
        if rec:
            results.append(rec)
            log_fn(f"✓ Возовоз  {r['origin']}→{r['destination']} | {rec['price_rub']} ₽")
        else:
            log_fn(f"✗ Возовоз  {r['origin']}→{r['destination']} | нет данных")
        time.sleep(3)

    _save(results, log_fn)


# ════════════════════════════════════════════════════════
#  Сохранение в CSV
# ════════════════════════════════════════════════════════

def _save(results, log_fn=print):
    cols = ["company_name", "origin", "destination", "weight_kg",
            "price_rub", "delivery_days_min", "delivery_days_max"]
    os.makedirs("data", exist_ok=True)
    if results:
        pd.DataFrame(results, columns=cols).to_csv(EXPORT_CSV, index=False, encoding="utf-8-sig")
        log_fn("─" * 50)
        log_fn(f"✓ Сохранено {len(results)} строк → {EXPORT_CSV}")
    else:
        log_fn("✗ Данных нет — CSV не обновлён.")


# ════════════════════════════════════════════════════════
#  Точка входа
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "mock"
    if mode == "live":
        run_live()
    else:
        run_mock()
