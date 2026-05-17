import os
import time
import sys
import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv, set_key
from tqdm import tqdm

# КОНФИГУРАЦИЯ
API          = "https://api.vk.com/method"
V            = "5.199"
QUERIES_FILE = "vk_queries.txt"
OUTPUT_CSV   = "leads_vk_export.csv"
DEFAULT_QUERIES = [
    "фермерские продукты",
    "фермерское хозяйство",
    "сыроварня",
    "экопродукты",
]


# БЛОК 1: ПАРСЕР ВКонтакте
def get_token():
    load_dotenv()
    token = os.getenv("VK_SERVICE_TOKEN", "").strip()
    if token:
        return token
    print("Токен VK не найден.")
    print("Получить его можно здесь: https://vk.com/apps?act=manage")
    token = input("Введите сервисный ключ ВК: ").strip()
    if not token:
        raise SystemExit("Токен не введён, выход.")
    env_path = ".env"
    if not os.path.exists(env_path):
        open(env_path, "w").close()
    set_key(env_path, "VK_SERVICE_TOKEN", token)
    print("✓ Токен сохранён в .env\n")
    return token


def load_queries():
    if not os.path.exists(QUERIES_FILE):
        print(f"Файл {QUERIES_FILE} не найден — создаю с базовыми запросами.")
        with open(QUERIES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(DEFAULT_QUERIES))
        print(f"✓ {QUERIES_FILE} создан\n")
    with open(QUERIES_FILE, encoding="utf-8") as f:
        queries = [line.strip() for line in f if line.strip()]
    print(f"Загружено запросов из {QUERIES_FILE}: {len(queries)}")
    return queries


def vk_get(method, params, token, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(
                f"{API}/{method}",
                params={"access_token": token, "v": V, **params},
                timeout=10,
            )
            data = r.json()
            if "error" in data:
                code = data["error"]["error_code"]
                msg  = data["error"]["error_msg"]
                if code == 6:
                    wait = 2 ** attempt  # 1 → 2 → 4 сек
                    tqdm.write(f"  Rate limit, жду {wait}с и повторяю...")
                    time.sleep(wait)
                    continue
                tqdm.write(f"  VK error {code}: {msg}")
                return None
            return data["response"]
        except Exception as e:
            tqdm.write(f"  Request failed: {e}")
            time.sleep(1)
    return None


def search_groups(query, token):
    time.sleep(0.5)
    result = vk_get(
        "groups.search",
        {"q": query, "type": "group", "sort": 6, "count": 100},
        token,
    )
    if not result:
        return []
    return [g["id"] for g in result["items"]]


def get_group_details(group_ids, token):
    details = []
    batches = [group_ids[i:i + 500] for i in range(0, len(group_ids), 500)]
    for batch in tqdm(batches, desc="Загрузка деталей", unit="батч"):
        time.sleep(0.5)
        result = vk_get(
            "groups.getById",
            {
                "group_ids": ",".join(str(x) for x in batch),
                "fields": "city,contacts,members_count,description,site",
            },
            token,
        )
        if not result:
            continue
        groups = result if isinstance(result, list) else result.get("groups", [])
        details.extend(groups)
    return details


def extract_contact(contacts, field):
    for c in contacts or []:
        v = c.get(field, "").strip()
        if v:
            return v
    return ""


def run_parser():
    token   = get_token()
    queries = load_queries()
    all_ids = set()
    for query in tqdm(queries, desc="Поиск групп", unit="запрос"):
        ids = search_groups(query, token)
        all_ids.update(ids)
        tqdm.write(f"  «{query}»: {len(ids)} групп")
    print(f"\nУникальных групп: {len(all_ids)}")
    groups = get_group_details(list(all_ids), token)
    print(f"Деталей получено: {len(groups)}")
    leads = []
    for g in groups:
        members = g.get("members_count", 0)
        if members < 500 or members > 500_000:
            continue
        city        = (g.get("city") or {}).get("title", "")
        contacts    = g.get("contacts") or []
        screen_name = g.get("screen_name") or f"club{g.get('id')}"
        leads.append({
            "group_id":      g.get("id"),
            "name":          g.get("name", ""),
            "city":          city,
            "members_count": members,
            "phone":         extract_contact(contacts, "phone"),
            "email":         extract_contact(contacts, "email"),
            "vk_url":        f"https://vk.com/{screen_name}",
        })
    print(f"Лидов после фильтрации: {len(leads)}")
    if not leads:
        print("Нет лидов для сохранения.")
        return
    df = pd.DataFrame(leads)
    df.drop_duplicates(subset="group_id", inplace=True)
    df.sort_values("members_count", ascending=False, inplace=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"✓ Сохранено {len(df)} лидов → {OUTPUT_CSV}")


# БЛОК 2: ДАШБОРД STREAMLIT
def run_dashboard():
    st.set_page_config(layout="wide", page_title="EcoLogistic: Анализ Аудитории")
    st.title("🌱 EcoLogistic: Аудитория фермеров и крафта")
    @st.cache_data
    def load_data():
        try:
            df = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
            df["city"] = df["city"].fillna("Не указан").replace("", "Не указан")
            return df
        except FileNotFoundError:
            return None
    df_raw = load_data()
    if df_raw is None:
        st.error(
            f"Файл {OUTPUT_CSV} не найден. "
            "Сначала запустите парсер: python app.py --parse"
        )
        st.stop()
    # ── Сайдбар ─────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Фильтры")
        cities = sorted(df_raw["city"].unique().tolist())
        selected_cities = st.multiselect("Выбор города", cities, default=[])
        min_m = int(df_raw["members_count"].min())
        max_m = int(df_raw["members_count"].max())
        members_range = st.slider(
            "Количество подписчиков", min_m, max_m, (min_m, max_m)
        )
        only_contacts = st.checkbox("Только с телефоном / email")
    # ── Фильтрация ──────────────────────────────────────────────────────────
    df = df_raw.copy()
    if selected_cities:
        df = df[df["city"].isin(selected_cities)]
    df = df[df["members_count"].between(*members_range)]
    if only_contacts:
        has = (
            (df["phone"].notna() & (df["phone"] != ""))
            | (df["email"].notna() & (df["email"] != ""))
        )
        df = df[has]
    # ── Вкладки ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(
        ["📊 Сводка", "🗺 География спроса", "📋 База лидов"]
    )
    with tab1:
        has_contact = (
            (df["phone"].notna() & (df["phone"] != ""))
            | (df["email"].notna() & (df["email"] != ""))
        )
        col1, col2, col3 = st.columns(3)
        col1.metric("Найдено сообществ",     f"{len(df):,}")
        col2.metric("Общий охват аудитории", f"{df['members_count'].sum():,}")
        col3.metric("Лидов с контактами",    f"{has_contact.sum():,}")
        st.divider()
        top_cities = (
            df.groupby("city")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(15)
        )
        fig_bar = px.bar(
            top_cities,
            x="count", y="city", orientation="h",
            title="Топ-15 городов по числу сообществ",
            labels={"count": "Количество групп", "city": "Город"},
            color="count",
            color_continuous_scale="Greens",
        )
        fig_bar.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    with tab2:
        if df.empty:
            st.info("Нет данных для отображения — попробуйте изменить фильтры.")
        else:
            fig_tree = px.treemap(
                df,
                path=["city", "name"],
                values="members_count",
                title="Доля аудитории по городам и сообществам (размер = подписчики)",
                color="members_count",
                color_continuous_scale="Greens",
                hover_data={"members_count": ":,"},
            )
            fig_tree.update_traces(textinfo="label+value")
            fig_tree.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_tree, use_container_width=True)
    with tab3:
        display_df = df.drop(columns=["group_id"], errors="ignore")
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                "vk_url": st.column_config.LinkColumn(
                    "Ссылка ВК", display_text="Открыть"
                ),
                "members_count": st.column_config.NumberColumn(
                    "Подписчики", format="%d"
                ),
            },
            hide_index=True,
        )
        csv_string = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇ Скачать текущую выборку (CSV)",
            data=csv_string,
            file_name="leads_filtered.csv",
            mime="text/csv",
        )


# ТОЧКА ВХОДА
if __name__ == "__main__":
    if "--parse" in sys.argv:
        run_parser()
    else:
        print("Используйте одну из команд:")
        print("  Парсинг:  python app.py --parse")
        print("  Дашборд:  streamlit run app.py")
else:
    # Streamlit импортирует файл как модуль — запускаем дашборд автоматически
    run_dashboard()
