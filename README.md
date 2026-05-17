# DS-project
import time
import re
import sys
import os
import threading
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# pip install streamlit plotly requests playwright pandas python-dotenv
# playwright install chromium

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CDEK_CLIENT_ID     = os.getenv("CDEK_CLIENT_ID",     "EMscd6r9JnFiQ3bLoyjJY6eM78JrJceI")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "PjLZkKBHEiLK3YsjtNrt3TGNG0ahs3kG")
CDEK_AUTH_URL      = "https://api.cdek.ru/v2/oauth/token"
CDEK_CALC_URL      = "https://api.cdek.ru/v2/calculator/tariff"
ROUTES_CSV         = "routes.csv"
EXPORT_CSV         = "real_tariffs_export.csv"


#  Парсер: СДЭК 

def get_cdek_token():
    try:
        resp = requests.post(
            CDEK_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CDEK_CLIENT_ID,
                "client_secret": CDEK_CLIENT_SECRET,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Error getting CDEK token: {e}", file=sys.stderr)
        return None


def get_cdek_tariff(origin_code, dest_code, weight_kg, origin="", destination=""):
    token = get_cdek_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "type": 1,
        "tariff_code": 480,
        "from_location": {"code": origin_code},
        "to_location": {"code": dest_code},
        "packages": [{"weight": int(weight_kg * 1000), "length": 10, "width": 10, "height": 10}],
    }

    try:
        resp = requests.post(CDEK_CALC_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        price = data.get("delivery_sum") or data.get("total_sum")
        if price is None:
            print(f"No price in CDEK response for {origin}→{destination}: {data}", file=sys.stderr)
            return None

        print(f"CDEK: {origin}→{destination} | {weight_kg}кг | {float(price)}₽ | {data.get('period_min')}-{data.get('period_max')} дней")
        return {
            "company_name": "СДЭК",
            "origin": origin or str(origin_code),
            "destination": destination or str(dest_code),
            "weight_kg": weight_kg,
            "price_rub": float(price),
            "delivery_days_min": data.get("period_min"),
            "delivery_days_max": data.get("period_max"),
        }

    except Exception as e:
        print(f"Error fetching CDEK tariff {origin}→{destination}: {e}", file=sys.stderr)
        return None


# Парсер: Возовоз 

def scrape_vozovoz_calculator(origin, destination, weight_kg):
    company_name = "Возовоз"
    print(f"Scraping {company_name}: {origin}→{destination} {weight_kg}кг...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("https://vozovoz.ru/order/create/", wait_until="domcontentloaded", timeout=30_000)

            # поле "Откуда" — кастомный dropdown, имитируем живой ввод
            page.locator("div.dp-input-icon-padding input").nth(0).click()
            page.locator("div.dp-input-icon-padding input").nth(0).fill(origin)
            page.wait_for_timeout(1000)
            page.locator("div.dp-menu-min-width div[role='option']").first.click()
            page.wait_for_timeout(1000)

            # поле "Куда"
            page.locator("div.dp-input-icon-padding input").nth(1).click()
            page.locator("div.dp-input-icon-padding input").nth(1).fill(destination)
            page.wait_for_timeout(1000)
            page.locator("div.dp-menu-min-width div[role='option']").first.click()
            page.wait_for_timeout(1000)

            # поле веса
            page.get_by_placeholder("Вес").click()
            page.get_by_placeholder("Вес").fill(str(weight_kg))

            # кнопка расчёта
            page.get_by_text("Рассчитать").click()
            page.wait_for_timeout(2000)

            # цена — пробуем два возможных селектора
            raw_price = page.locator(".total-price-value, span:has-text('Всего') + span").first.inner_text()
            cleaned = re.sub(r"[^\d.,]", "", raw_price).replace(",", ".")

            try:
                price = float(cleaned)
            except ValueError:
                print(f"Can't parse Возовоз price: {raw_price!r}", file=sys.stderr)
                return None

            print(f"{company_name}: {origin}→{destination} | {weight_kg}кг | {price}₽")
            return {
                "company_name": company_name,
                "origin": origin,
                "destination": destination,
                "weight_kg": weight_kg,
                "price_rub": price,
                "delivery_days_min": None,
                "delivery_days_max": None,
            }

        except Exception as e:
            print(f"Error scraping {company_name}: {e}", file=sys.stderr)
            return None
        finally:
            browser.close()


# Сборщик: запускается по кнопке из дашборда 

def run_parser(log_placeholder):
    if not os.path.exists(ROUTES_CSV):
        log_placeholder.error(f"Файл {ROUTES_CSV} не найден рядом со скриптом.")
        return

    df_routes = pd.read_csv(ROUTES_CSV)
    routes = df_routes.to_dict("records")
    results = []
    lines = []

    def log(msg):
        lines.append(msg)
        log_placeholder.code("\n".join(lines))

    log(f"Загружено маршрутов: {len(routes)}")
    log("─" * 50)
    log("СДЭК API...")

    for route in routes:
        record = get_cdek_tariff(
            route["origin_code"], route["dest_code"], route["weight_kg"],
            route["origin"], route["destination"]
        )
        if record:
            results.append(record)
            log(f"✓ СДЭК  {route['origin']}→{route['destination']} | {record['price_rub']} ₽")
        else:
            log(f"✗ СДЭК  {route['origin']}→{route['destination']} | нет данных")
        time.sleep(1.5)

    log("─" * 50)
    log("Возовоз scraper...")

    for route in routes:
        record = scrape_vozovoz_calculator(
            route["origin"], route["destination"], route["weight_kg"]
        )
        if record:
            results.append(record)
            log(f"✓ Возовоз  {route['origin']}→{route['destination']} | {record['price_rub']} ₽")
        else:
            log(f"✗ Возовоз  {route['origin']}→{route['destination']} | нет данных")
        time.sleep(3)

    columns = ["company_name", "origin", "destination", "weight_kg",
               "price_rub", "delivery_days_min", "delivery_days_max"]

    if results:
        pd.DataFrame(results, columns=columns).to_csv(EXPORT_CSV, index=False, encoding="utf-8-sig")
        log("─" * 50)
        log(f"✓ Сохранено {len(results)} строк → {EXPORT_CSV}")
    else:
        log("Данных нет — CSV не обновлён.")


# Дашборд 

st.set_page_config(layout="wide", page_title="EcoLogistic Analytics")
st.title("📊 EcoLogistic: Анализ логистического рынка")


@st.cache_data
def load_data():
    if not os.path.exists(EXPORT_CSV):
        return pd.DataFrame(columns=[
            "company_name", "origin", "destination",
            "weight_kg", "price_rub", "delivery_days_min", "delivery_days_max"
        ])
    df = pd.read_csv(EXPORT_CSV)
    df["delivery_days_min"] = pd.to_numeric(df["delivery_days_min"], errors="coerce")
    df["delivery_days_max"] = pd.to_numeric(df["delivery_days_max"], errors="coerce")
    return df


# Сайдбар 
st.sidebar.header("Сбор данных")

if st.sidebar.button("🔄 Обновить данные", use_container_width=True):
    st.sidebar.info("Парсер запущен, это займёт несколько минут...")
    log_area = st.sidebar.empty()
    run_parser(log_area)
    load_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Фильтры")

df = load_data()

if df.empty:
    st.warning("Нет данных. Нажми «Обновить данные» в сайдбаре чтобы запустить парсер.")
    st.stop()

origins = sorted(df["origin"].dropna().unique().tolist())
selected_origins = st.sidebar.multiselect("Город отправления", origins, default=origins)

destinations = sorted(df["destination"].dropna().unique().tolist())
selected_destinations = st.sidebar.multiselect("Город назначения", destinations, default=destinations)

weight_min = float(df["weight_kg"].min())
weight_max = float(df["weight_kg"].max())
if weight_min == weight_max:
    weight_max = weight_min + 1.0
selected_weight = st.sidebar.slider("Вес груза (кг)", weight_min, weight_max, (weight_min, weight_max))

filtered = df[
    df["origin"].isin(selected_origins) &
    df["destination"].isin(selected_destinations) &
    df["weight_kg"].between(selected_weight[0], selected_weight[1])
]

#Вкладки 

tab1, tab2, tab3 = st.tabs(["Сводные метрики", "Сравнение конкурентов", "Сырые данные"])


with tab1:
    avg_price    = filtered["price_rub"].mean()
    num_companies = filtered["company_name"].nunique()
    min_days     = filtered["delivery_days_min"].min()

    col1, col2, col3 = st.columns(3)
    col1.metric("Средняя стоимость доставки (₽)", f"{avg_price:,.0f} ₽" if not pd.isna(avg_price) else "—")
    col2.metric("Количество анализируемых ТК", num_companies)
    col3.metric("Минимальный срок доставки (дней)", f"{int(min_days)} дн." if not pd.isna(min_days) else "—")

    st.subheader("Средняя стоимость доставки по транспортным компаниям")
    avg_by_company = (
        filtered.groupby("company_name", as_index=False)["price_rub"]
        .mean()
        .rename(columns={"price_rub": "avg_price"})
        .sort_values("avg_price", ascending=False)
    )

    if avg_by_company.empty:
        st.info("Нет данных для выбранных фильтров.")
    else:
        fig_bar = px.bar(
            avg_by_company,
            x="company_name",
            y="avg_price",
            color="company_name",
            labels={"company_name": "Транспортная компания", "avg_price": "Средняя цена (₽)"},
            text_auto=".0f",
        )
        fig_bar.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig_bar, use_container_width=True)


with tab2:
    st.subheader("Бенчмаркинг: стоимость по направлениям и компаниям")

    if filtered.empty:
        st.info("Нет данных для выбранных фильтров.")
    else:
        fig_scatter = px.scatter(
            filtered,
            x="destination",
            y="price_rub",
            color="company_name",
            size="weight_kg",
            hover_data=["origin", "weight_kg", "delivery_days_min", "delivery_days_max"],
            labels={
                "destination": "Город назначения",
                "price_rub": "Стоимость (₽)",
                "company_name": "Компания",
                "weight_kg": "Вес (кг)",
            },
        )
        fig_scatter.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_scatter, use_container_width=True)


with tab3:
    st.subheader(f"Сырые данные ({len(filtered)} строк)")
    st.dataframe(filtered, use_container_width=True)

    csv_bytes = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ Скачать CSV",
        data=csv_bytes,
        file_name="filtered_tariffs.csv",
        mime="text/csv",
    )
