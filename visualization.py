import json
from typing import Any, Dict, List, Set


def build_graphviz_dot(nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
    colors = {
        "SETask": "#f97316",
        "Model": "#0284c7",
        "Dataset": "#16a34a",
        "Paper": "#6d28d9",
        "Benchmark": "#dc2626",
        "Collection": "#7c3aed",
        "Space": "#0f766e",
        "User": "#334155",
        "Organization": "#be123c",
    }

    dot_lines = [
        "digraph task_subgraph {",
        "  rankdir=LR;",
        '  graph [bgcolor="white"];',
        '  node [shape=box, style="filled,rounded", color="#111827", fillcolor="#e5e7eb", fontname="Helvetica"];',
        '  edge [color="#374151", fontname="Helvetica"];',
    ]

    seen_nodes = set()
    for node in nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        label = str(node.get("label", "Node"))
        title = str(node.get("title", node_id))
        fill = colors.get(label, "#e5e7eb")
        safe_id = node_id.replace('"', "'")
        safe_text = f"{label}\\n{title}".replace('"', "'")
        dot_lines.append(f'  "{safe_id}" [label="{safe_text}", fillcolor="{fill}"];')

    for rel in relationships:
        source = str(rel.get("source", "")).strip().replace('"', "'")
        target = str(rel.get("target", "")).strip().replace('"', "'")
        type_name = str(rel.get("type", "REL")).replace('"', "'")
        if not source or not target:
            continue
        if source not in seen_nodes or target not in seen_nodes:
            continue
        dot_lines.append(f'  "{source}" -> "{target}" [label="{type_name}"];')

    dot_lines.append("}")
    return "\n".join(dot_lines)


def build_cytoscape_html(
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    height_px: int = 700,
) -> str:
    type_color_map: Dict[str, str] = {
        "SETask": "#f97316",
        "TaskGroup": "#64748b",
        "Artifact": "#0ea5e9",
        "Model": "#0284c7",
        "Dataset": "#16a34a",
        "Paper": "#7c3aed",
        "Benchmark": "#dc2626",
        "Collection": "#6d28d9",
        "Space": "#0f766e",
        "User": "#334155",
        "Organization": "#be123c",
    }

    def _short_node_label(title_text: str) -> str:
        title = title_text.strip()
        if not title:
            return ""
        compact = title.split("/")[-1].strip() or title
        max_len = 22
        return compact if len(compact) <= max_len else f"{compact[: max_len - 1]}..."

    node_items: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    for node in nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in node_ids:
            continue
        node_ids.add(node_id)
        label = str(node.get("label", "Node"))
        title = str(node.get("title", node_id))
        display = _short_node_label(title)
        node_items.append(
            {
                "data": {
                    "id": node_id,
                    "label": label,
                    "title": title,
                    "display": display,
                    "fill": type_color_map.get(label, "#0ea5e9"),
                }
            }
        )

    edge_items: List[Dict[str, Any]] = []
    edge_seen: Set[str] = set()
    for idx, rel in enumerate(relationships):
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
        edge_items.append({"data": {"id": edge_id, "source": source, "target": target, "label": rel_type}})

    elements_json = json.dumps(node_items + edge_items)
    type_color_map_json = json.dumps(type_color_map)

    return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        html, body {{ margin: 0; padding: 0; background: #f8fafc; font-family: \"Segoe UI\", Tahoma, Geneva, Verdana, sans-serif; }}
        #wrapper {{ height: {height_px}px; width: 100%; display: grid; grid-template-rows: auto 1fr; gap: 8px; }}
        #toolbar {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }}
        #toolbar button {{ border: 1px solid #cbd5e1; background: #f1f5f9; color: #0f172a; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        #meta {{ font-size: 12px; color: #334155; margin-right: 8px; }}
        #legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-left: 4px; }}
        .legend-item {{ display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: #0f172a; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 999px; padding: 2px 8px; }}
        .legend-dot {{ width: 10px; height: 10px; border-radius: 999px; border: 1px solid rgba(0, 0, 0, 0.25); }}
        #cy {{ height: 100%; width: 100%; background: radial-gradient(circle at 20% 20%, #ffffff 0%, #f1f5f9 100%); border: 1px solid #e2e8f0; border-radius: 8px; }}
    </style>
    <script src=\"https://unpkg.com/cytoscape@3.30.1/dist/cytoscape.min.js\"></script>
</head>
<body>
    <div id=\"wrapper\">
        <div id=\"toolbar\">
            <button id=\"fitBtn\">Fit</button>
            <button id=\"resetBtn\">Re-layout</button>
            <span id=\"meta\"></span>
            <div id=\"legend\"></div>
        </div>
        <div id=\"cy\"></div>
    </div>

    <script>
        const elements = {elements_json};
        const typeColorMap = {type_color_map_json};
        const nodeCount = elements.filter(e => e.data && e.data.id && !e.data.source).length;
        const edgeCount = elements.filter(e => e.data && e.data.source).length;
        document.getElementById("meta").textContent = `Nodes: ${{nodeCount}} | Relationships: ${{edgeCount}}`;

        const legend = document.getElementById("legend");
        const presentTypes = [...new Set(elements
            .filter(e => e.data && e.data.label && !e.data.source)
            .map(e => e.data.label))
        ].sort((a, b) => a.localeCompare(b));

        presentTypes.forEach(typeName => {{
            const item = document.createElement("span");
            item.className = "legend-item";
            const dot = document.createElement("span");
            dot.className = "legend-dot";
            dot.style.backgroundColor = typeColorMap[typeName] || "#0ea5e9";
            const text = document.createElement("span");
            text.textContent = typeName;
            item.appendChild(dot);
            item.appendChild(text);
            legend.appendChild(item);
        }});

        const cy = cytoscape({{
            container: document.getElementById("cy"),
            elements,
            style: [
                {{ selector: "node", style: {{ "label": "data(display)", "font-size": 10, "background-color": "data(fill)", "color": "#0f172a", "text-wrap": "wrap", "text-max-width": 96, "text-valign": "bottom", "text-halign": "center", "width": 26, "height": 26, "border-width": 1, "border-color": "#1f2937" }} }},
                {{ selector: "node[label = 'SETask']", style: {{ "background-color": "#f97316", "border-color": "#c2410c", "width": 34, "height": 34 }} }},
                {{ selector: "node[label = 'TaskGroup']", style: {{ "background-color": "#64748b", "border-color": "#334155", "width": 30, "height": 30 }} }},
                {{ selector: "node[label = 'Artifact']", style: {{ "background-color": "#0ea5e9", "border-color": "#0369a1" }} }},
                {{ selector: "node[label = 'Model']", style: {{ "background-color": "#0284c7", "border-color": "#075985" }} }},
                {{ selector: "node[label = 'Dataset']", style: {{ "background-color": "#16a34a", "border-color": "#166534" }} }},
                {{ selector: "node[label = 'Paper']", style: {{ "background-color": "#7c3aed", "border-color": "#5b21b6" }} }},
                {{ selector: "node[label = 'Benchmark']", style: {{ "background-color": "#dc2626", "border-color": "#991b1b" }} }},
                {{ selector: "node[label = 'Collection']", style: {{ "background-color": "#6d28d9", "border-color": "#4c1d95" }} }},
                {{ selector: "node[label = 'Space']", style: {{ "background-color": "#0f766e", "border-color": "#134e4a" }} }},
                {{ selector: "node[label = 'User']", style: {{ "background-color": "#334155", "border-color": "#0f172a", "width": 24, "height": 24 }} }},
                {{ selector: "node[label = 'Organization']", style: {{ "background-color": "#be123c", "border-color": "#881337", "width": 24, "height": 24 }} }},
                {{ selector: "edge", style: {{ "width": 1.2, "line-color": "#64748b", "target-arrow-color": "#64748b", "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.8, "label": "data(label)", "font-size": 8, "color": "#334155", "text-background-color": "#ffffff", "text-background-opacity": 0.7, "text-background-padding": 2, "text-rotation": "autorotate" }} }}
            ],
            layout: {{ name: "cose", animate: false, fit: true, padding: 35, idealEdgeLength: function() {{ return 180; }}, nodeRepulsion: function() {{ return 16000; }}, edgeElasticity: function() {{ return 40; }}, gravity: 0.25, numIter: 1200 }},
            wheelSensitivity: 0.2
        }});

        document.getElementById("fitBtn").addEventListener("click", () => cy.fit(undefined, 40));
        document.getElementById("resetBtn").addEventListener("click", () => {{
            cy.layout({{ name: "cose", animate: false, fit: true, padding: 35, idealEdgeLength: function() {{ return 180; }}, nodeRepulsion: function() {{ return 16000; }}, edgeElasticity: function() {{ return 40; }}, gravity: 0.25, numIter: 1200 }}).run();
        }});
    </script>
</body>
</html>
"""
