# Evaluation

Evaluation of Ask Houston (open data portal) and Ask Houston+ (adds City GIS
address lookup, weather and air quality), run against the live City of Houston Open
Data portal, City ArcGIS layers, the National Weather Service and EPA AirNow. The
tools were redesigned and every measurement repeated on November 15, 2026; all 8
agent questions were asked that day in Claude Desktop, connected to the MCP server
over stdio. Raw output: [results.md](results.md).

## Summary

| Measure | Result |
|---|---|
| Agent questions answered correctly | 8 of 8 in Claude Desktop over MCP, on the final tools |
| Answer-key errors the agent caught | 2 (questions 3 and 4) |
| Unit tests | 74 of 74 passing, locally and in CI |
| Live tool calls | 70 across all 7 measured tools, with 0 errors |
| Median tool response time | 0.15–0.58 seconds (live, uncached) |

## Testing methodology

| Layer | How | Result |
|---|---|---|
| Unit | `uv run pytest tests/ -v`: canned portal, GIS, weather and air quality responses through a real MCP client, no network | 74 passed |
| CI | GitHub Actions runs lint, format check and tests on every push | Passing |
| Known answers | `scripts/run_eval.py` calls the tools against the live services and records the correct answer to each question; checked by hand | Collected for all 8 questions; 2 corrected |
| Agent | All 8 questions asked in Claude Desktop connected to the MCP server over stdio, each in a new chat (Nov 15); scored against the known answers | 8 of 8 matched |

## Agent questions

Questions 1–5 and 7 use Ask Houston tools; questions 6 and 8 need Ask Houston+.
Each question was asked in a new Claude Desktop chat on November 15, after Claude
Desktop was restarted and its tool list confirmed the redesigned tools.

| # | Question | Known answer | Agent |
|---|---|---|---|
| 1 | Which department publishes the most datasets? | Planning and Development (25), then Finance (13). "Legacy Portal" (28) is a holding group, not a department | Matched; excluded Legacy Portal and noted 13 departments and topics publish nothing yet |
| 2 | What columns does the most recent Payroll table have, and how many rows? | Payroll 2026: 26,220 rows, 20 data columns plus the portal's `_id` | Matched; also found Birth Year changed from number to text in 2024 |
| 3 | How many datasets include council district data? | 3 by search (a 4th result, Property Tax, is a false match); at least 9 carry a district column | Matched; set aside the false matches and warned that search misses datasets with district columns |
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
| `houston_query_records` summary mode | Counts, sums and averages per group computed on the server over up to 100,000 rows; question 7 read 26,220 rows in 0.15 seconds instead of 263 paged calls of 100 rows |
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
| houston_query_records | 0.13 | 0.15 | 0.18 | 0 |
| houston_lookup_address | 0.27 | 0.20 | 0.27 | 0 |
| houston_weather_forecast * | 0.28 | 0.00 | 0.28 | 0 |
| houston_air_quality * | 0.27 | 0.00 | 0.27 | 0 |

\* Weather and air quality responses are cached briefly on the server, so the
first call measures the live National Weather Service and AirNow, and later calls
measure the cache. `houston_browse_catalog` and `houston_get_dataset` are slower
because each makes several portal requests in parallel.

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

## Lessons learned and recommendations

1. **Metadata decides answer quality.** The top publisher is listed as "Legacy
   Portal," which is not a department, so an honest answer to "who publishes the
   most?" is misleading. Recommendation: assign every dataset to its owning
   department.
2. **Tagging limits discovery.** Search finds 3 council district datasets, but at
   least 9 carry a district column. Recommendation: tag every dataset with the
   shared keys it contains, such as council district, super neighborhood and ZIP code.
3. **Yearly tables hide freshness.** The newest budget, FY2025, sits inside one
   dataset as "Budget 2025" and was last updated October 2024, so FY2026 and FY2027
   are missing. Titles alone suggested 2013. Recommendation: publish update
   schedules for featured datasets and keep yearly tables current.
4. **GIS turns general answers into personal ones.** Address-level questions need
   the City's boundary layers; the district record's 2024 date also shows why
   update dates matter.
5. **Discovery varies from run to run.** The agent picks its own search keywords,
   so one run of the new-resident question missed the library inventory and the
   next found it. A search for "park" matched only parking data. Recommendation:
   give featured datasets clear titles and tags, such as "library locations" and
   "parks," and score open-ended questions over several runs.
6. **Metadata can contradict itself.** "Houston Libraries" carries a 2026 update
   date but says "Updated Aug 2023" in its description. Recommendation: check that
   descriptions and update dates agree when a dataset is refreshed.
7. **The agent is honest about its memory.** The chat keeps only the text of earlier
   answers, not their tool results. In a later turn the agent noticed it couldn't
   show tool results behind earlier claims and labeled them unverified.
   Recommendation: ask each evaluation question in a fresh chat, and consider
   logging tool calls.
8. **Thin tools push work onto the agent.** Before the redesign, totals meant
   paging through hundreds of 100-row calls. Moving counting to the server made
   question 7 a single call. Recommendation: design MCP tools around the question
   being asked, not around the API's endpoints.
9. **Schemas drift across years.** Payroll's Birth Year is a number in 2022–2023
   and text from 2024, which breaks joins across years. Recommendation: keep column
   types stable across yearly tables, as part of a machine-readable data standard.
10. **Check the answer key, too.** The agent corrected two known answers. Build
    known answers from the same depth of inspection the agent uses, and review any
    disagreement before scoring it a failure.