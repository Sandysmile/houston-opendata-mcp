"""Server configuration loaded from environment variables or a .env file.

Every field can be overridden by an environment variable of the same name
(upper- or lower-case). Copy `.env.example` to `.env` for local development.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP server settings. Override any field via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Transport ─────────────────────────────────────────────────────────────
    # "stdio"           — local subprocess (Claude Desktop / Claude Code / Zed)
    # "streamable-http" — remote HTTP server (containers, cloud deploys)
    #
    # app.py also switches to HTTP when a platform sets PORT.
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # ── Upstream portal ───────────────────────────────────────────────────────
    # Operator-controlled origins. Tools never accept a URL from the caller.
    ckan_api_url: str = "https://data.houstontx.gov/api/3/action/"
    portal_url: str = "https://data.houstontx.gov"

    # ── Chat agent ────────────────────────────────────────────────────────────
    agent_model: str = "claude-sonnet-5-5"

    # ── City GIS (Ask Houston+) ───────────────────────────────────────────────
    # Off: "Ask Houston", the open data portal only.
    # On (USE_ARCGIS=true): "Ask Houston+", which adds an address lookup against
    # the City's ArcGIS Online layers. The layers themselves are fixed in gis.py.
    use_arcgis: bool = False

    # ── Weather and air quality (Ask Houston+) ────────────────────────────────
    # The weather forecast (National Weather Service) needs no key. Air quality
    # (EPA AirNow) needs a free key from https://docs.airnowapi.org. Keep it in
    # Streamlit secrets or a local .env file, never in the repo.
    airnow_api_key: str = ""


settings = Settings()
