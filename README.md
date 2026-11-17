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

**Evaluation (November 2026):** 8 known-answer questions, including one the portal
can't answer, asked in two agent configurations. Each matched 7 and was partial on
1 (question 3: the district-dataset count is a lower bound); the Streamlit app also
made one error in supporting detail, recorded separately. 70 live tool calls with 0
errors; 81 of 81 unit tests passing (November 16, 2026). The test also exposed
metadata gaps worth fixing.
See [eval/EVALUATION.md](eval/EVALUATION.md).

## Works with any MCP client

This is a standard MCP server: any MCP client can connect, over stdio locally or
stateless HTTP at `/api/mcp`. It was tested with Claude Desktop; the Streamlit demo
app uses Claude. The server itself is not tied to any one AI vendor.

## Design approach: built as an experiment

The server is designed to answer a question, not only to serve data: *can AI
actually use our open data, and where does it fail?*

| Design idea | How the code delivers it |
|---|---|
| **A fair comparison.** One server, two versions, same AI, same questions, so the only difference is the data. | One setting, `USE_ARCGIS` in `config.py`, turns Ask Houston into Ask Houston+ |
| **MCP as an AI-readiness test.** Comparing answers with and without MCP shows which datasets AI can't use, and why. | `scripts/run_eval.py` collects known answers from the live tools; [eval/EVALUATION.md](eval/EVALUATION.md) scores the agent against them |
| **Questions that probe failure.** The test set includes data the portal doesn't have, so the agent must say so instead of guessing. | Question 5 (employee commute time); every tool returns an `error` with a fix-it `hint` |
| **City data as the key to national data.** The City's own list of 118 ZIP codes turns National Weather Service and EPA AirNow data into Houston answers. | `src/houston_opendata/data/houston_zip_centroids.csv`, used by `conditions.py` |
| **Tools shaped like the questions people ask.** | 8 tools built around questions; `houston_query_records` counts and totals on the server; `tool_docs.py` gives every client the same descriptions |
| **Tested in two agent configurations.** | The same 8 questions in Claude Desktop (an MCP client, over stdio) and the Streamlit app's chat agent (the same tool functions, called directly); 7 matched and 1 partial in each |

The evaluation found problems in three layers, data sources, tools and deployment,
and each became a recommendation for the City's open data program.

**Data sources, MCP design and deployment all matter.** The data sources decide what the AI can know; the design of the tools and the choice of deployment decide how well it uses that data.

## Tools

Each tool answers a question a person or agent actually asks, rather than mirroring
one portal endpoint. Inputs are validated with Pydantic models (`models.py`); bad
values in the right shape come back with a fix-it `hint`.

| Tool | Question it answers | What it combines |
|---|---|---|
| `houston_search_datasets` | Is there data on this subject? | Keyword, department and topic filters in one search |
| `houston_browse_catalog` | What does the portal cover, and who publishes the most? | Department and topic listings, paged past the portal's 25-item cap, ranked |
| `houston_get_dataset` | What's in this dataset, and which table should I query? | Dataset metadata + column lists and row counts for up to 6 tables, read in parallel; picks the newest table |
| `houston_describe_table` | How are values written in this table? | Columns, row count and sample rows, so exact-match filters work |
| `houston_query_records` | Which records match? How many, or how much, by group? | Rows mode, or summary mode: counts, sums and averages over up to 100,000 rows, computed on the server |

With `USE_ARCGIS=true`, the server adds three more tools:

| Tool | Question it answers |
|---|---|
| `houston_lookup_address` | Who represents me, and what neighborhood am I in? Matches the address to City address points, then checks city limits, council district and super neighborhood layers in parallel: one call instead of five GIS queries. An exact match wins; if several addresses fit, it returns the choices to ask the user about |
| `houston_weather_forecast` | Should I plan around the weather? NWS forecast plus active alerts (such as flood warnings), joined to the City's own ZIP list (no key needed) |
| `houston_air_quality` | Is the air healthy right now? EPA AirNow current reading and forecast, joined to the City's ZIP list (needs `AIRNOW_API_KEY`) |

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
