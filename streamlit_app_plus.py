"""Ask Houston+: the same app as streamlit_app.py, with the City GIS lookup on.

Streamlit Community Cloud allows one app per repo, branch, and main file, so
Ask Houston+ deploys from this file. It turns on USE_ARCGIS before anything is
imported, so the chat and the MCP endpoint both get the address lookup.

    streamlit run streamlit_app_plus.py
"""

from __future__ import annotations

import os

os.environ["USE_ARCGIS"] = "true"

from streamlit_app import app  # noqa: E402, F401
