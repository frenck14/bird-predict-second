# Manx Shearwater (Noordse Pijlstormvogel) feasibility assessment

GBIF data retrieved **2026-10-15**.

## Scope and method

The GBIF Species Match API returned an exact, accepted species match for *Puffinus puffinus (Brunnich, 1764)* (taxon key `5229380`). Occurrence counts use `taxonKey` and `country=NL` with no additional basis-of-record filter. GBIF's `eventDate` facet aggregates every matching occurrence without paging through individual records. Daily counts use the first ten characters of each facet date, matching the existing Bird-Predict date rule. Partial dates cannot be assigned to a unique observation day.

The raw Manx Shearwater event-date facet buckets are archived at `data/raw/manx_shearwater_event_date_facets.csv`. The shared weather dataset spans **2010-10-01 to 2026-08-10** (5,793 dates); weather-window totals below include only GBIF days present in that calendar.

## Manx Shearwater record volume

| Measure | Count |
|---|---:|
| Total GBIF occurrence records | 1,369 |
| Records assigned to a complete calendar date | 1,348 |
| Records in partial-date facets | 1 |
| Records with no event-date facet | 20 |
| Distinct observation days with complete dates | 305 |
| Complete-date observation period | 1914-09-15 to 2026-07-09 |

### Records per year

Counts below include only records assigned to a complete calendar date; years with no records are omitted. The last year may be partial.

| Year | Records |
|---:|---:|
| 1914 | 1 |
| 1918 | 1 |
| 1921 | 1 |
| 1927 | 1 |
| 1941 | 1 |
| 1950 | 2 |
| 1952 | 1 |
| 1970 | 1 |
| 1971 | 15 |
| 1974 | 2 |
| 1980 | 8 |
| 1981 | 15 |
| 1983 | 12 |
| 1984 | 8 |
| 1985 | 1 |
| 1986 | 1 |
| 1987 | 5 |
| 1988 | 4 |
| 1990 | 3 |
| 1992 | 2 |
| 1994 | 4 |
| 1995 | 3 |
| 1996 | 2 |
| 1998 | 4 |
| 1999 | 6 |
| 2000 | 1 |
| 2001 | 3 |
| 2002 | 1 |
| 2003 | 1 |
| 2004 | 7 |
| 2005 | 6 |
| 2006 | 3 |
| 2007 | 21 |
| 2008 | 6 |
| 2009 | 15 |
| 2010 | 24 |
| 2011 | 55 |
| 2012 | 18 |
| 2013 | 9 |
| 2014 | 32 |
| 2015 | 5 |
| 2016 | 9 |
| 2017 | 114 |
| 2018 | 59 |
| 2019 | 61 |
| 2020 | 24 |
| 2021 | 14 |
| 2022 | 34 |
| 2023 | 466 |
| 2024 | 17 |
| 2025 | 238 |
| 2026 | 1 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2025-09-16 | 123 |
| 2 | 2023-10-22 | 83 |
| 3 | 2023-10-21 | 76 |
| 4 | 2023-10-14 | 46 |
| 5 | 2023-10-28 | 38 |
| 6 | 2023-10-07 | 35 |
| 7 | 2023-10-23 | 34 |
| 8 | 2017-09-14 | 33 |
| 9 | 2025-09-21 | 33 |
| 10 | 2017-09-13 | 29 |
| 11 | 2025-09-18 | 27 |
| 12 | 2023-10-29 | 23 |
| 13 | 2018-09-23 | 22 |
| 14 | 2014-04-12 | 20 |
| 15 | 2017-09-12 | 17 |
| 16 | 2022-10-08 | 15 |
| 17 | 2019-09-30 | 14 |
| 18 | 2023-10-30 | 14 |
| 19 | 2011-09-07 | 13 |
| 20 | 2023-10-20 | 13 |

### High-count days

| Daily threshold | All complete-date years | Shared weather calendar |
|---:|---:|---:|
| ≥10 records/day | 31 | 30 |
| ≥25 records/day | 11 | 11 |
| ≥50 records/day | 3 | 3 |

## Comparison with existing target species

All three species were queried from GBIF in the same run, using the same country and event-date facet method. The first table covers all complete-date years; the second restricts counts to the shared weather calendar.

| Species | GBIF records | Complete-date records | Observation days | ≥10 days | ≥25 days | ≥50 days |
|---|---:|---:|---:|---:|---:|---:|
| Manx Shearwater | 1,369 | 1,348 | 305 | 31 | 11 | 3 |
| Yellow-browed Warbler | 38,941 | 38,910 | 1,579 | 583 | 371 | 215 |
| Pallid Swift | 3,029 | 3,011 | 85 | 46 | 31 | 16 |

| Species | Complete-date records in weather window | Observation days | ≥10 days | ≥25 days | ≥50 days |
|---|---:|---:|---:|---:|---:|
| Manx Shearwater | 1,162 | 176 | 30 | 11 | 3 |
| Yellow-browed Warbler | 36,581 | 1,057 | 528 | 356 | 210 |
| Pallid Swift | 2,971 | 83 | 45 | 30 | 16 |

## Forecasting feasibility and recommendation

Manx Shearwater has substantially less data than either existing target: about 28.4× fewer GBIF records than Yellow-browed Warbler and 2.2× fewer than Pallid Swift. It has more distinct observation days than Pallid Swift, but its high-count targets are much rarer: within the shared weather period it has 30 ≥10-record days, 11 ≥25-record days, and 3 ≥50-record days, compared with 45, 30, and 16 for Pallid Swift.

The ≥10 target has only 30 positive days in the weather window, and the ≥25 and ≥50 targets have 11 and 3. These events are concentrated in a few years (most notably 2017, 2023, and 2025), leaving too few independent positive events for credible forward-held-out model evaluation, especially at the higher thresholds. A model could be prototyped for exploratory analysis, but its scores would be unstable and could mostly reflect seasonality, observer effort, or isolated reporting surges.

**Recommendation: do not make Manx Shearwater the next operational Bird-Predict target yet.** Keep it as a candidate for a descriptive or exploratory study; reconsider forecasting after more high-count events accrue or after a broader, validated observation source and a longer weather history are available.

## Data caveats

- GBIF `country=NL` uses the occurrence country code, not a coordinate-based Netherlands boundary.
- The total count includes records without usable day-level dates and may include records from multiple datasets or observation types. These counts represent reported occurrences, not independent birds or population abundance.
- Of the 1,369 Manx Shearwater records, 20 have no event-date facet and 1 has only a partial date.
- The event-date facets are an aggregate of all matching GBIF records, not a record-level occurrence download. GBIF data can change after this retrieval date.
