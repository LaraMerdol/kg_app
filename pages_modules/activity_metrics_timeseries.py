"""
Activity-Level Metrics Over Time (2022-2026)
==============================================
Displays 3 figures tracking key metrics by SE activity over time:
  1. Model Count - Cumulative number of models associated with each activity
  2. Dataset Count - Cumulative number of datasets linked to models within each activity
  3. Task Coverage - Proportion of defined tasks that have at least one model
"""

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ModuleNotFoundError:
    px = None
    go = None

try:
    from ..config import CACHE_FILE
    from ..data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation, utc_now_iso
    from ..queries.activity_metrics_timeseries import (
        MODELS_BY_ACTIVITY_YEAR_QUERY,
        DATASETS_BY_ACTIVITY_YEAR_QUERY,
        TASK_COVERAGE_BY_ACTIVITY_YEAR_QUERY,
    )
except ImportError:
    from config import CACHE_FILE
    from data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation, utc_now_iso
    from queries.activity_metrics_timeseries import (
        MODELS_BY_ACTIVITY_YEAR_QUERY,
        DATASETS_BY_ACTIVITY_YEAR_QUERY,
        TASK_COVERAGE_BY_ACTIVITY_YEAR_QUERY,
    )


def _ensure_plotly() -> bool:
    if px is None or go is None:
        st.error("This page requires the optional 'plotly' package. Install it with 'pip install plotly' and restart Streamlit.")
        return False
    return True


def render_activity_metrics_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    """Render activity-level metrics over time (monthly series from 2020 onward)."""
    if not _ensure_plotly():
        return

    chart_start = pd.Timestamp("2021-01-01")
    chart_end = pd.Timestamp("2026-01-01")

    st.subheader("Activity Metrics Over Time (Quarterly, 2021-Q1 to 2026-Q1)")
    st.caption(
        "Track key metrics across SE activities from 2021-Q1 to 2026-Q1 using quarterly buckets."
    )

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load metrics (cache first)", type="primary")
    refresh_clicked = col_refresh.button("Refresh from DB")

    if not (load_clicked or refresh_clicked):
        st.info("Click 'Load metrics' to fetch activity metrics over time.")
        return

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    def _quarter_bucket_to_timestamp(bucket: str) -> pd.Timestamp:
        bucket_text = str(bucket)
        year_text, quarter_text = bucket_text.split("-Q")
        year = int(year_text)
        quarter = int(quarter_text)
        month = (quarter - 1) * 3 + 1
        return pd.Timestamp(year=year, month=month, day=1)

    def _timestamp_to_quarter_bucket(ts: pd.Timestamp) -> str:
        quarter = ((int(ts.month) - 1) // 3) + 1
        return f"{int(ts.year)}-Q{quarter}"

    def _pad_from_start(df: pd.DataFrame, value_col: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        frames = []
        for activity_name, group in df.groupby("activity_name"):
            g = group.copy()
            g["time_point"] = g["time_bucket"].apply(_quarter_bucket_to_timestamp)
            g = g.dropna(subset=["time_point"])
            g = g[(g["time_point"] >= start) & (g["time_point"] <= end)]
            if g.empty:
                continue
            timeline = pd.DataFrame({"time_point": pd.date_range(start=start, end=end, freq="QS")})
            merged = timeline.merge(g[["time_point", value_col]], on="time_point", how="left")
            merged[value_col] = pd.to_numeric(merged[value_col], errors="coerce").fillna(0)
            merged["activity_name"] = activity_name
            merged["time_bucket"] = merged["time_point"].apply(_timestamp_to_quarter_bucket)
            frames.append(merged)
        return pd.concat(frames, ignore_index=True) if frames else df

    chart_config = {"displaylogo": False, "responsive": True, "scrollZoom": False}
    with st.spinner("Loading activity metrics over time..."):
        try:
            # Fetch all three metrics
            st.write("Fetching Model Count...")
            model_rows, model_source, model_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODELS_BY_ACTIVITY_YEAR_QUERY,
                row_limit=int(row_limit),
                prefer_cache=load_clicked,
            )

            st.write("Fetching Dataset Count...")
            dataset_rows, dataset_source, dataset_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=DATASETS_BY_ACTIVITY_YEAR_QUERY,
                row_limit=int(row_limit),
                prefer_cache=load_clicked,
            )

            st.write("Fetching Task Coverage...")
            coverage_rows, coverage_source, coverage_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_COVERAGE_BY_ACTIVITY_YEAR_QUERY,
                row_limit=int(row_limit),
                prefer_cache=load_clicked,
            )

            # Provide feedback on data sources
            st.success(f"✓ Model Count: {model_info}")
            st.success(f"✓ Dataset Count: {dataset_info}")
            st.success(f"✓ Task Coverage: {coverage_info}")

            # Process and visualize each metric
            st.markdown("---")
            st.markdown("## (1) Model Count Over Time")
            st.caption("The number of models created each quarter for each activity between 2021-Q1 and 2026-Q1")

            if model_rows:
                model_df = pd.DataFrame(model_rows)
                model_df["model_count"] = pd.to_numeric(model_df["model_count"], errors="coerce").fillna(0)
                model_df = _pad_from_start(model_df, "model_count", chart_start, chart_end)
                model_df = model_df.sort_values(["activity_name", "time_point", "time_bucket"])

                fig_models = px.line(
                    model_df,
                    x="time_bucket",
                    y="model_count",
                    color="activity_name",
                    markers=True,
                    title="New Models Created per Quarter by Activity (2021-Q1 to 2026-Q1)",
                    labels={
                        "time_bucket": "Quarter",
                        "model_count": "New Models in Quarter",
                        "activity_name": "Activity",
                    },
                    template="plotly_white",
                )
                fig_models.update_layout(
                    hovermode="x unified",
                    dragmode="zoom",
                    xaxis=dict(type="category", categoryorder="category ascending"),
                    height=500,
                )
                st.plotly_chart(fig_models, use_container_width=True, config=chart_config)

                st.dataframe(model_df[["activity_name", "time_bucket", "model_count"]], use_container_width=True)
            else:
                st.warning("No model count data available.")

            st.markdown("---")
            st.markdown("## (2) Dataset Count Over Time")
            st.caption("The cumulative number of datasets linked to models within each activity between 2021-Q1 and 2026-Q1")

            if dataset_rows:
                dataset_df = pd.DataFrame(dataset_rows)
                dataset_df["dataset_count"] = pd.to_numeric(dataset_df["dataset_count"], errors="coerce").fillna(0)
                dataset_df = _pad_from_start(dataset_df, "dataset_count", chart_start, chart_end)
                dataset_df = dataset_df.sort_values(["activity_name", "time_point", "time_bucket"])
                dataset_df["new_dataset_count"] = dataset_df["dataset_count"]
                dataset_df["dataset_count"] = dataset_df.groupby("activity_name")["dataset_count"].cumsum()

                fig_datasets = px.line(
                    dataset_df,
                    x="time_bucket",
                    y="dataset_count",
                    color="activity_name",
                    markers=True,
                    title="Dataset Count by Activity (2021-Q1 to 2026-Q1)",
                    labels={
                        "time_bucket": "Quarter",
                        "dataset_count": "Number of Datasets",
                        "activity_name": "Activity",
                    },
                    template="plotly_white",
                )
                fig_datasets.update_layout(
                    hovermode="x unified",
                    dragmode="zoom",
                    xaxis=dict(type="category", categoryorder="category ascending"),
                    height=500,
                )
                st.plotly_chart(fig_datasets, use_container_width=True, config=chart_config)

                st.dataframe(dataset_df[["activity_name", "time_bucket", "dataset_count"]], use_container_width=True)

                st.markdown("### (2b) New Datasets per Quarter")
                st.caption("Non-cumulative number of new datasets linked to models in each quarter.")

                fig_new_datasets = px.line(
                    dataset_df,
                    x="time_bucket",
                    y="new_dataset_count",
                    color="activity_name",
                    markers=True,
                    title="New Datasets per Quarter by Activity (2021-Q1 to 2026-Q1)",
                    labels={
                        "time_bucket": "Quarter",
                        "new_dataset_count": "New Datasets in Quarter",
                        "activity_name": "Activity",
                    },
                    template="plotly_white",
                )
                fig_new_datasets.update_layout(
                    hovermode="x unified",
                    dragmode="zoom",
                    xaxis=dict(type="category", categoryorder="category ascending"),
                    height=420,
                )
                st.plotly_chart(fig_new_datasets, use_container_width=True, config=chart_config)

                st.dataframe(
                    dataset_df[["activity_name", "time_bucket", "new_dataset_count"]],
                    use_container_width=True,
                )
            else:
                st.warning("No dataset count data available.")

            st.markdown("---")
            st.markdown("## (3) Task Coverage Over Time")
            st.caption("The proportion of defined tasks within each activity that have at least one model between 2021-Q1 and 2026-Q1")

            if coverage_rows:
                coverage_df = pd.DataFrame(coverage_rows)
                coverage_df["monthly_tasks_with_models"] = pd.to_numeric(coverage_df["monthly_tasks_with_models"], errors="coerce").fillna(0)
                coverage_df["total_tasks"] = pd.to_numeric(coverage_df["total_tasks"], errors="coerce").fillna(0)
                # Preserve per-activity denominator while padding missing months from 2022-01.
                total_tasks_by_activity = coverage_df.groupby("activity_name")["total_tasks"].max().to_dict()
                coverage_df = _pad_from_start(coverage_df, "monthly_tasks_with_models", chart_start, chart_end)
                coverage_df["total_tasks"] = coverage_df["activity_name"].map(total_tasks_by_activity).fillna(0)
                coverage_df = coverage_df.sort_values(["activity_name", "time_point", "time_bucket"])
                coverage_df["tasks_with_models"] = coverage_df.groupby("activity_name")["monthly_tasks_with_models"].cumsum()
                coverage_df["task_coverage_ratio"] = coverage_df["tasks_with_models"] / coverage_df["total_tasks"].replace(0, pd.NA)
                coverage_df["coverage_percent"] = coverage_df["task_coverage_ratio"].fillna(0) * 100

                fig_coverage = px.line(
                    coverage_df,
                    x="time_bucket",
                    y="coverage_percent",
                    color="activity_name",
                    markers=True,
                    title="Task Coverage by Activity (2021-Q1 to 2026-Q1)",
                    labels={
                        "time_bucket": "Quarter",
                        "coverage_percent": "Coverage (%)",
                        "activity_name": "Activity",
                    },
                    template="plotly_white",
                )
                fig_coverage.update_layout(
                    hovermode="x unified",
                    dragmode="zoom",
                    xaxis=dict(type="category", categoryorder="category ascending"),
                    yaxis=dict(range=[0, 100]),
                    height=500,
                )
                st.plotly_chart(fig_coverage, use_container_width=True, config=chart_config)

                # Show data table with coverage ratio and percent
                display_df = coverage_df[["activity_name", "time_bucket", "total_tasks", "tasks_with_models", "coverage_percent"]].copy()
                display_df.columns = ["Activity", "Quarter", "Total Tasks", "Tasks with Models", "Coverage (%)"]
                st.dataframe(display_df, use_container_width=True)
            else:
                st.warning("No task coverage data available.")

        except Exception as exc:
            st.error(f"Error loading metrics: {str(exc)}")
