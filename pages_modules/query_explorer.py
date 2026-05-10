"""Query Explorer and Cache management pages."""

import pandas as pd
import streamlit as st

try:
    from ..config import CACHE_FILE
    from ..data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation
except ImportError:
    from config import CACHE_FILE
    from data import cached_entries_for_ui, get_data_with_fallback, query_looks_write_operation


def render_query_explorer_page(uri: str, username: str, password: str, database: str, row_limit: int) -> None:
    """Render a free-form query explorer for running custom Cypher queries."""
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
    """Render the cache management page."""
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
