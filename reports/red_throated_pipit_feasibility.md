# Red-throated Pipit (Anthus cervinus) feasibility assessment

GBIF data retrieved **2026-10-15**.

## Scope and method

GBIF Species Match returned an exact, accepted species match for *Anthus cervinus (Pallas, 1811)* (taxon key `2490283`). Occurrences use `taxonKey` and `country=NL`, without a basis-of-record filter. Counts were retrieved using GBIF's event-date facet, rather than paging through individual occurrences. Daily counts use the first ten characters of each date facet; partial dates cannot be assigned to a unique observation day.

The Pipit facet buckets are archived at `data/raw/red_throated_pipit_event_date_facets.csv`. The project's shared weather calendar spans **2010-10-01 to 2026-08-10** (5,793 days). Weather-window counts include only observation dates present in that calendar.

## Red-throated Pipit record volume

| Measure | Count |
|---|---:|
| Total GBIF records | 3,330 |
| Records assigned to a complete calendar date | 3,310 |
| Records in partial-date facets | 2 |
| Records with no event-date facet | 18 |
| Distinct observation days with complete dates | 657 |
| Complete-date observation period | 1964-09-05 to 2026-05-11 |

### Records per year

Counts include records assigned to a complete calendar date; years with no records are omitted. The latest year may be partial.

| Year | Records |
|---:|---:|
| 1964 | 1 |
| 1965 | 1 |
| 1967 | 3 |
| 1968 | 5 |
| 1970 | 4 |
| 1976 | 1 |
| 1977 | 1 |
| 1978 | 3 |
| 1979 | 3 |
| 1980 | 3 |
| 1981 | 2 |
| 1982 | 1 |
| 1983 | 9 |
| 1985 | 4 |
| 1986 | 1 |
| 1987 | 13 |
| 1988 | 9 |
| 1989 | 4 |
| 1990 | 10 |
| 1991 | 25 |
| 1992 | 25 |
| 1993 | 26 |
| 1994 | 8 |
| 1995 | 13 |
| 1996 | 28 |
| 1997 | 8 |
| 1998 | 18 |
| 1999 | 14 |
| 2000 | 16 |
| 2001 | 16 |
| 2002 | 9 |
| 2003 | 10 |
| 2004 | 12 |
| 2005 | 8 |
| 2006 | 18 |
| 2007 | 14 |
| 2008 | 15 |
| 2009 | 181 |
| 2010 | 96 |
| 2011 | 192 |
| 2012 | 84 |
| 2013 | 56 |
| 2014 | 97 |
| 2015 | 45 |
| 2016 | 100 |
| 2017 | 158 |
| 2018 | 464 |
| 2019 | 221 |
| 2020 | 293 |
| 2021 | 439 |
| 2022 | 123 |
| 2023 | 52 |
| 2024 | 86 |
| 2025 | 134 |
| 2026 | 128 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2021-05-01 | 178 |
| 2 | 2018-05-09 | 138 |
| 3 | 2018-05-11 | 104 |
| 4 | 2019-10-26 | 102 |
| 5 | 2021-05-02 | 77 |
| 6 | 2018-05-08 | 74 |
| 7 | 2017-05-06 | 65 |
| 8 | 2018-05-10 | 57 |
| 9 | 2009-05-01 | 41 |
| 10 | 2011-05-07 | 40 |
| 11 | 2021-04-30 | 38 |
| 12 | 2009-05-02 | 33 |
| 13 | 2020-09-26 | 33 |
| 14 | 2022-05-08 | 33 |
| 15 | 2026-05-01 | 33 |
| 16 | 2019-10-25 | 32 |
| 17 | 2022-05-09 | 30 |
| 18 | 2021-05-03 | 29 |
| 19 | 2019-10-27 | 28 |
| 20 | 2026-05-02 | 28 |

### High-count days

| Daily threshold | All complete-date years | Shared weather calendar |
|---:|---:|---:|
| ≥10 records/day | 71 | 60 |
| ≥25 records/day | 25 | 22 |
| ≥50 records/day | 8 | 8 |

## Comparison with Bird-Predict candidate species

Each species was queried from GBIF in the same run using the same country and event-date facet method. The first table covers all complete-date years; the second uses only the shared weather dates.

| Species | GBIF records | Complete-date records | Observation days | ≥10 days | ≥25 days | ≥50 days |
|---|---:|---:|---:|---:|---:|---:|
| Red-throated Pipit | 3,330 | 3,310 | 657 | 71 | 25 | 8 |
| Yellow-browed Warbler | 38,941 | 38,910 | 1,579 | 583 | 371 | 215 |
| Pallid Swift | 3,029 | 3,011 | 85 | 46 | 31 | 16 |
| Manx Shearwater | 1,369 | 1,348 | 305 | 31 | 11 | 3 |

| Species | Complete-date records in weather window | Observation days | ≥10 days | ≥25 days | ≥50 days |
|---|---:|---:|---:|---:|---:|
| Red-throated Pipit | 2,705 | 405 | 60 | 22 | 8 |
| Yellow-browed Warbler | 36,581 | 1,057 | 528 | 356 | 210 |
| Pallid Swift | 2,971 | 83 | 45 | 30 | 16 |
| Manx Shearwater | 1,162 | 176 | 30 | 11 | 3 |

## Forecasting feasibility and recommendation

Red-throated Pipit has 3,330 GBIF records, versus 38,941 for Yellow-browed Warbler, 3,029 for Pallid Swift, and 1,369 for Manx Shearwater. Its target-event support in the common weather period is 60 ≥10-record days, 22 ≥25-record days, and 8 ≥50-record days.

Against Manx Shearwater, the Pipit has more positive days at all three thresholds: 60 vs 30 at ≥10, 22 vs 11 at ≥25, and 8 vs 3 at ≥50.
Against Pallid Swift, the Pipit has more ≥10-record days (60 vs 45), but fewer ≥25-record days (22 vs 30) and ≥50-record days (8 vs 16).

This makes the Pipit a better-supported next experiment than Manx Shearwater, particularly for the ≥10 target, but does not establish it as a better forecaster than Pallid Swift.


GBIF volume and high-count-day totals indicate data availability, not forecast skill. Before choosing it over the existing targets, it would still need the same forward-chained evaluation against seasonal baselines, with enough positive events in the held-out years to make metrics interpretable.

**Recommendation:** prioritize Red-throated Pipit over Manx Shearwater for the next exploratory Bird-Predict evaluation. Treat it as a plausible ≥10-event target, not as an established upgrade over Pallid Swift; do not promote it operationally until it passes the shared forward-chained evaluation.

## Data caveats

- GBIF `country=NL` is the country-code filter, not a coordinate-based Netherlands boundary.
- GBIF records represent reported occurrences, not independent birds or population abundance. Reporting effort and data-source coverage can vary over time.
- Of 3,330 total records, 18 have no event-date facet and 2 have only a partial date.
- The total is a GBIF count and includes records without usable day-level dates. Facets can change as GBIF is updated.
