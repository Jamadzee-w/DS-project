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

from playwright.sync_api import sync_playwright

# ── Конфиг ──────────────────────────────────────────────────────────────────
CDEK_CLIENT_ID     = os.getenv("CDEK_CLIENT_ID",     "EMscd6r9JnFiQ3bLoyjJY6eM78JrJceI")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "PjLZkKBHEiLK3YsjtNrt3TGNG0ahs3kG")
CDEK_AUTH_URL      = "https://api.cdek.ru/v2/oauth/token"
CDEK_CALC_URL      = "https://api.cdek.ru/v2/calculator/tariff"
ROUTES_CSV         = "data/routes.csv"
EXPORT_CSV         = "data/real_tariffs_export.csv"


# ════════════════════════════════════════════════════════════════════════════
#  КЛАСС 1 — СДЭК (REST API)
# ════════════════════════════════════════════════════════════════════════════

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

    def get_tariff(
        self,
        origin_code: int,
        dest_code: int,
        weight_kg: float,
        origin: str = "",
        destination: str = "",
    ) -> dict | None:
        """POST к /v2/calculator/tariff — возвращает price + period_min/max."""
        if not self._token:
            self._token = self._authenticate()

        payload = {
            "type": 1,
            "tariff_code": 480,
            "from_location": {"code": origin_code},
            "to_location":   {"code": dest_code},
            "packages": [{
                "weight": int(weight_kg * 1000),
                "length": 10,
                "width":  10,
                "height": 10,
            }],
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
                print(f"[СДЭК] нет цены для {origin}→{destination}: {data}", file=sys.stderr)
                return None

            print(f"[СДЭК] {origin}→{destination} | {weight_kg}кг | {float(price):.0f}₽ "
                  f"| {data.get('period_min')}-{data.get('period_max')} дн.")
            return {
                "company_name":      "СДЭК",
                "origin":            origin or str(origin_code),
                "destination":       destination or str(dest_code),
                "weight_kg":         weight_kg,
                "price_rub":         float(price),
                "delivery_days_min": data.get("period_min"),
                "delivery_days_max": data.get("period_max"),
            }

        except Exception as e:
            print(f"[СДЭК] ошибка {origin}→{destination}: {e}", file=sys.stderr)
            return None


# ════════════════════════════════════════════════════════════════════════════
#  КЛАСС 2 — Возовоз (Playwright scraper)
# ════════════════════════════════════════════════════════════════════════════

class VozovozScraper:
    """Парсит калькулятор vozovoz.ru через headless Chromium."""

    COMPANY = "Возовоз"

    def get_tariff(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> dict | None:
        print(f"[Возовоз] {origin}→{destination} {weight_kg}кг ...")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page()

            try:
                page.goto(
                    "https://vozovoz.ru/order/create/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

                # поле «Откуда»
                page.locator("div.dp-input-icon-padding input").nth(0).click()
                page.locator("div.dp-input-icon-padding input").nth(0).fill(origin)
                page.wait_for_timeout(1000)
                page.locator("div.dp-menu-min-width div[role='option']").first.click()
                page.wait_for_timeout(1000)

                # поле «Куда»
                page.locator("div.dp-input-icon-padding input").nth(1).click()
                page.locator("div.dp-input-icon-padding input").nth(1).fill(destination)
                page.wait_for_timeout(1000)
                page.locator("div.dp-menu-min-width div[role='option']").first.click()
                page.wait_for_timeout(1000)

                # вес
                page.get_by_placeholder("Вес").click()
                page.get_by_placeholder("Вес").fill(str(weight_kg))

                # расчёт
                page.get_by_text("Рассчитать").click()
                page.wait_for_timeout(2500)

                raw = page.locator(
                    ".total-price-value, span:has-text('Всего') + span"
                ).first.inner_text()

                cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
                price   = float(cleaned)

                print(f"[Возовоз] {origin}→{destination} | {weight_kg}кг | {price:.0f}₽")
                return {
                    "company_name":      self.COMPANY,
                    "origin":            origin,
                    "destination":       destination,
                    "weight_kg":         weight_kg,
                    "price_rub":         price,
                    "delivery_days_min": None,
                    "delivery_days_max": None,
                }

            except Exception as e:
                print(f"[Возовоз] ошибка {origin}→{destination}: {e}", file=sys.stderr)
                return None
            finally:
                browser.close()


# ════════════════════════════════════════════════════════════════════════════
#  СБОРЩИК — читает routes.csv, запускает оба парсера, пишет export
# ════════════════════════════════════════════════════════════════════════════

def run():
    if not os.path.exists(ROUTES_CSV):
        print(f"Файл {ROUTES_CSV} не найден.", file=sys.stderr)
        sys.exit(1)

    routes  = pd.read_csv(ROUTES_CSV).to_dict("records")
    results = []

    cdek     = CDEKParser(CDEK_CLIENT_ID, CDEK_CLIENT_SECRET)
    vozovoz  = VozovozScraper()

    # — СДЭК —
    print("\n" + "─" * 50)
    print("СДЭК API")
    print("─" * 50)
    for r in routes:
        rec = cdek.get_tariff(
            r["origin_code"], r["dest_code"], r["weight_kg"],
            r["origin"],      r["destination"],
        )
        if rec:
            results.append(rec)
        time.sleep(1.5)

    # — Возовоз —
    print("\n" + "─" * 50)
    print("Возовоз scraper")
    print("─" * 50)
    for r in routes:
        rec = vozovoz.get_tariff(r["origin"], r["destination"], r["weight_kg"])
        if rec:
            results.append(rec)
        time.sleep(3)

    # — Сохранение —
    cols = [
        "company_name", "origin", "destination",
        "weight_kg", "price_rub",
        "delivery_days_min", "delivery_days_max",
    ]
    os.makedirs("data", exist_ok=True)
    if results:
        pd.DataFrame(results, columns=cols).to_csv(
            EXPORT_CSV, index=False, encoding="utf-8-sig"
        )
        print(f"\n✓ Сохранено {len(results)} строк → {EXPORT_CSV}")
    else:
        print("\n✗ Данных нет — CSV не создан.")


if __name__ == "__main__":
    run()
