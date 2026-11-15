# Evaluation results

Run on 2026-11-15 09:35 against the live portal and City GIS layers.

## Known answers

Confirm each one on data.houstontx.gov, then ask the same question in the app.

| # | Question | Known answer |
|---|---|---|
| 1 | Which department publishes the most datasets? | Legacy Portal (28), Planning and Development (25), Finance Department (13) |
| 2 | What columns does the most recent Payroll table have, and how many rows? | [Payroll 2026](https://data.houstontx.gov/dataset/payroll/resource/8fd8aaa8-3ed4-4aef-b5b6-b4bc65e5c2ab), chosen by year 2026 in its name: 26220 rows; columns: _id, Hash1, Hash2, Birth Year, Gender, Race, Pay Grade, FLSA Status, EEOJ Code, Employment Type, Department ID, Department Name, Status, Year, Date Position Began, Date Position Ended, Annual Base Salary, Gross Pay, Base Pay, Overtime Pay, Other Pay |
| 3 | How many datasets include council district data? | 4 (keyword search for "council district") |
| 4 | Which budget year is the newest on the portal? | 2013 (Fiscal Year 2013 TIRZ Capital Improvement Projects Budget) |
| 5 | What is the average commute time of City of Houston employees? | Not on the portal. The agent should say so and not invent a number. |
| 6 (Ask Houston+) | What council district and super neighborhood is 901 Bagby St in? | Inside city limits: True; council district: {"DISTRICT": "I", "MEMBER": "JOAQUIN MARTINEZ", "PHONE": "832-393-3011", "YEAR": 2024}; super neighborhood: {"PERIMETER": 39256.388, "POLYID": 61, "SNBNAME": "DOWNTOWN", "cohgisCOHG": 0, "cohgisCO_1": 0, "COUNCIL_AC": " ", "RECOGNITIO": " ", "SnbrInfoUR": "http://www.houstontx.gov/superneighborhoods/profiles/SN_61.htm", "WeCan": " ", "Top10": " "} |
| 7 | Which three departments have the most employees on the newest payroll? | Police (7,759), Fire (5,402), Houston Public Works (4,751); 26,220 of 26,220 rows read, complete: True |
| 8 (Ask Houston+) | Is it a good time to be outside in 77002? | Today: Showers And Thunderstorms, 60°F, rain 88%; alerts: none; AQI 55 (Moderate). Changes hourly: compare with the agent's answer at the same time. |

## Response times (seconds, 10 calls each, run locally)

| Tool | First call | Median | Slowest | Errors |
|---|---|---|---|---|
| houston_search_datasets | 0.18 | 0.19 | 0.34 | 0 |
| houston_browse_catalog | 0.59 | 0.58 | 0.78 | 0 |
| houston_get_dataset | 0.38 | 0.43 | 0.49 | 0 |
| houston_query_records | 0.13 | 0.15 | 0.18 | 0 |
| houston_lookup_address | 0.27 | 0.20 | 0.27 | 0 |
| houston_weather_forecast * | 0.28 | 0.00 | 0.28 | 0 |
| houston_air_quality * | 0.27 | 0.00 | 0.27 | 0 |

\* Weather and air quality responses are cached briefly on the server, so the first call measures the live National Weather Service and AirNow, and later calls measure the cache.
