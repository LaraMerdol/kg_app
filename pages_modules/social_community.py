"""Social Community analysis pages."""

from typing import List

import pandas as pd
import streamlit as st

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
    from ..data import get_data_with_fallback
    from ..queries import (
        SOCIAL_COMMUNITY_COUNTS_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_OWNER_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_ORG_TYPE_QUERY,
        SOCIAL_COMMUNITY_NETWORK_QUERY,
    )
except ImportError:
    from data import get_data_with_fallback
    from queries import (
        SOCIAL_COMMUNITY_COUNTS_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_OWNER_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_ORG_TYPE_QUERY,
        SOCIAL_COMMUNITY_NETWORK_QUERY,
    )


def _prepare_task_index_df(rows: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for column in [
        "numModels",
        "numDatasets",
        "numPapers",
        "numBenchmarks",
        "numModelUserContributors",
        "numModelOrganizationContributors",
        "numDatasetUserContributors",
        "numDatasetOrganizationContributors",
        "numPaperUserContributors",
        "numPaperOrganizationContributors",
        "numBenchmarkUserContributors",
        "numBenchmarkOrganizationContributors",
        "numUsers",
        "numOrganizations",
        "topModelContributorModelCount",
        "mostDownloadedModelDownloads",
        "mostLikedModelLikes",
        "numHubContributors",
        "numProHubContributors",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    for column in ["modelContributorBusFactorRatio", "proHubContributorRatio"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    if "seTask" in df.columns:
        df["seTask"] = df["seTask"].fillna("").astype(str)

    sort_cols = [col for col in ["numUsers", "numModels", "numDatasets", "seTask"] if col in df.columns]
    if sort_cols:
        ascending = [False, False, False, True][: len(sort_cols)]
        df = df.sort_values(sort_cols, ascending=ascending)

    return df.reset_index(drop=True)


def _normalize_activities(value: object) -> List[str]:
    if isinstance(value, list):
        activities = [str(item).strip() for item in value if str(item).strip()]
        return activities or ["Unmapped"]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return ["Unmapped"]


def _model_publisher_dominance(user_count: int, org_count: int) -> str:
    if user_count > org_count:
        return "User Dominated"
    if org_count > user_count:
        return "Organization Dominated"
    return "Tie"


def _load_likes_by_owner_df(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
    prefer_cache: bool,
) -> pd.DataFrame:
    rows, source, info = get_data_with_fallback(
        uri=uri,
        username=username,
        password=password,
        database=database,
        query=SOCIAL_COMMUNITY_MODEL_LIKES_BY_OWNER_QUERY,
        row_limit=row_limit,
        prefer_cache=prefer_cache,
    )
    if source == "online":
        st.success(info)
    else:
        st.warning(info)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for column in ["likes"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    if "model_id" in df.columns:
        df["model_id"] = df["model_id"].fillna("").astype(str)
    df["owner_type"] = df["owner_type"].fillna("Unknown").astype(str)
    return df.sort_values(["likes", "owner_type", "model_id"], ascending=[False, True, True]).reset_index(drop=True)


def _load_likes_by_org_type_df(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
    prefer_cache: bool,
) -> pd.DataFrame:
    rows, source, info = get_data_with_fallback(
        uri=uri,
        username=username,
        password=password,
        database=database,
        query=SOCIAL_COMMUNITY_MODEL_LIKES_BY_ORG_TYPE_QUERY,
        row_limit=row_limit,
        prefer_cache=prefer_cache,
    )
    if source == "online":
        st.success(info)
    else:
        st.warning(info)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if "likes" in df.columns:
        df["likes"] = pd.to_numeric(df["likes"], errors="coerce").fillna(0.0)
    if "model_id" in df.columns:
        df["model_id"] = df["model_id"].fillna("").astype(str)
    df["organization_type"] = df["organization_type"].fillna("Unknown").astype(str)
    return df.sort_values(["likes", "organization_type", "model_id"], ascending=[False, True, True]).reset_index(drop=True)


def render_analysis_2_placeholder(
    uri: str,
    username: str,
    password: str,
    database: str,
    row_limit: int,
    nav_page: str | None = None,
) -> None:
    """Render Social Community as task-level contribution summary tables."""
    if not _ensure_plotly():
        return

    st.subheader("Social Community Analysis")
    st.caption("Task-wise summary of artifact counts and contributor counts (no graph visualization).")

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    index_key = "social_community_task_index_rows"
    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load community index (cache first)", type="primary", key="social_community_load")
    refresh_clicked = col_refresh.button("Refresh community index from DB", key="social_community_refresh")

    if load_clicked or refresh_clicked or index_key not in st.session_state:
        task_limit = min(max(int(row_limit), 1), 200)
        query_params = {"task_limit": task_limit}

        with st.spinner("Loading community counts..."):
            try:
                counts_rows, source, info = get_data_with_fallback(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    query=SOCIAL_COMMUNITY_COUNTS_QUERY,
                    row_limit=task_limit,
                    params=query_params,
                    prefer_cache=load_clicked,
                )
                if source == "online":
                    st.success(info)
                else:
                    st.warning(info)
            except Exception as exc:
                st.error(f"Could not load community counts: {exc}")
                st.session_state[index_key] = []
                counts_rows = []

        if counts_rows:
            with st.spinner("Loading network stats (users, organizations, hub contributors)..."):
                try:
                    network_rows, _, net_info = get_data_with_fallback(
                        uri=uri,
                        username=username,
                        password=password,
                        database=database,
                        query=SOCIAL_COMMUNITY_NETWORK_QUERY,
                        row_limit=task_limit,
                        params=query_params,
                        prefer_cache=load_clicked,
                    )
                    st.info(f"Network stats: {net_info}")
                except Exception as exc:
                    st.warning(f"Network stats unavailable (memory limit): {exc}")
                    network_rows = []

            counts_by_task = {r["seTask"]: r for r in counts_rows}
            for net_row in network_rows:
                task = net_row.get("seTask")
                if task in counts_by_task:
                    counts_by_task[task].update(net_row)
            st.session_state[index_key] = list(counts_by_task.values())

    rows = st.session_state.get(index_key, [])
    if not rows:
        st.info("Load the community index to browse task-level contribution stats.")
        return

    df = _prepare_task_index_df(rows)
    if df.empty:
        st.info("No SETasks were returned from the database.")
        return

    if "seActivities" in df.columns:
        df["seActivities"] = df["seActivities"].apply(_normalize_activities)
        df["seActivity"] = df["seActivities"].apply(lambda activities: ", ".join(activities))
    else:
        df["seActivities"] = [["Unmapped"] for _ in range(len(df))]
        df["seActivity"] = "Unmapped"

    st.markdown("### Task Community Index")
    st.caption("Tasks are ranked by related users, then by model and dataset contributors.")

    metrics = st.columns(7)
    metrics[0].metric("Tasks", f"{len(df)}")
    metrics[1].metric("Models", f"{int(df['numModels'].sum()) if 'numModels' in df.columns else 0}")
    metrics[2].metric("Datasets", f"{int(df['numDatasets'].sum()) if 'numDatasets' in df.columns else 0}")
    metrics[3].metric("Papers", f"{int(df['numPapers'].sum()) if 'numPapers' in df.columns else 0}")
    metrics[4].metric(
        "Models by Users",
        f"{int(df['numModelsOwnedByUsers'].sum()) if 'numModelsOwnedByUsers' in df.columns else 0}",
    )
    metrics[5].metric("Related Users", f"{int(df['numUsers'].sum()) if 'numUsers' in df.columns else 0}")
    metrics[6].metric("Related Organizations", f"{int(df['numOrganizations'].sum()) if 'numOrganizations' in df.columns else 0}")

    if nav_page and nav_page != "All Tasks":
        st.caption(f"Focused view triggered from the {nav_page} navigation tab.")

    display_columns = [
        "seTask",
        "seActivity",
        "numModels",
        "numDatasets",
        "numPapers",
        "numBenchmarks",
        "numModelsOwnedByUsers",
        "numModelsOwnedByOrganizations",
        "numDatasetUserContributors",
        "numDatasetOrganizationContributors",
        "numPaperUserContributors",
        "numPaperOrganizationContributors",
        "numBenchmarkUserContributors",
        "numBenchmarkOrganizationContributors",
        "numUsers",
        "numOrganizations",
        "topModelContributor",
        "topModelContributorType",
        "topModelContributorModelCount",
        "modelContributorBusFactorRatio",
        "mostDownloadedModel",
        "mostDownloadedModelDownloads",
        "mostLikedModel",
        "mostLikedModelLikes",
        "numHubContributors",
        "numProHubContributors",
        "proHubContributorRatio",
    ]
    visible_columns = [col for col in display_columns if col in df.columns]

    rename_map = {
        "seTask": "SETask",
        "seActivity": "SEActivity",
        "numModels": "Models",
        "numDatasets": "Datasets",
        "numPapers": "Papers",
        "numBenchmarks": "Benchmarks",
        "numModelsOwnedByUsers": "Models Owned by Users",
        "numModelsOwnedByOrganizations": "Models Owned by Organizations",
        "numDatasetUserContributors": "Dataset Contributors (Users)",
        "numDatasetOrganizationContributors": "Dataset Contributors (Organizations)",
        "numPaperUserContributors": "Paper Contributors (Users)",
        "numPaperOrganizationContributors": "Paper Contributors (Organizations)",
        "numBenchmarkUserContributors": "Benchmark Contributors (Users)",
        "numBenchmarkOrganizationContributors": "Benchmark Contributors (Organizations)",
        "numUsers": "All Related Users",
        "numOrganizations": "All Related Organizations",
        "topModelContributor": "Top Model Publisher",
        "topModelContributorType": "Top Publisher Type",
        "topModelContributorModelCount": "Top Contributor Models",
        "modelContributorBusFactorRatio": "Bus Factor Ratio (Model Publishers)",
        "mostDownloadedModel": "Most Downloaded Model",
        "mostDownloadedModelDownloads": "Most Downloaded Model Downloads",
        "mostLikedModel": "Most Liked Model",
        "mostLikedModelLikes": "Most Liked Model Likes",
        "numHubContributors": "Hub Contributors",
        "numProHubContributors": "Pro Hub Contributors",
        "proHubContributorRatio": "Pro User Ratio (Hub Contributors)",
    }

    summary_df = df[visible_columns].rename(columns=rename_map)
    st.dataframe(summary_df, use_container_width=True, height=460)

    st.download_button(
        "Download social community table (CSV)",
        data=summary_df.to_csv(index=False),
        file_name="social_community_task_summary.csv",
        mime="text/csv",
    )

    # ============ Ownership Dominance Visualization ============
    try:
        if "numModels" in df.columns and (
            "numModelsOwnedByUsers" in df.columns or "numModelsOwnedByOrganizations" in df.columns
        ):
            dom_df = df.copy()
            dom_df["numModelsOwnedByUsers"] = dom_df.get("numModelsOwnedByUsers", 0).fillna(0).astype(int) if hasattr(
                dom_df.get("numModelsOwnedByUsers", None), "fillna"
            ) else dom_df.get("numModelsOwnedByUsers", 0)
            dom_df["numModelsOwnedByOrganizations"] = dom_df.get("numModelsOwnedByOrganizations", 0).fillna(0).astype(int) if hasattr(
                dom_df.get("numModelsOwnedByOrganizations", None), "fillna"
            ) else dom_df.get("numModelsOwnedByOrganizations", 0)

            dom_df["numModels"] = dom_df["numModels"].fillna(0).astype(int)
            dom_df["user_count"] = dom_df["numModelsOwnedByUsers"].fillna(0).astype(int)
            dom_df["org_count"] = dom_df["numModelsOwnedByOrganizations"].fillna(0).astype(int)
            dom_df["orphan_count"] = dom_df.apply(lambda r: max(0, int(r["numModels"]) - int(r["user_count"]) - int(r["org_count"])), axis=1)
            dom_df["dominance_total"] = dom_df.apply(
                lambda r: int(r["user_count"]) + int(r["org_count"]) + int(r["orphan_count"]),
                axis=1,
            )

            def pct(n, total):
                return float(n) * 100.0 / float(total) if total and total > 0 else 0.0

            dom_df["user_pct"] = dom_df.apply(lambda r: pct(r["user_count"], r["dominance_total"]), axis=1)
            dom_df["org_pct"] = dom_df.apply(lambda r: pct(r["org_count"], r["dominance_total"]), axis=1)
            dom_df["orphan_pct"] = dom_df.apply(lambda r: pct(r["orphan_count"], r["dominance_total"]), axis=1)

            def classify_dominance(row):
                if row["org_pct"] >= 60:
                    return "Org-Dominated"
                elif row["user_pct"] >= 60:
                    return "User-Dominated"
                else:
                    return "Mixed"

            dom_df["dominance"] = dom_df.apply(classify_dominance, axis=1)

            st.markdown("### Ownership Dominance by Task")
            st.caption("Classifies tasks as Org-Dominated, User-Dominated, or Mixed based on % of models with publishers.")

            # Show distribution counts
            dist = dom_df["dominance"].value_counts().to_dict()
            dist_text = ", ".join([f"{k}: {v}" for k, v in dist.items()])
            st.text(f"Dominance distribution — {dist_text}")

            # Prepare categories and plotting order
            categories = ["Org-Dominated", "Mixed", "User-Dominated"]
            cols = st.columns(3)
            max_display = 200
            colors = {"user_pct": "#4a90d9", "org_pct": "#d94a4a", "orphan_pct": "#cccccc"}

            import plotly.express as _px
            for idx, cat in enumerate(categories):
                subset = dom_df[dom_df["dominance"] == cat].copy()
                if subset.empty:
                    cols[idx].markdown(f"**{cat}** — (0 tasks)")
                    continue

                subset = subset.sort_values("org_pct", ascending=True).head(max_display)
                plot_df = subset[["seTask", "user_pct", "org_pct", "orphan_pct"]].copy()

                # convert to long form for stacked bars
                long_df = plot_df.reset_index().melt(id_vars=["seTask"], value_vars=["user_pct", "org_pct", "orphan_pct"], var_name="owner", value_name="pct")
                owner_map = {"user_pct": "User", "org_pct": "Organization", "orphan_pct": "No Owner"}
                long_df["owner_label"] = long_df["owner"].map(owner_map)

                fig = _px.bar(
                    long_df,
                    y="seTask",
                    x="pct",
                    color="owner_label",
                    orientation="h",
                    category_orders={"owner_label": ["User", "Organization", "No Owner"], "seTask": plot_df["seTask"].tolist()},
                    color_discrete_map={"User": colors["user_pct"], "Organization": colors["org_pct"], "No Owner": colors["orphan_pct"]},
                    title=f"{cat} ({len(subset)} tasks)",
                    labels={"pct": "% of Models", "owner_label": "Owner", "seTask": "SETask"},
                )

                fig_height = max(100, 110 + 24 * len(plot_df))
                fig.update_layout(
                    barmode="stack",
                    height=fig_height,
                    xaxis=dict(range=[0, 100], title="% of Models"),
                    showlegend=(idx == 0),
                    margin=dict(l=10, r=10, t=55, b=10),
                    title_font=dict(size=18),
                    font=dict(size=13),
                    legend=dict(font=dict(size=12), title=dict(text="Owner", font=dict(size=13))),
                )
                fig.update_xaxes(title_font=dict(size=14), tickfont=dict(size=12))
                fig.update_yaxes(title_font=dict(size=14), tickfont=dict(size=12))
                fig.update_traces(marker_line_color="#ffffff", marker_line_width=0.6, hovertemplate="%{x:.1f}%<extra>%{color}</extra>")
                cols[idx].plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not render ownership dominance visualization: {exc}")

    popularity_cols = {
        "seTask",
        "seActivity",
        "mostDownloadedModel",
        "mostDownloadedModelDownloads",
        "mostLikedModel",
        "mostLikedModelLikes",
    }
    if popularity_cols.issubset(df.columns):
        popularity_df = df[
            [
                "seTask",
                "seActivity",
                "mostDownloadedModel",
                "mostDownloadedModelDownloads",
                "mostLikedModel",
                "mostLikedModelLikes",
            ]
        ].copy()
        popularity_df = popularity_df.rename(
            columns={
                "seTask": "SETask",
                "seActivity": "SEActivity",
                "mostDownloadedModel": "Most Downloaded Model",
                "mostDownloadedModelDownloads": "Downloads",
                "mostLikedModel": "Most Liked Model",
                "mostLikedModelLikes": "Likes",
            }
        )

        st.markdown("### Task Model Popularity Index")
        st.caption("Per task: top model by downloads and top model by likes.")
        st.dataframe(popularity_df, use_container_width=True, height=320)

        st.download_button(
            "Download task model popularity index (CSV)",
            data=popularity_df.to_csv(index=False),
            file_name="social_community_task_model_popularity_index.csv",
            mime="text/csv",
        )

    st.divider()

    st.subheader("Model Likes by Owner Type")
    st.caption("Compares SEModel likes for models published by users versus organizations.")

    likes_state_key = "social_community_model_likes_by_owner_rows"
    load_likes_clicked = st.button("Load likes comparison", type="primary", key="social_community_likes_load")

    if load_likes_clicked or likes_state_key not in st.session_state:
        try:
            st.session_state[likes_state_key] = _load_likes_by_owner_df(
                uri=uri,
                username=username,
                password=password,
                database=database,
                row_limit=max(int(row_limit), 200000000),
                prefer_cache=load_clicked,
            )
        except Exception as exc:
            st.error(f"Could not load likes comparison: {exc}")
            st.session_state[likes_state_key] = pd.DataFrame()

    likes_df = st.session_state.get(likes_state_key, pd.DataFrame())
    if likes_df.empty:
        st.info("Load the likes comparison to compare model popularity for user and organization publishers.")
    else:
        likes_summary = (
            likes_df.groupby("owner_type", as_index=False)
            .agg(
                n=("likes", "size"),
                mean_likes=("likes", "mean"),
                median_likes=("likes", "median"),
                min_likes=("likes", "min"),
                max_likes=("likes", "max"),
                std_likes=("likes", "std"),
            )
            .sort_values(["mean_likes", "owner_type"], ascending=[False, True])
            .reset_index(drop=True)
        )
        likes_summary["std_likes"] = likes_summary["std_likes"].fillna(0.0)

        st.markdown("#### Likes Summary Table")
        st.dataframe(
            likes_summary.assign(
                mean_likes=likes_summary["mean_likes"].round(2),
                median_likes=likes_summary["median_likes"].round(2),
                min_likes=likes_summary["min_likes"].round(2),
                max_likes=likes_summary["max_likes"].round(2),
                std_likes=likes_summary["std_likes"].round(2),
            ),
            use_container_width=True,
            height=220,
        )

        likes_bins_df = likes_df[["owner_type", "likes"]].copy()
        likes_bins_df["likes"] = likes_bins_df["likes"].fillna(0.0)

        bin_edges = [0, 10, 100, 500, 1000, 2000, float("inf")]
        bin_labels = ["<10", "10-100", "100-500", "500-1k", "1K-2K", "2K+"]
        likes_bins_df["like_bin"] = pd.cut(
            likes_bins_df["likes"],
            bins=bin_edges,
            labels=bin_labels,
            include_lowest=True,
            right=True,
        )

        chart_df = (
            likes_bins_df.groupby(["like_bin", "owner_type"], as_index=False)
            .size()
            .rename(columns={"size": "model_count"})
        )
        chart_df["owner_total"] = chart_df.groupby("owner_type")["model_count"].transform("sum")
        chart_df["model_ratio"] = chart_df.apply(
            lambda row: (float(row["model_count"]) / float(row["owner_total"])) if float(row["owner_total"]) > 0 else 0.0,
            axis=1,
        )
        chart_df["like_bin"] = pd.Categorical(chart_df["like_bin"], categories=bin_labels, ordered=True)
        chart_df = chart_df.sort_values(["like_bin", "owner_type"]).reset_index(drop=True)

        fig = px.bar(
            chart_df,
            y="owner_type",
            x="model_ratio",
            color="like_bin",
            orientation="h",
            barmode="stack",
            category_orders={"like_bin": bin_labels, "owner_type": ["User", "Organization"]},
            title="Horizontal Stacked Distribution of Model Likes by Owner Type",
            labels={"like_bin": "Likes Bin", "model_ratio": "Share of Owner Models", "owner_type": "Owner Type"},
        )
        fig.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
        fig.update_layout(height=420, legend_title_text="Likes Bin", xaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Model Likes by Organization Type")
    st.caption("Organization-only likes distribution, split by organization_type with normalized bars.")

    org_likes_state_key = "social_community_model_likes_by_org_type_rows"
    load_org_likes_clicked = st.button("Load organization type likes", type="secondary", key="social_community_org_likes_load")

    if load_org_likes_clicked or org_likes_state_key not in st.session_state:
        try:
            st.session_state[org_likes_state_key] = _load_likes_by_org_type_df(
                uri=uri,
                username=username,
                password=password,
                database=database,
                row_limit=max(int(row_limit), 5000000),
                prefer_cache=load_clicked,
            )
        except Exception as exc:
            st.error(f"Could not load organization type likes: {exc}")
            st.session_state[org_likes_state_key] = pd.DataFrame()

    org_likes_df = st.session_state.get(org_likes_state_key, pd.DataFrame())
    if org_likes_df.empty:
        st.info("Load organization type likes to compare likes distributions across organization categories.")
    else:
        org_type_summary = (
            org_likes_df.groupby("organization_type", as_index=False)
            .agg(
                n=("likes", "size"),
                mean_likes=("likes", "mean"),
                median_likes=("likes", "median"),
                min_likes=("likes", "min"),
                max_likes=("likes", "max"),
            )
            .sort_values(["n", "mean_likes", "organization_type"], ascending=[False, False, True])
            .reset_index(drop=True)
        )
        st.markdown("#### Organization Type Likes Summary")
        st.dataframe(
            org_type_summary.assign(
                mean_likes=org_type_summary["mean_likes"].round(2),
                median_likes=org_type_summary["median_likes"].round(2),
                min_likes=org_type_summary["min_likes"].round(2),
                max_likes=org_type_summary["max_likes"].round(2),
            ),
            use_container_width=True,
            height=260,
        )

        org_bins_df = org_likes_df[["organization_type", "likes"]].copy()
        org_bins_df["likes"] = org_bins_df["likes"].fillna(0.0)
        bin_edges = [0, 10, 100, 500, 1000, 2000, float("inf")]
        bin_labels = ["<10", "10-100", "100-500", "500-1k", "1K-2K", "2K+"]
        org_bins_df["like_bin"] = pd.cut(
            org_bins_df["likes"],
            bins=bin_edges,
            labels=bin_labels,
            include_lowest=True,
            right=True,
        )

        org_chart_df = (
            org_bins_df.groupby(["like_bin", "organization_type"], as_index=False)
            .size()
            .rename(columns={"size": "model_count"})
        )
        org_chart_df["org_total"] = org_chart_df.groupby("organization_type")["model_count"].transform("sum")
        org_chart_df["model_ratio"] = org_chart_df.apply(
            lambda row: (float(row["model_count"]) / float(row["org_total"])) if float(row["org_total"]) > 0 else 0.0,
            axis=1,
        )
        org_chart_df["like_bin"] = pd.Categorical(org_chart_df["like_bin"], categories=bin_labels, ordered=True)

        org_order = org_type_summary["organization_type"].tolist()
        org_fig = px.bar(
            org_chart_df,
            y="organization_type",
            x="model_ratio",
            color="like_bin",
            orientation="h",
            barmode="stack",
            category_orders={"like_bin": bin_labels, "organization_type": org_order},
            title="Horizontal Stacked Distribution of Model Likes by Organization Type",
            labels={
                "like_bin": "Likes Bin",
                "model_ratio": "Share of Organization-Type Models",
                "organization_type": "Organization Type",
            },
        )
        org_fig.update_traces(marker_line_color="#ffffff", marker_line_width=1.2)
        org_fig.update_layout(height=max(360, 80 + 38 * max(1, len(org_order))), legend_title_text="Likes Bin", xaxis_tickformat=".0%")
        st.plotly_chart(org_fig, use_container_width=True)

    st.divider()

    if {"seTask", "seActivity", "numHubContributors", "numProHubContributors", "proHubContributorRatio"}.issubset(df.columns):
        pro_df = df[["seTask", "seActivity", "numHubContributors", "numProHubContributors", "proHubContributorRatio"]].copy()
        pro_df["Pro User %"] = pro_df["proHubContributorRatio"].map(lambda value: f"{float(value) * 100:.2f}%")
        pro_df["proHubContributorRatio"] = pro_df["proHubContributorRatio"].map(lambda value: f"{float(value):.4f}")
        pro_df = pro_df.rename(
            columns={
                "seTask": "SETask",
                "seActivity": "SEActivity",
                "numHubContributors": "Hub Contributors",
                "numProHubContributors": "Pro Hub Contributors",
                "proHubContributorRatio": "Pro User Ratio",
            }
        )
        pro_df = pro_df[["SETask", "SEActivity", "Hub Contributors", "Pro Hub Contributors", "Pro User Ratio", "Pro User %"]]

        st.subheader("All Tasks Tab: Pro User Ratio by Task Hub Contributors")
        st.caption("Pro User Ratio = pro hub contributors / all hub contributors, where hub contributors are model, dataset, and paper publishers tied to the task.")
        st.dataframe(pro_df, use_container_width=True, height=320)

        st.download_button(
            "Download pro user ratio table (CSV)",
            data=pro_df.to_csv(index=False),
            file_name="social_community_task_pro_user_ratio.csv",
            mime="text/csv",
        )

        activity_rows = []
        for _, row in df.iterrows():
            task_name = str(row.get("seTask", ""))
            activities = _normalize_activities(row.get("seActivities", ["Unmapped"]))
            hub_count = int(row.get("numHubContributors", 0))
            pro_hub_count = int(row.get("numProHubContributors", 0))
            for activity in activities:
                activity_rows.append(
                    {
                        "SEActivity": activity,
                        "SETask": task_name,
                        "Hub Contributors": hub_count,
                        "Pro Hub Contributors": pro_hub_count,
                    }
                )

        activity_pro_df = pd.DataFrame(activity_rows)
        if not activity_pro_df.empty:
            activity_index_df = (
                activity_pro_df.groupby("SEActivity", as_index=False)
                .agg(
                    tasks=("SETask", "nunique"),
                    hubContributors=("Hub Contributors", "sum"),
                    proHubContributors=("Pro Hub Contributors", "sum"),
                )
                .sort_values(["proHubContributors", "hubContributors", "SEActivity"], ascending=[False, False, True])
                .reset_index(drop=True)
            )
            activity_index_df["proHubContributorRatio"] = activity_index_df.apply(
                lambda row: (
                    float(row["proHubContributors"]) / float(row["hubContributors"])
                    if int(row["hubContributors"]) > 0
                    else 0.0
                ),
                axis=1,
            )
            activity_index_df["Pro User Ratio"] = activity_index_df["proHubContributorRatio"].map(lambda v: f"{v:.4f}")
            activity_index_df["Pro User %"] = activity_index_df["proHubContributorRatio"].map(lambda v: f"{v * 100:.2f}%")

            activity_index_df = activity_index_df.rename(
                columns={
                    "tasks": "Tasks",
                    "hubContributors": "Hub Contributors",
                    "proHubContributors": "Pro Hub Contributors",
                }
            )
            activity_index_df = activity_index_df[
                ["SEActivity", "Tasks", "Hub Contributors", "Pro Hub Contributors", "Pro User Ratio", "Pro User %"]
            ]

            st.markdown("### SEActivity Pro User Ratio Index")
            st.caption("Aggregated index across tasks: hub contributors include model, dataset, and paper publishers.")
            st.dataframe(activity_index_df, use_container_width=True, height=320)

            st.download_button(
                "Download SEActivity pro user ratio index (CSV)",
                data=activity_index_df.to_csv(index=False),
                file_name="social_community_seactivity_pro_user_ratio_index.csv",
                mime="text/csv",
            )

    if {
        "seTask",
        "seActivity",
        "topModelContributor",
        "topModelContributorType",
        "topModelContributorModelCount",
        "modelContributorBusFactorRatio",
    }.issubset(df.columns):
        bus_df = df[
            [
                "seTask",
                "seActivity",
                "topModelContributor",
                "topModelContributorType",
                "topModelContributorModelCount",
                "modelContributorBusFactorRatio",
            ]
        ].copy()
        bus_df["modelContributorBusFactorRatio"] = bus_df["modelContributorBusFactorRatio"].map(lambda x: f"{x:.4f}")
        bus_df = bus_df.rename(
            columns={
                "seTask": "SETask",
                "seActivity": "SEActivity",
                "topModelContributor": "Top Model Publisher",
                "topModelContributorType": "Publisher Type",
                "topModelContributorModelCount": "Top Contributor Models",
                "modelContributorBusFactorRatio": "Bus Factor Ratio",
            }
        )

        st.markdown("### Bus Factor Analysis by Task")
        st.caption("Bus Factor Ratio = (models from top model publisher: user or organization) / (all models in the task).")
        st.dataframe(bus_df, use_container_width=True, height=320)

    dominance_columns = {"seTask", "seActivity", "numModelUserContributors", "numModelOrganizationContributors"}
    if dominance_columns.issubset(df.columns):
        dominance_df = df.copy()
        dominance_df["dominance"] = dominance_df.apply(
            lambda row: _model_publisher_dominance(
                int(row.get("numModelUserContributors", 0)),
                int(row.get("numModelOrganizationContributors", 0)),
            ),
            axis=1,
        )

        user_dominated_df = dominance_df[dominance_df["dominance"] == "User Dominated"][
            ["seTask", "seActivity", "numModelUserContributors", "numModelOrganizationContributors"]
        ].rename(
            columns={
                "seTask": "SETask",
                "seActivity": "SEActivity",
                "numModelUserContributors": "Model Publishers (Users)",
                "numModelOrganizationContributors": "Model Publishers (Organizations)",
            }
        )

        org_dominated_df = dominance_df[dominance_df["dominance"] == "Organization Dominated"][
            ["seTask", "seActivity", "numModelUserContributors", "numModelOrganizationContributors"]
        ].rename(
            columns={
                "seTask": "SETask",
                "seActivity": "SEActivity",
                "numModelUserContributors": "Model Publishers (Users)",
                "numModelOrganizationContributors": "Model Publishers (Organizations)",
            }
        )

        st.markdown("### Task Dominance by Model Publishers")
        dom_metrics = st.columns(3)
        dom_metrics[0].metric("User-Dominated Tasks", f"{len(user_dominated_df)}")
        dom_metrics[1].metric("Organization-Dominated Tasks", f"{len(org_dominated_df)}")
        dom_metrics[2].metric("Tied Tasks", f"{int((dominance_df['dominance'] == 'Tie').sum())}")

        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("#### Tasks Dominated by User Model Publishers")
            st.dataframe(user_dominated_df, use_container_width=True, height=280)
        with right_col:
            st.markdown("#### Tasks Dominated by Organization Model Publishers")
            st.dataframe(org_dominated_df, use_container_width=True, height=280)
