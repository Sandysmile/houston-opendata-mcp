# Houston Open Data MCP

An MCP server that lets an AI assistant search and read public data from the
[City of Houston Open Data portal](https://data.houstontx.gov), which runs on CKAN.

Built from the [GSA MCP hackathon template](https://github.com/GSA-TTS/mcp-hackathon-template)
as a **Dataset Access Server**. It is read-only, and it needs no key or sign-in.

> **Disclaimer**
> Hackathon prototype built on the [City of Houston's public open data portal](https://data.houstontx.gov).
> This is an independent project and **not an official City of Houston service**.
> Answers reflect published datasets and may be incomplete or out of date — verify
> anything important against the source dataset.

## Why it matters

People already ask AI about city services. This project tests whether AI can actually
use Houston's open data to answer them. With the same AI and the same question, the
answer goes from generic (no MCP), to grounded in City datasets (Ask Houston), to
specific to your address (Ask Houston+).

**Evaluation (November 2026):** 6 of 6 known-answer questions correct, including one
the portal can't answer; 30 live tool calls with 0 errors and a median of about
0.2 seconds; 52 unit tests passing. The test also exposed metadata gaps worth fixing.
See [eval/EVALUATION.md](eval/EVALUATION.md).

## Tools

| Tool | What it does |
|---|---|
| `houston_search_datasets` | Search the catalog by keyword, department, or topic |
| `houston_get_dataset` | Open a dataset and list its resources |
| `houston_describe_table` | List a table's columns and row count |
| `houston_query_records` | Read rows with filters, sorting, and paging |
| `houston_list_organizations` | List departments and their dataset counts |
| `houston_list_groups` | List topic groups and their dataset counts |

With `USE_ARCGIS=true`, the server adds three more tools:

| Tool | What it does |
|---|---|
| `houston_lookup_address` | Find an address's city limits, council district, and super neighborhood, using City GIS layers on ArcGIS Online |
| `houston_weather_forecast` | Weather forecast and active alerts for a Houston ZIP code, from the National Weather Service (no key needed) |
| `houston_air_quality` | Current air quality and forecast for a Houston ZIP code, from EPA AirNow (needs `AIRNOW_API_KEY`) |

Both ZIP code tools use `src/houston_opendata/data/houston_zip_centroids.csv`: the 118
ZIP codes fully or partially within the City (from the open data portal), each with a
center point from the Census Bureau's 2026 ZCTA Gazetteer.

The server also offers two prompts (`explore_houston_topic`, `compare_by_geography`)
and two resources (`houston://info/server`, `houston://docs/join-keys`).

## Run it on your computer

Install [uv](https://docs.astral.sh/uv/), then, in PowerShell or any terminal:

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run streamlit run streamlit_app.py
```

The page opens at <http://localhost:8501> and the MCP endpoint is
`http://localhost:8501/api/mcp`. Check the endpoint from a second terminal:

```bash
uv run python scripts/smoke_test.py http://localhost:8501/api/mcp
```

To run it as a local stdio server for Claude Code instead, use `uv run python main.py`.

## Chat agent

The page's **Ask** tab is a chat agent that uses Claude and the same read-only tools.
It needs `ANTHROPIC_API_KEY` and `APP_PASSWORD`, set as Streamlit secrets or locally in
`.streamlit/secrets.toml`, which Git ignores. Copy `.streamlit/secrets.toml.example` to
start. API usage is billed separately from a Claude plan.

## Ask Houston and Ask Houston+

One codebase runs as two apps, so the only difference between them is the data:

| App | `USE_ARCGIS` | Data sources |
|---|---|---|
| **Ask Houston** | `"false"` (default) | Open Data Portal |
| **Ask Houston+** | `"true"` | Open Data Portal + City GIS address lookup + weather (NWS) and air quality (AirNow) by ZIP code |

Set `USE_ARCGIS` in each Streamlit app's secrets. The City GIS layers are fixed in
`src/houston_opendata/gis.py`: site addresses, city limits, council districts, and
super neighborhoods. For air quality, also add `AIRNOW_API_KEY` to Ask Houston+'s
secrets; a free key comes from <https://docs.airnowapi.org>. Both apps also give the
agent today's date in Houston time.

## Host it

See **[deploy/streamlit/README.md](deploy/streamlit/README.md)**. One process serves
the Streamlit page at `/` and MCP at `/api/mcp`. Streamlit Community Cloud may block
outside MCP clients, so test it with `scripts/smoke_test.py`.

## Repo layout

```
streamlit_app.py            # Streamlit host: page + /api/mcp
Dockerfile.streamlit        # Same host, in a container
main.py                     # Local stdio entry point
src/houston_opendata/
├── app.py                  # Builds FastMCP, picks the transport
├── portal.py               # Read-only CKAN client, shared by the tools and the page
├── gis.py                  # Read-only City GIS client for Ask Houston+
├── conditions.py           # Weather (NWS) and air quality (AirNow) by ZIP code
├── data/                   # Houston ZIP codes with center points
├── page.py                 # Streamlit page
├── config.py, models.py, utils.py, routes.py
├── tools/                  # One file per tool
├── prompts/
└── resources/
scripts/smoke_test.py       # Checks a running server with a real MCP client
scripts/run_eval.py         # Collects known answers and response times
tests/                      # Tests that run without network access
eval/EVALUATION.md          # Evaluation write-up for the hackathon submission
eval/results.md             # Raw output of scripts/run_eval.py
deploy/streamlit/           # Hosting guide
```

## Add a tool

Create `src/houston_opendata/tools/my_tool.py` with a `register(mcp)` function, then
call it from `tools/__init__.py`. Put any portal call in `portal.py`.

## Security

- Tools use only allow-listed CKAN read actions. There is no SQL endpoint and no write action.
- The portal and City GIS addresses come from server code and configuration, never from
  a tool argument.
- Identifiers are validated before any request, and upstream errors are sanitized.
- The endpoint has no authentication, which suits public data. Review your agency's
  requirements before using it beyond the hackathon.

## License

[MIT](LICENSE). See [SECURITY.md](SECURITY.md).
