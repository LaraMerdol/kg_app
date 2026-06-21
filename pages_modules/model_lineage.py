"""Model Lineage analysis pages."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from neo4j import GraphDatabase

try:
    from ..data import get_data_with_fallback
    from ..queries import (
        MODEL_LINEAGE_ALL_TASKS_QUERY,
        MODEL_LINEAGE_BASE_FAMILY_TAG_CLOUD_QUERY,
        MODEL_LINEAGE_BASE_MODELS_BY_TASK_QUERY,
        MODEL_LINEAGE_BY_ACTIVITY_QUERY,
        MODEL_LINEAGE_FAMILY_EDGES_QUERY,
        MODEL_LINEAGE_FAMILY_NODES_QUERY,
        MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_ACTIVITY_QUERY,
        MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_TASK_QUERY,
    )
    from .query_lineage_table import CSV_PATH, generate_lineage_table, load_saved_lineage_table
    from .rq_adaptation_activity_experiment import (
        build_lineage_length_stats as build_activity_lineage_length_stats,
        get_adaptation_data_by_activity,
        plot_average_lineage_length as plot_activity_average_lineage_length,
        plot_lineage_length_distribution as plot_activity_lineage_length_distribution,
    )
    from .rq_adaptation_task_experiment import (
        build_lineage_length_stats as build_task_lineage_length_stats,
        get_adaptation_data,
        plot_average_lineage_length as plot_task_average_lineage_length,
        plot_lineage_length_distribution as plot_task_lineage_length_distribution,
    )
except ImportError:
    from data import get_data_with_fallback
    from queries import (
        MODEL_LINEAGE_ALL_TASKS_QUERY,
        MODEL_LINEAGE_BASE_FAMILY_TAG_CLOUD_QUERY,
        MODEL_LINEAGE_BASE_MODELS_BY_TASK_QUERY,
        MODEL_LINEAGE_BY_ACTIVITY_QUERY,
        MODEL_LINEAGE_FAMILY_EDGES_QUERY,
        MODEL_LINEAGE_FAMILY_NODES_QUERY,
        MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_ACTIVITY_QUERY,
        MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_TASK_QUERY,
    )
    from pages_modules.query_lineage_table import CSV_PATH, generate_lineage_table, load_saved_lineage_table
    from pages_modules.rq_adaptation_activity_experiment import (
        build_lineage_length_stats as build_activity_lineage_length_stats,
        get_adaptation_data_by_activity,
        plot_average_lineage_length as plot_activity_average_lineage_length,
        plot_lineage_length_distribution as plot_activity_lineage_length_distribution,
    )
    from pages_modules.rq_adaptation_task_experiment import (
        build_lineage_length_stats as build_task_lineage_length_stats,
        get_adaptation_data,
        plot_average_lineage_length as plot_task_average_lineage_length,
        plot_lineage_length_distribution as plot_task_lineage_length_distribution,
    )


def _prepare_lineage_df(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    int_cols = ["total", "finetunes", "adapters", "merges", "quantizations"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    share_cols = ["finetuneShare", "adapterShare", "mergeShare", "quantShare"]
    for col in share_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if id_col in df.columns:
        df[id_col] = df[id_col].fillna("").astype(str)

    ordered_cols = [
        id_col,
        "total",
        "finetunes",
        "adapters",
        "merges",
        "quantizations",
        "finetuneShare",
        "adapterShare",
        "mergeShare",
        "quantShare",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    return df[ordered_cols]


def _prepare_length_distribution_df(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    rename_map = {
        "numSeeds": "totalModels",
        "len0": "len0Models",
        "len1": "len1Models",
        "len2": "len2Models",
        "len3": "len3Models",
        "len4": "len4Models",
        "len5plus": "len5PlusModels",
    }
    existing_renames = {k: v for k, v in rename_map.items() if k in df.columns and v not in df.columns}
    if existing_renames:
        df = df.rename(columns=existing_renames)

    int_cols = [
        "totalModels",
        "len0Models",
        "len1Models",
        "len2Models",
        "len3Models",
        "len4Models",
        "len5PlusModels",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if id_col in df.columns:
        df[id_col] = df[id_col].fillna("").astype(str)

    ordered_cols = [
        id_col,
        "totalModels",
        "len0Models",
        "len1Models",
        "len2Models",
        "len3Models",
        "len4Models",
        "len5PlusModels",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    return df[ordered_cols]


def _prepare_base_models_df(df: pd.DataFrame) -> pd.DataFrame:
    int_cols = ["numSeeds", "numBaseModels", "numPopularBases", "numNotPopularBases"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if "avgLineageLength" in df.columns:
        df["avgLineageLength"] = pd.to_numeric(df["avgLineageLength"], errors="coerce").fillna(0.0)

    if "seTask" in df.columns:
        df["seTask"] = df["seTask"].fillna("").astype(str)

    def _format_complex(value: object) -> str:
        if value is None:
            return "[]"
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=True)
        return str(value)

    for col in ["popularBaseModels", "topNotPopularBaseModels", "allBaseModels"]:
        if col in df.columns:
            df[col] = df[col].map(_format_complex)

    ordered_cols = [
        "seTask",
        "numSeeds",
        "avgLineageLength",
        "numBaseModels",
        "numPopularBases",
        "numNotPopularBases",
        "popularBaseModels",
        "topNotPopularBaseModels",
        "allBaseModels",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    return df[ordered_cols]


def _split_semicolon_values(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []

    if isinstance(value, list):
        values = value
    else:
        values = str(value).split(";")

    return [item.strip() for item in values if str(item).strip()]


def _build_lineage_summary_tables(table_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_df = table_df.copy()
    summary_df["max_lineage_length"] = pd.to_numeric(summary_df["max_lineage_length"], errors="coerce").fillna(0).astype(int)

    task_rows = []
    if "se_task" in summary_df.columns:
        for _, row in summary_df.iterrows():
            tasks = _split_semicolon_values(row.get("se_task"))
            for task in tasks:
                task_rows.append({"se_task": task, "max_lineage_length": row["max_lineage_length"]})

    activity_rows = []
    if "se_activity" in summary_df.columns:
        for _, row in summary_df.iterrows():
            activities = _split_semicolon_values(row.get("se_activity"))
            for activity in activities:
                activity_rows.append({"se_activity": activity, "max_lineage_length": row["max_lineage_length"]})

    task_summary_df = pd.DataFrame(task_rows)
    if not task_summary_df.empty:
        task_summary_df = (
            task_summary_df.groupby("se_task", as_index=False)
            .agg(
                avg_lineage_depth=("max_lineage_length", "mean"),
                model_count=("max_lineage_length", "size"),
            )
            .sort_values(["avg_lineage_depth", "model_count", "se_task"], ascending=[False, False, True])
        )
        task_summary_df["avg_lineage_depth"] = task_summary_df["avg_lineage_depth"].round(2)

    activity_summary_df = pd.DataFrame(activity_rows)
    if not activity_summary_df.empty:
        activity_summary_df = (
            activity_summary_df.groupby("se_activity", as_index=False)
            .agg(
                avg_lineage_depth=("max_lineage_length", "mean"),
                model_count=("max_lineage_length", "size"),
            )
            .sort_values(["avg_lineage_depth", "model_count", "se_activity"], ascending=[False, False, True])
        )
        activity_summary_df["avg_lineage_depth"] = activity_summary_df["avg_lineage_depth"].round(2)

    distribution_df = (
        summary_df.groupby("max_lineage_length", as_index=False)
        .agg(model_count=("se_model_id", "count"))
        .sort_values("max_lineage_length", ascending=True)
    )

    return task_summary_df, activity_summary_df, distribution_df


def _build_adaptation_distribution_table(table_df: pd.DataFrame, group_col: str, group_label: str) -> pd.DataFrame:
    if group_col not in table_df.columns or "adaptation_type" not in table_df.columns:
        return pd.DataFrame()

    rows = []
    for _, row in table_df.iterrows():
        groups = _split_semicolon_values(row.get(group_col))
        adaptation_type = str(row.get("adaptation_type") or "Unknown").strip() or "Unknown"
        for group_value in groups:
            rows.append({group_label: group_value, "adaptation_type": adaptation_type})

    if not rows:
        return pd.DataFrame()

    exploded_df = pd.DataFrame(rows)
    if exploded_df.empty:
        return pd.DataFrame()

    counts = pd.crosstab(exploded_df[group_label], exploded_df["adaptation_type"])
    counts["total"] = counts.sum(axis=1)
    counts = counts.reset_index().sort_values(["total", group_label], ascending=[False, True]).set_index(group_label)

    adaptation_cols = [col for col in counts.columns if col != "total"]
    adaptation_cols = sorted(adaptation_cols, key=lambda col: (-int(counts[col].sum()), str(col)))

    total_values = counts["total"].replace(0, pd.NA)
    display_df = pd.DataFrame(index=counts.index)
    for col in adaptation_cols:
        shares = counts[col].div(total_values).fillna(0.0) * 100
        display_df[col] = counts[col].astype(int).astype(str) + " (" + shares.round(1).astype(str) + "%)"

    display_df["total"] = counts["total"].astype(int).astype(str)
    display_df.index.name = group_label
    return display_df


def _calculate_hhi(group_df: pd.DataFrame, count_col: str = "count", normalized: bool = False) -> float:
    if group_df.empty or count_col not in group_df.columns:
        return 0.0

    total = group_df[count_col].sum()
    if total <= 0:
        return 0.0

    n = len(group_df)  # number of distinct competitors
    market_shares = group_df[count_col] / total
    hhi_raw = float((market_shares ** 2).sum())

    if normalized:
        if n <= 1:
            return 1.0  # monopoly by definition
        hhi_norm = (hhi_raw - 1 / n) / (1 - 1 / n)
        return round(max(0.0, min(1.0, hhi_norm)), 4)

    return round(hhi_raw * 10000, 1)


def _build_top_base_models_consolidated(table_df: pd.DataFrame, group_col: str, group_label: str, top_n: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build consolidated table of top base models per group with derived model counts and HHI per group."""
    if group_col not in table_df.columns or "base_model" not in table_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    rows = []
    for _, row in table_df.iterrows():
        groups = _split_semicolon_values(row.get(group_col))
        base_models = _split_semicolon_values(row.get("base_model"))
        for group_value in groups:
            for base_model in base_models:
                rows.append({group_label: group_value, "base_model": base_model})

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    exploded_df = pd.DataFrame(rows)
    
    # Count occurrences per group and base model
    counts = exploded_df.groupby([group_label, "base_model"]).size().reset_index(name="count")
    
    # Calculate HHI per group and count total unique models
    hhi_per_group = []
    for group_value in counts[group_label].unique():
        group_data = counts[counts[group_label] == group_value]
        hhi = _calculate_hhi(group_data, "count", normalized=True)
        total_models = len(group_data)
        hhi_per_group.append({group_label: group_value, "Total Models": total_models, "HHI": hhi})
    
    hhi_df = pd.DataFrame(hhi_per_group).sort_values(group_label)
    
    # Get top N per group and build result
    result_rows = []
    for group_value in counts[group_label].unique():
        group_data = counts[counts[group_label] == group_value].sort_values("count", ascending=False).head(top_n)
        result_rows.append(group_data)
    
    if result_rows:
        result_df = pd.concat(result_rows, ignore_index=True)
        result_df = result_df.rename(columns={"base_model": "Base Model", "count": "Derived Models"})
        result_df = result_df[[group_label, "Base Model", "Derived Models"]].sort_values([group_label, "Derived Models"], ascending=[True, False])
        return result_df, hhi_df
    return pd.DataFrame(), pd.DataFrame()


def _build_top_immediate_ancestors_consolidated(table_df: pd.DataFrame, group_col: str, group_label: str, top_n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build consolidated table of top immediate ancestors per group with derived model counts and HHI per group."""
    if group_col not in table_df.columns or "immediate_ancestor" not in table_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    rows = []
    for _, row in table_df.iterrows():
        groups = _split_semicolon_values(row.get(group_col))
        immediate_ancestors = _split_semicolon_values(row.get("immediate_ancestor"))
        for group_value in groups:
            for ancestor in immediate_ancestors:
                rows.append({group_label: group_value, "immediate_ancestor": ancestor})

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    exploded_df = pd.DataFrame(rows)
    
    # Count occurrences per group and ancestor
    counts = exploded_df.groupby([group_label, "immediate_ancestor"]).size().reset_index(name="count")
    
    # Calculate HHI per group and count total unique models
    hhi_per_group = []
    for group_value in counts[group_label].unique():
        group_data = counts[counts[group_label] == group_value]
        hhi = _calculate_hhi(group_data, "count", normalized=True)
        total_models = len(group_data)
        hhi_per_group.append({group_label: group_value, "Total Models": total_models, "HHI": hhi})
    
    hhi_df = pd.DataFrame(hhi_per_group).sort_values(group_label)
    
    # Get top N per group and build result
    result_rows = []
    for group_value in counts[group_label].unique():
        group_data = counts[counts[group_label] == group_value].sort_values("count", ascending=False).head(top_n)
        result_rows.append(group_data)
    
    if result_rows:
        result_df = pd.concat(result_rows, ignore_index=True)
        result_df = result_df.rename(columns={"immediate_ancestor": "Immediate Ancestor", "count": "Derived Models"})
        result_df = result_df[[group_label, "Immediate Ancestor", "Derived Models"]].sort_values([group_label, "Derived Models"], ascending=[True, False])
        return result_df, hhi_df
    return pd.DataFrame(), pd.DataFrame()


def _build_ranked_model_table(table_df: pd.DataFrame, source_col: str, value_label: str, top_n: int) -> pd.DataFrame:
    if source_col not in table_df.columns:
        return pd.DataFrame()

    rows = []
    for _, row in table_df.iterrows():
        model_id = str(row.get("se_model_id") or "").strip()
        if not model_id:
            continue
        values = _split_semicolon_values(row.get(source_col))
        for value in values:
            rows.append({value_label: value, "se_model_id": model_id})

    if not rows:
        return pd.DataFrame()

    exploded_df = pd.DataFrame(rows)
    ranked_df = (
        exploded_df.groupby(value_label)["se_model_id"]
        .nunique()
        .reset_index(name="Derived Models")
        .sort_values(["Derived Models", value_label], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )
    ranked_df.insert(0, "Rank", range(1, len(ranked_df) + 1))
    return ranked_df


def _render_all_tasks_lineage_table(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    st.subheader("SEModel Lineage Overview Table")
    st.caption("This page now displays the flat CSV/table generated by query_lineage_table.py.")

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load saved CSV", type="primary", key="lineage_table_load_csv")
    refresh_clicked = col_refresh.button("Refresh from Neo4j", key="lineage_table_refresh_csv")

    table_df = None
    csv_path = CSV_PATH

    if refresh_clicked:
        if not password:
            st.error("Please provide Neo4j password in the sidebar.")
            return

        with st.spinner("Building lineage table and saving CSV..."):
            try:
                table_df, csv_path, xlsx_path = generate_lineage_table(uri, username, password, database)
                st.success(f"Saved {len(table_df)} rows to {csv_path}")
                if xlsx_path is not None:
                    st.caption(f"Excel export updated at {xlsx_path}")
            except Exception as exc:
                st.error(str(exc))
                return
    elif load_clicked:
        try:
            table_df = load_saved_lineage_table(csv_path)
            st.info(f"Loaded saved CSV from {csv_path}")
        except Exception as exc:
            st.warning(str(exc))
            st.info("Use Refresh from Neo4j to regenerate the CSV.")
            return
    else:
        try:
            table_df = load_saved_lineage_table(csv_path)
            st.caption(f"Auto-loaded cached CSV from {csv_path}. Use Refresh to update.")
        except Exception:
            st.info(f"No cached CSV found at {csv_path}. Use Refresh from Neo4j to generate it.")
            return

    if table_df is None or table_df.empty:
        st.info("No lineage table rows available.")
        return

    table_df = table_df.copy()
    table_df["max_lineage_length"] = pd.to_numeric(table_df["max_lineage_length"], errors="coerce").fillna(0).astype(int)
    task_summary_df, activity_summary_df, distribution_df = _build_lineage_summary_tables(table_df)
    task_adaptation_df = _build_adaptation_distribution_table(table_df, "se_task", "se_task")
    activity_adaptation_df = _build_adaptation_distribution_table(table_df, "se_activity", "se_activity")
    ranked_base_models_df = _build_ranked_model_table(table_df, "base_model", "Base Model", top_n=20)
    ranked_immediate_ancestors_df = _build_ranked_model_table(table_df, "immediate_ancestor", "Immediate Ancestor", top_n=20)
    task_base_models, task_base_models_hhi = _build_top_base_models_consolidated(table_df, "se_task", "SE Task", top_n=3)
    activity_base_models, activity_base_models_hhi = _build_top_base_models_consolidated(table_df, "se_activity", "SE Activity", top_n=3)
    task_ancestors, task_ancestors_hhi = _build_top_immediate_ancestors_consolidated(table_df, "se_task", "SE Task", top_n=5)
    activity_ancestors, activity_ancestors_hhi = _build_top_immediate_ancestors_consolidated(table_df, "se_activity", "SE Activity", top_n=5)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Rows", len(table_df))
    metric_cols[1].metric("Unique SE models", table_df["se_model_id"].nunique() if "se_model_id" in table_df.columns else len(table_df))
    metric_cols[2].metric("Max lineage length", int(table_df["max_lineage_length"].max()))
    metric_cols[3].metric("Original models", int((table_df["max_lineage_length"] == 0).sum()))

    st.markdown("### Average Lineage Depth by SETask")
    if task_summary_df.empty:
        st.info("No SE task values were found in the lineage table.")
    else:
        st.dataframe(task_summary_df, use_container_width=True, hide_index=True)

    st.markdown("### Average Lineage Depth by SEActivity")
    if activity_summary_df.empty:
        st.info("No SE activity values were found in the lineage table.")
    else:
        st.dataframe(activity_summary_df, use_container_width=True, hide_index=True)

    st.markdown("### Adaptation Type Distribution by SETask")
    st.caption("Counts are shown as count (row share%) for each task and adaptation type.")
    if task_adaptation_df.empty:
        st.info("No SE task values were found for adaptation type distribution.")
    else:
        st.dataframe(task_adaptation_df, use_container_width=True)

    st.markdown("### Adaptation Type Distribution by SEActivity")
    st.caption("Counts are shown as count (row share%) for each activity and adaptation type.")
    if activity_adaptation_df.empty:
        st.info("No SE activity values were found for adaptation type distribution.")
    else:
        st.dataframe(activity_adaptation_df, use_container_width=True)

    st.markdown("### Ranked Top Base Models")
    st.caption("Overall ranking of base models by number of derived SEModels in the lineage table.")
    if ranked_base_models_df.empty:
        st.info("No base model data found.")
    else:
        st.dataframe(ranked_base_models_df, use_container_width=True, hide_index=True)

    st.markdown("### Ranked Top Immediate Ancestor Models")
    st.caption("Overall ranking of immediate ancestor models by number of direct descendants in the lineage table.")
    if ranked_immediate_ancestors_df.empty:
        st.info("No immediate ancestor data found.")
    else:
        st.dataframe(ranked_immediate_ancestors_df, use_container_width=True, hide_index=True)

    st.markdown("### Top 3 Base Models by SE Task")
    st.caption("Most frequently used base models for each task with number of derived models.")
    if task_base_models.empty:
        st.info("No base model data found for tasks.")
    else:
        st.dataframe(task_base_models, use_container_width=True, hide_index=True)

    st.markdown("### Normalized HHI (Base Models) by SE Task")
    st.caption("Normalized Herfindahl-Hirschman Index (0-1) measuring concentration of base models per task (higher = more concentrated).")
    if task_base_models_hhi.empty:
        st.info("No HHI data available for task base models.")
    else:
        st.dataframe(task_base_models_hhi, use_container_width=True, hide_index=True)

    st.markdown("### Top 5 Immediate Ancestors by SE Task")
    st.caption("Most frequently used immediate parent models for each task with number of direct descendants.")
    if task_ancestors.empty:
        st.info("No immediate ancestor data found for tasks.")
    else:
        st.dataframe(task_ancestors, use_container_width=True, hide_index=True)

    st.markdown("### Normalized HHI (Immediate Ancestors) by SE Task")
    st.caption("Normalized Herfindahl-Hirschman Index (0-1) measuring concentration of immediate ancestors per task (higher = more concentrated).")
    if task_ancestors_hhi.empty:
        st.info("No HHI data available for task immediate ancestors.")
    else:
        st.dataframe(task_ancestors_hhi, use_container_width=True, hide_index=True)

    st.markdown("### Top 3 Base Models by SE Activity")
    st.caption("Most frequently used base models for each activity with number of derived models.")
    if activity_base_models.empty:
        st.info("No base model data found for activities.")
    else:
        st.dataframe(activity_base_models, use_container_width=True, hide_index=True)

    st.markdown("### Normalized HHI (Base Models) by SE Activity")
    st.caption("Normalized Herfindahl-Hirschman Index (0-1) measuring concentration of base models per activity (higher = more concentrated).")
    if activity_base_models_hhi.empty:
        st.info("No HHI data available for activity base models.")
    else:
        st.dataframe(activity_base_models_hhi, use_container_width=True, hide_index=True)

    st.markdown("### Top 5 Immediate Ancestors by SE Activity")
    st.caption("Most frequently used immediate parent models for each activity with number of direct descendants.")
    if activity_ancestors.empty:
        st.info("No immediate ancestor data found for activities.")
    else:
        st.dataframe(activity_ancestors, use_container_width=True, hide_index=True)

    st.markdown("### Normalized HHI (Immediate Ancestors) by SE Activity")
    st.caption("Normalized Herfindahl-Hirschman Index (0-1) measuring concentration of immediate ancestors per activity (higher = more concentrated).")
    if activity_ancestors_hhi.empty:
        st.info("No HHI data available for activity immediate ancestors.")
    else:
        st.dataframe(activity_ancestors_hhi, use_container_width=True, hide_index=True)

    st.markdown("### Lineage Depth Distribution for All SE Models")
    if distribution_df.empty:
        st.info("No lineage depth values available for the distribution chart.")
    else:
        fig_distribution = px.bar(
            distribution_df,
            x="max_lineage_length",
            y="model_count",
            labels={"max_lineage_length": "Lineage Depth", "model_count": "SE Models"},
            title="Distribution of Lineage Depth Across All SE Models",
        )
        fig_distribution.update_layout(height=420, xaxis_title="Lineage Depth", yaxis_title="SE Models")
        st.plotly_chart(fig_distribution, use_container_width=True)

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    csv_text = table_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_text,
        file_name=csv_path.name,
        mime="text/csv",
        key="lineage_table_download_csv",
    )


def _render_lineage_length_by_task(uri: str, username: str, password: str, database: str) -> None:
    st.subheader("Lineage Length Statistics by SETask")
    st.caption("Distribution and average lineage length by task with configurable thresholds.")

    col_a, col_b, col_c = st.columns(3)
    min_models = col_a.number_input("Minimum models per task", min_value=1, max_value=500, value=20, step=1, key="lineage_task_min_models")
    max_depth = col_b.number_input("Maximum lineage depth", min_value=1, max_value=100, value=20, step=1, key="lineage_task_max_depth")
    top_groups = col_c.number_input("Top tasks to display", min_value=1, max_value=100, value=25, step=1, key="lineage_task_top_groups")

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load saved stats", type="primary", key="lineage_task_load_saved")
    refresh_clicked = col_refresh.button("Refresh from Neo4j", key="lineage_task_refresh_db")

    output_dir = Path("outputs") / "lineage_app"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "lineage_length_stats_task.csv"
    dist_path = output_dir / "lineage_length_distribution_task.png"
    avg_path = output_dir / "average_lineage_length_task.png"

    stats_df = None

    if refresh_clicked:
        if not password:
            st.error("Please provide Neo4j password in the sidebar.")
            return

        with st.spinner("Computing lineage statistics by task..."):
            try:
                driver = GraphDatabase.driver(uri, auth=(username, password))
                query_threshold = max(int(min_models) - 1, 0)
                raw_df = get_adaptation_data(driver, query_threshold, int(max_depth))
                driver.close()

                stats_df = build_task_lineage_length_stats(raw_df, "task_id", "task_name", int(min_models))
                stats_df.to_csv(csv_path, index=False)
                st.success(f"Saved {len(stats_df)} task rows to {csv_path}")
            except Exception as exc:
                st.error(str(exc))
                return
    elif load_clicked:
        if not csv_path.exists():
            st.warning(f"No saved task stats at {csv_path}. Use Refresh from Neo4j first.")
            return
        stats_df = pd.read_csv(csv_path)
        st.info(f"Loaded saved task stats from {csv_path}")
    else:
        st.info("Click Load saved stats or Refresh from Neo4j.")
        return

    if stats_df is None or stats_df.empty:
        st.info("No task lineage statistics available for the selected thresholds.")
        return

    shown_df = stats_df.head(int(top_groups)).copy()

    metric_cols = st.columns(4)
    metric_cols[0].metric("Tasks shown", len(shown_df))
    metric_cols[1].metric("Total models", int(shown_df["totalModels"].sum()))
    metric_cols[2].metric("Avg lineage length", f"{shown_df['avgLineageLength'].mean():.2f}")
    metric_cols[3].metric("Max lineage length", int(shown_df["maxLineageLength"].max()))

    plot_task_lineage_length_distribution(
        shown_df,
        "task_name",
        str(dist_path),
        "Lineage Length Distribution by SETask",
        "SE Task",
    )
    plot_task_average_lineage_length(
        shown_df,
        "task_name",
        str(avg_path),
        "Average Lineage Length by SETask",
        "SE Task",
    )

    st.markdown("### Lineage Length Distribution")
    if dist_path.exists():
        st.image(str(dist_path), use_container_width=True)

    st.markdown("### Average Lineage Length")
    if avg_path.exists():
        st.image(str(avg_path), use_container_width=True)

    st.markdown("### Task Lineage Statistics")
    st.dataframe(shown_df, use_container_width=True, hide_index=True)


def _render_lineage_length_by_activity(uri: str, username: str, password: str, database: str) -> None:
    st.subheader("Lineage Length Statistics by SEActivity")
    st.caption("Distribution and average lineage length by activity with configurable thresholds.")

    col_a, col_b, col_c = st.columns(3)
    min_models = col_a.number_input("Minimum models per activity", min_value=1, max_value=500, value=20, step=1, key="lineage_activity_min_models")
    max_depth = col_b.number_input("Maximum lineage depth", min_value=1, max_value=100, value=20, step=1, key="lineage_activity_max_depth")
    top_groups = col_c.number_input("Top activities to display", min_value=1, max_value=100, value=25, step=1, key="lineage_activity_top_groups")

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load saved stats", type="primary", key="lineage_activity_load_saved")
    refresh_clicked = col_refresh.button("Refresh from Neo4j", key="lineage_activity_refresh_db")

    output_dir = Path("outputs") / "lineage_app"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "lineage_length_stats_activity.csv"
    dist_path = output_dir / "lineage_length_distribution_activity.png"
    avg_path = output_dir / "average_lineage_length_activity.png"

    stats_df = None

    if refresh_clicked:
        if not password:
            st.error("Please provide Neo4j password in the sidebar.")
            return

        with st.spinner("Computing lineage statistics by activity..."):
            try:
                driver = GraphDatabase.driver(uri, auth=(username, password))
                raw_df = get_adaptation_data_by_activity(driver, int(max_depth))
                driver.close()

                dedup_df = raw_df.drop_duplicates(subset=["model_id", "activity_name"])
                stats_df = build_activity_lineage_length_stats(dedup_df, "activity_name", "activity_name", int(min_models))
                stats_df.to_csv(csv_path, index=False)
                st.success(f"Saved {len(stats_df)} activity rows to {csv_path}")
            except Exception as exc:
                st.error(str(exc))
                return
    elif load_clicked:
        if not csv_path.exists():
            st.warning(f"No saved activity stats at {csv_path}. Use Refresh from Neo4j first.")
            return
        stats_df = pd.read_csv(csv_path)
        st.info(f"Loaded saved activity stats from {csv_path}")
    else:
        st.info("Click Load saved stats or Refresh from Neo4j.")
        return

    if stats_df is None or stats_df.empty:
        st.info("No activity lineage statistics available for the selected thresholds.")
        return

    shown_df = stats_df.head(int(top_groups)).copy()

    metric_cols = st.columns(4)
    metric_cols[0].metric("Activities shown", len(shown_df))
    metric_cols[1].metric("Total models", int(shown_df["totalModels"].sum()))
    metric_cols[2].metric("Avg lineage length", f"{shown_df['avgLineageLength'].mean():.2f}")
    metric_cols[3].metric("Max lineage length", int(shown_df["maxLineageLength"].max()))

    plot_activity_lineage_length_distribution(
        shown_df,
        "activity_name",
        str(dist_path),
        "Lineage Length Distribution by SEActivity",
        "SE Activity",
    )
    plot_activity_average_lineage_length(
        shown_df,
        "activity_name",
        str(avg_path),
        "Average Lineage Length by SEActivity",
        "SE Activity",
    )

    st.markdown("### Lineage Length Distribution")
    if dist_path.exists():
        st.image(str(dist_path), use_container_width=True)

    st.markdown("### Average Lineage Length")
    if avg_path.exists():
        st.image(str(avg_path), use_container_width=True)

    st.markdown("### Activity Lineage Statistics")
    st.dataframe(shown_df, use_container_width=True, hide_index=True)


def _render_family_summary_page() -> None:
    st.subheader("Lineage Family Summary")
    st.caption("Visualization of base-model family concentration from family_summary.csv.")

    csv_path = Path(__file__).resolve().parent / "family_summary.csv"
    if not csv_path.exists():
        st.error(f"Family summary CSV not found at {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        st.error(f"Could not read family summary CSV: {exc}")
        return

    if df.empty:
        st.info("Family summary CSV is empty.")
        return

    int_cols = ["rank", "n_base_models", "total_descendants", "n_tasks"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    float_cols = ["share_pct", "cumulative_share_pct"]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Families", int(df["family"].nunique()) if "family" in df.columns else len(df))
    metric_cols[1].metric("Total descendants", int(df["total_descendants"].sum()) if "total_descendants" in df.columns else 0)
    metric_cols[2].metric("Top family share", f"{df['share_pct'].max():.2f}%" if "share_pct" in df.columns else "N/A")
    metric_cols[3].metric("Families covering 80%", int((df["cumulative_share_pct"] <= 80.0).sum()) if "cumulative_share_pct" in df.columns else 0)

    top_n_default = min(20, len(df))
    top_n = st.slider("Top families to visualize", min_value=5, max_value=max(5, len(df)), value=max(5, top_n_default), step=1)
    shown_df = df.sort_values("rank", ascending=True).head(int(top_n)).copy() if "rank" in df.columns else df.head(int(top_n)).copy()

    if {"family", "total_descendants"}.issubset(shown_df.columns):
        fig_desc = px.bar(
            shown_df.sort_values("total_descendants", ascending=True),
            x="total_descendants",
            y="family",
            orientation="h",
            color="total_descendants",
            color_continuous_scale="tealgrn",
            title="Top Families by Total Descendants",
        )
        fig_desc.update_layout(height=560, xaxis_title="Descendants", yaxis_title="Family")
        st.plotly_chart(fig_desc, use_container_width=True)

    if {"rank", "cumulative_share_pct"}.issubset(shown_df.columns):
        fig_cum = px.line(
            shown_df.sort_values("rank"),
            x="rank",
            y="cumulative_share_pct",
            markers=True,
            title="Cumulative Share by Family Rank",
        )
        fig_cum.add_hline(y=80.0, line_dash="dash", line_color="#ef4444")
        fig_cum.update_layout(height=360, xaxis_title="Family Rank", yaxis_title="Cumulative Share (%)")
        st.plotly_chart(fig_cum, use_container_width=True)

    st.markdown("### Family Summary Table")
    st.dataframe(shown_df, use_container_width=True, hide_index=True)

    if {"family", "tasks", "base_models", "top_base_model"}.issubset(df.columns):
        selected_family = st.selectbox("Inspect family details", options=df["family"].astype(str).tolist())
        family_row = df[df["family"].astype(str) == selected_family].head(1)
        if not family_row.empty:
            row = family_row.iloc[0]
            st.markdown(f"**Top base model:** {row.get('top_base_model', 'N/A')}")
            st.markdown(f"**Top base model descendants:** {int(row.get('top_base_model_descendants', 0))}")
            with st.expander("Tasks"):
                st.write(str(row.get("tasks", "")))
            with st.expander("Base models"):
                st.write(str(row.get("base_models", "")))
            se_models_raw = str(row.get("SEmodels", "") or "").strip()
            se_models = [item.strip() for item in se_models_raw.split(";") if item.strip()]
            with st.expander("SEModels"):
                if se_models:
                    st.caption(f"{len(se_models)} models in this family")
                    st.markdown("\n".join(f"- {model}" for model in se_models))
                else:
                    st.info("No SEModels available for this family.")


def render_analysis_3_placeholder(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
    nav_page: str,
) -> None:
    """Render Model Lineage analysis with all pages."""
    if nav_page == "All Tasks":
        _render_all_tasks_lineage_table(uri, username, password, database, row_limit)
        return
    
    if nav_page == "Specific Task":
        _render_specific_task_lineage(uri, username, password, database, row_limit)
        return

    if nav_page == "Artifact Overlaps":
        _render_lineage_length_by_task(uri, username, password, database)
        return

    if nav_page == "Task Specificity":
        _render_lineage_length_by_activity(uri, username, password, database)
        return

    if nav_page == "Family Summary":
        _render_family_summary_page()
        return

    st.info("Model Lineage analysis for this tab is coming soon")


def _render_specific_task_lineage(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    st.subheader("Specific Task Model Lineage Family")
    st.caption("Visualize the complete lineage family for a task with model categorization (base, middle, leaf).")

    task_name = st.text_input("SETask name", value="code understanding", key="lineage_task_name")
    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load lineage family (cache first)", type="primary", key="lineage_specific_load")
    refresh_clicked = col_refresh.button("Refresh from DB", key="lineage_specific_refresh")

    if not (load_clicked or refresh_clicked):
        st.info("Enter a task name and click Load.")
        return

    if not task_name.strip():
        st.error("Please enter SETask name.")
        return

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    with st.spinner("Loading task lineage family..."):
        try:
            # Fetch nodes with color-coding
            node_rows, node_source, node_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_FAMILY_NODES_QUERY,
                row_limit=max(int(row_limit), 5000),
                params={"task_name": task_name.strip()},
                prefer_cache=load_clicked,
            )

            if node_source == "online":
                st.success(node_info)
            else:
                st.warning(node_info)

            # Fetch edges
            edge_rows, edge_source, edge_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_FAMILY_EDGES_QUERY,
                row_limit=max(int(row_limit), 5000),
                params={"task_name": task_name.strip()},
                prefer_cache=load_clicked,
            )

            family_rows, family_source, family_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_BASE_FAMILY_TAG_CLOUD_QUERY,
                row_limit=200,
                params={"task_name": task_name.strip()},
                prefer_cache=load_clicked,
            )

            if not node_rows:
                st.warning("No models found for this task.")
                st.write("Debug: node_rows is empty")
                st.write(f"Debug: node_source={node_source}, edge_source={edge_source}")
                st.write(f"Debug: task_name='{task_name.strip()}'")
                return

            # Build summary stats
            st.write(f"Debug: Received {len(node_rows)} node rows")
            st.write(f"Debug: First node row keys: {list(node_rows[0].keys()) if node_rows else 'N/A'}")
            
            node_data = [row.get("node", {}) for row in node_rows if row.get("node")]
            st.write(f"Debug: Extracted {len(node_data)} node_data items")
            if node_rows and not node_data:
                st.write(f"Debug: First raw row: {node_rows[0]}")
            
            models = [n for n in node_data if n.get("label") in {"Model", "SEModel"}]
            root_models = [m for m in models if m.get("modelType") == "Root Model"]
            middle_models = [m for m in models if m.get("modelType") == "Middle Model"]
            seed_models = [m for m in models if m.get("modelType") == "Seed Model"]
            seeds = [m for m in models if m.get("isSeed")]

            st.info(f"Found {len(node_data)} nodes ({len(models)} models), {len(edge_rows)} edges")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Models", len(models))
            col2.metric("Root Models", len(root_models))
            col3.metric("Middle Models", len(middle_models))
            col4.metric("Seed Models (typed)", len(seed_models))
            col5.metric("Seed Models (for task)", len(seeds))

            # Build cytoscape HTML
            if node_data and edge_rows:
                edge_data = [row.get("edge", {}) for row in edge_rows if row.get("edge")]
                cytoscape_html = _build_lineage_cytoscape_html(node_data, edge_data)
                st.markdown("### Lineage Family Graph")
                st.caption("Green=Root (longest depth), Blue=Middle, Red=Seed, Orange=Task")
                st.caption("Debug renderer: components.html (iframe JS enabled)")
                st.markdown(
                    "<div style='display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 8px 0;'>"
                    "<span style='display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;'>"
                    "<span style='width:10px;height:10px;border-radius:999px;background:#22c55e;display:inline-block;'></span>Root Model"
                    "</span>"
                    "<span style='display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;'>"
                    "<span style='width:10px;height:10px;border-radius:999px;background:#3b82f6;display:inline-block;'></span>Middle Model"
                    "</span>"
                    "<span style='display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;'>"
                    "<span style='width:10px;height:10px;border-radius:999px;background:#ef4444;display:inline-block;'></span>Seed Model"
                    "</span>"
                    "<span style='display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;'>"
                    "<span style='width:10px;height:10px;border-radius:999px;background:#f97316;display:inline-block;'></span>Task"
                    "</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                components.html(cytoscape_html, height=820, scrolling=False)

                st.markdown("### Fallback Graph (Graphviz)")
                st.caption("If interactive graph is blocked by browser/runtime policy, this static fallback still shows lineage connectivity.")
                st.graphviz_chart(_build_lineage_graphviz_dot(node_data, edge_data), use_container_width=True)
            else:
                st.info("No lineage relationships found.")

            st.markdown("### Base Model Family Tag Cloud")
            st.caption("Most-used root/base model families for this task (bigger tag = used by more seed models).")
            _render_base_family_tag_cloud(family_rows)

        except Exception as exc:
            st.error(str(exc))


def _build_lineage_cytoscape_html(nodes, edges, height_px=760):
    """Build Cytoscape visualization with color-coded nodes."""
    node_items = []
    node_ids = set()

    for node in nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in node_ids:
            continue
        node_ids.add(node_id)
        label = str(node.get("label", "Node"))
        title = str(node.get("title", node_id))
        color = str(node.get("color", "#3b82f6"))
        model_type = str(node.get("modelType", "Unknown"))

        node_items.append({
            "data": {
                "id": node_id,
                "label": label,
                "title": title,
                "display": title,
                "modelType": model_type,
                "color": color,
            }
        })

    edge_items = []
    edge_seen = set()

    for idx, rel in enumerate(edges):
        source = str(rel.get("source", "")).strip()
        target = str(rel.get("target", "")).strip()
        rel_type = str(rel.get("type", "REL")).strip()

        if not source or not target:
            continue
        if source not in node_ids or target not in node_ids:
            continue

        edge_id = f"{source}|{rel_type}|{target}|{idx}"
        if edge_id in edge_seen:
            continue
        edge_seen.add(edge_id)

        edge_items.append({
            "data": {
                "id": edge_id,
                "source": source,
                "target": target,
                "label": rel_type,
            }
        })

    elements_json = json.dumps(node_items + edge_items)

    return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        html, body, #wrapper {{ margin: 0; padding: 0; }}
        body {{ 
            height: {height_px}px;
            background: #f8fafc;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        }}
        #wrapper {{ height: 100%; width: 100%; display: grid; grid-template-rows: auto 1fr; gap: 8px; }}
        #toolbar {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }}
        #toolbar button {{ border: 1px solid #cbd5e1; background: #f1f5f9; color: #0f172a; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        #meta {{ font-size: 12px; color: #334155; margin-right: 8px; }}
        #legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-left: 4px; }}
        .legend-item {{ display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: #0f172a; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 999px; padding: 2px 8px; }}
        .legend-dot {{ width: 10px; height: 10px; border-radius: 999px; border: 1px solid rgba(0, 0, 0, 0.25); }}
        #cy {{ height: 100%; width: 100%; background: radial-gradient(circle at 20% 20%, #ffffff 0%, #f1f5f9 100%); border: 1px solid #e2e8f0; border-radius: 8px; }}
        #error {{ color: #dc2626; font-weight: bold; padding: 10px; background: #fecaca; border-radius: 4px; }}
    </style>
    <script src=\"https://unpkg.com/cytoscape@3.30.1/dist/cytoscape.min.js\"></script>
</head>
<body>
    <div id=\"wrapper\">
        <div id=\"toolbar\">
            <button id=\"fitBtn\">Fit</button>
            <button id=\"layoutBtn\">Re-layout</button>
            <span id=\"meta\"></span>
            <div id="legend"></div>
        </div>
        <div id=\"cy\"></div>
        <div id=\"error\" style=\"display:none;\"></div>
    </div>
    <script>
        console.log('Cytoscape HTML loaded');
        const elements = {elements_json};
        console.log('Elements:', elements);
        
        if (!elements || elements.length === 0) {{
            document.getElementById('error').textContent = 'No data to display';
            document.getElementById('error').style.display = 'block';
            console.error('Elements array is empty');
        }} else {{
            const nodeCount = elements.filter(e => e.data && e.data.id && !e.data.source).length;
            const edgeCount = elements.filter(e => e.data && e.data.source).length;
            document.getElementById('meta').textContent = `Nodes: ${{nodeCount}} | Edges: ${{edgeCount}}`;
            console.log('Node count:', nodeCount, 'Edge count:', edgeCount);

            const legendItems = [
                {{ label: 'Task', color: '#f97316' }},
                {{ label: 'Root Model', color: '#22c55e' }},
                {{ label: 'Middle Model', color: '#3b82f6' }},
                {{ label: 'Seed Model', color: '#ef4444' }},
                {{ label: 'Seed (Root) Model', color: '#7e22ce' }},
            ];
            const legend = document.getElementById('legend');
            legendItems.forEach(function(entry) {{
                const label = entry.label;
                const color = entry.color;
                const chip = document.createElement('span');
                chip.className = 'legend-item';
                const dot = document.createElement('span');
                dot.className = 'legend-dot';
                dot.style.backgroundColor = color;
                const text = document.createElement('span');
                text.textContent = label;
                chip.appendChild(dot);
                chip.appendChild(text);
                legend.appendChild(chip);
            }});

            if (typeof cytoscape === 'undefined') {{
                document.getElementById('error').textContent = 'Cytoscape library failed to load';
                document.getElementById('error').style.display = 'block';
                console.error('Cytoscape not loaded');
            }} else {{
                try {{
                    const cy = cytoscape({{
                        container: document.getElementById('cy'),
                        elements,
                        style: [
                            {{
                                selector: 'node',
                                style: {{
                                    'label': 'data(display)',
                                    'font-size': 11,
                                    'background-color': 'data(color)',
                                    'border-width': 2,
                                    'border-color': '#1f2937',
                                    'text-halign': 'center',
                                    'text-valign': 'center',
                                    'text-wrap': 'wrap',
                                    'text-max-width': 120,
                                }}
                            }},
                            {{
                                selector: 'edge',
                                style: {{
                                    'target-arrow-shape': 'triangle',
                                    'target-arrow-color': '#6b7280',
                                    'line-color': '#9ca3af',
                                    'arrow-scale': 1.5,
                                    'curve-style': 'bezier',
                                    'label': 'data(label)',
                                    'font-size': 9,
                                    'text-background-color': '#ffffff',
                                    'text-background-padding': '2px',
                                    'text-background-opacity': 0.8,
                                }}
                            }},
                        ],
                        layout: {{
                            name: 'cose',
                            fit: true,
                            padding: 20,
                            idealEdgeLength: 140,
                            nodeRepulsion: 18000,
                            animate: true,
                            animationDuration: 500,
                        }},
                    }});

                    document.getElementById('fitBtn').onclick = () => cy.fit(cy.elements(), 20);
                    document.getElementById('layoutBtn').onclick = () => cy.layout({{
                        name: 'cose',
                        fit: true,
                        padding: 20,
                        idealEdgeLength: 140,
                        nodeRepulsion: 18000,
                        animate: true,
                        animationDuration: 500,
                    }}).run();

                    cy.fit(cy.elements(), 20);
                    console.log('Cytoscape initialized successfully');
                }} catch (err) {{
                    document.getElementById('error').textContent = 'Error initializing graph: ' + err.message;
                    document.getElementById('error').style.display = 'block';
                    console.error('Cytoscape error:', err);
                }}
            }}
        }}
    </script>
</body>
</html>
"""


def _build_lineage_graphviz_dot(nodes, edges):
    """Build a Graphviz DOT fallback for lineage visualization."""
    lines = [
        "digraph lineage {",
        "  rankdir=LR;",
        '  graph [bgcolor="white"];',
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", color="#1f2937"];',
        '  edge [color="#64748b", fontname="Helvetica", fontsize=9];',
    ]

    seen = set()
    for node in nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        title = str(node.get("title", node_id)).replace('"', "'")
        color = str(node.get("color", "#3b82f6"))
        safe_id = node_id.replace('"', "'")
        lines.append(f'  "{safe_id}" [label="{title}", fillcolor="{color}"];')

    for rel in edges:
        src = str(rel.get("source", "")).strip().replace('"', "'")
        dst = str(rel.get("target", "")).strip().replace('"', "'")
        typ = str(rel.get("type", "REL")).replace('"', "'")
        if not src or not dst:
            continue
        if src not in seen or dst not in seen:
            continue
        lines.append(f'  "{src}" -> "{dst}" [label="{typ}"];')

    lines.append("}")
    return "\n".join(lines)


def _render_base_family_tag_cloud(family_rows):
    """Render a simple tag cloud from family usage rows."""
    if not family_rows:
        st.info("No base-family usage rows returned for this task.")
        return

    df = pd.DataFrame(family_rows)
    if df.empty or "family" not in df.columns or "usage" not in df.columns:
        st.info("No base-family usage rows returned for this task.")
        return

    df["family"] = df["family"].fillna("unknown").astype(str)
    df["usage"] = pd.to_numeric(df["usage"], errors="coerce").fillna(0).astype(int)
    df = df[df["usage"] > 0].sort_values(["usage", "family"], ascending=[False, True])
    if df.empty:
        st.info("No positive base-family usage values for this task.")
        return

    max_usage = int(df["usage"].max())
    min_font = 14
    max_font = 44
    palette = ["#1d4ed8", "#0f766e", "#be123c", "#7c2d12", "#4338ca", "#0f766e", "#7e22ce", "#1f2937"]

    chips = []
    for idx, row in enumerate(df.head(30).itertuples(index=False)):
        family = str(row.family)
        usage = int(row.usage)
        ratio = usage / max_usage if max_usage > 0 else 0
        font_px = int(min_font + (max_font - min_font) * ratio)
        color = palette[idx % len(palette)]
        chips.append(
            f"<span style='font-size:{font_px}px; font-weight:700; color:{color}; line-height:1.1; margin:6px 10px; display:inline-block;'>{family} ({usage})</span>"
        )

    html = (
        "<div style='padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; "
        "background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);'>"
        + "".join(chips)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    with st.expander("See family counts table"):
        st.dataframe(df.head(40), use_container_width=True, hide_index=True)
