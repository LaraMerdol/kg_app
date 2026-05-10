"""Shared utility functions for visualization and data processing."""

import json
from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict

import pandas as pd
import plotly.express as px

try:
    from ..visualization import build_cytoscape_html
except ImportError:
    from visualization import build_cytoscape_html


def build_task_artifact_sets(rows: List[dict]) -> Dict[str, Set[str]]:
    """Build a mapping of tasks to their artifacts."""
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


def build_similarity_matrix(
    overlap_df: pd.DataFrame,
    tasks: List[str],
    metric_col: str = "jaccardArtifacts",
) -> pd.DataFrame:
    """Build a similarity matrix from overlap dataframe."""
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
    """Compute summary statistics per task."""
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
    """Extract shared and unique artifacts for a task pair."""
    a1 = task_to_artifacts.get(task1, set())
    a2 = task_to_artifacts.get(task2, set())

    shared = sorted(a1 & a2)
    only1 = sorted(a1 - a2)
    only2 = sorted(a2 - a1)

    shared_df = pd.DataFrame({"shared_artifact": shared})
    only1_df = pd.DataFrame({f"only_in_{task1}": only1})
    only2_df = pd.DataFrame({f"only_in_{task2}": only2})

    return shared_df, only1_df, only2_df


def build_task_overlap_dependency_graph_html(
    overlap_df: pd.DataFrame,
    task_activity_map: Dict[str, List[str]],
    min_jaccard: float = 0.05,
    top_k_per_task: int = 4,
    height_px: int = 760,
) -> str:
    """Build task overlap dependency graph visualization."""
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
    """Build cross-task artifact dependency graph visualization."""
    import numpy as np

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
