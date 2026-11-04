"""Streamlit host: one process serving the web page and the MCP endpoint.

    streamlit run streamlit_app.py           # Streamlit-managed hosts
    uvicorn streamlit_app:app --port 8501    # container hosts

Serves `/` (the page), `/api/mcp` (MCP over streamable HTTP), and `/api/health`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from starlette.routing import Mount  # noqa: E402
from streamlit.starlette import App  # noqa: E402

from houston_opendata.app import create_http_app  # noqa: E402

mcp_app = create_http_app()

app = App(
    "src/houston_opendata/page.py",
    routes=[Mount("/api", app=mcp_app)],
    lifespan=mcp_app.lifespan,
)
