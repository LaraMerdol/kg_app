"""Model Lineage analysis pages."""

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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


def _render_all_tasks_lineage_table(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    st.subheader("All Tasks Model Lineage")
    st.caption("For each SETask, count lineage relation types and their shares among lineage edges.")
    confidence_is_null = st.toggle(
        "Use only relationships where confidence IS NULL",
        value=False,
        key="lineage_confidence_is_null_toggle",
        help="Off: confidence IS NOT NULL. On: confidence IS NULL.",
    )
    col_depth, col_pop = st.columns(2)
    max_lineage_depth = col_depth.slider(
        "Base-model max lineage depth",
        min_value=1,
        max_value=10,
        value=10,
        step=1,
        key="lineage_base_max_depth",
    )
    popularity_threshold = col_pop.slider(
        "Base-model popularity threshold",
        min_value=1,
        max_value=30,
        value=5,
        step=1,
        key="lineage_base_popularity_threshold",
    )

    col_load, col_refresh = st.columns([1, 1])
    load_clicked = col_load.button("Load all tasks (cache first)", type="primary", key="lineage_all_tasks_load")
    refresh_clicked = col_refresh.button("Refresh all tasks from DB", key="lineage_all_tasks_refresh")

    if not (load_clicked or refresh_clicked):
        st.info("Click Load to fetch model lineage stats for all tasks.")
        return

    if not password:
        st.error("Please provide Neo4j password in the sidebar.")
        return

    all_tasks_limit = max(int(row_limit), 10000)

    with st.spinner("Loading all tasks model lineage data..."):
        try:
            rows, source, info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_ALL_TASKS_QUERY,
                row_limit=all_tasks_limit,
                params={"confidence_is_null": confidence_is_null},
                prefer_cache=load_clicked,
            )

            if source == "online":
                st.success(info)
            else:
                st.warning(info)

            st.markdown("### Base Models by SETask")
            base_rows, base_source, base_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_BASE_MODELS_BY_TASK_QUERY,
                row_limit=all_tasks_limit,
                params={
                    "max_lineage_depth": int(max_lineage_depth),
                    "popularity_threshold": int(popularity_threshold),
                },
                prefer_cache=load_clicked,
            )
            if base_source == "online":
                st.success(base_info)
            else:
                st.warning(base_info)

            base_df = pd.DataFrame(base_rows)
            if base_df.empty:
                st.info("No base-model rows returned for SETasks.")
            else:
                base_df = _prepare_base_models_df(base_df)
                st.caption(
                    f"Base-model settings: max depth <= {int(max_lineage_depth)}, popularity threshold > {int(popularity_threshold)}"
                )
                st.dataframe(
                    base_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "avgLineageLength": st.column_config.NumberColumn("avgLineageLength", format="%.3f"),
                    },
                )

            st.markdown("### Model Lineage Length Distribution by SETask")
            task_len_rows, task_len_source, task_len_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_TASK_QUERY,
                row_limit=all_tasks_limit,
                params={"confidence_is_null": confidence_is_null},
                prefer_cache=load_clicked,
            )
            if task_len_source == "online":
                st.success(task_len_info)
            else:
                st.warning(task_len_info)

            task_len_df = pd.DataFrame(task_len_rows)
            if task_len_df.empty:
                st.info("No SETask lineage length rows returned.")
            else:
                task_len_df = _prepare_length_distribution_df(task_len_df, id_col="seTask")
                st.dataframe(task_len_df, use_container_width=True, hide_index=True)

            st.markdown("### Model Lineage Length Distribution by SEActivity")
            activity_len_rows, activity_len_source, activity_len_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_ACTIVITY_QUERY,
                row_limit=all_tasks_limit,
                params={"confidence_is_null": confidence_is_null},
                prefer_cache=load_clicked,
            )
            if activity_len_source == "online":
                st.success(activity_len_info)
            else:
                st.warning(activity_len_info)

            activity_len_df = pd.DataFrame(activity_len_rows)
            if activity_len_df.empty:
                st.info("No SEActivity lineage length rows returned.")
            else:
                activity_len_df = _prepare_length_distribution_df(activity_len_df, id_col="seActivity")
                st.dataframe(activity_len_df, use_container_width=True, hide_index=True)

            st.markdown("### Relation-Type Shares by SETask")

            df = pd.DataFrame(rows)
            if df.empty:
                st.info("No model lineage rows returned.")
                return
            task_df = _prepare_lineage_df(df, id_col="seTask")

            st.caption(f"Returned {len(df)} tasks (limit used: {all_tasks_limit}).")
            st.caption(
                "Confidence filter: confidence IS NULL"
                if confidence_is_null
                else "Confidence filter: confidence IS NOT NULL"
            )
            st.dataframe(
                task_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "finetuneShare": st.column_config.NumberColumn("finetuneShare", format="%.3f"),
                    "adapterShare": st.column_config.NumberColumn("adapterShare", format="%.3f"),
                    "mergeShare": st.column_config.NumberColumn("mergeShare", format="%.3f"),
                    "quantShare": st.column_config.NumberColumn("quantShare", format="%.3f"),
                },
            )

            st.markdown("### Relation-Type Shares by SEActivity")
            activity_rows, activity_source, activity_info = get_data_with_fallback(
                uri=uri,
                username=username,
                password=password,
                database=database,
                query=MODEL_LINEAGE_BY_ACTIVITY_QUERY,
                row_limit=all_tasks_limit,
                params={"confidence_is_null": confidence_is_null},
                prefer_cache=load_clicked,
            )

            if activity_source == "online":
                st.success(activity_info)
            else:
                st.warning(activity_info)

            activity_df = pd.DataFrame(activity_rows)
            if activity_df.empty:
                st.info("No SEActivity-level model lineage rows returned.")
                return

            activity_df = _prepare_lineage_df(activity_df, id_col="seActivity")
            st.caption(f"Returned {len(activity_df)} SEActivity rows (limit used: {all_tasks_limit}).")
            st.dataframe(
                activity_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "finetuneShare": st.column_config.NumberColumn("finetuneShare", format="%.3f"),
                    "adapterShare": st.column_config.NumberColumn("adapterShare", format="%.3f"),
                    "mergeShare": st.column_config.NumberColumn("mergeShare", format="%.3f"),
                    "quantShare": st.column_config.NumberColumn("quantShare", format="%.3f"),
                },
            )
        except Exception as exc:
            st.error(str(exc))


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
