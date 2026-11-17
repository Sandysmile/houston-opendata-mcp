# Evaluation

Evaluation of Ask Houston (open data portal) and Ask Houston+ (adds City GIS
address lookup, weather and air quality), run against the live City of Houston Open
Data portal, City ArcGIS layers, the National Weather Service and EPA AirNow. The
tools were redesigned and every measurement repeated on November 15, 2026; all 8
agent questions were asked that day in Claude Desktop, connected to the MCP server
over stdio. Raw output: [results.md](results.md).

## Design approach

The evaluation is designed as an experiment. One server runs in two versions with
the same AI and the same questions, so the only difference is the data each can
reach: Ask Houston (the open data portal) and Ask Houston+ (adds City GIS layers,
weather and air quality). The questions include one the portal can't answer, and
the same questions were also asked with no MCP server and in two agent
configurations. The
result is an AI-readiness test: it shows which datasets AI can use, which it
can't, and why.

## Summary

| Measure | Result |
|---|---|
| Agent questions, Claude Desktop over MCP (stdio) | 7 matched, 1 partial (question 3: the district-dataset count is a lower bound) |
| Answer-key errors the agent caught | 2 (questions 3 and 4) |
| Agent questions, Streamlit app chat (same tool functions, called directly, not over MCP) | 7 matched, 1 partial (question 3); missed summary mode on question 7 until descriptions were shared |
| Errors in supporting detail | 1 (question 2, Streamlit app: counted 4 numeric pay columns; there are 5) |
| Unit tests | 81 of 81 passing (`uv run pytest tests/`, November 16, 2026) |
| Live tool calls | 70 across all 7 measured tools, with 0 errors |
| Median tool response time | 0.15–0.58 seconds for the five uncached tools (live); summary mode not yet timed separately |

## Data sources

Every source is public. Addresses and layers are fixed in the server's code, so no
tool accepts a URL from the caller.

| Source | Publisher | What it provides | Tools |
|---|---|---|---|
| [City of Houston Open Data Portal](https://data.houstontx.gov) (CKAN) | City of Houston departments | Dataset catalog, metadata and queryable tables | search_datasets, browse_catalog, get_dataset, describe_table, query_records |
| [COH Site Addresses](https://services.arcgis.com/NummVBqZSIJKUeVR/ArcGIS/rest/services/COH_SiteAddresses/FeatureServer/0) (ArcGIS Online) | Planning and Development | Official address points, matched to a location | lookup_address |
| [COH City Limits](https://services.arcgis.com/NummVBqZSIJKUeVR/ArcGIS/rest/services/City_Limits_Full/FeatureServer/0) | Planning and Development | Whether a point is inside city limits (Pending areas count as outside) | lookup_address |
| [Houston Council Districts](https://services.arcgis.com/NummVBqZSIJKUeVR/ArcGIS/rest/services/Houston_Council_Districts_view/FeatureServer/2) | City of Houston | District and council member (record dated 2024) | lookup_address |
| [Houston Super Neighborhoods](https://services.arcgis.com/NummVBqZSIJKUeVR/ArcGIS/rest/services/Super_Neighborhoods/FeatureServer/0) | City of Houston | Super neighborhood name, number and profile link | lookup_address |
| City ZIP code list (`houston_zip_centroids.csv`) | Open data portal (118 ZIP codes in the City) and Census Bureau 2026 ZCTA Gazetteer (center points) | Limits weather and air quality to the City and turns a ZIP code into a location | weather_forecast, air_quality |
| [National Weather Service API](https://www.weather.gov/documentation/services-web-api) | NOAA | Forecast and active alerts | weather_forecast |
| [EPA AirNow API](https://docs.airnowapi.org) | EPA | Current air quality and forecast by reporting area | air_quality |

## Testing methodology

| Layer | How | Result |
|---|---|---|
| Unit | `uv run pytest tests/ -v`: canned portal, GIS, weather and air quality responses through a real MCP client, no network; includes missing-value averages and exact, ambiguous and nonexistent addresses | 81 passed (November 16) |
| CI | GitHub Actions runs lint, format check and tests on every push | Passing |
| Known answers | `scripts/run_eval.py` calls the tools against the live services and records the correct answer to each question; checked by hand | Collected for all 8 questions; 2 corrected |
| Agent | All 8 questions asked in Claude Desktop connected to the MCP server over stdio, each in a new chat (Nov 15); scored against the known answers | 7 matched, 1 partial |

## Agent questions

Questions 1–5 and 7 use Ask Houston tools; questions 6 and 8 need Ask Houston+.
Each question was asked in a new Claude Desktop chat on November 15, after Claude
Desktop was restarted and its tool list confirmed the redesigned tools.

| # | Question | Known answer | Agent |
|---|---|---|---|
| 1 | Which department publishes the most datasets? | Planning and Development (25), then Finance (13). "Legacy Portal" (28) is a holding group, not a department | Matched; excluded Legacy Portal and noted 13 departments and topics publish nothing yet |
| 2 | What columns does the most recent Payroll table have, and how many rows? | Payroll 2026: 26,220 rows, 20 data columns plus the portal's `_id` | Matched; also found Birth Year changed from number to text in 2024 |
| 3 | How many datasets include council district data? | 3 by search (a 4th result, Property Tax, is a false match); at least 9 carry a district column | **Partial.** Reported 3, set aside the false match and warned that search misses datasets with district columns. The full count is unknown (at least 9), so this is scored partial, not matched |
| 4 | Which budget year is the newest on the portal? | FY2025 (Budget 2025 table, updated Oct 17, 2024) | Matched; noted FY2026 and FY2027 are missing |
| 5 | What is the average commute time of City of Houston employees? | Not on the portal | Said so, showed what it searched, invented no number |
| 6 | What council district and super neighborhood is 901 Bagby St in? | District I (record dated 2024); Downtown, super neighborhood 61 | Matched; flagged the 2024 date on the district layer |
| 7 | Which three departments have the most employees on the newest payroll? | Police (7,759), Fire (5,402), Houston Public Works (4,751), counted on the server | Matched; added Active-only counts and the Status breakdown |
| 8 | Is it a good time to be outside in 77002? | Nov 15 morning: showers and thunderstorms, about 90% rain, no alerts; AQI 55 (Moderate) | Matched; led with the answer, noted readings cover the region, suggested Monday |

### The agent corrected the answer key

The first answer key came from simple keyword and title checks, and two of its
answers were wrong. The agent caught both:

- **Question 3.** Keyword search returns 4 datasets, but one is Property Tax, which
  only mentions "City Council" and "Appraisal District." Checking columns found at
  least 9 datasets with council district data, only 3 of them tagged.
- **Question 4.** The key said 2013, the newest year in any dataset *title*. The
  agent looked inside the Budget dataset, which holds one table per year through
  Budget 2025. The evaluation script now looks inside datasets too.

An earlier round on November 11 asked questions 1–6 in the Streamlit chat with the
first version of the tools; its "match" on question 4 agreed with the wrong key.

## Two agent configurations compared

After the redesign, the same 8 questions were asked in two agent configurations on
November 15, each question in a fresh chat. Only the first is an MCP client: Claude
Desktop connects to the MCP server over stdio. The second, the Streamlit app's chat
agent, calls the same tool functions directly, with its own system prompt and limits
(6 tool rounds, 1,500 tokens per answer, 50 rows per call).

| # | Streamlit app | Claude Desktop | Difference |
|---|---|---|---|
| 1 | Correct | Correct | None |
| 2 | Correct on rows and columns; **error** in supporting detail: 4 numeric pay columns, there are 5 | Correct; found Birth Year changed type in 2024 | App made an error; Desktop more thorough |
| 3 | Partial: 3, "a floor, not a full count" | Partial: 3, "probably low" | None |
| 4 | Correct: FY2025, confirmed by sorting the table (said 2013 on Nov 11, old tools) | Correct: FY2025 | None now |
| 5 | Correct; said what it didn't check | Correct; suggested other sources | None |
| 6 | Correct | Correct; flagged the 2024 date | None |
| 7 | Correct, but counted department by department | Correct, with summary mode | Desktop used the tool as designed |
| 8 | Correct, with reading and forecast times | Correct | None |

Each configuration matched 7 of 8 and was partial on question 3. The app's error on
question 2 is recorded separately rather than folded into a match: it answered the
question asked (rows and columns) but got a supporting count wrong.

| Question | Configuration | Error | Effect on score |
|---|---|---|---|
| 2 | Streamlit app | Said 4 of the pay columns are numeric; there are 5 | Scored matched on the question asked; error listed here |

They differed in how:

- **Depth.** Claude Desktop explored further and found extra issues; the app, with
  tighter limits and a "keep answers short" prompt, answered and stopped.
- **Transparency.** The app said more about what it did *not* check and when data
  was issued; Claude Desktop said more about what it found.
- **Tool use.** On question 7 the app missed summary mode. It had its own one-line
  tool descriptions, while Claude Desktop read the full ones from the MCP server.
  Fixed the same day: both configurations now read one set of descriptions
  (`tool_docs.py`), and a unit test keeps them in step.
- **Memory.** Claude Desktop sometimes referred to other chats; the app answered
  each question on its own, which is easier to reproduce.

Each configuration suits a different audience: the app for residents who want a short,
careful answer, and Claude Desktop for analysts and data stewards.

## Comparison question: a new resident

An open-ended question with no single right answer, asked three ways to show how
the data source changes the answer: "I just moved to 611 Walker St. What City
resources can I connect with?"

Known facts from the City GIS layers: inside city limits; Council District I
(Joaquin Martinez, record dated 2024); Downtown, super neighborhood 61.

| Version | What the answer included | Specific to the address? | Sources cited? |
|---|---|---|---|
| Claude with no MCP server | General City resources: 311, HoustonTX.gov, how to look up a council member, the library, AlertHouston | No | Web pages only |
| Ask Houston | Said it can't look up an address. Pointed to the council district, super neighborhood and jurisdiction datasets; found the Central Library at 500 McKinney St in the library inventory; noted no trash schedule dataset | Partly: nearby library, but no district | Yes, portal links with update dates |
| Ask Houston+ | Inside city limits with full service; District I, Joaquin Martinez and phone, record dated 2024; Downtown super neighborhood profile; recycling facilities and food inspection datasets; no trash schedule | Yes | Yes, portal links with update dates |

Result: only Ask Houston+ placed the resident in a council district and super
neighborhood. Both MCP versions cited their sources and stated what they couldn't
find, instead of guessing.

A second Ask Houston+ run of the same question searched more keywords and this time
found the library inventory and a 311 knowledge base dataset. The first run had
reported no library listing. It also surfaced two new findings: the "Houston
Libraries" dataset shows an update date of 2026-11-03 while its description says
"Updated Aug 2023," and a search for "park" returned only parking datasets.

## Tool design: built around user goals

The first version's portal tools mirrored CKAN endpoints one to one, so a
question such as "how many rows are in the newest payroll table?" took four calls
(search, get, describe, query). On November 15 the tools were reworked around the
questions people ask:

| Change | Effect |
|---|---|
| `houston_browse_catalog` replaces two list tools | One call shows departments and topics, ranked, paged past CKAN's 25-item cap |
| `houston_get_dataset` lists columns and row counts for queryable tables, read in parallel, and picks the newest | "Most recent payroll" is answered without guessing; question 2 dropped from three calls to one |
| `houston_describe_table` adds sample rows | The agent sees how values are written before using exact-match filters |
| `houston_query_records` summary mode | Counts, sums and averages per group computed on the server over up to 100,000 rows; question 7 read all 26,220 rows in one tool call instead of 263 paged calls of 100 rows. Averages use only the numeric values, so missing pay values no longer pull them down |
| `houston_lookup_address` prefers an exact normalized match | When several City addresses fit and none matches exactly (such as units at one address), it returns the candidates and asks the agent to check with the user, instead of using the first row |
| Pydantic input types in `models.py` for every tool | Shape and size are validated before any request; format problems still return a fix-it hint |

Ask Houston now has 5 tools and Ask Houston+ has 8.

## Performance

Each tool was called 10 times from a local run on November 15, 2026, against the
live services (seconds).

| Tool | First call | Median | Slowest | Errors |
|---|---|---|---|---|
| houston_search_datasets | 0.18 | 0.19 | 0.34 | 0 |
| houston_browse_catalog | 0.59 | 0.58 | 0.78 | 0 |
| houston_get_dataset | 0.38 | 0.43 | 0.49 | 0 |
| houston_query_records (records mode, 5 rows) | 0.13 | 0.15 | 0.18 | 0 |
| houston_lookup_address | 0.27 | 0.20 | 0.27 | 0 |
| houston_weather_forecast * | 0.28 | 0.00 | 0.28 | 0 |
| houston_air_quality * | 0.27 | 0.00 | 0.27 | 0 |

\* Weather and air quality responses are cached briefly on the server, so the
first call measures the live National Weather Service and AirNow, and later calls
measure the cache. `houston_browse_catalog` and `houston_get_dataset` are slower
because each makes several portal requests in parallel.

Summary mode was not timed in this run: the `houston_query_records` row is a
5-row records query. `scripts/run_eval.py` now times summary mode on its own row.

Hosted response times add the hosting platform's network latency, and the first
request after the hosted app has been idle can take longer while it wakes up.

## Security considerations

- Public data only, with read-only CKAN actions and no SQL endpoint.
- Fixed upstream origins for the portal and GIS layers, no redirects, and a 5 MB response limit.
- Inputs are validated twice before any request: Pydantic models check shape and size, and the portal, GIS and weather clients check formats (UUIDs, slugs, street addresses, City ZIP codes). Errors are sanitized.
- Summaries are capped at 100,000 rows, so one question can't trigger an unbounded scan.
- The AirNow key lives in Streamlit secrets or a local `.env` file, both excluded from git.
- The agent treats tool results as data, not instructions, and declines to profile individuals.
- No authentication on the endpoint, which suits public data. Hosting platforms' rate limits are the only throttle.
- **Deployment:** locally the server runs over stdio with no network endpoint. The hosted demo is a password-protected prototype for evaluation, not a public City service; review agency rules before any wider use.
- **Governance:** tools, descriptions and settings are versioned in Git, and lint plus 81 tests run in CI on every push.
- **Vendor neutrality:** a standard MCP server that works with any MCP client. Tested with Claude Desktop; the Streamlit demo app uses Claude.

## Lessons learned and recommendations

The lessons fall into three layers of an MCP service, each improved separately:
the **data sources** it reads, the **tools** that reach them, and the
**deployment** that puts the tools in front of people, through an AI client or an
app.

**Data sources, MCP design and deployment all matter.** The data sources decide what the AI can know; the design of the tools and the choice of deployment decide how well it uses that data.

### 1. Improving the data sources

Improving data sources means two things: fixing the data already published, and
selecting and connecting the sources that make answers local.

1. **Assign every dataset to its owner.** The top publisher is "Legacy Portal,"
   which is not a department, so "who publishes the most?" needs a caveat.
   Recommendation: assign every dataset to its owning department.
2. **Tag the shared keys a dataset contains.** Search finds 3 council district
   datasets, but at least 9 carry a district column. Recommendation: tag every
   dataset with its keys, such as council district, super neighborhood and ZIP code.
3. **Keep yearly tables current.** The newest budget, FY2025, sits inside one
   dataset as "Budget 2025" and was last updated October 2024, so FY2026 and FY2027
   are missing. Recommendation: publish update schedules for featured datasets.
4. **Keep column types stable.** Payroll's Birth Year is a number in 2022–2023 and
   text from 2024, which breaks joins across years. Recommendation: make stable
   types part of a machine-readable data standard.
5. **Make metadata agree with itself.** "Houston Libraries" carries a 2026 update
   date but says "Updated Aug 2023" in its description, and the council district
   layer is dated 2024. Recommendation: check descriptions and dates at each refresh.
6. **Select and connect the sources that make answers local.** Four selected City
   GIS layers (site addresses, city limits, council districts and super
   neighborhoods) placed an address in its district and neighborhood. National
   Weather Service forecasts and EPA AirNow readings became Houston answers through
   the City's own list of 118 ZIP codes, hosted on the open data portal. ZIP codes
   cross district lines, so address questions need the GIS layers too.
   Recommendation: publish authoritative boundary layers and keyed reference
   tables, such as the ZIP code list, next to the catalog.
7. **Name datasets the way people ask.** One run of the new-resident question
   missed the library inventory, and "park" matched only parking data.
   Recommendation: give featured datasets clear titles and tags.

### 2. Improving the tools

On November 15 the tools were consolidated and reconfigured: 9 tools became 8
(two list tools merged into `houston_browse_catalog`), `houston_get_dataset` now
returns columns and picks the newest table, `houston_query_records` gained summary
mode, and every input is a validated Pydantic model.

8. **Consolidate tools around questions, not endpoints.** Two list tools that
   mirrored CKAN endpoints became one catalog tool, and steps the agent used to
   chain (search, open, describe, query) now happen inside fewer, richer tools.
   Totals once meant paging through hundreds of 100-row calls; summary mode made
   question 7 one call. Recommendation: do multi-step work (newest table, counts
   by group) on the server.
9. **Good tools help limited agents most.** The capped app answered question 4
   wrong with the old tools and right with the new ones; Claude Desktop, with no
   caps, got it right both times.
10. **Descriptions decide what the agent finds.** With the same code, the app missed
    summary mode because its tool description was one line. Recommendation: write
    descriptions around the question each mode answers, and keep one copy.

### 3. Improving the deployment

The same tools reach people two ways: through an AI client (Claude Desktop, over
MCP) or through an app (the Streamlit chat, calling the tools directly).

11. **The agent configuration shapes the answer.** The same tools gave short, careful answers in
    the app and longer, analytical ones in Claude Desktop. Recommendation: choose
    the configuration and its limits for the audience.
12. **Test in more than one agent configuration.** Testing only in the app would have
    hidden the description gap; testing only in Claude Desktop would have hidden the
    effect of the caps. Recommendation: evaluate an MCP server in at least two agent
    configurations, such as an MCP client and an app that calls the tools directly.
13. **Restart and confirm before testing.** Claude Desktop kept running the old
    server until it was restarted. Recommendation: check the client's tool list
    before each evaluation round.
14. **Test in fresh chats.** Claude Desktop sometimes drew on other chats, and the
    app's chat keeps earlier answers. Recommendation: ask each evaluation question
    in a new chat, and consider logging tool calls.
15. **Check the answer key, too.** The agent corrected two known answers.
    Recommendation: build known answers with the same depth the agent uses, and
    review disagreements before scoring them as failures.
