"""Successful Models analysis pages."""

import json
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from ..data import get_data_with_fallback
    from ..queries import SUCCESSFUL_MODELS_TASK_BENCHMARK_COMPARISON_QUERY
except ImportError:
    from data import get_data_with_fallback
    from queries import SUCCESSFUL_MODELS_TASK_BENCHMARK_COMPARISON_QUERY


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _min_max_normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return [0.0 for _ in values]
    scale = max_value - min_value
    return [(value - min_value) / scale for value in values]


def _prepare_grouped_models_df(rows: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if "ModelCount" in df.columns:
        df["ModelCount"] = pd.to_numeric(df["ModelCount"], errors="coerce").fillna(0).astype(int)

    def _format_models(value: object) -> str:
        if not isinstance(value, list):
            return "[]"
        return json.dumps(value, ensure_ascii=True)

    def _pick_top(models: object, key: str) -> Dict[str, Any]:
        if not isinstance(models, list) or not models:
            return {}
        sorted_models = sorted(
            models,
            key=lambda item: (
                -float(item.get(key, 0) or 0),
                -float(item.get("score", 0) or 0),
                str(item.get("modelName", "")).lower(),
            ),
        )
        return sorted_models[0] if sorted_models else {}

    if "Models" in df.columns:
        df["Models"] = df["Models"].apply(lambda value: value if isinstance(value, list) else [])
        enriched_models: List[List[Dict[str, Any]]] = []
        for models in df["Models"]:
            popularity_values = [float(model.get("popularity", 0) or 0) for model in models]
            normalized_values = _min_max_normalize(popularity_values)
            enriched_group: List[Dict[str, Any]] = []
            for model, normalized_value in zip(models, normalized_values):
                enriched_model = dict(model)
                enriched_model["normalizedPopularity"] = float(normalized_value)
                enriched_group.append(enriched_model)
            enriched_models.append(enriched_group)
        df["Models"] = enriched_models
        df["TopPopularModel"] = df["Models"].apply(lambda models: _pick_top(models, "popularity").get("modelName", ""))
        df["TopPopularModelPopularity"] = df["Models"].apply(
            lambda models: int(_pick_top(models, "popularity").get("popularity", 0) or 0)
        )
        df["TopPopularModelNormalizedPopularity"] = df["Models"].apply(
            lambda models: float(_pick_top(models, "popularity").get("normalizedPopularity", 0.0) or 0.0)
        )
        df["TopQualityModel"] = df["Models"].apply(lambda models: _pick_top(models, "score").get("modelName", ""))
        df["TopQualityModelScore"] = df["Models"].apply(lambda models: float(_pick_top(models, "score").get("score", 0) or 0))
        df["Models"] = df["Models"].map(_format_models)

    for column in [
        "TopPopularModelPopularity",
        "TopPopularModelNormalizedPopularity",
        "TopQualityModelScore",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    sort_cols = [col for col in ["TaskName", "BenchmarkName", "Metric"] if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[True] * len(sort_cols))

    return df.reset_index(drop=True)


def _prepare_flat_models_df(rows: List[dict]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []

    for row in rows:
        task_name = _safe_str(row.get("TaskName"))
        benchmark_name = _safe_str(row.get("BenchmarkName"))
        metric = _safe_str(row.get("Metric"))
        models = row.get("Models", []) if isinstance(row, dict) else []
        if not isinstance(models, list):
            models = []

        ranked_by_popularity = sorted(
            models,
            key=lambda item: (
                -float(item.get("popularity", 0) or 0),
                -float(item.get("score", 0) or 0),
                str(item.get("modelName", "")).lower(),
            ),
        )
        ranked_by_quality = sorted(
            models,
            key=lambda item: (
                -float(item.get("score", 0) or 0),
                -float(item.get("popularity", 0) or 0),
                str(item.get("modelName", "")).lower(),
            ),
        )

        popularity_ranks: Dict[str, int] = {}
        quality_ranks: Dict[str, int] = {}

        for index, model in enumerate(ranked_by_popularity, start=1):
            model_key = _safe_str(model.get("modelId") or model.get("modelName"))
            popularity_ranks[model_key] = index

        for index, model in enumerate(ranked_by_quality, start=1):
            model_key = _safe_str(model.get("modelId") or model.get("modelName"))
            quality_ranks[model_key] = index

        for model in models:
            model_key = _safe_str(model.get("modelId") or model.get("modelName"))
            popularity = int(model.get("popularity", 0) or 0)
            score = float(model.get("score", 0) or 0)
            pop_rank = popularity_ranks.get(model_key, 0)
            quality_rank = quality_ranks.get(model_key, 0)
            records.append(
                {
                    "TaskName": task_name,
                    "BenchmarkName": benchmark_name,
                    "Metric": metric,
                    "ModelName": _safe_str(model.get("modelName")),
                    "ModelId": _safe_str(model.get("modelId")),
                    "Popularity": popularity,
                    "QualityScore": score,
                    "PopularityRank": pop_rank,
                    "QualityRank": quality_rank,
                    "RankGap": quality_rank - pop_rank if pop_rank and quality_rank else 0,
                }
            )

    detail_df = pd.DataFrame(records)
    if detail_df.empty:
        return detail_df

    detail_df["Popularity"] = pd.to_numeric(detail_df["Popularity"], errors="coerce").fillna(0).astype(int)
    detail_df["QualityScore"] = pd.to_numeric(detail_df["QualityScore"], errors="coerce").fillna(0.0)
    detail_df["PopularityRank"] = pd.to_numeric(detail_df["PopularityRank"], errors="coerce").fillna(0).astype(int)
    detail_df["QualityRank"] = pd.to_numeric(detail_df["QualityRank"], errors="coerce").fillna(0).astype(int)
    detail_df["RankGap"] = pd.to_numeric(detail_df["RankGap"], errors="coerce").fillna(0).astype(int)
    detail_df["NormalizedPopularity"] = detail_df.groupby(["TaskName", "BenchmarkName", "Metric"], dropna=False)["Popularity"].transform(
        lambda series: _min_max_normalize([float(value) for value in series.tolist()])
    )

    detail_df = detail_df.sort_values(
        ["TaskName", "BenchmarkName", "Metric", "PopularityRank", "QualityRank", "ModelName"],
        ascending=[True, True, True, True, True, True],
    )
    return detail_df.reset_index(drop=True)


def _prepare_task_quality_popularity_index_df(detail_df: pd.DataFrame) -> pd.DataFrame:
    if detail_df.empty:
        return detail_df

    index_df = (
        detail_df.groupby("TaskName", dropna=False)
        .agg(
            ModelCount=("ModelName", "count"),
            BenchmarkGroupCount=(("BenchmarkName", "nunique")),
            AvgQualityScore=("QualityScore", "mean"),
            MedianQualityScore=("QualityScore", "median"),
            AvgNormalizedPopularity=("NormalizedPopularity", "mean"),
            MedianNormalizedPopularity=("NormalizedPopularity", "median"),
        )
        .reset_index()
    )

    index_df["QualityPopularityIndex"] = index_df.apply(
        lambda row: float(row["AvgQualityScore"]) / float(row["AvgNormalizedPopularity"]) if float(row["AvgNormalizedPopularity"]) > 0 else 0.0,
        axis=1,
    )
    index_df["QualityPopularityBalance"] = index_df["AvgQualityScore"] - index_df["AvgNormalizedPopularity"]

    index_df = index_df.sort_values(
        ["QualityPopularityIndex", "AvgQualityScore", "ModelCount", "TaskName"],
        ascending=[False, False, False, True],
    )
    return index_df.reset_index(drop=True)


def render_analysis_4_placeholder(*_args, **kwargs) -> None:
    """Render successful-models comparison tables."""
    uri, username, password, database, row_limit = _args[:5]

    st.subheader("Successful Models Analysis")
    st.caption("Compares model popularity and benchmark quality only within the same SETask, benchmark, and evaluation metric.")

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    index_key = "successful_models_comparison_rows"
    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load successful models (cache first)", type="primary", key="successful_models_load")
    refresh_clicked = col_refresh.button("Refresh successful models from DB", key="successful_models_refresh")

    if load_clicked or refresh_clicked or index_key not in st.session_state:
        with st.spinner("Loading successful models comparison..."):
            try:
                rows, source, info = get_data_with_fallback(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    query=SUCCESSFUL_MODELS_TASK_BENCHMARK_COMPARISON_QUERY,
                    row_limit=max(int(row_limit), 10000),
                    params={"task_limit": max(int(row_limit), 10000)},
                    prefer_cache=load_clicked,
                )
                st.session_state[index_key] = rows
                if source == "online":
                    st.success(info)
                else:
                    st.warning(info)
            except Exception as exc:
                st.error(f"Could not load successful models comparison: {exc}")
                st.session_state[index_key] = []

    rows = st.session_state.get(index_key, [])
    if not rows:
        st.info("Load the successful-models index to compare popularity and evaluation quality.")
        return

    grouped_df = _prepare_grouped_models_df(rows)
    if grouped_df.empty:
        st.info("No task/benchmark/metric groups with more than one model were returned.")
        return

    detail_df = _prepare_flat_models_df(rows)
    task_index_df = _prepare_task_quality_popularity_index_df(detail_df)

    st.markdown("### Task Quality / Popularity Index")
    st.caption("Aggregated per task from all comparable model rows. The index is average quality divided by average normalized popularity.")
    st.dataframe(
        task_index_df[
            [
                col
                for col in [
                    "TaskName",
                    "ModelCount",
                    "BenchmarkGroupCount",
                    "AvgQualityScore",
                    "AvgNormalizedPopularity",
                    "QualityPopularityIndex",
                    "QualityPopularityBalance",
                ]
                if col in task_index_df.columns
            ]
        ],
        use_container_width=True,
        height=320,
    )

    st.download_button(
        "Download task quality/popularity index (CSV)",
        data=task_index_df.to_csv(index=False),
        file_name="successful_models_task_quality_popularity_index.csv",
        mime="text/csv",
    )

    st.markdown("### Task Benchmark Metric Comparison")
    st.caption("Each row groups models that are evaluated on the same benchmark with the same metric for the same task.")
    st.dataframe(
        grouped_df[
            [
                col
                for col in [
                    "TaskName",
                    "BenchmarkName",
                    "Metric",
                    "ModelCount",
                    "TopPopularModel",
                    "TopPopularModelPopularity",
                    "TopPopularModelNormalizedPopularity",
                    "TopQualityModel",
                    "TopQualityModelScore",
                    "Models",
                ]
                if col in grouped_df.columns
            ]
        ],
        use_container_width=True,
        height=460,
    )

    st.download_button(
        "Download grouped comparison (CSV)",
        data=grouped_df.to_csv(index=False),
        file_name="successful_models_grouped_comparison.csv",
        mime="text/csv",
    )

    st.markdown("### Model-Level Comparison")
    st.caption("Popularity is based on model likes; quality is the benchmark evaluation score within the same task/benchmark/metric group.")
    st.dataframe(detail_df, use_container_width=True, height=520)

    st.download_button(
        "Download model-level comparison (CSV)",
        data=detail_df.to_csv(index=False),
        file_name="successful_models_model_level_comparison.csv",
        mime="text/csv",
    )

    if not detail_df.empty:
        scatter_df = detail_df.copy()
        scatter_df["TaskBenchmarkMetric"] = (
            scatter_df["TaskName"].astype(str)
            + " | "
            + scatter_df["BenchmarkName"].astype(str)
            + " | "
            + scatter_df["Metric"].astype(str)
        )

        st.markdown("### Popularity vs Quality Scatter Plot")
        st.caption("Popularity is normalized to a 0-1 scale within each task, benchmark, and metric group; quality stays as the evaluation score.")
        fig = px.scatter(
            scatter_df,
            x="NormalizedPopularity",
            y="QualityScore",
            color="TaskName",
            hover_data={
                "TaskName": True,
                "BenchmarkName": True,
                "Metric": True,
                "ModelName": True,
                "ModelId": True,
                "Popularity": True,
                "NormalizedPopularity": ":.4f",
                "QualityScore": ":.4f",
                "PopularityRank": True,
                "QualityRank": True,
                "RankGap": True,
                "TaskBenchmarkMetric": False,
            },
            opacity=0.78,
            title="Normalized model popularity vs benchmark quality",
        )
        fig.update_traces(marker=dict(size=10, line=dict(width=0.5, color="rgba(0,0,0,0.35)")))
        fig.update_layout(legend_title_text="SETask", height=700, margin=dict(l=20, r=20, t=60, b=20))
        st.plotly_chart(fig, use_container_width=True)
