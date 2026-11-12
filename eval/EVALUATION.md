# Evaluation

Evaluation of Ask Houston (open data portal) and Ask Houston+ (adds City GIS
address lookup), run on November 11, 2026 against the live City of Houston Open
Data portal and City ArcGIS layers. Raw output: [results.md](results.md).

## Summary

| Measure | Result |
|---|---|
| Agent questions answered correctly | 6 of 6 |
| Unit tests | 52 of 52 passing, locally and in CI |
| Live tool calls | 30, with 0 errors |
| Median tool response time | 0.16–0.21 seconds |

## Testing methodology

| Layer | How | Result |
|---|---|---|
| Unit | `uv run pytest tests/ -v`: canned portal and GIS responses through a real MCP client, no network | 52 passed |
| CI | GitHub Actions runs lint, format check and tests on every push | Passing |
| Known answers | `scripts/run_eval.py` calls the tools against the live portal and records the correct answer to each question | Collected for all 6 questions |
| Agent | The same questions asked in the Ask Houston and Ask Houston+ apps, scored against the known answers | 6 of 6 matched |

## Agent questions

Questions 1–5 were asked in Ask Houston and question 6 in Ask Houston+.

| # | Question | Known answer | Agent |
|---|---|---|---|
| 1 | Which department publishes the most datasets? | Legacy Portal (28), Planning and Development (25), Finance Department (13) | Matched |
| 2 | What columns does the most recent Payroll table have, and how many rows? | Payroll 2026: 26,220 rows, 20 data columns plus the portal's `_id` | Matched |
| 3 | How many datasets include council district data? | 4 by keyword search | Matched |
| 4 | Which budget year is the newest on the portal? | 2013, from dataset titles | Matched |
| 5 | What is the average commute time of City of Houston employees? | Not on the portal | Said the portal doesn't hold it; invented no number |
| 6 | What council district and super neighborhood is 901 Bagby St in? | District I (record dated 2024); Downtown, super neighborhood 61 | Matched |

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

## Performance

Each tool was called 10 times from a local run against the live portal and GIS
layers (seconds).

| Tool | First call | Median | Slowest | Errors |
|---|---|---|---|---|
| houston_search_datasets | 0.36 | 0.16 | 0.36 | 0 |
| houston_query_records | 0.16 | 0.21 | 0.31 | 0 |
| houston_lookup_address | 0.25 | 0.20 | 0.25 | 0 |

Hosted response times add the hosting platform's network latency, and the first
request after the hosted app has been idle can take longer while it wakes up.

## Security considerations

- Public data only, with read-only CKAN actions and no SQL endpoint.
- Fixed upstream origins for the portal and GIS layers, no redirects, and a 5 MB response limit.
- Identifiers are validated before any request. Errors are sanitized.
- The agent treats tool results as data, not instructions, and declines to profile individuals.
- No authentication on the endpoint, which suits public data. Hosting platforms' rate limits are the only throttle.

## Lessons learned and recommendations

1. **Metadata decides answer quality.** The top publisher is listed as "Legacy
   Portal," which is not a department, so an honest answer to "who publishes the
   most?" is misleading. Recommendation: assign every dataset to its owning
   department.
2. **Tagging limits discovery.** Only 4 datasets match "council district," although
   district data is used more widely. Recommendation: apply consistent tags and
   keywords for shared keys such as council district.
3. **Titles carry freshness.** No budget dataset title is newer than 2013.
   Recommendation: confirm whether newer budgets exist under other titles, and
   publish update dates and schedules for featured datasets.
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