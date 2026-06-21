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
        SOCIAL_COMMUNITY_MODEL_PUBLISHER_DISTRIBUTION_QUERY,
        SOCIAL_COMMUNITY_TOP_CONTRIBUTORS_QUERY,
        SOCIAL_COMMUNITY_NETWORK_QUERY,
    )
except ImportError:
    from data import get_data_with_fallback
    from queries import (
        SOCIAL_COMMUNITY_COUNTS_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_OWNER_QUERY,
        SOCIAL_COMMUNITY_MODEL_LIKES_BY_ORG_TYPE_QUERY,
        SOCIAL_COMMUNITY_MODEL_PUBLISHER_DISTRIBUTION_QUERY,
        SOCIAL_COMMUNITY_TOP_CONTRIBUTORS_QUERY,
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
        return activities or ["NoActivity"]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return ["NoActivity"]


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


def _load_publisher_distribution_df(
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
        query=SOCIAL_COMMUNITY_MODEL_PUBLISHER_DISTRIBUTION_QUERY,
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

    for column in ["uniqueContributors", "uniqueModels"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    if "publisher_type" in df.columns:
        df["publisher_type"] = df["publisher_type"].fillna("Unknown").astype(str)
    if "organization_division" in df.columns:
        df["organization_division"] = df["organization_division"].fillna("N/A").astype(str)

    return df.sort_values(["publisher_type", "organization_division"], ascending=[True, True]).reset_index(drop=True)


def _load_top_contributors_df(
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
        query=SOCIAL_COMMUNITY_TOP_CONTRIBUTORS_QUERY,
        row_limit=row_limit,
        params={"top_limit": row_limit},
        prefer_cache=prefer_cache,
    )
    if source == "online":
        st.success(info)
    else:
        st.warning(info)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for column in ["uniqueModels", "uniqueSETasks"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    for column in ["contributor", "contributorType", "organizationDivision"]:
        if column in df.columns:
            df[column] = df[column].fillna("").astype(str)

    if "seTasks" in df.columns:
        df["seTasks"] = df["seTasks"].apply(
            lambda value: ", ".join([str(item).strip() for item in value if str(item).strip()]) if isinstance(value, list) else str(value)
        )

    return df.sort_values(["uniqueModels", "uniqueSETasks", "contributor"], ascending=[False, False, True]).reset_index(drop=True)


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
    else:
        df["seActivities"] = [["NoActivity"] for _ in range(len(df))]

    st.markdown("### Task Community Index")
    st.caption("Tasks are ranked by related users, then by model and dataset contributors.")

    metrics = st.columns(4)
    metrics[0].metric("Tasks", f"{len(df)}")
    metrics[1].metric(
        "Models by Users",
        f"{int(df['numModelsOwnedByUsers'].sum()) if 'numModelsOwnedByUsers' in df.columns else 0}",
    )
    metrics[2].metric("Related Users", f"{int(df['numUsers'].sum()) if 'numUsers' in df.columns else 0}")
    metrics[3].metric("Related Organizations", f"{int(df['numOrganizations'].sum()) if 'numOrganizations' in df.columns else 0}")

    if nav_page and nav_page != "All Tasks":
        st.caption(f"Focused view triggered from the {nav_page} navigation tab.")

    display_columns = [
        "seTask",
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
            max_display = 28
            panel_height = 620
            colors = {"user_pct": "#4a90d9", "org_pct": "#d94a4a", "orphan_pct": "#cccccc"}

            truncated_counts = {
                cat: max(0, int((dom_df["dominance"] == cat).sum()) - max_display)
                for cat in categories
            }
            if any(count > 0 for count in truncated_counts.values()):
                st.caption(
                    "Each dominance panel shows up to "
                    f"{max_display} tasks to keep all three charts approximately the same size and readable."
                )

            import plotly.express as _px
            for idx, cat in enumerate(categories):
                subset = dom_df[dom_df["dominance"] == cat].copy()
                if subset.empty:
                    cols[idx].markdown(f"**{cat}** — (0 tasks)")
                    continue

                if cat == "Org-Dominated":
                    subset = subset.sort_values("org_pct", ascending=True)
                elif cat == "User-Dominated":
                    subset = subset.sort_values("user_pct", ascending=True)
                else:
                    subset = subset.assign(balance_gap=(subset["user_pct"] - subset["org_pct"]).abs())
                    subset = subset.sort_values(["balance_gap", "orphan_pct"], ascending=[True, True])

                subset = subset.head(max_display)
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
                    title=(
                        f"{cat} ({len(subset)} shown"
                        + (f", +{truncated_counts[cat]} more" if truncated_counts[cat] > 0 else "")
                        + ")"
                    ),
                    labels={"pct": "% of Models", "owner_label": "Owner", "seTask": "SETask"},
                )

                fig.update_layout(
                    barmode="stack",
                    height=panel_height,
                    xaxis=dict(range=[0, 100], title="% of Models"),
                    showlegend=(idx == 0),
                    margin=dict(l=10, r=10, t=70, b=10),
                    title_font=dict(size=18),
                    font=dict(size=13),
                    legend=dict(font=dict(size=12), title=dict(text="Owner", font=dict(size=13))),
                )
                fig.update_xaxes(title_font=dict(size=14), tickfont=dict(size=12))
                fig.update_yaxes(title_font=dict(size=14), tickfont=dict(size=12), automargin=True)
                fig.update_traces(marker_line_color="#ffffff", marker_line_width=0.6, hovertemplate="%{x:.1f}%<extra>%{color}</extra>")
                cols[idx].plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not render ownership dominance visualization: {exc}")

    popularity_cols = {
        "seTask",
        "mostDownloadedModel",
        "mostDownloadedModelDownloads",
        "mostLikedModel",
        "mostLikedModelLikes",
    }
    if popularity_cols.issubset(df.columns):
        popularity_df = df[
            [
                "seTask",
                "mostDownloadedModel",
                "mostDownloadedModelDownloads",
                "mostLikedModel",
                "mostLikedModelLikes",
            ]
        ].copy()
        popularity_df = popularity_df.rename(
            columns={
                "seTask": "SETask",
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

    if {"seTask", "numHubContributors", "numProHubContributors", "proHubContributorRatio"}.issubset(df.columns):
        pro_df = df[["seTask", "numHubContributors", "numProHubContributors", "proHubContributorRatio"]].copy()
        pro_df["Pro User %"] = pro_df["proHubContributorRatio"].map(lambda value: f"{float(value) * 100:.2f}%")
        pro_df["proHubContributorRatio"] = pro_df["proHubContributorRatio"].map(lambda value: f"{float(value):.4f}")
        pro_df = pro_df.rename(
            columns={
                "seTask": "SETask",
                "numHubContributors": "Hub Contributors",
                "numProHubContributors": "Pro Hub Contributors",
                "proHubContributorRatio": "Pro User Ratio",
            }
        )
        pro_df = pro_df[["SETask", "Hub Contributors", "Pro Hub Contributors", "Pro User Ratio", "Pro User %"]]

        st.subheader("All Tasks Tab: Pro User Ratio by Task Hub Contributors")
        st.caption("Pro User Ratio = pro hub contributors / all hub contributors, where hub contributors are model, dataset, and paper publishers tied to the task.")
        st.dataframe(pro_df, use_container_width=True, height=320)

        st.download_button(
            "Download pro user ratio table (CSV)",
            data=pro_df.to_csv(index=False),
            file_name="social_community_task_pro_user_ratio.csv",
            mime="text/csv",
        )

    if {
        "seTask",
        "topModelContributor",
        "topModelContributorType",
        "topModelContributorModelCount",
        "modelContributorBusFactorRatio",
    }.issubset(df.columns):
        bus_df = df[
            [
                "seTask",
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
                "topModelContributor": "Top Model Publisher",
                "topModelContributorType": "Publisher Type",
                "topModelContributorModelCount": "Top Contributor Models",
                "modelContributorBusFactorRatio": "Bus Factor Ratio",
            }
        )

        st.markdown("### Bus Factor Analysis by Task")
        st.caption("Bus Factor Ratio = (models from top model publisher: user or organization) / (all models in the task).")
        st.dataframe(bus_df, use_container_width=True, height=320)

    dominance_columns = {"seTask", "numModelUserContributors", "numModelOrganizationContributors"}
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
            ["seTask", "numModelUserContributors", "numModelOrganizationContributors"]
        ].rename(
            columns={
                "seTask": "SETask",
                "numModelUserContributors": "Model Publishers (Users)",
                "numModelOrganizationContributors": "Model Publishers (Organizations)",
            }
        )

        org_dominated_df = dominance_df[dominance_df["dominance"] == "Organization Dominated"][
            ["seTask", "numModelUserContributors", "numModelOrganizationContributors"]
        ].rename(
            columns={
                "seTask": "SETask",
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

    st.divider()

    # ============ General Model Statistics by Publisher Type ============
    st.subheader("General Model Statistics by Publisher Type")
    st.caption("Overview of unique model counts and statistics across user publishers, organization publishers, and organization type divisions.")

    try:
        stats_data = []

        # User vs Organization model statistics from likes data
        if not likes_df.empty:
            user_models = likes_df[likes_df["owner_type"] == "User"].drop_duplicates(subset=["model_id"])
            org_models = likes_df[likes_df["owner_type"] == "Organization"].drop_duplicates(subset=["model_id"])

            stats_data.append({
                "Publisher Type": "User",
                "Total Unique Models": len(user_models),
                "Avg Likes": round(user_models["likes"].mean(), 2) if len(user_models) > 0 else 0,
                "Median Likes": int(user_models["likes"].median()) if len(user_models) > 0 else 0,
                "Min Likes": int(user_models["likes"].min()) if len(user_models) > 0 else 0,
                "Max Likes": int(user_models["likes"].max()) if len(user_models) > 0 else 0,
            })

            stats_data.append({
                "Publisher Type": "Organization",
                "Total Unique Models": len(org_models),
                "Avg Likes": round(org_models["likes"].mean(), 2) if len(org_models) > 0 else 0,
                "Median Likes": int(org_models["likes"].median()) if len(org_models) > 0 else 0,
                "Min Likes": int(org_models["likes"].min()) if len(org_models) > 0 else 0,
                "Max Likes": int(org_models["likes"].max()) if len(org_models) > 0 else 0,
            })

            stats_df = pd.DataFrame(stats_data)

            st.markdown("#### Model Publisher Type Statistics")
            st.dataframe(stats_df, use_container_width=True, height=160)

            # Create a visualization comparing user vs organization models
            comparison_data = [{
                "Category": "User-Owned",
                "Total Models": len(user_models),
            }, {
                "Category": "Organization-Owned",
                "Total Models": len(org_models),
            }]
            comparison_df = pd.DataFrame(comparison_data)

            fig_comparison = px.bar(
                comparison_df,
                x="Category",
                y="Total Models",
                title="Total Unique Models by Publisher Type",
                labels={"Total Models": "Model Count"},
                color="Category",
                color_discrete_map={"User-Owned": "#4a90d9", "Organization-Owned": "#d94a4a"},
            )
            fig_comparison.update_layout(height=380, showlegend=False)
            st.plotly_chart(fig_comparison, use_container_width=True)
        else:
            st.info("Load likes comparison data above to see model statistics by publisher type.")

        # Unique Contributor Distribution
        st.markdown("#### Unique Contributor Distribution")
        st.caption("Direct SEModel publisher counts grouped by user type, organization type, and organization divisions.")

        publisher_state_key = "social_community_publisher_distribution_rows"
        load_publisher_clicked = st.button(
            "Load publisher distribution",
            type="primary",
            key="social_community_publisher_distribution_load",
        )

        if load_publisher_clicked or publisher_state_key not in st.session_state:
            try:
                st.session_state[publisher_state_key] = _load_publisher_distribution_df(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    row_limit=max(int(row_limit), 5000000),
                    prefer_cache=load_clicked,
                )
            except Exception as exc:
                st.error(f"Could not load publisher distribution: {exc}")
                st.session_state[publisher_state_key] = pd.DataFrame()

        publisher_df = st.session_state.get(publisher_state_key, pd.DataFrame())
        if publisher_df.empty:
            st.info("Load publisher distribution to see unique contributor counts by owner type and organization division.")
        else:
            display_publisher_df = publisher_df.rename(
                columns={
                    "publisher_type": "Publisher Type",
                    "organization_division": "Organization Division",
                    "uniqueContributors": "Unique Contributors",
                    "uniqueModels": "Unique Models",
                }
            )
            st.dataframe(display_publisher_df, use_container_width=True, height=220)

            pub_fig = px.bar(
                display_publisher_df,
                x="Organization Division",
                y="Unique Contributors",
                color="Publisher Type",
                barmode="group",
                title="Unique Contributors by Publisher Type and Organization Division",
                labels={
                    "Organization Division": "Organization Division",
                    "Unique Contributors": "Unique Contributors",
                    "Publisher Type": "Publisher Type",
                },
            )
            pub_fig.update_layout(height=420, xaxis_tickangle=-20)
            st.plotly_chart(pub_fig, use_container_width=True)

            model_fig = px.bar(
                display_publisher_df,
                x="Organization Division",
                y="Unique Models",
                color="Publisher Type",
                barmode="group",
                title="Unique Models by Publisher Type and Organization Division",
                labels={
                    "Organization Division": "Organization Division",
                    "Unique Models": "Unique Models",
                    "Publisher Type": "Publisher Type",
                },
            )
            model_fig.update_layout(height=420, xaxis_tickangle=-20)
            st.plotly_chart(model_fig, use_container_width=True)

            st.download_button(
                "Download publisher distribution (CSV)",
                data=display_publisher_df.to_csv(index=False),
                file_name="social_community_publisher_distribution.csv",
                mime="text/csv",
            )

        st.markdown("#### Top 100 SEModel Contributors")
        st.caption("Top contributors ranked by unique SEModel publications, with contributor type and published task count.")

        top_contrib_state_key = "social_community_top_contributors_rows"
        load_top_contrib_clicked = st.button(
            "Load top 100 contributors",
            type="primary",
            key="social_community_top_contributors_load",
        )

        if load_top_contrib_clicked or top_contrib_state_key not in st.session_state:
            try:
                st.session_state[top_contrib_state_key] = _load_top_contributors_df(
                    uri=uri,
                    username=username,
                    password=password,
                    database=database,
                    row_limit=100,
                    prefer_cache=load_clicked,
                )
            except Exception as exc:
                st.error(f"Could not load top contributors: {exc}")
                st.session_state[top_contrib_state_key] = pd.DataFrame()

        top_contrib_df = st.session_state.get(top_contrib_state_key, pd.DataFrame())
        if top_contrib_df.empty:
            st.info("Load the top 100 contributors table to see the highest-volume SEModel publishers.")
        else:
            display_top_contrib_df = top_contrib_df.rename(
                columns={
                    "contributor": "Contributor",
                    "contributorType": "Contributor Type",
                    "organizationDivision": "Organization Division",
                    "uniqueModels": "Unique Models",
                    "uniqueSETasks": "Unique SETasks",
                    "seTasks": "SETasks",
                }
            )
            st.dataframe(display_top_contrib_df, use_container_width=True, height=420)

            st.download_button(
                "Download top 100 contributors (CSV)",
                data=display_top_contrib_df.to_csv(index=False),
                file_name="social_community_top_100_contributors.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.warning(f"Could not render model statistics by publisher type: {exc}")
