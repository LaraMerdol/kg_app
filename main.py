import sys
from pathlib import Path

import streamlit as st

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
        render_activity_metrics_page,
    )


def main() -> None:
    st.set_page_config(page_title="Neo4j Task App", layout="wide")

    if "nav_analysis" not in st.session_state:
        st.session_state.nav_analysis = 1
        st.session_state.nav_page = "All Tasks"

    with st.sidebar:
        st.header("Navigation")
        current_analysis = st.session_state.nav_analysis
        selected_analysis = st.radio(
            "Select Analysis",
            [
                ("Artifact Ecosystem", 1),
                ("Social Community", 2),
                ("Model Lineage", 3),
                ("Activity Metrics", "activity_metrics"),
                ("Query Explorer", "explorer"),
                ("Cache", "cache"),
            ],
            format_func=lambda x: x[0],
            key="sidebar_analysis",
        )

        if selected_analysis[1] != current_analysis:
            st.session_state.nav_analysis = selected_analysis[1]
            if selected_analysis[1] in (1, 2, 3):
                st.session_state.nav_page = "All Tasks"

        st.divider()
        st.header("Connection Settings")
        uri = st.text_input("Neo4j URI", value=DEFAULT_URI)
        username = st.text_input("Username", value=DEFAULT_USER)
        password = st.text_input("Password", type="password", value="01234567")
        database = st.text_input("Database", value=DEFAULT_DATABASE)
        row_limit = st.number_input("Row limit", min_value=1, max_value=10000, value=200, step=10)

    current_analysis = st.session_state.nav_analysis
    if current_analysis not in (1, 2, 3, "activity_metrics", "explorer", "cache"):
        st.session_state.nav_analysis = 1
        current_analysis = 1

    if current_analysis in (1, 2, 3):
        analysis_names = {
            1: "Artifact Ecosystem",
            2: "Social Community",
            3: "Model Lineage",
        }
        st.title(analysis_names[current_analysis])

    if current_analysis == 1:
        render_all_tasks_ecosystem_page(uri, username, password, database, int(row_limit))
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


if __name__ == "__main__":
    main()
