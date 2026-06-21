from collections import Counter
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import itertools
from collections import defaultdict
from typing import Any, Dict, Set, Tuple, List

import numpy as np
try:
    import plotly.express as px
except ModuleNotFoundError:
    px = None


def _ensure_plotly() -> bool:
    if px is None:
        st.error("This page requires the optional 'plotly' package. Install it with 'pip install plotly' and restart Streamlit.")
        return False
    return True


try:
    from ..config import CACHE_FILE
    from ..data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation, utc_now_iso
    from ..queries import (
        ALL_TASKS_ECOSYSTEM_QUERY,
        ALL_TASKS_MOST_USED_AND_LIKED_DATASETS_QUERY,
        ALL_TASKS_ECOSYSTEM_RATIO_QUERY,
        ALL_TASKS_DATASET_MODULE_DISTRIBUTION_QUERY,
        ALL_TASKS_SEMODEL_DATASET_PROPERTIES_QUERY,
        TASK_ACTIVITY_BY_TASK_QUERY,
        TASK_ACTIVITY_TOP_OVERLAPS_QUERY,
        TASK_ARTIFACT_COUNTS_QUERY,
        TASK_ARTIFACT_SPECIFICITY_QUERY,
        TASK_ARTIFACT_TASK_SHARE_QUERY,
        TASK_ARTIFACT_TYPE_COUNTS_QUERY,
        TASK_ARTIFACT_PAIR_DETAILS_QUERY,
        TASK_ARTIFACT_PAIR_OVERLAP_QUERY,
        TASK_ARTIFACT_TOP_OVERLAPS_QUERY,
        TASK_ECOSYSTEM_QUERY,
        TASK_PAIR_SUBGRAPH_QUERY,
        TASK_SUBGRAPH_QUERY,
    )
    from ..visualization import build_cytoscape_html, build_graphviz_dot
except ImportError:
    from config import CACHE_FILE
    from data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation, utc_now_iso
    from queries import (
        ALL_TASKS_ECOSYSTEM_QUERY,
        ALL_TASKS_MOST_USED_AND_LIKED_DATASETS_QUERY,
        ALL_TASKS_ECOSYSTEM_RATIO_QUERY,
        ALL_TASKS_DATASET_MODULE_DISTRIBUTION_QUERY,
        ALL_TASKS_SEMODEL_DATASET_PROPERTIES_QUERY,
        TASK_ACTIVITY_BY_TASK_QUERY,
        TASK_ACTIVITY_TOP_OVERLAPS_QUERY,
        TASK_ARTIFACT_COUNTS_QUERY,
        TASK_ARTIFACT_SPECIFICITY_QUERY,
        TASK_ARTIFACT_TASK_SHARE_QUERY,
        TASK_ARTIFACT_TYPE_COUNTS_QUERY,
        TASK_ARTIFACT_PAIR_DETAILS_QUERY,
        TASK_ARTIFACT_PAIR_OVERLAP_QUERY,
        TASK_ARTIFACT_TOP_OVERLAPS_QUERY,
        TASK_ECOSYSTEM_QUERY,
        TASK_PAIR_SUBGRAPH_QUERY,
        TASK_SUBGRAPH_QUERY,
    )
    from visualization import build_cytoscape_html, build_graphviz_dot


def render_task_ecosystem_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    if not _ensure_plotly():
        return

    st.subheader("Task Ecosystem Analysis")
    st.caption(
        "For each SE task in our knowledge graph, we build a task-centered subgraph with models, datasets, papers, benchmarks, collections, and spaces."
    )

    task_name = st.text_input("SETask name", value="code understanding")
    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load (cache first)", type="primary")
    refresh_clicked = col_refresh.button("Refresh from DB")

    if not (load_clicked or refresh_clicked):
        st.info("Enter a task and click Load.")
        return

    if not task_name.strip():
        st.error("Please enter SETask name.")
        return

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    with st.spinner("Loading task ecosystem..."):
        try:
            rows, source, info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ECOSYSTEM_QUERY,
                row_limit=int(row_limit),
                params={"task_name": task_name.strip()},
                prefer_cache=load_clicked,
            )

            if source == "online":
                st.success(info)
            else:
                st.warning(info)

            st.markdown("### Ecosystem Summary Table")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

            if rows and isinstance(rows[0], dict):
                top_row = rows[0]
                most_used_df = pd.DataFrame(
                    [
                        {
                            "artifactType": "Dataset",
                            "mostUsed": str(top_row.get("mostUsedDataset", "") or ""),
                            "linkedModelCount": int(top_row.get("mostUsedDatasetCount", 0) or 0),
                        },
                        {
                            "artifactType": "Benchmark",
                            "mostUsed": str(top_row.get("mostUsedBenchmark", "") or ""),
                            "linkedModelCount": int(top_row.get("mostUsedBenchmarkCount", 0) or 0),
                        },
                        {
                            "artifactType": "Collection",
                            "mostUsed": str(top_row.get("mostUsedCollection", "") or ""),
                            "linkedModelCount": int(top_row.get("mostUsedCollectionCount", 0) or 0),
                        },
                        {
                            "artifactType": "Space",
                            "mostUsed": str(top_row.get("mostUsedSpace", "") or ""),
                            "linkedModelCount": int(top_row.get("mostUsedSpaceCount", 0) or 0),
                        },
                    ]
                )

                st.markdown("### Most Used Artifacts")
                st.caption("Top entities ranked by number of linked models within the selected SETask.")
                st.dataframe(most_used_df, use_container_width=True)

            subgraph_rows, subgraph_source, subgraph_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_SUBGRAPH_QUERY,
                row_limit=int(row_limit),
                params={"task_name": task_name.strip(), "subgraph_model_limit": int(row_limit)},
                prefer_cache=load_clicked,
            )

            if subgraph_source == "cache":
                st.warning(f"Subgraph snapshot: {subgraph_info}")
            else:
                st.success("Subgraph snapshot refreshed from DB.")

            if subgraph_rows:
                first_row = subgraph_rows[0]
                nodes = first_row.get("nodes", []) if isinstance(first_row, dict) else []
                relationships = first_row.get("relationships", []) if isinstance(first_row, dict) else []
                if nodes:
                    st.markdown("### Subgraph Snapshot")
                    show_mode = st.radio("Visualization", ["Cytoscape.js", "Graphviz", "Both"], horizontal=True)
                    dot = build_graphviz_dot(nodes, relationships)
                    if show_mode in ("Graphviz", "Both"):
                        st.graphviz_chart(dot, use_container_width=True)
                    if show_mode in ("Cytoscape.js", "Both"):
                        components.html(build_cytoscape_html(nodes, relationships, height_px=760), height=800, scrolling=False)

                    st.caption(f"Nodes: {len(nodes)} | Relationships: {len(relationships)}")
                    payload = {
                        "task_name": task_name.strip(),
                        "source": subgraph_source,
                        "nodes": nodes,
                        "relationships": relationships,
                        "generated_at": utc_now_iso(),
                    }
                    st.download_button(
                        "Download subgraph snapshot (JSON)",
                        data=json.dumps(payload, indent=2),
                        file_name=f"subgraph_{task_name.strip().replace(' ', '_')}.json",
                        mime="application/json",
                    )
                else:
                    st.info("No subgraph nodes found for this task.")
            else:
                st.info("No subgraph snapshot returned.")
        except Exception as exc:
            st.error(str(exc))


def render_all_tasks_ecosystem_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    if not _ensure_plotly():
        return

    st.subheader("All Tasks Ecosystem Overview")
    st.caption("Aggregated ecosystem count statistics for all SETasks.")

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load all tasks (cache first)", type="primary")
    refresh_clicked = col_refresh.button("Refresh all tasks from DB")

    if not (load_clicked or refresh_clicked):
        st.info("Click Load to fetch all tasks ecosystem data.")
        return

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    # This page is intended to show all tasks, not the smaller interactive row-limit default.
    all_tasks_limit = max(int(row_limit), 10000)

    with st.spinner("Loading all tasks ecosystem data..."):
        try:
            rows, source, info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=ALL_TASKS_ECOSYSTEM_QUERY,
                row_limit=all_tasks_limit,
                prefer_cache=load_clicked,
            )

            if source == "online":
                st.success(info)
            else:
                st.warning(info)

            df = pd.DataFrame(rows)
            if not df.empty:
                numeric_cols = [
                    "numModels",
                    "numModelsWithDataset",
                    "numModelsWithCollection",
                    "numModelsWithSpace",
                    "numModelsWithBenchmark",
                    "numDatasets",
                    "numPapers",
                    "numBenchmarks",
                    "numCollections",
                    "numSpaces",
                ]
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

                for col in ["seTask"]:
                    if col in df.columns:
                        df[col] = df[col].fillna("").astype(str)

                # Per-task completeness ratios using model count as denominator.
                def _safe_completeness_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
                    raw = numerator.astype(float).div(denominator.astype(float).replace(0, np.nan))
                    return raw.fillna(0.0)

                def _col_series(col_name: str) -> pd.Series:
                    return df[col_name] if col_name in df.columns else pd.Series(0, index=df.index)

                if "numModels" in df.columns:
                    paper_source = df["numModelsWithPaper"] if "numModelsWithPaper" in df.columns else _col_series("numPapers")
                    df["datasetCompletenessRatio"] = _safe_completeness_ratio(_col_series("numModelsWithDataset"), df["numModels"])
                    df["collectionCompletenessRatio"] = _safe_completeness_ratio(_col_series("numModelsWithCollection"), df["numModels"])
                    df["spaceCompletenessRatio"] = _safe_completeness_ratio(_col_series("numModelsWithSpace"), df["numModels"])
                    df["benchmarkCompletenessRatio"] = _safe_completeness_ratio(_col_series("numModelsWithBenchmark"), df["numModels"])
                    df["paperCompletenessRatio"] = _safe_completeness_ratio(paper_source, df["numModels"])
                else:
                    df["datasetCompletenessRatio"] = 0.0
                    df["collectionCompletenessRatio"] = 0.0
                    df["spaceCompletenessRatio"] = 0.0
                    df["benchmarkCompletenessRatio"] = 0.0
                    df["paperCompletenessRatio"] = 0.0

                view_cols = [
                    "seTask",
                    "numModels",
                    "numModelsWithDataset",
                    "numModelsWithCollection",
                    "numModelsWithSpace",
                    "numModelsWithBenchmark",
                    "numDatasets",
                    "numPapers",
                    "numBenchmarks",
                    "numCollections",
                    "numSpaces",
                ]
                view_cols = [c for c in view_cols if c in df.columns]

                st.caption(f"Returned {len(df)} tasks (limit used: {all_tasks_limit}).")
                st.markdown("### All Tasks Ecosystem Summary")
                st.dataframe(df[view_cols], use_container_width=True)

                try:
                    task_dataset_rows, task_dataset_source, task_dataset_info = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=ALL_TASKS_MOST_USED_AND_LIKED_DATASETS_QUERY,
                        row_limit=all_tasks_limit,
                        prefer_cache=load_clicked,
                    )

                    if task_dataset_source == "online":
                        st.success(task_dataset_info)
                    else:
                        st.warning(task_dataset_info)

                    task_dataset_df = pd.DataFrame(task_dataset_rows)
                    if not task_dataset_df.empty:
                        if "mostUsedDatasetCount" in task_dataset_df.columns:
                            task_dataset_df["mostUsedDatasetCount"] = (
                                pd.to_numeric(task_dataset_df["mostUsedDatasetCount"], errors="coerce")
                                .fillna(0)
                                .astype(int)
                            )
                        # Top-3 list columns: ensure numeric lists are cast where appropriate
                        if "top3MostUsedCounts" in task_dataset_df.columns:
                            def _cast_int_list(x):
                                if not x:
                                    return []
                                try:
                                    return [int(i) for i in x]
                                except Exception:
                                    return x

                            task_dataset_df["top3MostUsedCounts"] = task_dataset_df["top3MostUsedCounts"].apply(_cast_int_list)
                        if "top3MostLikedLikes" in task_dataset_df.columns:
                            def _cast_int_list2(x):
                                if not x:
                                    return []
                                try:
                                    return [int(i) for i in x]
                                except Exception:
                                    return x

                            task_dataset_df["top3MostLikedLikes"] = task_dataset_df["top3MostLikedLikes"].apply(_cast_int_list2)
                        if "mostLikedDatasetLikes" in task_dataset_df.columns:
                            task_dataset_df["mostLikedDatasetLikes"] = (
                                pd.to_numeric(task_dataset_df["mostLikedDatasetLikes"], errors="coerce")
                                .fillna(0)
                                .astype(int)
                            )
                        if "mostUsedDatasetLikes" in task_dataset_df.columns:
                            task_dataset_df["mostUsedDatasetLikes"] = (
                                pd.to_numeric(task_dataset_df["mostUsedDatasetLikes"], errors="coerce")
                                .fillna(0)
                                .astype(int)
                            )
                        if "mostLikedDatasetUsedCount" in task_dataset_df.columns:
                            task_dataset_df["mostLikedDatasetUsedCount"] = (
                                pd.to_numeric(task_dataset_df["mostLikedDatasetUsedCount"], errors="coerce")
                                .fillna(0)
                                .astype(int)
                            )

                        dataset_display_cols = [
                            "seTask",
                            "mostUsedDataset",
                            "mostUsedDatasetCount",
                            "top3MostUsedDatasets",
                            "top3MostUsedCounts",
                            "mostUsedDatasetLikes",
                            "mostLikedDataset",
                            "mostLikedDatasetLikes",
                            "top3MostLikedDatasets",
                            "top3MostLikedLikes",
                            "mostLikedDatasetUsedCount",
                        ]
                        dataset_display_cols = [c for c in dataset_display_cols if c in task_dataset_df.columns]

                        st.markdown("### Most Used And Most Liked Dataset Per SETask")
                        st.caption(
                            "Includes cross-metrics: likes for the most-used dataset and linked-model count for the most-liked dataset."
                        )
                        st.dataframe(task_dataset_df[dataset_display_cols], use_container_width=True, height=420)
                    else:
                        st.info("No rows were returned for most-used/most-liked dataset summary.")
                except Exception as exc:
                    st.warning(f"Could not build most-used/most-liked dataset table: {exc}")

                st.markdown("### SEModel Dataset Modalities and Formats")
                st.caption("Unique datasets linked to SEModels, with raw n.modalities and n.formats values plus task coverage.")

                try:
                    dataset_props_rows, dataset_props_source, dataset_props_info = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=ALL_TASKS_SEMODEL_DATASET_PROPERTIES_QUERY,
                        row_limit=all_tasks_limit,
                        params={"dataset_limit": min(max(int(row_limit), 1), 2000)},
                        prefer_cache=load_clicked,
                    )

                    if dataset_props_source == "online":
                        st.success(dataset_props_info)
                    else:
                        st.warning(dataset_props_info)

                    dataset_props_df = pd.DataFrame(dataset_props_rows)
                    if not dataset_props_df.empty:
                        if "linkedModels" in dataset_props_df.columns:
                            dataset_props_df["linkedModels"] = pd.to_numeric(dataset_props_df["linkedModels"], errors="coerce").fillna(0).astype(int)
                        if "taskCount" in dataset_props_df.columns:
                            dataset_props_df["taskCount"] = pd.to_numeric(dataset_props_df["taskCount"], errors="coerce").fillna(0).astype(int)
                        if "modalities" in dataset_props_df.columns:
                            dataset_props_df["modalities"] = dataset_props_df["modalities"].apply(
                                lambda values: ", ".join([str(v).strip() for v in values if str(v).strip()]) if isinstance(values, list) else str(values)
                            )
                        if "formats" in dataset_props_df.columns:
                            dataset_props_df["formats"] = dataset_props_df["formats"].apply(
                                lambda values: ", ".join([str(v).strip() for v in values if str(v).strip()]) if isinstance(values, list) else str(values)
                            )
                        if "tasks" in dataset_props_df.columns:
                            dataset_props_df["tasks"] = dataset_props_df["tasks"].apply(
                                lambda values: ", ".join([str(v).strip() for v in values if str(v).strip()]) if isinstance(values, list) else str(values)
                            )

                        dataset_props_display_cols = [
                            "datasetId",
                            "datasetName",
                            "modalities",
                            "formats",
                            "linkedModels",
                            "taskCount",
                            "tasks",
                        ]
                        dataset_props_display_cols = [c for c in dataset_props_display_cols if c in dataset_props_df.columns]

                        st.dataframe(dataset_props_df[dataset_props_display_cols], use_container_width=True, height=360)
                    else:
                        st.info("No dataset modality/module rows were returned.")
                except Exception as exc:
                    st.warning(f"Could not build dataset modality/module table: {exc}")

                st.markdown("### Per Task Most Used Format and Modality")
                st.caption("For each SETask, this shows the most frequent dataset format and modality among datasets linked to its SEModels.")

                try:
                    module_dist_rows, module_dist_source, module_dist_info = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=ALL_TASKS_DATASET_MODULE_DISTRIBUTION_QUERY,
                        row_limit=all_tasks_limit,
                        prefer_cache=load_clicked,
                    )

                    if module_dist_source == "online":
                        st.success(module_dist_info)
                    else:
                        st.warning(module_dist_info)

                    module_dist_df = pd.DataFrame(module_dist_rows)
                    if not module_dist_df.empty:
                        if "seActivities" in module_dist_df.columns:
                            module_dist_df["seActivities"] = module_dist_df["seActivities"].apply(
                                lambda values: ", ".join([str(v).strip() for v in values if str(v).strip()]) if isinstance(values, list) else str(values)
                            )
                        for column in [
                            "numDatasets",
                            "mostUsedFormatCount",
                            "mostUsedModalityCount",
                        ]:
                            if column in module_dist_df.columns:
                                module_dist_df[column] = pd.to_numeric(module_dist_df[column], errors="coerce").fillna(0).astype(int)

                        module_dist_display_cols = [
                            "seTask",
                            "seActivities",
                            "numDatasets",
                            "mostUsedFormat",
                            "mostUsedFormatCount",
                            "mostUsedModality",
                            "mostUsedModalityCount",
                        ]
                        module_dist_display_cols = [c for c in module_dist_display_cols if c in module_dist_df.columns]

                        st.dataframe(module_dist_df[module_dist_display_cols], use_container_width=True, height=360)
                    else:
                        st.info("No per-task format/modality rows were returned.")
                except Exception as exc:
                    st.warning(f"Could not build per-task format/modality table: {exc}")

                st.markdown("### Artifact Distribution per SETask")
                st.caption(
                    "Stacked view of Models, Datasets, Papers, Benchmarks, Collections, and Spaces "
                    "for top tasks by total artifact volume."
                )
                top_task_n = st.slider(
                    "Top tasks to display",
                    min_value=20,
                    max_value=30,
                    value=25,
                    step=1,
                    key="artifact_distribution_top_n",
                )

                artifact_count_cols = [
                    "numModels",
                    "numDatasets",
                    "numPapers",
                    "numBenchmarks",
                    "numCollections",
                    "numSpaces",
                ]
                available_artifact_cols = [c for c in artifact_count_cols if c in df.columns]

                if "seTask" in df.columns and available_artifact_cols:
                    artifact_plot_df = df[["seTask"] + available_artifact_cols].copy()
                    artifact_plot_df["totalArtifacts"] = artifact_plot_df[available_artifact_cols].sum(axis=1)
                    if "numModels" in artifact_plot_df.columns:
                        artifact_plot_df = artifact_plot_df.sort_values(
                            ["numModels", "totalArtifacts", "seTask"],
                            ascending=[False, False, True],
                        )
                    else:
                        artifact_plot_df = artifact_plot_df.sort_values(
                            ["totalArtifacts", "seTask"],
                            ascending=[False, True],
                        )
                    artifact_plot_df = artifact_plot_df.head(int(top_task_n))

                    rename_cols = {
                        "numModels": "Models",
                        "numDatasets": "Datasets",
                        "numPapers": "Papers",
                        "numBenchmarks": "Benchmarks",
                        "numCollections": "Collections",
                        "numSpaces": "Spaces",
                    }
                    artifact_plot_df = artifact_plot_df.rename(columns=rename_cols)
                    artifact_types = [rename_cols[c] for c in available_artifact_cols]

                    stacked_df = artifact_plot_df.melt(
                        id_vars=["seTask"],
                        value_vars=artifact_types,
                        var_name="Artifact Type",
                        value_name="Count",
                    )

                    artifact_color_map = {
                        "Models": "#0284c7",
                        "Datasets": "#16a34a",
                        "Papers": "#eda53a",
                        "Benchmarks": "#dc2626",
                        "Collections": "#6d28d9",
                        "Spaces": "#0f766e",
                    }

                    stacked_fig = px.bar(
                        stacked_df,
                        x="seTask",
                        y="Count",
                        color="Artifact Type",
                        category_orders={"Artifact Type": artifact_types},
                        color_discrete_map=artifact_color_map,
                        title=f"Artifact distribution across top {len(artifact_plot_df)} SETasks",
                    )
                    stacked_fig.update_layout(
                        barmode="stack",
                        xaxis_title="SETask",
                        yaxis_title="Artifact count (log scale)",
                        yaxis_type="log",
                        xaxis_tickangle=-35,
                        height=560,
                        legend_title_text="Artifact Type",
                        legend=dict(
                            orientation="v",
                            x=10,
                            y=100,
                            xanchor="right",
                            yanchor="bottom",
                            bgcolor="rgba(255,255,255,0.78)",
                        ),
                    )
                    st.plotly_chart(stacked_fig, use_container_width=True)
                else:
                    st.info("Artifact distribution chart is unavailable because required columns are missing.")

                ratio_cols = [
                    "datasetCompletenessRatio",
                    "collectionCompletenessRatio",
                    "spaceCompletenessRatio",
                    "benchmarkCompletenessRatio",
                    "paperCompletenessRatio",
                ]

                def _sum_numeric_col(col_name: str) -> float:
                    if col_name == "numModelsWithPaper":
                        if col_name in df.columns:
                            series = df[col_name]
                        elif "numPapers" in df.columns:
                            series = df["numPapers"]
                        else:
                            series = pd.Series(0, index=df.index)
                    else:
                        series = _col_series(col_name)
                    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())

                total_models = _sum_numeric_col("numModels")
                dataset_linked_models = _sum_numeric_col("numModelsWithDataset")
                collection_linked_models = _sum_numeric_col("numModelsWithCollection")
                space_linked_models = _sum_numeric_col("numModelsWithSpace")
                benchmark_linked_models = _sum_numeric_col("numModelsWithBenchmark")
                paper_linked_models = _sum_numeric_col("numModelsWithPaper")

                def _global_ratio(linked: float, total: float) -> float:
                    if total <= 0:
                        return 0.0
                    return linked / total

                agg_ratio_df = pd.DataFrame(
                    {
                        "Dimension": ["Dataset", "Collection", "Space", "Benchmark", "Paper"],
                        "Linked models": [
                            int(dataset_linked_models),
                            int(collection_linked_models),
                            int(space_linked_models),
                            int(benchmark_linked_models),
                            int(paper_linked_models),
                        ],
                        "Global ratio": [
                            _global_ratio(dataset_linked_models, total_models),
                            _global_ratio(collection_linked_models, total_models),
                            _global_ratio(space_linked_models, total_models),
                            _global_ratio(benchmark_linked_models, total_models),
                            _global_ratio(paper_linked_models, total_models),
                        ],
                    }
                )

                st.markdown("### Completeness Metrics (Per SETask)")
                st.caption(f"Total SEModels in scope: {int(total_models)}")

                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("Dataset completeness", f"{agg_ratio_df.loc[0, 'Global ratio']:.2f}")
                mc2.metric("Collection completeness", f"{agg_ratio_df.loc[1, 'Global ratio']:.2f}")
                mc3.metric("Space completeness", f"{agg_ratio_df.loc[2, 'Global ratio']:.2f}")
                mc4.metric("Benchmark completeness", f"{agg_ratio_df.loc[3, 'Global ratio']:.2f}")
                mc5.metric("Paper completeness", f"{agg_ratio_df.loc[4, 'Global ratio']:.2f}")

                ratio_fig = px.bar(
                    agg_ratio_df,
                    x="Dimension",
                    y="Global ratio",
                    text_auto=".2f",
                    color="Dimension",
                    title="Global SEModel completeness ratio by dimension",
                    range_y=[0, 1],
                )
                ratio_fig.update_layout(showlegend=False, height=340)
                st.plotly_chart(ratio_fig, use_container_width=True)

                # st.markdown("### Completeness Metrics (Per SEActivity)")
                # st.caption("EMI is loaded from a static snapshot: outputs/emi_run_latest/emi_seactivity_raw.csv")
                # st.markdown(
                #     """
                #     <div style="padding: 0.75rem 1rem; border-radius: 0.5rem; border: 1px solid #e5e7eb; background: #f8fafc;">
                #       <strong>Ecosystem Maturity Index (EMI)</strong><br/>
                #       For an SE activity <em>a</em> in year <em>y</em>, we compute a weighted score from seven components.
                #     </div>
                #     """,
                #     unsafe_allow_html=True,
                # )
                # st.latex(
                #     r"EMI(a,y)=0.30\cdot\hat{\beta}(a,y)+0.30\cdot\hat{\mu}(a,y)+0.20\cdot\gamma(a,y)+0.10\cdot\delta(a,y)+0.10\cdot\pi(a,y)"
                # )
                # st.markdown(
                #     """
                #     **Component meanings**
                #     - $\hat{\beta}(a,y)$: benchmark completeness ratio
                #     - $\hat{\mu}(a,y)$: log-normalized average models per task (fixed global scale)
                #     - $\gamma(a,y)$: task coverage, $1 - \mathrm{tasksWithoutModelsRatio}$
                #     - $\delta(a,y)$: dataset completeness ratio
                #     - $\pi(a,y)$: paper completeness ratio

                #     """
                # )

                try:
                    activity_rows, _, _ = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=TASK_ACTIVITY_BY_TASK_QUERY,
                        row_limit=max(all_tasks_limit, 10000),
                        prefer_cache=load_clicked,
                    )
                except Exception as exc:
                    st.warning(f"Could not load task-activity mapping for SEActivity completeness: {exc}")
                    activity_rows = []

                task_activity_map: Dict[str, str] = {}
                for row in activity_rows:
                    task_name = str(row.get("task", "")).strip()
                    if not task_name:
                        continue
                    activities = [str(a).strip() for a in (row.get("activities") or []) if str(a).strip()]
                    task_activity_map[task_name] = activities[0] if activities else "NoActivity"

                task_model_count_map: Dict[str, int] = {}
                try:
                    type_count_rows_for_activity, _, _ = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=TASK_ARTIFACT_TYPE_COUNTS_QUERY,
                        row_limit=max(all_tasks_limit, 10000),
                        prefer_cache=load_clicked,
                    )
                    task_model_count_map = {
                        str(row.get("task", "")).strip(): int(row.get("modelCount", 0) or 0)
                        for row in type_count_rows_for_activity
                        if str(row.get("task", "")).strip()
                    }
                except Exception as exc:
                    st.warning(f"Could not load task model counts for SEActivity zero-model metrics: {exc}")

                activity_ratio_df = pd.DataFrame({"seTask": list(task_activity_map.keys())})
                if activity_ratio_df.empty and "seTask" in df.columns:
                    activity_ratio_df = pd.DataFrame({"seTask": df["seTask"].astype(str).tolist()})

                activity_ratio_df["seActivity"] = activity_ratio_df["seTask"].map(
                    lambda task: task_activity_map.get(str(task), "NoActivity")
                )

                def _task_mapped_numeric(col_name: str) -> pd.Series:
                    if "seTask" not in df.columns or col_name not in df.columns:
                        return pd.Series(0, index=activity_ratio_df.index)
                    mapped = activity_ratio_df["seTask"].map(df.set_index("seTask")[col_name])
                    return pd.to_numeric(mapped, errors="coerce").fillna(0)

                fallback_num_models = _task_mapped_numeric("numModels")
                model_count_from_type_query = pd.to_numeric(
                    activity_ratio_df["seTask"].map(lambda task: task_model_count_map.get(str(task), np.nan)),
                    errors="coerce",
                )
                activity_ratio_df["numModels"] = model_count_from_type_query.fillna(fallback_num_models).fillna(0)
                activity_ratio_df["numModelsWithDataset"] = _task_mapped_numeric("numModelsWithDataset")
                activity_ratio_df["numModelsWithCollection"] = _task_mapped_numeric("numModelsWithCollection")
                activity_ratio_df["numModelsWithSpace"] = _task_mapped_numeric("numModelsWithSpace")
                activity_ratio_df["numModelsWithBenchmark"] = _task_mapped_numeric("numModelsWithBenchmark")
                if "numModelsWithPaper" in df.columns:
                    activity_ratio_df["__linkedPaperModels"] = _task_mapped_numeric("numModelsWithPaper")
                else:
                    activity_ratio_df["__linkedPaperModels"] = _task_mapped_numeric("numPapers")

                activity_agg_df = (
                    activity_ratio_df.groupby("seActivity", as_index=False)
                    .agg(
                        taskCount=("seTask", "count"),
                        totalModels=("numModels", "sum"),
                        tasksWithoutModels=("numModels", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) <= 0).sum())),
                        linkedDatasetModels=("numModelsWithDataset", "sum"),
                        linkedCollectionModels=("numModelsWithCollection", "sum"),
                        linkedSpaceModels=("numModelsWithSpace", "sum"),
                        linkedBenchmarkModels=("numModelsWithBenchmark", "sum"),
                        linkedPaperModels=("__linkedPaperModels", "sum"),
                    )
                )

                activity_agg_df["datasetCompletenessRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["linkedDatasetModels"]), float(r["totalModels"])),
                    axis=1,
                )
                activity_agg_df["collectionCompletenessRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["linkedCollectionModels"]), float(r["totalModels"])),
                    axis=1,
                )
                activity_agg_df["spaceCompletenessRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["linkedSpaceModels"]), float(r["totalModels"])),
                    axis=1,
                )
                activity_agg_df["benchmarkCompletenessRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["linkedBenchmarkModels"]), float(r["totalModels"])),
                    axis=1,
                )
                activity_agg_df["paperCompletenessRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["linkedPaperModels"]), float(r["totalModels"])),
                    axis=1,
                )
                activity_agg_df["tasksWithoutModelsRatio"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["tasksWithoutModels"]), float(r["taskCount"])),
                    axis=1,
                )
                activity_agg_df["avgModelsPerTask"] = activity_agg_df.apply(
                    lambda r: _global_ratio(float(r["totalModels"]), float(r["taskCount"])),
                    axis=1,
                )

                emi_csv_path = Path(__file__).resolve().parents[1] / "outputs" / "emi_run_latest" / "emi_seactivity_raw.csv"
                emi_history_df = pd.DataFrame()
                latest_emi_year = None
                if emi_csv_path.exists():
                    try:
                        emi_history_df = pd.read_csv(emi_csv_path)
                        if not emi_history_df.empty and {"seActivity", "year", "EMI"}.issubset(emi_history_df.columns):
                            emi_history_df["seActivity"] = emi_history_df["seActivity"].fillna("NoActivity").astype(str)
                            emi_history_df["year"] = pd.to_numeric(emi_history_df["year"], errors="coerce")
                            emi_history_df["EMI"] = pd.to_numeric(emi_history_df["EMI"], errors="coerce")
                            emi_history_df = emi_history_df.dropna(subset=["year", "EMI"]).copy()
                            if not emi_history_df.empty:
                                emi_history_df["year"] = emi_history_df["year"].astype(int)
                                latest_emi_year = int(emi_history_df["year"].max())
                                latest_emi_map = (
                                    emi_history_df[emi_history_df["year"] == latest_emi_year]
                                    .groupby("seActivity", as_index=False)["EMI"]
                                    .mean()
                                    .set_index("seActivity")["EMI"]
                                )
                                activity_agg_df["EMI"] = activity_agg_df["seActivity"].map(latest_emi_map)
                            else:
                                activity_agg_df["EMI"] = np.nan
                        else:
                            activity_agg_df["EMI"] = np.nan
                    except Exception as exc:
                        st.warning(f"Could not load EMI snapshot CSV: {exc}")
                        activity_agg_df["EMI"] = np.nan
                else:
                    st.warning(f"EMI snapshot file not found: {emi_csv_path}")
                    activity_agg_df["EMI"] = np.nan

                activity_agg_df = activity_agg_df.sort_values(
                    ["EMI", "totalModels", "seActivity"],
                    ascending=[False, False, True],
                    na_position="last",
                )

                st.dataframe(
                    activity_agg_df[
                        [
                            "seActivity",
                            "taskCount",
                            "totalModels",
                            "tasksWithoutModels",
                            "tasksWithoutModelsRatio",
                            "avgModelsPerTask",
                            # "linkedDatasetModels",
                            # "linkedCollectionModels",
                            # "linkedSpaceModels",
                            # "linkedBenchmarkModels",
                            "datasetCompletenessRatio",
                            "collectionCompletenessRatio",
                            "spaceCompletenessRatio",
                            "benchmarkCompletenessRatio",
                            "paperCompletenessRatio",
                            "EMI",
                        ]
                    ].head(5),
                    use_container_width=True,
                    height=360,
                )

                st.markdown("### Model Linkage Rates by SEActivity")
                st.caption(
                    "Stacked bar charts per SEActivity showing model linkage rates to datasets, collections, spaces, benchmarks, papers, and none."
                )

                donut_task_n = st.slider(
                    "SEActivities to show",
                    min_value=6,
                    max_value=24,
                    value=12,
                    step=3,
                    key="seactivity_model_linkage_donut_count",
                )

                required_linkage_cols = [
                    "seActivity",
                    "totalModels",
                    "datasetCompletenessRatio",
                    "collectionCompletenessRatio",
                    "spaceCompletenessRatio",
                    "benchmarkCompletenessRatio",
                    "paperCompletenessRatio",
                ]
                has_linkage_inputs = all(c in activity_agg_df.columns for c in required_linkage_cols)

                if has_linkage_inputs:
                    linkage_task_df = activity_agg_df[required_linkage_cols].copy()
                    linkage_task_df["totalModels"] = pd.to_numeric(linkage_task_df["totalModels"], errors="coerce").fillna(0)
                    linkage_task_df = linkage_task_df[linkage_task_df["totalModels"] > 0].copy()
                    linkage_task_df = linkage_task_df.head(int(donut_task_n))

                    linkage_color_map = {
                        "Datasets": "#16a34a",
                        "Collections": "#6d28d9",
                        "Spaces": "#0f766e",
                        "Benchmarks": "#dc2626",
                        "Papers": "#ea580c",
                        "None": "#94a3b8",
                    }

                    linkage_plot_rows = []
                    for _, task_row in linkage_task_df.iterrows():
                        category_values = {
                            "Datasets": float(task_row.get("datasetCompletenessRatio", 0.0)),
                            "Collections": float(task_row.get("collectionCompletenessRatio", 0.0)),
                            "Spaces": float(task_row.get("spaceCompletenessRatio", 0.0)),
                            "Benchmarks": float(task_row.get("benchmarkCompletenessRatio", 0.0)),
                            "Papers": float(task_row.get("paperCompletenessRatio", 0.0)),
                        }

                        linkage_plot_rows.append(
                            {
                                "seActivity": task_row.get("seActivity", ""),
                                "totalModels": float(task_row.get("totalModels", 0.0)),
                                **category_values,
                            }
                        )

                    linkage_plot_df = pd.DataFrame(linkage_plot_rows)
                    linkage_categories = ["Datasets", "Collections", "Spaces", "Benchmarks", "Papers"]
                    chart_cols_per_row = 2
                    for row_start in range(0, len(linkage_plot_df), chart_cols_per_row):
                        row_slice = linkage_plot_df.iloc[row_start : row_start + chart_cols_per_row]
                        chart_cols = st.columns(chart_cols_per_row)
                        for i, (_, task_row) in enumerate(row_slice.iterrows()):
                            with chart_cols[i]:
                                activity_name = str(task_row.get("seActivity", "NoActivity"))
                                activity_bar_df = pd.DataFrame(
                                    {
                                        "Linkage": linkage_categories,
                                        "Rate": [
                                            100.0 * float(task_row.get("Datasets", 0.0)),
                                            100.0 * float(task_row.get("Collections", 0.0)),
                                            100.0 * float(task_row.get("Spaces", 0.0)),
                                            100.0 * float(task_row.get("Benchmarks", 0.0)),
                                            100.0 * float(task_row.get("Papers", 0.0)),
                                        ],
                                    }
                                )
                                activity_bar_df = activity_bar_df[activity_bar_df["Rate"] > 0].copy()

                                activity_fig = px.bar(
                                    activity_bar_df,
                                    x="Linkage",
                                    y="Rate",
                                    color="Linkage",
                                    category_orders={"Linkage": linkage_categories},
                                    color_discrete_map=linkage_color_map,
                                    title=activity_name,
                                    text_auto=".2f",
                                )
                                activity_fig.update_traces(
                                    textposition="outside",
                                    textfont=dict(size=16, color="#111827"),
                                    cliponaxis=False,
                                )
                                activity_fig.update_layout(
                                    height=340,
                                    margin=dict(l=10, r=10, t=40, b=10),
                                    xaxis_title="Artifact category",
                                    yaxis_title="Percentage",
                                    font=dict(size=15),
                                    title_font=dict(size=18),
                                    xaxis=dict(tickfont=dict(size=16), title_font=dict(size=15)),
                                    yaxis=dict(tickfont=dict(size=16), title_font=dict(size=15)),
                                    showlegend=False,
                                )
                                activity_fig.update_yaxes(range=[0, 100], ticksuffix="%")
                                st.plotly_chart(activity_fig, use_container_width=True)
                else:
                    st.info("SEActivity linkage bar chart is unavailable because required columns are missing.")

                per_task_ratio_df = df[["seTask", "numModels"] + ratio_cols].copy()
                per_task_ratio_df["overallCompletenessRatio"] = per_task_ratio_df[ratio_cols].mean(axis=1)
                per_task_ratio_df = per_task_ratio_df.sort_values(
                    ["overallCompletenessRatio", "numModels", "seTask"],
                    ascending=[False, False, True],
                )

                st.markdown("### Per-task model completeness ratios")
                st.dataframe(
                    per_task_ratio_df,
                    use_container_width=True,
                    height=460,
                )

                # Additional table: each task's share of ecosystem totals, computed by a query.
                try:
                    coverage_rows, coverage_source, coverage_info = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=ALL_TASKS_ECOSYSTEM_RATIO_QUERY,
                        row_limit=all_tasks_limit,
                        prefer_cache=load_clicked,
                    )

                    if coverage_source == "online":
                        st.success(coverage_info)
                    else:
                        st.warning(coverage_info)

                    coverage_df = pd.DataFrame(coverage_rows)
                    if not coverage_df.empty:
                        pct_cols = [
                            "modelSharePct",
                            "datasetSharePct",
                            "paperSharePct",
                            "benchmarkSharePct",
                            "collectionSharePct",
                            "spaceSharePct",
                        ]
                        for col in pct_cols:
                            if col in coverage_df.columns:
                                coverage_df[col] = pd.to_numeric(coverage_df[col], errors="coerce").fillna(0.0).mul(100.0).round(1)

                        display_cols = [
                            "seTask",
                            "numModels", "totalModels", "modelSharePct",
                            "numDatasets", "totalDatasets", "datasetSharePct",
                            "numPapers", "totalPapers", "paperSharePct",
                            "numBenchmarks", "totalBenchmarks", "benchmarkSharePct",
                            "numCollections", "totalCollections", "collectionSharePct",
                            "numSpaces", "totalSpaces", "spaceSharePct",
                        ]
                        display_cols = [c for c in display_cols if c in coverage_df.columns]

                        rename_cols = {
                            "numModels": "Task models",
                            "totalModels": "All models",
                            "modelSharePct": "Models share %",
                            "numDatasets": "Task datasets",
                            "totalDatasets": "All datasets",
                            "datasetSharePct": "Datasets share %",
                            "numPapers": "Task papers",
                            "totalPapers": "All papers",
                            "paperSharePct": "Papers share %",
                            "numBenchmarks": "Task benchmarks",
                            "totalBenchmarks": "All benchmarks",
                            "benchmarkSharePct": "Benchmarks share %",
                            "numCollections": "Task collections",
                            "totalCollections": "All collections",
                            "collectionSharePct": "Collections share %",
                            "numSpaces": "Task spaces",
                            "totalSpaces": "All spaces",
                            "spaceSharePct": "Spaces share %",
                        }

                        st.markdown("### Per-task share of ecosystem totals")
                        st.caption("Each share is computed as task count ÷ ecosystem total for that artifact type (percent, rounded to 0.1%).")
                        st.dataframe(coverage_df[display_cols].rename(columns=rename_cols), use_container_width=True, height=460)
                    else:
                        st.info("No ratio rows were returned for the ecosystem totals table.")
                except Exception as exc:
                    st.warning(f"Could not build per-task share table: {exc}")
            else:
                st.info("No tasks found.")
        except Exception as exc:
            st.error(str(exc))


# def render_all_tasks_ecosystem_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
#     # Reuse the current ecosystem renderer to keep navigation imports stable.
#     render_task_ecosystem_page(uri, username, password, database, row_limit)

def build_task_artifact_sets(rows: List[dict]) -> Dict[str, Set[str]]:
    task_to_artifacts: Dict[str, Set[str]] = defaultdict(set)

    for row in rows:
        task = row.get("task")
        artifact_type = row.get("artifact_type")
        artifact_id = row.get("artifact_id")

        if not task or not artifact_type or artifact_id is None:
            continue

        artifact_key = f"{artifact_type}:{artifact_id}"
        task_to_artifacts[str(task)].add(artifact_key)

    return dict(task_to_artifacts)


def compute_pairwise_overlaps(
    task_to_artifacts: Dict[str, Set[str]]
) -> pd.DataFrame:
    records = []
    tasks = sorted(task_to_artifacts.keys())

    for task1, task2 in itertools.combinations(tasks, 2):
        a1 = task_to_artifacts[task1]
        a2 = task_to_artifacts[task2]

        intersection = a1 & a2
        union = a1 | a2

        inter_size = len(intersection)
        size1 = len(a1)
        size2 = len(a2)

        jaccard = inter_size / len(union) if union else 0.0
        overlap_coeff = inter_size / min(size1, size2) if min(size1, size2) > 0 else 0.0

        records.append(
            {
                "task1": task1,
                "task2": task2,
                "sharedArtifactCount": inter_size,
                "task1ArtifactCount": size1,
                "task2ArtifactCount": size2,
                "jaccardArtifacts": jaccard,
                "overlapCoeffArtifacts": overlap_coeff,
                "sampleSharedArtifacts": sorted(intersection)[:20],
            }
        )

    return pd.DataFrame(records)


def build_similarity_matrix(
    overlap_df: pd.DataFrame,
    tasks: List[str],
    metric_col: str = "jaccardArtifacts",
) -> pd.DataFrame:
    matrix = pd.DataFrame(0.0, index=tasks, columns=tasks)

    for task in tasks:
        matrix.loc[task, task] = 1.0

    for _, row in overlap_df.iterrows():
        t1 = row["task1"]
        t2 = row["task2"]
        value = float(row[metric_col])
        matrix.loc[t1, t2] = value
        matrix.loc[t2, t1] = value

    return matrix


def compute_task_summary(task_to_artifacts: Dict[str, Set[str]]) -> pd.DataFrame:
    records = []
    for task, artifacts in task_to_artifacts.items():
        type_counter = defaultdict(int)
        for artifact in artifacts:
            artifact_type = artifact.split(":", 1)[0]
            type_counter[artifact_type] += 1

        record = {
            "task": task,
            "artifactCount": len(artifacts),
        }
        record.update(type_counter)
        records.append(record)

    df = pd.DataFrame(records).fillna(0)
    if not df.empty:
        df = df.sort_values(["artifactCount", "task"], ascending=[False, True])
    return df


def extract_pair_details(
    task_to_artifacts: Dict[str, Set[str]],
    task1: str,
    task2: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    a1 = task_to_artifacts.get(task1, set())
    a2 = task_to_artifacts.get(task2, set())

    shared = sorted(a1 & a2)
    only1 = sorted(a1 - a2)
    only2 = sorted(a2 - a1)

    shared_df = pd.DataFrame({"shared_artifact": shared})
    only1_df = pd.DataFrame({f"only_in_{task1}": only1})
    only2_df = pd.DataFrame({f"only_in_{task2}": only2})

    return shared_df, only1_df, only2_df


def build_overlap_graph_html(
    selected_task1: str,
    selected_task2: str,
    detail_rows: List[Dict[str, Any]],
) -> str:
    nodes: List[Dict[str, Any]] = [
        {"data": {"id": selected_task1, "label": "SETask", "title": selected_task1, "display": f"Task: {selected_task1}"}},
        {"data": {"id": selected_task2, "label": "SETask", "title": selected_task2, "display": f"Task: {selected_task2}"}},
    ]
    edges: List[Dict[str, Any]] = [
        {"data": {"id": f"{selected_task1}__{selected_task2}", "source": selected_task1, "target": selected_task2, "label": "overlaps"}}
    ]

    seen_artifacts: Set[str] = set()
    seen_groups: Set[str] = {selected_task1, selected_task2}

    for row in detail_rows:
        artifact_key = str(row.get("artifactKey", "")).strip()
        artifact_type = str(row.get("artifactType", "Artifact")).strip() or "Artifact"
        groups = [str(g).strip() for g in (row.get("groups") or []) if str(g).strip()]

        if not artifact_key:
            continue

        if artifact_key not in seen_artifacts:
            nodes.append(
                {
                    "data": {
                        "id": artifact_key,
                        "label": artifact_type,
                        "title": artifact_key,
                        "display": artifact_key,
                    }
                }
            )
            seen_artifacts.add(artifact_key)

        if row.get("inTask1"):
            edges.append({"data": {"id": f"{selected_task1}__{artifact_key}", "source": selected_task1, "target": artifact_key, "label": "has"}})
        if row.get("inTask2"):
            edges.append({"data": {"id": f"{selected_task2}__{artifact_key}", "source": selected_task2, "target": artifact_key, "label": "has"}})

        for group in groups:
            if group not in seen_groups:
                nodes.append(
                    {
                        "data": {
                            "id": group,
                            "label": "TaskGroup",
                            "title": group,
                            "display": group,
                        }
                    }
                )
                seen_groups.add(group)

            edge_id = f"{group}__{artifact_key}"
            if not any(edge["data"]["id"] == edge_id for edge in edges):
                edges.append({"data": {"id": edge_id, "source": group, "target": artifact_key, "label": "group"}})

    return build_cytoscape_html(nodes, edges, height_px=760)


def build_task_overlap_dependency_graph_html(
        overlap_df: pd.DataFrame,
        task_activity_map: Dict[str, List[str]],
    min_jaccard: float = 0.05,
    top_k_per_task: int = 4,
        height_px: int = 760,
) -> str:
        graph_df = overlap_df.copy()
        if graph_df.empty:
                return ""

        graph_df["jaccardArtifacts"] = pd.to_numeric(graph_df.get("jaccardArtifacts", 0), errors="coerce").fillna(0.0)
        graph_df["sharedArtifactCount"] = pd.to_numeric(graph_df.get("sharedArtifactCount", 0), errors="coerce").fillna(0).astype(int)
        graph_df = graph_df[graph_df["jaccardArtifacts"] >= float(min_jaccard)].copy()
        if graph_df.empty:
                return ""

        # Keep only strongest neighbors per task to avoid center blobs in dense graphs.
        sort_cols = ["jaccardArtifacts", "sharedArtifactCount"]
        graph_df = graph_df.sort_values(sort_cols, ascending=[False, False]).copy()
        keep_idx: Set[int] = set()
        for endpoint in ["task1", "task2"]:
            keep_idx.update(
                graph_df.groupby(endpoint, group_keys=False)
                .head(int(max(1, top_k_per_task)))
                .index
                .tolist()
            )
        graph_df = graph_df.loc[sorted(keep_idx)].copy()
        if graph_df.empty:
            return ""

        tasks = sorted({str(t).strip() for t in list(graph_df["task1"]) + list(graph_df["task2"]) if str(t).strip()})
        activities = sorted(
                {
                        (task_activity_map.get(t, ["NoActivity"])[0] if task_activity_map.get(t) else "NoActivity")
                        for t in tasks
                },
                key=lambda x: str(x).lower(),
        )
        palette = px.colors.qualitative.Alphabet + px.colors.qualitative.Set3 + px.colors.qualitative.Dark24
        activity_color_map = {a: palette[i % len(palette)] for i, a in enumerate(activities)}

        node_items: List[Dict[str, Any]] = []
        for task in tasks:
                activity = task_activity_map.get(task, ["NoActivity"])[0] if task_activity_map.get(task) else "NoActivity"
                node_items.append(
                        {
                                "data": {
                                        "id": task,
                                        "label": task,
                                        "activity": activity,
                                        "color": activity_color_map.get(activity, "#64748b"),
                                }
                        }
                )

        edge_items: List[Dict[str, Any]] = []
        for idx, row in graph_df.iterrows():
                t1 = str(row.get("task1", "")).strip()
                t2 = str(row.get("task2", "")).strip()
                if not t1 or not t2 or t1 == t2:
                        continue
                jaccard = float(row.get("jaccardArtifacts", 0.0))
                shared = int(row.get("sharedArtifactCount", 0))
                edge_items.append(
                        {
                                "data": {
                                        "id": f"{t1}__{t2}__{idx}",
                                        "source": t1,
                                        "target": t2,
                                        "weight": jaccard,
                                        "shared": shared,
                                        "label": f"J={jaccard:.3f} | shared={shared}" if jaccard >= 0.20 else "",
                                }
                        }
                )

        elements_json = json.dumps(node_items + edge_items)

        return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        html, body {{ margin: 0; padding: 0; background: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        #wrapper {{ height: {height_px}px; width: 100%; display: grid; grid-template-rows: auto 1fr; gap: 8px; }}
        #toolbar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }}
        #toolbar button {{ border: 1px solid #cbd5e1; background: #f1f5f9; color: #0f172a; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        #meta {{ font-size: 12px; color: #334155; }}
        #cy {{ height: 100%; width: 100%; background: radial-gradient(circle at 20% 20%, #ffffff 0%, #f1f5f9 100%); border: 1px solid #e2e8f0; border-radius: 8px; }}
    </style>
    <script src=\"https://unpkg.com/cytoscape@3.30.1/dist/cytoscape.min.js\"></script>
</head>
<body>
    <div id=\"wrapper\">
        <div id=\"toolbar\">
            <button id=\"fitBtn\">Fit</button>
            <button id=\"layoutBtn\">Re-layout</button>
            <span id=\"meta\"></span>
        </div>
        <div id=\"cy\"></div>
    </div>
    <script>
        const elements = {elements_json};
        const nodeCount = elements.filter(e => e.data && e.data.id && !e.data.source).length;
        const edgeCount = elements.filter(e => e.data && e.data.source).length;
        document.getElementById('meta').textContent = `Tasks: ${{nodeCount}} | Overlap edges: ${{edgeCount}}`;

        const cy = cytoscape({{
            container: document.getElementById('cy'),
            elements,
            style: [
                {{
                    selector: 'node',
                    style: {{
                        'label': 'data(label)',
                        'font-size': 10,
                        'background-color': 'data(color)',
                        'border-width': 1,
                        'border-color': '#334155',
                        'width': 30,
                        'height': 30,
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'text-wrap': 'wrap',
                        'text-max-width': 120,
                        'color': '#0f172a'
                    }}
                }},
                {{
                    selector: 'edge',
                    style: {{
                        'curve-style': 'bezier',
                        'line-color': '#475569',
                        'opacity': 0.68,
                        'width': 'mapData(weight, 0, 1, 1.2, 16)',
                        'line-cap': 'round',
                        'label': 'data(label)',
                        'font-size': 9,
                        'text-background-color': '#ffffff',
                        'text-background-opacity': 0.88,
                        'text-background-padding': 3,
                        'text-rotation': 'autorotate',
                        'color': '#334155'
                    }}
                }}
            ],
            layout: {{
                name: 'cose',
                animate: false,
                fit: true,
                padding: 56,
                // High overlap => shorter ideal length (closer nodes), low overlap => longer length.
                idealEdgeLength: (edge) => {{
                    const w = Math.max(0, Math.min(1, Number(edge.data('weight') || 0)));
                    return 520 - (w * 420);
                }},
                nodeRepulsion: () => 120000,
                edgeElasticity: () => 260,
                nodeOverlap: 280,
                gravity: 0.03,
                componentSpacing: 280,
                numIter: 2400
            }},
            wheelSensitivity: 0.2
        }});

        document.getElementById('fitBtn').addEventListener('click', () => cy.fit(undefined, 40));
        document.getElementById('layoutBtn').addEventListener('click', () => {{
            cy.layout({{
                name: 'cose',
                animate: false,
                fit: true,
                padding: 56,
                idealEdgeLength: (edge) => {{
                    const w = Math.max(0, Math.min(1, Number(edge.data('weight') || 0)));
                    return 520 - (w * 420);
                }},
                nodeRepulsion: () => 120000,
                edgeElasticity: () => 260,
                nodeOverlap: 280,
                gravity: 0.03,
                componentSpacing: 280,
                numIter: 2400
            }}).run();
        }});
    </script>
</body>
</html>
"""


def build_cross_task_artifact_dependency_graph_html(
    artifact_share_df: pd.DataFrame,
    task_activity_map: Dict[str, List[str]],
    min_task_share_for_hub: int = 2,
    max_hub_artifacts: int = 25,
    selected_artifact_key: str = "",
    height_px: int = 840,
) -> str:
    if artifact_share_df is None or artifact_share_df.empty:
        return ""

    graph_df = artifact_share_df.copy()
    graph_df["taskShareCount"] = pd.to_numeric(graph_df.get("taskShareCount", 0), errors="coerce").fillna(0).astype(int)
    graph_df["task"] = graph_df.get("task", "").astype(str).str.strip()
    graph_df["artifactKey"] = graph_df.get("artifactKey", "").astype(str).str.strip()
    graph_df["artifactType"] = graph_df.get("artifactType", "Artifact").astype(str).str.strip().replace({"": "Artifact"})
    graph_df = graph_df[(graph_df["task"] != "") & (graph_df["artifactKey"] != "")].copy()
    if graph_df.empty:
        return ""

    selected_artifact_key = str(selected_artifact_key or "").strip()
    focused_mode = bool(selected_artifact_key)

    focused_tasks: List[str] = []
    focused_edge_label_map: Dict[str, str] = {}
    focused_edge_weight_map: Dict[str, int] = {}

    if focused_mode:
        focus_rows = graph_df[graph_df["artifactKey"] == selected_artifact_key].copy()
        if focus_rows.empty:
            return ""

        focused_tasks = sorted(
            {str(task).strip() for task in focus_rows["task"].tolist() if str(task).strip()},
            key=lambda value: value.lower(),
        )

        # Build task -> intermediary artifact-type counts within the selected-artifact neighborhood.
        # Intermediary artifacts are those shared by at least two focused tasks (excluding the selected artifact).
        neighbor_rows = graph_df[
            (graph_df["task"].isin(focused_tasks))
            & (graph_df["artifactKey"] != selected_artifact_key)
        ].copy()

        if not neighbor_rows.empty:
            shared_keys = set(
                neighbor_rows.groupby("artifactKey")["task"]
                .nunique()
                .loc[lambda s: s >= 2]
                .index
                .tolist()
            )
            bridge_rows = neighbor_rows[neighbor_rows["artifactKey"].isin(shared_keys)].copy()
        else:
            bridge_rows = pd.DataFrame(columns=neighbor_rows.columns)

        if not bridge_rows.empty:
            for task, task_group in bridge_rows.groupby("task"):
                task_name = str(task).strip()
                if not task_name:
                    continue

                type_counts = (
                    task_group.groupby("artifactType")
                    .size()
                    .sort_values(ascending=False)
                )
                if type_counts.empty:
                    focused_edge_label_map[task_name] = ""
                    focused_edge_weight_map[task_name] = 1
                    continue

                label_parts = [
                    f"[{int(count)} {str(artifact_type).strip().lower()}]"
                    for artifact_type, count in type_counts.items()
                    if str(artifact_type).strip()
                ]
                focused_edge_label_map[task_name] = " ".join(label_parts)
                focused_edge_weight_map[task_name] = int(type_counts.sum())

        graph_df = focus_rows.drop_duplicates(subset=["task", "artifactKey"]).copy()
    else:
        hub_df = (
            graph_df[graph_df["taskShareCount"] >= int(min_task_share_for_hub)]
            .sort_values(["taskShareCount", "artifactType", "artifactKey", "task"], ascending=[False, True, True, True])
            .head(int(max_hub_artifacts))
        )

        graph_df = hub_df.copy()
    if graph_df.empty:
        return ""

    tasks = (
        focused_tasks
        if focused_mode
        else sorted({str(task).strip() for task in graph_df["task"].tolist() if str(task).strip()}, key=lambda value: value.lower())
    )
    max_share = max(
        1,
        max(
            int(graph_df["taskShareCount"].max()) if not graph_df.empty else 1,
            max(focused_edge_weight_map.values()) if focused_edge_weight_map else 1,
        ),
    )

    palette = px.colors.qualitative.Alphabet + px.colors.qualitative.Set3 + px.colors.qualitative.Dark24
    activities = sorted(
        {
            (task_activity_map.get(task, ["NoActivity"])[0] if task_activity_map.get(task) else "NoActivity")
            for task in tasks
        },
        key=lambda value: str(value).lower(),
    )
    activity_color_map = {activity: palette[index % len(palette)] for index, activity in enumerate(activities)}
    artifact_color_map = {
        "Model": "#0284c7",
        "Dataset": "#16a34a",
        "Paper": "#6d28d9",
        "Benchmark": "#dc2626",
        "Collection": "#7c3aed",
        "Space": "#0f766e",
    }

    node_items: List[Dict[str, Any]] = []
    for task in tasks:
        activity = task_activity_map.get(task, ["NoActivity"])[0] if task_activity_map.get(task) else "NoActivity"
        node_items.append(
            {
                "data": {
                    "id": task,
                    "kind": "task",
                    "label": task,
                    "display": task,
                    "activity": activity,
                    "color": activity_color_map.get(activity, "#64748b"),
                }
            }
        )

    artifact_lookup = graph_df.drop_duplicates(subset=["artifactKey"])[["artifactKey", "artifactType", "taskShareCount"]]
    if focused_mode:
        artifact_lookup = artifact_lookup[artifact_lookup["artifactKey"] == selected_artifact_key].copy()
    for _, row in artifact_lookup.iterrows():
        artifact_key = str(row.get("artifactKey", "")).strip()
        if not artifact_key:
            continue
        artifact_type = str(row.get("artifactType", "Artifact")).strip() or "Artifact"
        share_count = int(row.get("taskShareCount", 0))
        display_label = artifact_key if share_count <= 1 else f"[{share_count}] {artifact_key}"
        if focused_mode and artifact_key == selected_artifact_key:
            display_label = f"[selected] {artifact_key}"
        node_items.append(
            {
                "data": {
                    "id": artifact_key,
                    "kind": "artifact",
                    "artifactType": artifact_type,
                    "shareCount": share_count,
                    "label": artifact_key,
                    "display": display_label,
                    "color": artifact_color_map.get(artifact_type, "#0ea5e9"),
                }
            }
        )

    edge_items: List[Dict[str, Any]] = []
    seen_edges: Set[str] = set()
    for idx, row in graph_df.iterrows():
        task = str(row.get("task", "")).strip()
        artifact_key = str(row.get("artifactKey", "")).strip()
        if not task or not artifact_key:
            continue
        if focused_mode and artifact_key != selected_artifact_key:
            continue
        edge_id = f"{task}__{artifact_key}__{idx}"
        if edge_id in seen_edges:
            continue
        seen_edges.add(edge_id)
        share_count = int(row.get("taskShareCount", 0))
        if focused_mode:
            share_count = int(focused_edge_weight_map.get(task, 1))
            edge_label = focused_edge_label_map.get(task, "")
        else:
            edge_label = ""
        edge_items.append(
            {
                "data": {
                    "id": edge_id,
                    "source": task,
                    "target": artifact_key,
                    "weight": share_count,
                    "label": edge_label,
                }
            }
        )

    elements_json = json.dumps(node_items + edge_items)

    return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        html, body {{ margin: 0; padding: 0; background: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        #wrapper {{ height: {height_px}px; width: 100%; display: grid; grid-template-rows: auto 1fr; gap: 8px; }}
        #toolbar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }}
        #toolbar button {{ border: 1px solid #cbd5e1; background: #f1f5f9; color: #0f172a; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        #meta {{ font-size: 12px; color: #334155; }}
        #cy {{ height: 100%; width: 100%; background: radial-gradient(circle at 20% 20%, #ffffff 0%, #f1f5f9 100%); border: 1px solid #e2e8f0; border-radius: 8px; }}
    </style>
    <script src=\"https://unpkg.com/cytoscape@3.30.1/dist/cytoscape.min.js\"></script>
</head>
<body>
    <div id=\"wrapper\">
        <div id=\"toolbar\">
            <button id=\"fitBtn\">Fit</button>
            <button id=\"layoutBtn\">Re-layout</button>
            <span id=\"meta\"></span>
        </div>
        <div id=\"cy\"></div>
    </div>
    <script>
        const elements = {elements_json};
        const taskCount = elements.filter(e => e.data && e.data.kind === 'task').length;
        const artifactCount = elements.filter(e => e.data && e.data.kind === 'artifact').length;
        const edgeCount = elements.filter(e => e.data && e.data.source).length;
        document.getElementById('meta').textContent = `Tasks: ${{taskCount}} | Artifacts: ${{artifactCount}} | Links: ${{edgeCount}}`;

        const cy = cytoscape({{
            container: document.getElementById('cy'),
            elements,
            style: [
                {{
                    selector: 'node',
                    style: {{
                        'label': 'data(display)',
                        'font-size': 10,
                        'color': '#0f172a',
                        'text-wrap': 'wrap',
                        'text-max-width': 150,
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'border-width': 1,
                        'border-color': '#334155',
                        'width': 26,
                        'height': 26,
                        'background-color': '#0ea5e9'
                    }}
                }},
                {{
                    selector: "node[kind = 'task']",
                    style: {{
                        'shape': 'ellipse',
                        'background-color': 'data(color)',
                        'border-color': '#334155',
                        'width': 28,
                        'height': 28
                    }}
                }},
                {{
                    selector: "node[kind = 'artifact']",
                    style: {{
                        'shape': 'round-rectangle',
                        'background-color': 'data(color)',
                        'border-color': '#0f172a',
                        'width': 'mapData(shareCount, 1, {max_share}, 26, 72)',
                        'height': 'mapData(shareCount, 1, {max_share}, 18, 50)',
                        'font-size': 9
                    }}
                }},
                {{
                    selector: "node[kind = 'artifact'][shareCount >= {max(2, int(min_task_share_for_hub))}]",
                    style: {{
                        'border-width': 2,
                        'border-color': '#111827'
                    }}
                }},
                {{
                    selector: 'edge',
                    style: {{
                        'curve-style': 'bezier',
                        'line-color': '#475569',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#475569',
                        'opacity': 0.78,
                        'width': 'mapData(weight, 1, {max_share}, 1.0, 10)',
                        'label': 'data(label)',
                        'font-size': 8,
                        'color': '#334155',
                        'text-background-color': '#ffffff',
                        'text-background-opacity': 0.88,
                        'text-background-padding': 2,
                        'text-rotation': 'autorotate'
                    }}
                }}
            ],
            layout: {{
                name: 'cose',
                animate: false,
                fit: true,
                padding: 44,
                idealEdgeLength: (edge) => {{
                    const weight = Math.max(1, Math.min({max_share}, Number(edge.data('weight') || 1)));
                    return 420 - ((weight - 1) * 55);
                }},
                nodeRepulsion: (node) => node.data('kind') === 'artifact' ? 48000 : 32000,
                edgeElasticity: () => 120,
                gravity: 0.04,
                componentSpacing: 240,
                numIter: 2000
            }},
            wheelSensitivity: 0.2
        }});

        document.getElementById('fitBtn').addEventListener('click', () => cy.fit(undefined, 40));
        document.getElementById('layoutBtn').addEventListener('click', () => {{
            cy.layout({{
                name: 'cose',
                animate: false,
                fit: true,
                padding: 44,
                idealEdgeLength: (edge) => {{
                    const weight = Math.max(1, Math.min({max_share}, Number(edge.data('weight') || 1)));
                    return 420 - ((weight - 1) * 55);
                }},
                nodeRepulsion: (node) => node.data('kind') === 'artifact' ? 48000 : 32000,
                edgeElasticity: () => 120,
                gravity: 0.04,
                componentSpacing: 240,
                numIter: 2000
            }}).run();
        }});
    </script>
</body>
</html>
"""

def render_task_artifact_overlaps_page(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
) -> None:
    if not _ensure_plotly():
        return

    st.subheader("Task Artifact Overlaps")
    st.caption("Pairwise overlap summary for tasks and activities.")

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    state_key = "task_artifact_overlap_state"
    refresh_clicked = False

    col_run, col_top = st.columns([1, 2])
    run_clicked = col_run.button("Load overlaps", type="primary")
    top_n = col_top.slider("Top overlaps", min_value=5, max_value=600, value=600, step=5)

    if run_clicked or state_key not in st.session_state:
        refresh_clicked = True

    if refresh_clicked:
        try:
            count_rows, source, info = get_data_with_fallback(
            uri=uri,
            username=username,
            password=password,
            database=database,
            query=TASK_ARTIFACT_COUNTS_QUERY,
            row_limit=int(row_limit),
        )

            if source == "online":
                st.success(info)
            else:
                st.warning(info)

            if not count_rows:
                st.info("No tasks returned.")
                return

            tasks = [str(row.get("task")).strip() for row in count_rows if row.get("task")]
            tasks = [task for task in tasks if task]
            if not tasks:
                st.info("No valid task ids found.")
                return

            count_map = {str(row.get("task")): int(row.get("artifactCount", 0)) for row in count_rows if row.get("task")}

            task_activity_rows, _, _ = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ACTIVITY_BY_TASK_QUERY,
                row_limit=int(row_limit),
            )
            task_activity_map = {
                str(row.get("task")): sorted([str(a).strip() for a in (row.get("activities") or []) if str(a).strip()])
                for row in task_activity_rows
                if row.get("task")
            }

            type_count_rows, _, _ = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ARTIFACT_TYPE_COUNTS_QUERY,
                row_limit=int(row_limit),
            )

            dataset_count_map = {str(row.get("task")): int(row.get("datasetCount", 0)) for row in type_count_rows if row.get("task")}
            model_count_map = {str(row.get("task")): int(row.get("modelCount", 0)) for row in type_count_rows if row.get("task")}
            space_count_map = {str(row.get("task")): int(row.get("spaceCount", 0)) for row in type_count_rows if row.get("task")}
            benchmark_count_map = {str(row.get("task")): int(row.get("benchmarkCount", 0)) for row in type_count_rows if row.get("task")}
            collection_count_map = {str(row.get("task")): int(row.get("collectionCount", 0)) for row in type_count_rows if row.get("task")}

            if len(tasks) < 2:
                st.session_state[state_key] = {"tasks": tasks, "count_map": count_map, "overlap_df": pd.DataFrame()}
                st.info("Not enough tasks to compute pairwise overlaps.")
                return

            overlap_rows, pair_source, pair_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ARTIFACT_TOP_OVERLAPS_QUERY,
                row_limit=int(top_n),
                params={"top_n": int(top_n)},
            )

            if pair_source == "online":
                st.success(pair_info)
            else:
                st.warning(pair_info)

            overlap_df = pd.DataFrame(overlap_rows)
            if overlap_df.empty:
                st.session_state[state_key] = {"tasks": tasks, "count_map": count_map, "overlap_df": pd.DataFrame()}
                st.info("No overlaps were returned by the database.")
                return

            overlap_df["task1ArtifactCount"] = overlap_df["task1"].map(lambda t: count_map.get(str(t), 0))
            overlap_df["task2ArtifactCount"] = overlap_df["task2"].map(lambda t: count_map.get(str(t), 0))
            overlap_df["jaccardArtifacts"] = overlap_df.apply(
                lambda r: (float(r["sharedArtifactCount"]) / float(r["task1ArtifactCount"] + r["task2ArtifactCount"] - r["sharedArtifactCount"]))
                if (r["task1ArtifactCount"] + r["task2ArtifactCount"] - r["sharedArtifactCount"]) > 0
                else 0.0,
                axis=1,
            )
            overlap_df["overlapCoeffArtifacts"] = overlap_df.apply(
                lambda r: (float(r["sharedArtifactCount"]) / float(min(r["task1ArtifactCount"], r["task2ArtifactCount"])))
                if min(r["task1ArtifactCount"], r["task2ArtifactCount"]) > 0
                else 0.0,
                axis=1,
            )

            overlap_df["task1DatasetCount"] = overlap_df["task1"].map(lambda t: dataset_count_map.get(str(t), 0))
            overlap_df["task2DatasetCount"] = overlap_df["task2"].map(lambda t: dataset_count_map.get(str(t), 0))
            overlap_df["jaccardDataset"] = overlap_df.apply(
                lambda r: (float(r.get("overlapDatasetCount", 0)) /
                           float(r["task1DatasetCount"] + r["task2DatasetCount"] - float(r.get("overlapDatasetCount", 0))))
                if (r["task1DatasetCount"] + r["task2DatasetCount"] - float(r.get("overlapDatasetCount", 0))) > 0
                else 0.0,
                axis=1,
            )

            overlap_df["task1ModelCount"] = overlap_df["task1"].map(lambda t: model_count_map.get(str(t), 0))
            overlap_df["task2ModelCount"] = overlap_df["task2"].map(lambda t: model_count_map.get(str(t), 0))
            overlap_df["jaccardModel"] = overlap_df.apply(
                lambda r: (float(r.get("overlapModelCount", 0)) /
                           float(r["task1ModelCount"] + r["task2ModelCount"] - float(r.get("overlapModelCount", 0))))
                if (r["task1ModelCount"] + r["task2ModelCount"] - float(r.get("overlapModelCount", 0))) > 0
                else 0.0,
                axis=1,
            )

            overlap_df["task1SpaceCount"] = overlap_df["task1"].map(lambda t: space_count_map.get(str(t), 0))
            overlap_df["task2SpaceCount"] = overlap_df["task2"].map(lambda t: space_count_map.get(str(t), 0))
            overlap_df["jaccardSpace"] = overlap_df.apply(
                lambda r: (float(r.get("overlapSpaceCount", 0)) /
                           float(r["task1SpaceCount"] + r["task2SpaceCount"] - float(r.get("overlapSpaceCount", 0))))
                if (r["task1SpaceCount"] + r["task2SpaceCount"] - float(r.get("overlapSpaceCount", 0))) > 0
                else 0.0,
                axis=1,
            )

            overlap_df["task1BenchmarkCount"] = overlap_df["task1"].map(lambda t: benchmark_count_map.get(str(t), 0))
            overlap_df["task2BenchmarkCount"] = overlap_df["task2"].map(lambda t: benchmark_count_map.get(str(t), 0))
            overlap_df["jaccardBenchmark"] = overlap_df.apply(
                lambda r: (float(r.get("overlapBenchmarkCount", 0)) /
                           float(r["task1BenchmarkCount"] + r["task2BenchmarkCount"] - float(r.get("overlapBenchmarkCount", 0))))
                if (r["task1BenchmarkCount"] + r["task2BenchmarkCount"] - float(r.get("overlapBenchmarkCount", 0))) > 0
                else 0.0,
                axis=1,
            )

            overlap_df["task1CollectionCount"] = overlap_df["task1"].map(lambda t: collection_count_map.get(str(t), 0))
            overlap_df["task2CollectionCount"] = overlap_df["task2"].map(lambda t: collection_count_map.get(str(t), 0))
            overlap_df["jaccardCollection"] = overlap_df.apply(
                lambda r: (float(r.get("overlapCollectionCount", 0)) /
                           float(r["task1CollectionCount"] + r["task2CollectionCount"] - float(r.get("overlapCollectionCount", 0))))
                if (r["task1CollectionCount"] + r["task2CollectionCount"] - float(r.get("overlapCollectionCount", 0))) > 0
                else 0.0,
                axis=1,
            )

            overlap_df = overlap_df.sort_values(
                ["sharedArtifactCount", "jaccardArtifacts", "overlapCoeffArtifacts"],
                ascending=[False, False, False],
            )

            def format_task_with_activity(task_name: str) -> str:
                activities = task_activity_map.get(str(task_name), [])
                activity_label = activities[0] if activities else "NoActivity"
                return f"{activity_label}/{task_name}"

            overlap_df["task1Display"] = overlap_df["task1"].map(format_task_with_activity)
            overlap_df["task2Display"] = overlap_df["task2"].map(format_task_with_activity)

            st.session_state[state_key] = {
                "tasks": tasks,
                "count_map": count_map,
                "task_activity_map": task_activity_map,
                "overlap_df": overlap_df,
            }

        except Exception as exc:
            st.error(str(exc))
            return

    state = st.session_state.get(state_key)
    if not state:
        st.info("Load overlaps to compute pairwise task similarity.")
        return

    tasks = state.get("tasks", [])
    count_map = state.get("count_map", {})
    task_activity_map = state.get("task_activity_map", {})
    overlap_df = state.get("overlap_df", pd.DataFrame())

    if overlap_df is None or overlap_df.empty:
        st.info("No overlaps were returned by the database.")
        return

    st.markdown("### Highest pairwise overlaps")
    jaccard_cols = [
        "task1Display",
        "task2Display",
        "jaccardArtifacts",
        "jaccardDataset",
        "jaccardModel",
        "jaccardSpace",
        "jaccardBenchmark",
        "jaccardCollection",
    ]
    visible_cols = [c for c in jaccard_cols if c in overlap_df.columns]
    overlap_df_view = overlap_df[visible_cols].sort_values("jaccardArtifacts", ascending=False)
    st.dataframe(overlap_df_view.head(int(top_n)), use_container_width=True)

    st.markdown("### SE Activity overlaps (Model / Dataset / Space)")
    st.caption("Computed via SETask USED_FOR SEActivity.")
    activity_state_key = "se_activity_overlap_state"
    col_act_run, col_act_top = st.columns([1, 2])
    activity_run_clicked = col_act_run.button("Load activity overlaps", type="secondary")

    if activity_run_clicked or activity_state_key not in st.session_state:
        try:
            activity_rows, activity_source, activity_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ACTIVITY_TOP_OVERLAPS_QUERY,
                row_limit=int(15),
                params={"top_n": int(15)},
            )

            if activity_source == "online":
                st.success(activity_info)
            else:
                st.warning(activity_info)

            activity_df = pd.DataFrame(activity_rows)
            st.session_state[activity_state_key] = activity_df
        except Exception as exc:
            st.error(str(exc))
            st.session_state[activity_state_key] = pd.DataFrame()

    activity_df = st.session_state.get(activity_state_key, pd.DataFrame())
    if activity_df is None or activity_df.empty:
        st.info("No SE activity overlaps found yet. Click 'Load activity overlaps'.")
    else:
        st.dataframe(activity_df.head(int(15)), use_container_width=True)

    # ============ NEW VISUALIZATIONS: SE ACTIVITY MODEL COUNTS AND OVERLAPS ============
    st.markdown("### Distinct Model Count by SE Activity")
    st.caption("Shows the number of distinct models associated with each SE activity.")
    
    if not activity_df.empty:
        activity_model_data = []
        for _, row in activity_df.iterrows():
            activity1 = row.get("activity1")
            activity2 = row.get("activity2")
            model_count1 = row.get("overlapModelCount", 0)
            model_count2 = row.get("overlapModelCount", 0)
            
            # For activity1, we need to calculate total distinct models
            # Get all model artifacts for this activity from the raw data
            if activity1 not in [d["activity"] for d in activity_model_data]:
                activity_model_data.append({
                    "activity": activity1,
                    "model_count": model_count1
                })
            if activity2 not in [d["activity"] for d in activity_model_data]:
                activity_model_data.append({
                    "activity": activity2,
                    "model_count": model_count2
                })
        
        if activity_model_data:
            # Create a more accurate count by re-querying or processing existing data
            # For now, we'll create a visualization from available overlap data
            activity_model_counts = {}
            
            for _, row in activity_df.iterrows():
                act1 = row.get("activity1")
                act2 = row.get("activity2")
                overlap_models = row.get("overlapModelCount", 0)
                
                # Initialize counts
                if act1 not in activity_model_counts:
                    activity_model_counts[act1] = {"overlap_models": 0, "total_appearances": 0}
                if act2 not in activity_model_counts:
                    activity_model_counts[act2] = {"overlap_models": 0, "total_appearances": 0}
                
                activity_model_counts[act1]["total_appearances"] += 1
                activity_model_counts[act2]["total_appearances"] += 1
                activity_model_counts[act1]["overlap_models"] += overlap_models
                activity_model_counts[act2]["overlap_models"] += overlap_models
            
            model_count_df = pd.DataFrame([
                {
                    "SE Activity": activity,
                    "Distinct Models (Overlaps)": counts.get("overlap_models", 0),
                    "Appearances": counts.get("total_appearances", 0)
                }
                for activity, counts in activity_model_counts.items()
            ]).sort_values("Distinct Models (Overlaps)", ascending=False)
            
            if not model_count_df.empty:
                fig_model_count = px.bar(
                    model_count_df,
                    x="SE Activity",
                    y="Distinct Models (Overlaps)",
                    title="Distinct Model Count by SE Activity",
                    labels={"Distinct Models (Overlaps)": "Model Count"},
                    color="Distinct Models (Overlaps)",
                    color_continuous_scale="Viridis",
                    hover_data=["Appearances"],
                    text="Distinct Models (Overlaps)",
                )
                fig_model_count.update_traces(textposition="outside")
                fig_model_count.update_layout(
                    xaxis_title="SE Activity",
                    yaxis_title="Distinct Model Count",
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig_model_count, use_container_width=True)
    
    # ============ MODEL OVERLAP VISUALIZATION ============
    st.markdown("### Model Overlap Between SE Activities")
    st.caption("Visualizes how models are shared between different SE activities.")
    
    if not activity_df.empty and len(activity_df) > 0:
        # Create model overlap scatter plot
        activity_df_plot = activity_df.copy()
        activity_df_plot["overlap_display"] = activity_df_plot.apply(
            lambda r: f"{r.get('activity1', 'N/A')}<br>↔<br>{r.get('activity2', 'N/A')}<br>(Models: {r.get('overlapModelCount', 0)}, Datasets: {r.get('overlapDatasetCount', 0)}, Spaces: {r.get('overlapSpaceCount', 0)})",
            axis=1
        )
        
        fig_overlap_scatter = px.scatter(
            activity_df_plot,
            x="activity1",
            y="activity2",
            size="overlapModelCount",
            color="jaccardModel",
            hover_data=["overlapModelCount", "overlapDatasetCount", "overlapSpaceCount", "jaccardModel", "jaccardDataset", "jaccardSpace"],
            title="Model Overlap Between SE Activities (Bubble Size = Model Count)",
            labels={
                "activity1": "SE Activity 1",
                "activity2": "SE Activity 2",
                "jaccardModel": "Jaccard Index (Models)",
            },
            color_continuous_scale="RdYlGn",
            size_max=40,
        )
        fig_overlap_scatter.update_layout(
            height=600,
            xaxis_title="SE Activity 1",
            yaxis_title="SE Activity 2",
            hovermode="closest",
        )
        st.plotly_chart(fig_overlap_scatter, use_container_width=True)
        
        # Create a table showing model overlap details
        st.markdown("**Model Overlap Details**")
        overlap_details = activity_df.copy()
        overlap_details = overlap_details[[
            "activity1",
            "activity2",
            "overlapModelCount",
            "overlapDatasetCount",
            "overlapSpaceCount",
            "jaccardModel",
            "jaccardDataset",
            "jaccardSpace"
        ]].sort_values("overlapModelCount", ascending=False)
        
        overlap_details.columns = [
            "Activity 1",
            "Activity 2",
            "Models",
            "Datasets",
            "Spaces",
            "Jaccard (Models)",
            "Jaccard (Datasets)",
            "Jaccard (Spaces)"
        ]
        
        st.dataframe(
            overlap_details,
            use_container_width=True,
            height=400
        )

    # ============ END OF NEW VISUALIZATIONS ============
    metric = st.selectbox(
        "Similarity metric",
        options=["jaccardArtifacts", "overlapCoeffArtifacts", "sharedArtifactCount"],
        index=0,
        key="task_artifact_overlap_metric",
    )

    # Order tasks by their first linked SE activity, then by task id.
    matrix_tasks = sorted(
        tasks,
        key=lambda t: (
            (task_activity_map.get(str(t), ["NoActivity"])[0] or "NoActivity").lower(),
            str(t).lower(),
        ),
    )

    matrix_source = overlap_df[
        overlap_df["task1"].isin(matrix_tasks) & overlap_df["task2"].isin(matrix_tasks)
    ].copy()
    matrix_df = build_similarity_matrix(matrix_source, matrix_tasks, metric_col=metric).astype(float)

    # Hide duplicate symmetric values by masking the upper triangle.
    upper_mask = np.triu(np.ones(matrix_df.shape, dtype=bool), k=1)
    matrix_df = matrix_df.mask(upper_mask)

    matrix_df.index = matrix_tasks
    matrix_df.columns = matrix_tasks

    activity_by_task = {
        t: (task_activity_map.get(str(t), ["NoActivity"])[0] or "NoActivity")
        for t in matrix_tasks
    }
    unique_activities = sorted(set(activity_by_task.values()), key=lambda v: str(v).lower())

    st.markdown("### Task similarity heatmap")
    palette = px.colors.qualitative.Alphabet + px.colors.qualitative.Set3 + px.colors.qualitative.Dark24
    activity_color_map = {
        activity: palette[i % len(palette)]
        for i, activity in enumerate(unique_activities)
    }
    colored_task_labels = [
        f"<span style='color:{activity_color_map.get(activity_by_task[t], '#222')}'>{t}</span>"
        for t in matrix_tasks
    ]

    heatmap_fig = px.imshow(
        matrix_df,
        text_auto=".2f" if metric != "sharedArtifactCount" else True,
        aspect="auto",
        color_continuous_scale="Blues",
        labels={"x": "SETask", "y": "SETask", "color": metric},
    )
    heatmap_fig.update_xaxes(
        tickmode="array",
        tickvals=matrix_tasks,
        ticktext=colored_task_labels,
    )
    heatmap_fig.update_yaxes(
        tickmode="array",
        tickvals=matrix_tasks,
        ticktext=colored_task_labels,
    )
    heatmap_fig.update_layout(height=1300)
    st.plotly_chart(heatmap_fig, use_container_width=True)

    st.markdown("### Task overlap network")
    st.caption(
        "Tasks are connected when they share artifacts. Edge width encodes Jaccard overlap across all artifacts."
    )
    graph_col1, graph_col2 = st.columns([1, 1])
    min_edge_jaccard = graph_col1.slider(
        "Min edge Jaccard",
        min_value=0.00,
        max_value=0.50,
        value=0.05,
        step=0.01,
        key="task_overlap_graph_min_jaccard",
    )
    top_k_neighbors = graph_col2.slider(
        "Top-k neighbors per task",
        min_value=1,
        max_value=12,
        value=4,
        step=1,
        key="task_overlap_graph_top_k",
    )

    dependency_graph_html = build_task_overlap_dependency_graph_html(
        overlap_df=matrix_source,
        task_activity_map=task_activity_map,
        min_jaccard=float(min_edge_jaccard),
        top_k_per_task=int(top_k_neighbors),
        height_px=980,
    )
    if dependency_graph_html:
        components.html(dependency_graph_html, height=900, scrolling=False)
    else:
        st.info("No overlap edges with positive Jaccard were found for the current task set.")

    st.markdown("### Hub artifacts")
    st.caption(
        "Hub artifacts are shared across many tasks."
    )
    artifact_share_state_key = "task_artifact_share_global_rows"
    if artifact_share_state_key not in st.session_state:
        try:
            artifact_share_rows, _, _ = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ARTIFACT_TASK_SHARE_QUERY,
                row_limit=max(int(row_limit), 200000),
                params={"top_n": max(int(row_limit), 200000)},
            )
            st.session_state[artifact_share_state_key] = artifact_share_rows
        except Exception as exc:
            st.warning(f"Could not load artifact-share statistics: {exc}")
            st.session_state[artifact_share_state_key] = []

    artifact_share_df = pd.DataFrame(st.session_state.get(artifact_share_state_key, []))
    if not artifact_share_df.empty:
        artifact_share_df["taskShareCount"] = pd.to_numeric(
            artifact_share_df.get("taskShareCount", 0), errors="coerce"
        ).fillna(0).astype(int)

        # Group artifacts and collect all tasks that share each one
        hub_artifacts = (
            artifact_share_df.sort_values(["taskShareCount", "artifactType", "artifactKey"], ascending=[False, True, True])
            .drop_duplicates(subset=["artifactKey"])
            .head(30)
        )
        
        # Build table with all tasks per artifact
        hub_df_data = []
        for _, row in hub_artifacts.iterrows():
            artifact_key = row["artifactKey"]
            artifact_type = row["artifactType"]
            task_share_count = row["taskShareCount"]
            
            # Get all tasks sharing this artifact
            tasks_sharing = artifact_share_df[artifact_share_df["artifactKey"] == artifact_key]["task"].tolist()
            tasks_str = ", ".join(sorted(set(tasks_sharing)))
            
            hub_df_data.append({
                "Artifact": artifact_key,
                "Type": artifact_type,
                "Tasks Sharing": task_share_count,
                "Tasks": tasks_str
            })
        
        hub_df = pd.DataFrame(hub_df_data)
        st.markdown("**Top hub artifacts (highest task sharing)**")
        st.dataframe(hub_df, use_container_width=True, height=360)

        st.markdown("### Cross-task artifact dependency graph")
        st.caption(
            "Enter an artifact key like Dataset:custom or Collection:diwank/k-65ecc81e3ec9c2d5f8fffcfb to show a focused neighborhood around that artifact."
        )
        artifact_graph_col1, artifact_graph_col2 = st.columns([2, 1])
        selected_artifact_key = artifact_graph_col1.text_input(
            "Artifact key",
            value="",
            placeholder="Dataset:custom or Collection:diwank/k-65ecc81e3ec9c2d5f8fffcfb",
            key="artifact_graph_focus_key",
        )
        min_hub_share = artifact_graph_col2.slider(
            "Hub threshold",
            min_value=2,
            max_value=20,
            value=2,
            step=1,
            key="artifact_graph_hub_threshold",
        )
        max_hub_artifacts = st.slider(
            "Hub artifacts",
            min_value=5,
            max_value=60,
            value=25,
            step=1,
            key="artifact_graph_hub_limit",
        )

        artifact_graph_html = build_cross_task_artifact_dependency_graph_html(
            artifact_share_df=artifact_share_df,
            task_activity_map=task_activity_map,
            min_task_share_for_hub=int(min_hub_share),
            max_hub_artifacts=int(max_hub_artifacts),
            selected_artifact_key=selected_artifact_key,
            height_px=920,
        )
        if artifact_graph_html:
            components.html(artifact_graph_html, height=960, scrolling=False)
        elif selected_artifact_key.strip():
            st.warning(f"No graph data found for artifact key: {selected_artifact_key}")
        else:
            st.info("No artifact dependency graph could be built from the available task-share rows.")

    st.markdown("### Aggregate SDLC activity effect across HF dimensions")
    st.caption("Compares mean Jaccard for task pairs in the same SEActivity vs different SEActivities.")

    pair_stats_df = overlap_df.copy()
    pair_stats_df["activity1"] = pair_stats_df["task1"].map(lambda t: activity_by_task.get(str(t), "NoActivity"))
    pair_stats_df["activity2"] = pair_stats_df["task2"].map(lambda t: activity_by_task.get(str(t), "NoActivity"))
    pair_stats_df["pairGroup"] = np.where(
        pair_stats_df["activity1"] == pair_stats_df["activity2"],
        "Same SDLC activity",
        "Different SDLC activities",
    )

    dimension_map = {
        "jaccardArtifacts": "All artifacts",
        "jaccardDataset": "Datasets",
        "jaccardModel": "Models",
        "jaccardSpace": "Spaces",
        "jaccardBenchmark": "Benchmarks",
        "jaccardCollection": "Collections",
    }
    available_dims = [c for c in dimension_map if c in pair_stats_df.columns]

    if available_dims:
        long_stats_df = pair_stats_df[["pairGroup"] + available_dims].melt(
            id_vars=["pairGroup"],
            var_name="dimension",
            value_name="jaccardValue",
        )
        long_stats_df["dimension"] = long_stats_df["dimension"].map(dimension_map)

        # Filter out zero Jaccard values before aggregation
        long_stats_df = long_stats_df[long_stats_df["jaccardValue"] > 0]

        agg_stats_df = (
            long_stats_df
            .groupby(["dimension", "pairGroup"], as_index=False)
            .agg(
                meanJaccard=("jaccardValue", "mean"),
                medianJaccard=("jaccardValue", "median"),
                pairCount=("jaccardValue", "size"),
            )
        )

        ordered_dimensions = list(dimension_map.values())
        for dimension_label in ordered_dimensions:
            dim_df = agg_stats_df[agg_stats_df["dimension"] == dimension_label].copy()
            if dim_df.empty:
                continue

            dim_fig = px.bar(
                dim_df,
                x="pairGroup",
                y="meanJaccard",
                color="pairGroup",
                text_auto=".3f",
                title=f"{dimension_label}: mean Jaccard by SDLC grouping",
                labels={"pairGroup": "Pair type", "meanJaccard": "Mean Jaccard"},
            )
            dim_fig.update_layout(showlegend=False, height=320)
            st.plotly_chart(dim_fig, use_container_width=True)

        pivot_df = agg_stats_df.pivot(index="dimension", columns="pairGroup", values="meanJaccard").reset_index()
        same_col = "Same SDLC activity"
        diff_col = "Different SDLC activities"
        if same_col in pivot_df.columns and diff_col in pivot_df.columns:
            pivot_df["liftRatio"] = pivot_df.apply(
                lambda r: (float(r[same_col]) / float(r[diff_col])) if float(r[diff_col]) > 0 else np.nan,
                axis=1,
            )

            # lift_fig = px.bar(
            #     pivot_df,
            #     x="dimension",
            #     y="liftRatio",
            #     text_auto=".2f",
            #     category_orders={"dimension": ordered_dimensions},
            #     title="Relative lift (same activity / different activities)",
            #     labels={"dimension": "HF dimension", "liftRatio": "Lift ratio"},
            # )
            # lift_fig.add_hline(y=1.0, line_dash="dash", line_color="gray")
            # lift_fig.update_layout(height=360)
            # st.plotly_chart(lift_fig, use_container_width=True)

        st.dataframe(agg_stats_df, use_container_width=True)
    else:
        st.info("No overlap count dimensions available for aggregate SDLC activity analysis.")

    st.markdown("### Inspect one task pair")
    pair_state_key = "task_artifact_overlap_selected_pair"
    with st.form("task_artifact_overlap_pair_form"):
        col1, col2 = st.columns(2)
        selected_task1 = col1.selectbox("Task 1", tasks, index=0, key="task_artifact_overlap_task1")
        default_index2 = 1 if len(tasks) > 1 else 0
        selected_task2 = col2.selectbox("Task 2", tasks, index=default_index2, key="task_artifact_overlap_task2")
        run_pairwise = st.form_submit_button("Run pairwise", type="primary")

    if run_pairwise:
        if selected_task1 == selected_task2:
            st.info("Select two different tasks to inspect overlap details.")
            st.session_state.pop(pair_state_key, None)
        else:
            st.session_state[pair_state_key] = {"task1": selected_task1, "task2": selected_task2}

    active_pair = st.session_state.get(pair_state_key)
    if not active_pair:
        st.info("Choose two tasks and click Run pairwise to load the graph.")
        return

    selected_task1 = str(active_pair.get("task1", "")).strip()
    selected_task2 = str(active_pair.get("task2", "")).strip()

    if not selected_task1 or not selected_task2:
        st.info("Choose two tasks and click Run pairwise to load the graph.")
        return

    try:
        pair_metrics_rows, _, _ = get_data_with_fallback(
            uri=uri,
            username=username,
            password=password,
            database=database,
            query=TASK_ARTIFACT_PAIR_OVERLAP_QUERY,
            row_limit=1,
            params={"task1": selected_task1, "task2": selected_task2},
        )

        pair_detail_limit = max(int(row_limit), 500)
        pair_rows, _, _ = get_data_with_fallback(
            uri=uri,
            username=username,
            password=password,
            database=database,
            query=TASK_ARTIFACT_PAIR_DETAILS_QUERY,
            row_limit=pair_detail_limit,
            params={"task1": selected_task1, "task2": selected_task2, "pair_detail_limit": pair_detail_limit},
        )

        detail_rows = pair_rows

        task1_artifacts = {str(row.get("artifactKey")) for row in detail_rows if row.get("inTask1")}
        task2_artifacts = {str(row.get("artifactKey")) for row in detail_rows if row.get("inTask2")}
        shared_artifacts = task1_artifacts & task2_artifacts

        if pair_metrics_rows:
            pair_metrics = pair_metrics_rows[0]
            inter_size = int(pair_metrics.get("sharedArtifactCount", len(shared_artifacts)))
            jaccard = float(pair_metrics.get("jaccardArtifacts", 0.0))
            overlap_coeff = float(pair_metrics.get("overlapCoeffArtifacts", 0.0))
        else:
            inter_size = len(shared_artifacts)
            union_size = len(task1_artifacts | task2_artifacts)
            jaccard = inter_size / union_size if union_size else 0.0
            overlap_coeff = inter_size / min(len(task1_artifacts), len(task2_artifacts)) if min(len(task1_artifacts), len(task2_artifacts)) > 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Shared artifacts", inter_size)
        m2.metric("Jaccard", f"{jaccard:.3f}")
        m3.metric("Overlap coefficient", f"{overlap_coeff:.3f}")

        st.markdown("### Pair graph grouped by SETask cluster")
        st.caption("Tasks are shown as cluster anchors. Artifact nodes connect to the task groups in seTaskGroups, so shared artifacts sit naturally between both tasks.")
        st.caption(f"Selected pair: {selected_task1} vs {selected_task2}")
        pair_graph_rows, _, _ = get_data_with_fallback(
            uri=uri,
            username=username,
            password=password,
            database=database,
            query=TASK_PAIR_SUBGRAPH_QUERY,
            row_limit=1,
            params={"task1": selected_task1, "task2": selected_task2, "subgraph_model_limit": int(row_limit)},
        )

        pair_nodes: List[Dict[str, Any]] = []
        pair_relationships: List[Dict[str, Any]] = []
        if pair_graph_rows and isinstance(pair_graph_rows[0], dict):
            pair_nodes = pair_graph_rows[0].get("nodes", []) or []
            pair_relationships = pair_graph_rows[0].get("relationships", []) or []

        if pair_nodes:
            components.html(build_cytoscape_html(pair_nodes, pair_relationships, height_px=760), height=800, scrolling=False)
            st.caption(f"Combined ecosystem nodes: {len(pair_nodes)} | relationships: {len(pair_relationships)}")
        else:
            st.warning("No combined ecosystem subgraph was returned for this task pair.")

        st.markdown("### Pair details")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Artifacts in {selected_task1}**")
            st.dataframe(pd.DataFrame({"artifact": sorted(task1_artifacts)}), use_container_width=True, height=320)
        with c2:
            st.markdown(f"**Artifacts in {selected_task2}**")
            st.dataframe(pd.DataFrame({"artifact": sorted(task2_artifacts)}), use_container_width=True, height=320)

    except Exception as exc:
        st.error(str(exc))


def render_task_specificity_page(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
) -> None:
    if not _ensure_plotly():
        return

    st.subheader("Task Specificity vs Generality")
    st.caption(
        "For a selected task, classify artifacts as exclusive to the task, shared with few tasks, or broadly shared infrastructure."
    )

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    state_key = "task_specificity_state"
    global_state_key = "task_specificity_global_stats_state"
    generic_threshold_for_stats = int(st.session_state.get("task_specificity_generic_threshold", 8))

    if global_state_key not in st.session_state:
        try:
            global_rows, _, _ = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ARTIFACT_TASK_SHARE_QUERY,
                row_limit=max(int(row_limit), 200000),
                params={"top_n": max(int(row_limit), 200000)},
            )
            st.session_state[global_state_key] = global_rows
        except Exception as exc:
            st.warning(f"Could not load global specificity statistics: {exc}")
            st.session_state[global_state_key] = []

    global_rows = st.session_state.get(global_state_key, [])
    global_df = pd.DataFrame(global_rows)
    if not global_df.empty:
        global_df["taskShareCount"] = pd.to_numeric(global_df.get("taskShareCount", 0), errors="coerce").fillna(0).astype(int)

        def top_task_ratio(frame: pd.DataFrame, ratio_type: str) -> Tuple[str, float, int]:
            if frame.empty:
                return "N/A", 0.0, 0

            summary = (
                frame.groupby("task", as_index=False)
                .agg(
                    totalArtifacts=("artifactKey", "count"),
                    exclusiveCount=("taskShareCount", lambda s: int((s <= 1).sum())),
                    genericCount=("taskShareCount", lambda s: int((s >= generic_threshold_for_stats).sum())),
                )
            )
            if summary.empty:
                return "N/A", 0.0, 0

            if ratio_type == "exclusive":
                summary["ratio"] = summary.apply(
                    lambda r: float(r["exclusiveCount"]) / float(r["totalArtifacts"]) if float(r["totalArtifacts"]) > 0 else 0.0,
                    axis=1,
                )
                ordered = summary.sort_values(["ratio", "exclusiveCount", "totalArtifacts", "task"], ascending=[False, False, False, True])
                best = ordered.iloc[0]
                return str(best["task"]), float(best["ratio"]), int(best["exclusiveCount"])

            summary["ratio"] = summary.apply(
                lambda r: float(r["genericCount"]) / float(r["totalArtifacts"]) if float(r["totalArtifacts"]) > 0 else 0.0,
                axis=1,
            )
            ordered = summary.sort_values(["ratio", "genericCount", "totalArtifacts", "task"], ascending=[False, False, False, True])
            best = ordered.iloc[0]
            return str(best["task"]), float(best["ratio"]), int(best["genericCount"])

        model_df = global_df[global_df["artifactType"] == "Model"].copy()

        top_exclusive_all = top_task_ratio(global_df, "exclusive")
        top_exclusive_model = top_task_ratio(model_df, "exclusive")
        top_generic_all = top_task_ratio(global_df, "generic")
        top_generic_model = top_task_ratio(model_df, "generic")

        per_task_summary = (
            global_df.groupby("task", as_index=False)
            .agg(
                totalArtifacts=("artifactKey", "count"),
                exclusiveCount=("taskShareCount", lambda s: int((s <= 1).sum())),
                genericCount=("taskShareCount", lambda s: int((s >= generic_threshold_for_stats).sum())),
            )
        )

        per_task_summary["exclusiveRatioPct"] = per_task_summary.apply(
            lambda r: (100.0 * float(r["exclusiveCount"]) / float(r["totalArtifacts"])) if float(r["totalArtifacts"]) > 0 else 0.0,
            axis=1,
        )
        per_task_summary["genericRatioPct"] = per_task_summary.apply(
            lambda r: (100.0 * float(r["genericCount"]) / float(r["totalArtifacts"])) if float(r["totalArtifacts"]) > 0 else 0.0,
            axis=1,
        )

        type_count_df = (
            global_df.groupby(["task", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "artifactTypeCount"})
        )
        type_count_pivot = (
            type_count_df.pivot(index="task", columns="artifactType", values="artifactTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )

        composition_df = per_task_summary.merge(type_count_pivot, on="task", how="left")

        artifact_types = sorted([c for c in type_count_pivot.columns if c != "task"])

        exclusive_type_df = (
            global_df[global_df["taskShareCount"] <= 1]
            .groupby(["task", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "exclusiveTypeCount"})
        )
        generic_type_df = (
            global_df[global_df["taskShareCount"] >= generic_threshold_for_stats]
            .groupby(["task", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "genericTypeCount"})
        )

        exclusive_type_pivot = (
            exclusive_type_df.pivot(index="task", columns="artifactType", values="exclusiveTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )
        generic_type_pivot = (
            generic_type_df.pivot(index="task", columns="artifactType", values="genericTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )

        exclusive_type_cols = []
        generic_type_cols = []
        for artifact_type in artifact_types:
            exc_col = f"exclusive_{artifact_type}Count"
            gen_col = f"generic_{artifact_type}Count"
            exclusive_type_cols.append(exc_col)
            generic_type_cols.append(gen_col)
            if artifact_type in exclusive_type_pivot.columns:
                exclusive_type_pivot = exclusive_type_pivot.rename(columns={artifact_type: exc_col})
            else:
                exclusive_type_pivot[exc_col] = 0

            if artifact_type in generic_type_pivot.columns:
                generic_type_pivot = generic_type_pivot.rename(columns={artifact_type: gen_col})
            else:
                generic_type_pivot[gen_col] = 0

        keep_exc_cols = ["task"] + exclusive_type_cols
        keep_gen_cols = ["task"] + generic_type_cols
        exclusive_type_pivot = exclusive_type_pivot[keep_exc_cols]
        generic_type_pivot = generic_type_pivot[keep_gen_cols]

        composition_df = composition_df.merge(exclusive_type_pivot, on="task", how="left")
        composition_df = composition_df.merge(generic_type_pivot, on="task", how="left")
        for col in exclusive_type_cols + generic_type_cols:
            if col not in composition_df.columns:
                composition_df[col] = 0
            composition_df[col] = pd.to_numeric(composition_df[col], errors="coerce").fillna(0).astype(int)

        for artifact_type in artifact_types:
            exc_ratio_col = f"exclusive{artifact_type}RatioPct"
            gen_ratio_col = f"generic{artifact_type}RatioPct"
            exc_count_col = f"exclusive_{artifact_type}Count"
            gen_count_col = f"generic_{artifact_type}Count"
            composition_df[exc_ratio_col] = composition_df.apply(
                lambda r: (100.0 * float(r.get(exc_count_col, 0)) / float(r.get(artifact_type, 0))) if float(r.get(artifact_type, 0)) > 0 else 0.0,
                axis=1,
            )
            composition_df[gen_ratio_col] = composition_df.apply(
                lambda r: (100.0 * float(r.get(gen_count_col, 0)) / float(r.get(artifact_type, 0))) if float(r.get(artifact_type, 0)) > 0 else 0.0,
                axis=1,
            )

        composition_df["exclusiveRatioPct"] = composition_df["exclusiveRatioPct"].round(2)
        composition_df["genericRatioPct"] = composition_df["genericRatioPct"].round(2)
        for artifact_type in artifact_types:
            type_count_col = artifact_type
            exc_ratio_col = f"exclusive{artifact_type}RatioPct"
            gen_ratio_col = f"generic{artifact_type}RatioPct"
            composition_df[exc_ratio_col] = composition_df.apply(
                lambda r: "-" if float(r.get(type_count_col, 0)) <= 0 else round(float(r.get(exc_ratio_col, 0.0)), 2),
                axis=1,
            )
            composition_df[gen_ratio_col] = composition_df.apply(
                lambda r: "-" if float(r.get(type_count_col, 0)) <= 0 else round(float(r.get(gen_ratio_col, 0.0)), 2),
                axis=1,
            )

        composition_df = composition_df.sort_values(
            ["exclusiveRatioPct", "totalArtifacts", "task"],
            ascending=[False, False, True],
        )

        st.markdown("### General statistics")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Top exclusive ratio (all)", f"{top_exclusive_all[1] * 100.0:.1f}%", top_exclusive_all[0])
        g2.metric("Top exclusive ratio (model)", f"{top_exclusive_model[1] * 100.0:.1f}%", top_exclusive_model[0])
        g3.metric("Top generic ratio (all)", f"{top_generic_all[1] * 100.0:.1f}%", top_generic_all[0])
        g4.metric("Top generic ratio (model)", f"{top_generic_model[1] * 100.0:.1f}%", top_generic_model[0])

        st.caption(f"Generic ratio uses current threshold: taskShareCount >= {generic_threshold_for_stats}")

        st.markdown("### General statistics table (all SETasks)")
        st.caption("Ordered by exclusive ratio. Includes overall and artifact-type exclusive/generic ratios.")

        base_cols = [
            "task",
            "totalArtifacts",
            "exclusiveRatioPct",
            "genericRatioPct",
        ]
        type_ratio_cols = []
        for artifact_type in artifact_types:
            exc_col = f"exclusive{artifact_type}RatioPct"
            gen_col = f"generic{artifact_type}RatioPct"
            if exc_col in composition_df.columns:
                type_ratio_cols.append(exc_col)
            if gen_col in composition_df.columns:
                type_ratio_cols.append(gen_col)

        display_cols = base_cols + type_ratio_cols

        st.dataframe(
            composition_df[display_cols],
            use_container_width=True,
            height=520,
        )

        activity_map_state_key = "task_specificity_activity_map_state"
        if activity_map_state_key not in st.session_state:
            try:
                task_activity_rows, _, _ = get_data_with_fallback(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    query=TASK_ACTIVITY_BY_TASK_QUERY,
                    row_limit=max(int(row_limit), 10000),
                )
                st.session_state[activity_map_state_key] = task_activity_rows
            except Exception as exc:
                st.warning(f"Could not load task-activity mapping: {exc}")
                st.session_state[activity_map_state_key] = []

        task_activity_rows = st.session_state.get(activity_map_state_key, [])
        task_to_activity: Dict[str, str] = {}
        for row in task_activity_rows:
            task_name = str(row.get("task", "")).strip()
            activities = [str(a).strip() for a in (row.get("activities") or []) if str(a).strip()]
            if not task_name:
                continue
            task_to_activity[task_name] = activities[0] if activities else "NoActivity"

        activity_df = global_df.copy()
        activity_df["seActivity"] = activity_df["task"].map(lambda t: task_to_activity.get(str(t), "NoActivity"))

        activity_summary = (
            activity_df.groupby("seActivity", as_index=False)
            .agg(
                totalArtifacts=("artifactKey", "count"),
                exclusiveCount=("taskShareCount", lambda s: int((s <= 1).sum())),
                genericCount=("taskShareCount", lambda s: int((s >= generic_threshold_for_stats).sum())),
            )
        )
        activity_summary["exclusiveRatioPct"] = activity_summary.apply(
            lambda r: (100.0 * float(r["exclusiveCount"]) / float(r["totalArtifacts"])) if float(r["totalArtifacts"]) > 0 else 0.0,
            axis=1,
        )
        activity_summary["genericRatioPct"] = activity_summary.apply(
            lambda r: (100.0 * float(r["genericCount"]) / float(r["totalArtifacts"])) if float(r["totalArtifacts"]) > 0 else 0.0,
            axis=1,
        )

        act_type_count_df = (
            activity_df.groupby(["seActivity", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "artifactTypeCount"})
        )
        act_type_count_pivot = (
            act_type_count_df.pivot(index="seActivity", columns="artifactType", values="artifactTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )
        activity_comp_df = activity_summary.merge(act_type_count_pivot, on="seActivity", how="left")

        act_exclusive_type_df = (
            activity_df[activity_df["taskShareCount"] <= 1]
            .groupby(["seActivity", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "exclusiveTypeCount"})
        )
        act_generic_type_df = (
            activity_df[activity_df["taskShareCount"] >= generic_threshold_for_stats]
            .groupby(["seActivity", "artifactType"], as_index=False)
            .size()
            .rename(columns={"size": "genericTypeCount"})
        )
        act_exclusive_pivot = (
            act_exclusive_type_df.pivot(index="seActivity", columns="artifactType", values="exclusiveTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )
        act_generic_pivot = (
            act_generic_type_df.pivot(index="seActivity", columns="artifactType", values="genericTypeCount")
            .fillna(0)
            .astype(int)
            .reset_index()
        )

        act_exclusive_cols = []
        act_generic_cols = []
        for artifact_type in artifact_types:
            exc_col = f"exclusive_{artifact_type}Count"
            gen_col = f"generic_{artifact_type}Count"
            act_exclusive_cols.append(exc_col)
            act_generic_cols.append(gen_col)

            if artifact_type in act_exclusive_pivot.columns:
                act_exclusive_pivot = act_exclusive_pivot.rename(columns={artifact_type: exc_col})
            else:
                act_exclusive_pivot[exc_col] = 0

            if artifact_type in act_generic_pivot.columns:
                act_generic_pivot = act_generic_pivot.rename(columns={artifact_type: gen_col})
            else:
                act_generic_pivot[gen_col] = 0

        act_exclusive_pivot = act_exclusive_pivot[["seActivity"] + act_exclusive_cols]
        act_generic_pivot = act_generic_pivot[["seActivity"] + act_generic_cols]

        activity_comp_df = activity_comp_df.merge(act_exclusive_pivot, on="seActivity", how="left")
        activity_comp_df = activity_comp_df.merge(act_generic_pivot, on="seActivity", how="left")
        for col in act_exclusive_cols + act_generic_cols:
            if col not in activity_comp_df.columns:
                activity_comp_df[col] = 0
            activity_comp_df[col] = pd.to_numeric(activity_comp_df[col], errors="coerce").fillna(0).astype(int)

        for artifact_type in artifact_types:
            exc_ratio_col = f"exclusive{artifact_type}RatioPct"
            gen_ratio_col = f"generic{artifact_type}RatioPct"
            exc_count_col = f"exclusive_{artifact_type}Count"
            gen_count_col = f"generic_{artifact_type}Count"
            activity_comp_df[exc_ratio_col] = activity_comp_df.apply(
                lambda r: (100.0 * float(r.get(exc_count_col, 0)) / float(r.get(artifact_type, 0))) if float(r.get(artifact_type, 0)) > 0 else 0.0,
                axis=1,
            )
            activity_comp_df[gen_ratio_col] = activity_comp_df.apply(
                lambda r: (100.0 * float(r.get(gen_count_col, 0)) / float(r.get(artifact_type, 0))) if float(r.get(artifact_type, 0)) > 0 else 0.0,
                axis=1,
            )

        activity_comp_df["exclusiveRatioPct"] = activity_comp_df["exclusiveRatioPct"].round(2)
        activity_comp_df["genericRatioPct"] = activity_comp_df["genericRatioPct"].round(2)
        for artifact_type in artifact_types:
            type_count_col = artifact_type
            exc_ratio_col = f"exclusive{artifact_type}RatioPct"
            gen_ratio_col = f"generic{artifact_type}RatioPct"
            activity_comp_df[exc_ratio_col] = activity_comp_df.apply(
                lambda r: "-" if float(r.get(type_count_col, 0)) <= 0 else round(float(r.get(exc_ratio_col, 0.0)), 2),
                axis=1,
            )
            activity_comp_df[gen_ratio_col] = activity_comp_df.apply(
                lambda r: "-" if float(r.get(type_count_col, 0)) <= 0 else round(float(r.get(gen_ratio_col, 0.0)), 2),
                axis=1,
            )

        activity_comp_df = activity_comp_df.sort_values(
            ["exclusiveRatioPct", "totalArtifacts", "seActivity"],
            ascending=[False, False, True],
        )

        activity_base_cols = [
            "seActivity",
            "totalArtifacts",
            "exclusiveRatioPct",
            "genericRatioPct",
        ]
        activity_type_ratio_cols = []
        for artifact_type in artifact_types:
            exc_col = f"exclusive{artifact_type}RatioPct"
            gen_col = f"generic{artifact_type}RatioPct"
            if exc_col in activity_comp_df.columns:
                activity_type_ratio_cols.append(exc_col)
            if gen_col in activity_comp_df.columns:
                activity_type_ratio_cols.append(gen_col)

        st.markdown("### Aggregated results by SEActivity")
        st.caption("Same ratio schema as task-level table, aggregated per SEActivity.")
        st.dataframe(
            activity_comp_df[activity_base_cols + activity_type_ratio_cols],
            use_container_width=True,
            height=420,
        )

    try:
        task_count_rows, _, _ = get_data_with_fallback(
            uri=uri,
            username=username,
            password=password,
            database=database,
            query=TASK_ARTIFACT_COUNTS_QUERY,
            row_limit=int(row_limit),
        )
    except Exception as exc:
        st.error(str(exc))
        return

    tasks = sorted({str(row.get("task")).strip() for row in task_count_rows if row.get("task")})
    if not tasks:
        st.info("No tasks found.")
        return

    col_task, col_few, col_gen, col_run = st.columns([2, 1, 1, 1])
    selected_task = col_task.selectbox("Task", tasks, key="task_specificity_task")
    few_threshold = col_few.slider("Few-task max", min_value=2, max_value=10, value=3, step=1, key="task_specificity_few_threshold")
    generic_threshold = col_gen.slider("Generic min", min_value=3, max_value=30, value=8, step=1, key="task_specificity_generic_threshold")
    run_clicked = col_run.button("Load", type="primary", key="task_specificity_load")

    if generic_threshold <= few_threshold:
        st.warning("Set 'Generic min' higher than 'Few-task max' to avoid overlapping categories.")

    if run_clicked or state_key not in st.session_state:
        try:
            specificity_rows, source, info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=TASK_ARTIFACT_SPECIFICITY_QUERY,
                row_limit=max(int(row_limit), 10000),
                params={"task_name": selected_task, "top_n": max(int(row_limit), 10000)},
            )

            if source == "online":
                st.success(info)
            else:
                st.warning(info)

            st.session_state[state_key] = {
                "task": selected_task,
                "rows": specificity_rows,
                "few_threshold": few_threshold,
                "generic_threshold": generic_threshold,
            }
        except Exception as exc:
            st.error(str(exc))
            return

    state = st.session_state.get(state_key, {})
    rows = state.get("rows", [])
    if not rows:
        st.info("No artifacts were returned for this task.")
        return

    selected_task = state.get("task", selected_task)
    few_threshold = int(state.get("few_threshold", few_threshold))
    generic_threshold = int(state.get("generic_threshold", generic_threshold))

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No artifacts were returned for this task.")
        return

    df["taskShareCount"] = pd.to_numeric(df.get("taskShareCount", 0), errors="coerce").fillna(0).astype(int)

    def classify_specificity(shared_count: int) -> str:
        if shared_count <= 1:
            return "Exclusive to task"
        if shared_count <= few_threshold:
            return "Semi-specific"
        if shared_count >= generic_threshold:
            return "Generic infrastructure"
        return "Moderately shared"

    df["specificityClass"] = df["taskShareCount"].map(classify_specificity)

    class_order = [
        "Exclusive to task",
        "Semi-specific",
        "Moderately shared",
        "Generic infrastructure",
    ]

    class_counts = (
        df.groupby("specificityClass", as_index=False)
        .size()
        .rename(columns={"size": "artifactCount"})
    )

    class_counts["specificityClass"] = pd.Categorical(
        class_counts["specificityClass"],
        categories=class_order,
        ordered=True,
    )
    class_counts = class_counts.sort_values("specificityClass")
    total_artifacts = int(class_counts["artifactCount"].sum())
    class_counts["pct"] = class_counts["artifactCount"].map(lambda x: (100.0 * float(x) / float(total_artifacts)) if total_artifacts > 0 else 0.0)

    st.markdown(f"### Specificity profile for: {selected_task}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total artifacts", total_artifacts)
    m2.metric(
        "Exclusive",
        int(class_counts.loc[class_counts["specificityClass"] == "Exclusive to task", "artifactCount"].sum()),
    )
    m3.metric(
        "Semi-specific",
        int(class_counts.loc[class_counts["specificityClass"] == "Semi-specific", "artifactCount"].sum()),
    )
    m4.metric(
        "Generic",
        int(class_counts.loc[class_counts["specificityClass"] == "Generic infrastructure", "artifactCount"].sum()),
    )

    fig = px.bar(
        class_counts,
        x="specificityClass",
        y="artifactCount",
        text="pct",
        color="specificityClass",
        category_orders={"specificityClass": class_order},
        labels={"specificityClass": "Specificity class", "artifactCount": "Artifact count"},
        title="Task specificity vs generality",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=420, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    if "artifactType" in df.columns:
        type_breakdown = (
            df.groupby(["artifactType", "specificityClass"], as_index=False)
            .size()
            .rename(columns={"size": "artifactCount"})
        )
        type_breakdown["specificityClass"] = pd.Categorical(
            type_breakdown["specificityClass"],
            categories=class_order,
            ordered=True,
        )
        type_breakdown = type_breakdown.sort_values(["artifactType", "specificityClass"])

        type_fig = px.bar(
            type_breakdown,
            x="artifactType",
            y="artifactCount",
            color="specificityClass",
            barmode="stack",
            category_orders={"specificityClass": class_order},
            labels={"artifactType": "Artifact type", "artifactCount": "Artifact count", "specificityClass": "Specificity"},
            title="Specificity composition by artifact type",
        )
        type_fig.update_layout(height=460)
        st.plotly_chart(type_fig, use_container_width=True)

    st.markdown("### Artifact-level details")
    detail_cols = [c for c in ["artifactKey", "artifactType", "taskShareCount", "specificityClass", "taskGroups"] if c in df.columns]
    st.dataframe(
        df[detail_cols].sort_values(["taskShareCount", "artifactType", "artifactKey"], ascending=[True, True, True]),
        use_container_width=True,
        height=420,
    )

def render_query_explorer_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    st.subheader("Query Explorer")
    default_query = "MATCH (n) RETURN labels(n) AS labels, count(*) AS count"
    query = st.text_area("Cypher query", value=default_query, height=160)

    if query_looks_write_operation(query):
        st.warning("This app is intended for read queries. Use MATCH/RETURN style query.")

    if st.button("Run query / Refresh", type="primary"):
        if not password:
            st.error("Please provide Neo4j password.")
        elif query_looks_write_operation(query):
            st.error("Write-style queries are blocked in this viewer. Use a read query.")
        else:
            try:
                rows, source, info = get_data_with_fallback(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    query=query,
                    row_limit=int(row_limit),
                )
                if source == "online":
                    st.success(info)
                else:
                    st.warning(info)
                df = pd.DataFrame(rows)
                st.subheader(f"Results ({len(df)} rows)")
                st.dataframe(df, use_container_width=True)
            except Exception as exc:
                st.error(str(exc))


def render_cache_page() -> None:
    st.subheader("Cache")
    col_clear, _ = st.columns([1, 3])
    if col_clear.button("Clear cache file"):
        try:
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()
            st.success("Cache cleared.")
        except OSError as exc:
            st.error(f"Could not clear cache file: {exc}")

    cached_rows = cached_entries_for_ui()
    if cached_rows:
        st.dataframe(pd.DataFrame(cached_rows), use_container_width=True)
    else:
        st.info("No cache entries yet. Run a query while DB is online to seed cache.")


def render_analysis_2_placeholder(*_args, **_kwargs) -> None:
    st.info("Social Community analysis coming soon")


def render_analysis_3_placeholder(*_args, **_kwargs) -> None:
    st.info("Model Lineage analysis coming soon")


def render_analysis_4_placeholder(*_args, **_kwargs) -> None:
    st.info("Successful Models analysis coming soon")
