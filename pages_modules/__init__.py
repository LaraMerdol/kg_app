"""
Page modules for the Neo4j Knowledge Graph Streamlit app.

Organized by analysis type:
- artifact_ecosystem: Artifact Ecosystem analysis
- social_community: Social Community analysis (placeholder)
- model_lineage: Model Lineage analysis (placeholder)
- successful_models: Successful Models analysis (placeholder)
- query_explorer: Query Explorer and Cache pages
"""

from .artifact_ecosystem import (
    render_all_tasks_ecosystem_page,
    render_task_ecosystem_page,
    render_task_artifact_overlaps_page,
    render_task_specificity_page,
)
from .social_community import render_analysis_2_placeholder
from .model_lineage import render_analysis_3_placeholder
from .successful_models import render_analysis_4_placeholder
from .query_explorer import render_query_explorer_page, render_cache_page
from .activity_metrics_timeseries import render_activity_metrics_page

__all__ = [
    "render_all_tasks_ecosystem_page",
    "render_task_ecosystem_page",
    "render_task_artifact_overlaps_page",
    "render_task_specificity_page",
    "render_analysis_2_placeholder",
    "render_analysis_3_placeholder",
    "render_analysis_4_placeholder",
    "render_query_explorer_page",
    "render_cache_page",
    "render_activity_metrics_page",
]
