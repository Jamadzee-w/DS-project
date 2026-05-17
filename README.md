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
            label="⬇️ Скачать текущую выборку (CSV)",
            data=csv_string,
            file_name="leads_filtered.csv",
            mime="text/csv",
        )


# =============================================================================
# ТОЧКА ВХОДА
# =============================================================================
if name == "main":
    if "--parse" in sys.argv:
        run_parser()
    else:
        print("Используйте одну из команд:")
        print("  Парсинг:  python app.py --parse")
        print("  Дашборд:  streamlit run app.py")
else:
    # Streamlit импортирует файл как модуль — запускаем дашборд автоматически
    run_dashboard()
