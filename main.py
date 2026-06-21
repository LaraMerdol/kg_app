import sys
import urllib.parse
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .config import DEFAULT_DATABASE, DEFAULT_URI, DEFAULT_USER
    from .pages_modules import (
        render_all_tasks_ecosystem_page,
        render_analysis_2_placeholder,
        render_analysis_3_placeholder,
        render_cache_page,
        render_query_explorer_page,
        render_task_artifact_overlaps_page,
        render_task_ecosystem_page,
        render_task_specificity_page,
        render_activity_metrics_page,
    )
except ImportError:
    from config import DEFAULT_DATABASE, DEFAULT_URI, DEFAULT_USER
    from pages_modules import (
        render_all_tasks_ecosystem_page,
        render_analysis_2_placeholder,
        render_analysis_3_placeholder,
        render_cache_page,
        render_query_explorer_page,
        render_task_artifact_overlaps_page,
        render_task_ecosystem_page,
        render_task_specificity_page,
        render_activity_metrics_page,
    )

from utils import scroll_to, scroll_to_hash

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ANALYSIS_FROM_PARAM: dict[str, int | str] = {
    "1": 1,
    "2": 2,
    "3": 3,
    "activity_metrics": "activity_metrics",
    "explorer": "explorer",
    "cache": "cache",
}

_ANALYSIS_TO_PARAM: dict[int | str, str] = {v: k for k, v in _ANALYSIS_FROM_PARAM.items()}

_VALID_PAGES = {
    "All Tasks",
    "Artifact Overlaps",
    "Task Specificity",
    "Family Summary",
    "Specific Task",
}

_ANALYSIS_OPTIONS = [
    ("Artifact Ecosystem", 1),
    ("Social Community", 2),
    ("Model Lineage", 3),
    ("Activity Metrics", "activity_metrics"),
    ("Query Explorer", "explorer"),
    ("Cache", "cache"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_query_params() -> tuple[int | str | None, str | None, str | None]:
    params = st.query_params
    analysis, page, section = None, None, None

    raw_analysis = params.get("analysis")
    if raw_analysis is not None:
        analysis = _ANALYSIS_FROM_PARAM.get(str(raw_analysis))

    raw_page = params.get("page")
    if raw_page is not None:
        if raw_page in _VALID_PAGES:  # no unquote() needed
            page = raw_page

    raw_section = params.get("section")
    if raw_section is not None:
        section = raw_section  # no unquote() needed

    return analysis, page, section


def _sync_query_params() -> None:
    target_analysis = _ANALYSIS_TO_PARAM.get(
        st.session_state.nav_analysis, str(st.session_state.nav_analysis)
    )
    target_page = st.session_state.nav_page
    # Only write when the value actually changed — unnecessary writes trigger
    # history.replaceState in the browser which strips any #hash from the URL.
    if st.query_params.get("analysis") != target_analysis:
        st.query_params["analysis"] = target_analysis
    if st.query_params.get("page") != target_page:
        st.query_params["page"] = target_page
    # Record what we just wrote so the next render can detect real navigations
    st.session_state._last_synced_analysis = st.session_state.nav_analysis
    st.session_state._last_synced_page = st.session_state.nav_page


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Neo4j Task App", layout="wide")

    url_analysis, url_page, _ = _read_query_params()
    _analysis_values = [opt[1] for opt in _ANALYSIS_OPTIONS]

    if "nav_analysis" not in st.session_state:
        # First load: initialise from URL
        st.session_state.nav_analysis = url_analysis if url_analysis is not None else 1
        st.session_state.nav_page = url_page if url_page is not None else "All Tasks"
        st.session_state._last_synced_analysis = st.session_state.nav_analysis
        st.session_state._last_synced_page = st.session_state.nav_page
        # Pre-populate radio key so the widget reflects the URL on first render
        _idx = _analysis_values.index(st.session_state.nav_analysis) if st.session_state.nav_analysis in _analysis_values else 0
        st.session_state["nav_radio_analysis"] = _ANALYSIS_OPTIONS[_idx]
    else:
        # Detect external navigation: URL differs from what we last wrote there
        last_analysis = st.session_state.get("_last_synced_analysis")
        last_page = st.session_state.get("_last_synced_page")
        if url_analysis is not None and url_analysis != last_analysis:
            st.session_state.nav_analysis = url_analysis
            st.session_state.nav_page = url_page if url_page is not None else "All Tasks"
            # Also update radio widget state so it doesn't override the URL
            _idx = _analysis_values.index(url_analysis) if url_analysis in _analysis_values else 0
            st.session_state["nav_radio_analysis"] = _ANALYSIS_OPTIONS[_idx]
        elif url_page is not None and url_page != last_page and url_analysis == last_analysis:
            st.session_state.nav_page = url_page

    # --- Sidebar ---
    with st.sidebar:
        st.header("Navigation")

        current_index = (
            _analysis_values.index(st.session_state.nav_analysis)
            if st.session_state.nav_analysis in _analysis_values
            else 0
        )

        selected_analysis = st.radio(
            "Select Analysis",
            _ANALYSIS_OPTIONS,
            index=current_index,
            key="nav_radio_analysis",
            format_func=lambda x: x[0],
        )

        # Analysis changed via radio
        if selected_analysis[1] != st.session_state.nav_analysis:
            st.session_state.nav_analysis = selected_analysis[1]
            st.session_state.nav_page = "All Tasks"
            st.rerun()

        st.divider()
        st.header("Connection Settings")
        uri = st.text_input("Neo4j URI", value=DEFAULT_URI)
        username = st.text_input("Username", value=DEFAULT_USER)
        password = st.text_input("Password", type="password", value="01234567")
        database = st.text_input("Database", value=DEFAULT_DATABASE)
        row_limit = st.number_input("Row limit", min_value=1, max_value=10000, value=200, step=10)

        st.divider()
        st.caption("🔗 Current URL reflects this view — copy it to share or bookmark.")

    # --- Page-level navigation (analysis 3 only) ---
    current_analysis = st.session_state.nav_analysis

    if current_analysis in (1, 2, 3):
        analysis_names = {1: "Artifact Ecosystem", 2: "Social Community", 3: "Model Lineage"}
        st.title(analysis_names[current_analysis])

        if current_analysis == 3:
            if st.session_state.nav_page == "Specific Task":
                st.session_state.nav_page = "All Tasks"

            page_col1, page_col2, page_col3, page_col4, _ = st.columns([1, 1, 1, 1, 2], gap="small")
            with page_col1:
                if st.button("All Tasks", use_container_width=True):
                    st.session_state.nav_page = "All Tasks"
                    st.rerun()
            with page_col2:
                if st.button("Lineage by Task", use_container_width=True):
                    st.session_state.nav_page = "Artifact Overlaps"
                    st.rerun()
            with page_col3:
                if st.button("Lineage by Activity", use_container_width=True):
                    st.session_state.nav_page = "Task Specificity"
                    st.rerun()
            with page_col4:
                if st.button("Family Summary", use_container_width=True):
                    st.session_state.nav_page = "Family Summary"
                    st.rerun()

            st.divider()

    # --- Sync URL after all state is settled ---
    _sync_query_params()

    # --- Render active page ---
    if current_analysis == 1:
        if st.session_state.nav_page == "All Tasks":
            render_all_tasks_ecosystem_page(uri, username, password, database, int(row_limit))
        elif st.session_state.nav_page == "Artifact Overlaps":
            render_task_artifact_overlaps_page(uri, username, password, database, int(row_limit))
        elif st.session_state.nav_page == "Task Specificity":
            render_task_specificity_page(uri, username, password, database, int(row_limit))
        else:
            render_task_ecosystem_page(uri, username, password, database, int(row_limit))
    elif current_analysis == 2:
        render_analysis_2_placeholder(uri, username, password, database, int(row_limit), st.session_state.nav_page)
    elif current_analysis == 3:
        render_analysis_3_placeholder(uri, username, password, database, int(row_limit), st.session_state.nav_page)
    elif current_analysis == "activity_metrics":
        st.title("Activity Metrics Over Time")
        render_activity_metrics_page(uri, username, password, database, int(row_limit))
    elif current_analysis == "explorer":
        render_query_explorer_page(uri, username, password, database, int(row_limit))
    elif current_analysis == "cache":
        render_cache_page()

    # --- Scroll to section anchor ---
    current_section = st.query_params.get("section")
    if current_section:
        scroll_to(urllib.parse.unquote(current_section))
    else:
        # Handle raw #hash URLs: browser fires hash-scroll before Streamlit
        # renders, so the element doesn't exist yet. This re-fires it after render.
        scroll_to_hash()


if __name__ == "__main__":
    main()