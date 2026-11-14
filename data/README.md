# Data

## houston_zip_centroids.csv

The 118 ZIP codes that are fully or partially within the City of Houston, each with a representative center point.

| Column | Meaning |
|---|---|
| `zip` | 5-digit ZIP code (stored as text) |
| `lat` | Latitude of the ZIP's internal point |
| `lon` | Longitude of the ZIP's internal point |

**Sources**
- ZIP list: City of Houston Open Data Portal: "ZIP codes fully within City of Houston" (50) and "ZIP codes partially within City of Houston" (68), combined.
- Center points: U.S. Census Bureau, 2026 ZCTA Gazetteer file (`INTPTLAT`, `INTPTLONG`).

ZCTAs are the Census Bureau's approximations of USPS ZIP code areas. The points are good for finding the nearest weather grid or air quality monitor. They aren't exact ZIP boundaries.

Used to look up weather forecasts (National Weather Service) and air quality (EPA AirNow) by ZIP code.
