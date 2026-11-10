"""Ask Houston+: the same host as streamlit_app.py, with the City GIS lookup on.

Streamlit Community Cloud allows one app per repo, branch, and main file, so
Ask Houston+ deploys from this file. It turns on USE_ARCGIS before anything is
imported, so the chat and the MCP endpoint both get the address lookup.

    streamlit run streamlit_app_plus.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["USE_ARCGIS"] = "true"

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
