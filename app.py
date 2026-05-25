import os
import pandas as pd
import streamlit as st
import plotly.express as px

from parser import run_mock, run_live

EXPORT_CSV = "data/real_tariffs_export.csv"

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


# ── Сайдбар ──────────────────────────────────────────────────────────────────
st.sidebar.header("Сбор данных")

col_mock, col_live = st.sidebar.columns(2)

if col_mock.button("🧪 Тест", use_container_width=True):
    st.sidebar.info("Загружаем тестовые данные...")
    log_area = st.sidebar.empty()
    lines = []
    def log(msg):
        lines.append(msg)
        log_area.code("\n".join(lines))
    run_mock(log)
    load_data.clear()
    st.rerun()

if col_live.button("🔄 Live", use_container_width=True):
    st.sidebar.info("Парсер запущен, займёт несколько минут...")
    log_area = st.sidebar.empty()
    lines = []
    def log(msg):
        lines.append(msg)
        log_area.code("\n".join(lines))
    run_live(log)
    load_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Фильтры")

df = load_data()

if df.empty:
    st.warning("Нет данных. Нажми **🧪 Тест** или **🔄 Live** в сайдбаре.")
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


# ── Вкладки ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Сводные метрики", "Сравнение конкурентов", "Сырые данные"])


with tab1:
    avg_price     = filtered["price_rub"].mean()
    num_companies = filtered["company_name"].nunique()
    min_days      = filtered["delivery_days_min"].min()

    col1, col2, col3 = st.columns(3)
    col1.metric("Средняя стоимость доставки (₽)", f"{avg_price:,.0f} ₽" if not pd.isna(avg_price) else "—")
    col2.metric("Количество анализируемых ТК", num_companies)
    col3.metric("Минимальный срок доставки (дней)", f"{int(min_days)} дн." if not pd.isna(min_days) else "—")

    st.subheader("Средняя стоимость по транспортным компаниям")
    avg_by_company = (
        filtered.groupby("company_name", as_index=False)["price_rub"]
        .mean()
        .rename(columns={"price_rub": "avg_price"})
        .sort_values("avg_price", ascending=False)
    )
    if not avg_by_company.empty:
        fig_bar = px.bar(
            avg_by_company,
            x="company_name", y="avg_price", color="company_name",
            labels={"company_name": "Транспортная компания", "avg_price": "Средняя цена (₽)"},
            text_auto=".0f",
        )
        fig_bar.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Стоимость по маршрутам")
    if not filtered.empty:
        fig_line = px.line(
            filtered.sort_values("destination"),
            x="destination", y="price_rub", color="company_name", markers=True,
            labels={"destination": "Город назначения", "price_rub": "Цена (₽)", "company_name": "Компания"},
        )
        fig_line.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_line, use_container_width=True)


with tab2:
    st.subheader("Бенчмаркинг: стоимость по направлениям и компаниям")
    if not filtered.empty:
        fig_scatter = px.scatter(
            filtered,
            x="destination", y="price_rub", color="company_name", size="weight_kg",
            hover_data=["origin", "weight_kg", "delivery_days_min", "delivery_days_max"],
            labels={"destination": "Город назначения", "price_rub": "Стоимость (₽)",
                    "company_name": "Компания", "weight_kg": "Вес (кг)"},
        )
        fig_scatter.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("Разница в цене: СДЭК vs Возовоз")
    pivot = filtered.pivot_table(index="destination", columns="company_name", values="price_rub")
    if "СДЭК" in pivot.columns and "Возовоз" in pivot.columns:
        pivot["Разница (₽)"] = pivot["СДЭК"] - pivot["Возовоз"]
        pivot["Дешевле"]     = pivot["Разница (₽)"].apply(lambda x: "Возовоз" if x > 0 else "СДЭК")
        st.dataframe(pivot.reset_index(), use_container_width=True)
        fig_diff = px.bar(
            pivot.reset_index(),
            x="destination", y="Разница (₽)", color="Дешевле",
            labels={"destination": "Маршрут"},
            title="Положительное значение = СДЭК дороже Возовоза",
        )
        fig_diff.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_diff, use_container_width=True)


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
