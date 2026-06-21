import streamlit as st
import streamlit.components.v1 as components


def anchor(name: str) -> None:
    components.html(f'<div id="{name}"></div>', height=0)


def captionlink(text: str, anchor_id: str, analysis, page: str) -> None:
    """Render a caption with an anchor div and a small clickable link icon."""
    url = f"?analysis={analysis}&page={page}&section={anchor_id}"
    components.html(f'<div id="{anchor_id}"></div>', height=0)
    st.markdown(
        f'<p style="font-size:0.85rem;color:#6b7280;margin:0 0 0.5rem 0;">'
        f'<a href="{url}" style="color:#9ca3af;text-decoration:none;margin-right:4px;" '
        f'title="Copy deep link">🔗</a>{text}</p>',
        unsafe_allow_html=True,
    )


def scroll_to(anchor_id: str) -> None:
    components.html(
        f"""
        <script>
            (function() {{
                let attempts = 0;
                const interval = setInterval(function() {{
                    const el = window.parent.document.getElementById('{anchor_id}');
                    if (el) {{
                        el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                        clearInterval(interval);
                    }} else if (++attempts > 100) {{
                        clearInterval(interval);
                    }}
                }}, 100);
            }})();
        </script>
        """,
        height=0,
    )


def scroll_to_hash() -> None:
    """Poll for the element named in window.parent.location.hash and scroll to it.

    Handles the SPA timing problem: on cold load the browser fires its native
    hash-scroll before Streamlit has rendered any content, so the element
    doesn't exist yet and the scroll silently fails.  This component re-runs
    the scroll after the render tree is in the DOM.
    """
    components.html(
        """
        <script>
            (function() {
                try {
                    const hash = window.parent.location.hash;
                    if (!hash || hash.length <= 1) return;
                    const id = decodeURIComponent(hash.substring(1));
                    let attempts = 0;
                    const interval = setInterval(function() {
                        const el = window.parent.document.getElementById(id);
                        if (el) {
                            el.scrollIntoView({behavior: 'smooth', block: 'start'});
                            clearInterval(interval);
                        } else if (++attempts > 150) {
                            clearInterval(interval);
                        }
                    }, 100);
                } catch(e) {}
            })();
        </script>
        """,
        height=0,
    )