# Bird-Predict Candidate-Species Assessment

GBIF data retrieved **2026-10-15**.

## Scope and method

GBIF Species Match and the occurrence event-date facet API were queried for each taxon in the same run. Each match must be an exact, accepted species-level match; occurrence queries use `taxonKey` and `country=NL`, with no basis-of-record filter. Total records are the GBIF occurrence count. Complete-date records and observation days are derived from event-date facet buckets whose first ten characters form a valid ISO calendar date; partial dates are excluded from day-level metrics. Unfaceted records cannot be assigned a date.

The shared KNMI weather calendar spans **2010-10-01 to 2026-08-10** (5,793 dates). Candidate forecastability is assessed using only dated records that fall within this common weather window. The shared calendar's uncovered historical years are not treated as weather-supported events.

## Candidate species: record summaries

| Species | Scientific name | GBIF records | Complete-date records | Partial-date records | No-date records | Observation days | Complete-date period |
|---|---|---:|---:|---:|---:|---|---|
| Blauwstaart | *Tarsiger cyanurus* | 4,145 | 4,127 | 0 | 18 | 173 | 1967-10-16 to 2025-10-22 |
| Citroenkwikstaart | *Motacilla citreola* | 1,668 | 1,650 | 0 | 18 | 135 | 1984-08-24 to 2026-05-10 |
| Kleine Spotvogel | *Iduna caligata* | 917 | 899 | 0 | 18 | 58 | 1982-10-02 to 2023-09-16 |
| Veldrietzanger | *Acrocephalus agricola* | 356 | 338 | 0 | 18 | 39 | 1967-05-27 to 2024-09-03 |

## Candidate species: annual counts and peak days

The following annual counts and top days cover all GBIF complete-date facets, including dates outside the KNMI weather calendar.

### Blauwstaart (*Tarsiger cyanurus*)

Archived date facets: `data/raw/blauwstaart_event_date_facets.csv`.

### Records per year

Counts include records with complete calendar dates; years without records are omitted. The most recent year may be incomplete.

| Year | Complete-date records |
|---:|---:|
| 1967 | 2 |
| 1985 | 9 |
| 1999 | 1 |
| 2007 | 721 |
| 2008 | 10 |
| 2009 | 1 |
| 2010 | 18 |
| 2011 | 421 |
| 2013 | 240 |
| 2014 | 2 |
| 2015 | 131 |
| 2016 | 553 |
| 2017 | 190 |
| 2019 | 210 |
| 2020 | 1,116 |
| 2021 | 168 |
| 2022 | 255 |
| 2023 | 32 |
| 2024 | 45 |
| 2025 | 2 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2016-10-15 | 224 |
| 2 | 2016-10-16 | 155 |
| 3 | 2015-04-10 | 131 |
| 4 | 2020-10-17 | 126 |
| 5 | 2020-10-16 | 118 |
| 6 | 2020-10-12 | 117 |
| 7 | 2017-11-26 | 94 |
| 8 | 2019-10-27 | 90 |
| 9 | 2016-12-06 | 89 |
| 10 | 2007-01-03 | 85 |
| 11 | 2013-10-15 | 84 |
| 12 | 2011-10-22 | 79 |
| 13 | 2007-01-04 | 72 |
| 14 | 2016-10-17 | 71 |
| 15 | 2017-11-25 | 70 |
| 16 | 2020-10-13 | 70 |
| 17 | 2020-10-11 | 64 |
| 18 | 2007-01-14 | 62 |
| 19 | 2021-10-16 | 62 |
| 20 | 2007-01-07 | 61 |

#### High-count days

| Daily record threshold | All complete-date years | Shared KNMI weather calendar |
|---:|---:|---:|
| ≥10 records/day | 89 | 69 |
| ≥25 records/day | 55 | 49 |
| ≥50 records/day | 29 | 24 |

### Citroenkwikstaart (*Motacilla citreola*)

Archived date facets: `data/raw/citroenkwikstaart_event_date_facets.csv`.

### Records per year

Counts include records with complete calendar dates; years without records are omitted. The most recent year may be incomplete.

| Year | Complete-date records |
|---:|---:|
| 1984 | 8 |
| 1991 | 7 |
| 1993 | 50 |
| 1994 | 8 |
| 1995 | 39 |
| 1996 | 9 |
| 1997 | 1 |
| 1998 | 14 |
| 1999 | 32 |
| 2000 | 1 |
| 2001 | 49 |
| 2002 | 15 |
| 2006 | 34 |
| 2007 | 22 |
| 2008 | 204 |
| 2009 | 156 |
| 2010 | 195 |
| 2011 | 124 |
| 2012 | 32 |
| 2013 | 36 |
| 2014 | 34 |
| 2015 | 186 |
| 2016 | 106 |
| 2017 | 80 |
| 2018 | 5 |
| 2019 | 5 |
| 2020 | 60 |
| 2021 | 8 |
| 2022 | 30 |
| 2024 | 80 |
| 2025 | 16 |
| 2026 | 4 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2015-05-10 | 93 |
| 2 | 2017-05-05 | 75 |
| 3 | 2024-04-29 | 68 |
| 4 | 2008-08-23 | 63 |
| 5 | 1993-05-05 | 49 |
| 6 | 2001-04-29 | 49 |
| 7 | 2010-11-01 | 48 |
| 8 | 2010-11-02 | 47 |
| 9 | 2016-04-29 | 42 |
| 10 | 2010-05-13 | 39 |
| 11 | 2010-10-31 | 39 |
| 12 | 2009-09-06 | 37 |
| 13 | 2016-08-21 | 36 |
| 14 | 2008-08-24 | 34 |
| 15 | 2008-08-25 | 34 |
| 16 | 2014-05-29 | 34 |
| 17 | 2009-08-19 | 30 |
| 18 | 2020-08-22 | 30 |
| 19 | 2011-08-25 | 29 |
| 20 | 2015-05-07 | 29 |

#### High-count days

| Daily record threshold | All complete-date years | Shared KNMI weather calendar |
|---:|---:|---:|
| ≥10 records/day | 49 | 24 |
| ≥25 records/day | 22 | 14 |
| ≥50 records/day | 4 | 3 |

### Kleine Spotvogel (*Iduna caligata*)

Archived date facets: `data/raw/kleine_spotvogel_event_date_facets.csv`.

### Records per year

Counts include records with complete calendar dates; years without records are omitted. The most recent year may be incomplete.

| Year | Complete-date records |
|---:|---:|
| 1982 | 5 |
| 1988 | 5 |
| 1990 | 7 |
| 1995 | 10 |
| 1996 | 116 |
| 1998 | 3 |
| 2001 | 5 |
| 2003 | 6 |
| 2006 | 65 |
| 2007 | 129 |
| 2008 | 63 |
| 2009 | 61 |
| 2013 | 99 |
| 2014 | 77 |
| 2015 | 31 |
| 2016 | 61 |
| 2017 | 51 |
| 2018 | 86 |
| 2019 | 1 |
| 2020 | 1 |
| 2023 | 17 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2013-10-04 | 77 |
| 2 | 2014-09-17 | 77 |
| 3 | 2007-09-15 | 61 |
| 4 | 2008-09-13 | 60 |
| 5 | 2016-09-06 | 56 |
| 6 | 2017-09-19 | 51 |
| 7 | 2007-09-16 | 48 |
| 8 | 2018-09-14 | 40 |
| 9 | 1996-08-31 | 39 |
| 10 | 2006-10-09 | 31 |
| 11 | 2009-09-12 | 28 |
| 12 | 1996-09-01 | 26 |
| 13 | 2015-09-12 | 25 |
| 14 | 1996-09-10 | 22 |
| 15 | 2018-09-16 | 22 |
| 16 | 2009-09-13 | 21 |
| 17 | 2018-09-15 | 20 |
| 18 | 2006-10-10 | 19 |
| 19 | 2006-10-11 | 15 |
| 20 | 2023-09-16 | 15 |

#### High-count days

| Daily record threshold | All complete-date years | Shared KNMI weather calendar |
|---:|---:|---:|
| ≥10 records/day | 23 | 9 |
| ≥25 records/day | 13 | 6 |
| ≥50 records/day | 6 | 4 |

### Veldrietzanger (*Acrocephalus agricola*)

Archived date facets: `data/raw/veldrietzanger_event_date_facets.csv`.

### Records per year

Counts include records with complete calendar dates; years without records are omitted. The most recent year may be incomplete.

| Year | Complete-date records |
|---:|---:|
| 1967 | 1 |
| 1989 | 1 |
| 1994 | 12 |
| 1997 | 3 |
| 1999 | 5 |
| 2003 | 5 |
| 2005 | 1 |
| 2006 | 9 |
| 2007 | 2 |
| 2008 | 12 |
| 2009 | 4 |
| 2010 | 2 |
| 2011 | 9 |
| 2012 | 2 |
| 2013 | 11 |
| 2014 | 3 |
| 2015 | 4 |
| 2016 | 4 |
| 2017 | 1 |
| 2018 | 6 |
| 2019 | 6 |
| 2020 | 1 |
| 2022 | 5 |
| 2024 | 229 |

### Top 20 record-count days

| Rank | Date | Records |
|---:|---|---:|
| 1 | 2024-09-02 | 210 |
| 2 | 2024-09-03 | 19 |
| 3 | 1994-09-18 | 12 |
| 4 | 2013-08-20 | 11 |
| 5 | 2019-09-10 | 6 |
| 6 | 1999-10-16 | 5 |
| 7 | 2006-09-17 | 5 |
| 8 | 2022-10-03 | 5 |
| 9 | 2006-10-14 | 4 |
| 10 | 2008-09-13 | 4 |
| 11 | 2011-09-10 | 4 |
| 12 | 2018-10-15 | 4 |
| 13 | 1997-08-12 | 3 |
| 14 | 2003-09-12 | 3 |
| 15 | 2008-06-04 | 3 |
| 16 | 2008-09-10 | 3 |
| 17 | 2009-09-09 | 3 |
| 18 | 2011-08-26 | 3 |
| 19 | 2015-06-07 | 3 |
| 20 | 2003-10-02 | 2 |

#### High-count days

| Daily record threshold | All complete-date years | Shared KNMI weather calendar |
|---:|---:|---:|
| ≥10 records/day | 4 | 3 |
| ≥25 records/day | 1 | 1 |
| ≥50 records/day | 1 | 1 |

## Comparison with established Bird-Predict species

The established comparison species were queried in the same GBIF run with the same country and event-date facet rules. This table's counts are limited to the common KNMI date range and are directly comparable across all eight taxa.

| Rank by weather-window support | Species | GBIF records | Complete-date records (all dates) | Complete-date records (KNMI window) | Observation days (KNMI window) | ≥10 days | Years with ≥10 days | ≥25 days | ≥50 days |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Yellow-browed Warbler | 38,941 | 38,910 | 36,581 | 1,057 | 528 | 16 | 356 | 210 |
| 2 | Blauwstaart | 4,145 | 4,127 | 3,383 | 113 | 69 | 11 | 49 | 24 |
| 3 | Red-throated Pipit | 3,330 | 3,310 | 2,705 | 405 | 60 | 14 | 22 | 8 |
| 4 | Pallid Swift | 3,029 | 3,011 | 2,971 | 83 | 45 | 11 | 30 | 16 |
| 5 | Manx Shearwater | 1,369 | 1,348 | 1,162 | 176 | 30 | 8 | 11 | 3 |
| 6 | Citroenkwikstaart | 1,668 | 1,650 | 940 | 77 | 24 | 12 | 14 | 3 |
| 7 | Kleine Spotvogel | 917 | 899 | 424 | 23 | 9 | 7 | 6 | 4 |
| 8 | Veldrietzanger | 356 | 338 | 281 | 20 | 3 | 2 | 1 | 1 |

## Forecast-potential ranking and recommendation

The ranking above is a **data-support / feasibility ranking**, not a claim of measured forecast skill. It is ordered lexicographically by the number of ≥10-record days in the shared weather window, then ≥25 days, ≥50 days, the number of years with at least one ≥10-record day, observation days, and complete-date records in that window. The ≥10 target is the primary Bird-Predict event threshold; the higher thresholds indicate whether a taxon can support more selective targets. This transparent ordering avoids an arbitrary composite score.

The four established species also have measured forward-chained results. Their ranking below is by mean best-model PR-AUC lift over the matched seasonal baseline across the 15 threshold/horizon scenarios. These results are empirical skill evidence; no such validation exists yet for the four new candidates.

| Rank | Previously evaluated species | Mean PR-AUC lift | Scenarios beating seasonality |
|---:|---|---:|---:|
| 1 | Yellow-browed Warbler | +0.1591 | 15/15 |
| 2 | Pallid Swift | +0.0864 | 14/15 |
| 3 | Manx Shearwater | +0.0160 | 13/15 |
| 4 | Red-throated Pipit | +0.0142 | 8/15 |

Yellow-browed Warbler and Pallid Swift show stronger weather-model results than Red-throated Pipit and Manx Shearwater in the existing comparison. A high candidate rank by records alone cannot establish that weather improves its forecast.

Among the four new candidates, the data-support ranking is 1. Blauwstaart, 2. Citroenkwikstaart, 3. Kleine Spotvogel, 4. Veldrietzanger. Prioritize the top new candidate for a forward-chained experiment only if its ≥10 high-count dates span enough distinct years to permit meaningful held-out evaluation. If all four candidates have few or no ≥10 days in the KNMI window, their records are not yet adequate for this count-target methodology.

### Interpretation and caveats

- These are GBIF occurrence/reporting counts, not numbers of individual birds or population-abundance estimates.
- GBIF reporting effort, data providers, and observer activity can vary by year and can be associated with both weather and season.
- `country=NL` is GBIF's country-code filter and is not a coordinate-based Netherlands boundary.
- The most recent year may be incomplete, date facets can change as GBIF is updated, and partial-date records do not count as complete-date observations.
- Many top-count days may belong to one observation or reporting episode; positive dates should not be assumed independent.
- The common KNMI calendar starts in 2010 and ends on 2026-08-10; older records are summarized but excluded from the weather-window feasibility ranking.
