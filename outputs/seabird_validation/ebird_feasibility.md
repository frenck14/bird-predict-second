# eBird feasibility audit for seabird forecasting

Audit only. No model code, thresholds or outputs were changed.

**Evidence labels.** *Verified* means I checked it in this repository or against the live GBIF API on 2026-11-12. *Background* means general knowledge of eBird products that I did not re-check here. Confirm background items before building on them.

## Bottom line

> **Which eBird features are most likely to improve BirdCast while remaining leakage-free?**

Only **lagged, effort-aware reporting-rate and regional-activity features** for the species and regions where eBird coverage is dense (Great Britain and Ireland). Lag them by at least one day. Build them from a **frozen archive** snapshot, not from today's data.

Expect a modest gain at best, mainly for European Storm-petrel and Manx Shearwater. Three facts limit what eBird can add:

1. **The labels already come largely from eBird.** The seabird cache is GBIF occurrences, and eBird is the dominant GBIF source for these species (table below). A feature built from eBird counts is therefore partly a lagged copy of the target. It will look good in validation because of persistence and reporting effort, not because it is predictive.
2. **The Netherlands is thinly covered by eBird.** Dutch records mostly come from other platforms, so eBird features say little about the Dutch coast, which the weather features target.
3. **GBIF only carries detections.** It has no checklists and no absences, so true reporting rate cannot be computed from GBIF alone.

## Current pipeline context (verified)

- Model inputs are KNMI weather features (`src/seabird_features.py`, `_build_seabird_features`) plus calendar terms. No occurrence or eBird lag features are used.
- Labels are daily occurrence-record counts per species and country, from `validation/seabirds/observations.csv`. The source is "GBIF occurrence cache (HUMAN_OBSERVATION)". The count is the number of records, not individuals.
- The cached files have no `datasetKey`, so the eBird share of the labels is not visible locally. The share below comes from the live GBIF API.
- `src/next_dutch_firsts_ebird.py` already uses the eBird API (`data/obs/{region}/recent`, `back=30`, key in `EBIRD_API_KEY`). That integration serves the Next Dutch Firsts forecast and is not part of the seabird forecasts.

## eBird share of seabird records (verified, GBIF API)

GBIF `HUMAN_OBSERVATION` records, 2010-2026, eBird dataset `4fa7b334-ce0d-4e88-aaae-2e0c138d049e`. Counts are live GBIF counts and will not match the local cache exactly.

| Species | GB eBird/all | IE eBird/all | NL eBird/all | BE eBird/all | DK eBird/all | All 5 countries | Records from eBird |
|---|---:|---:|---:|---:|---:|---:|---:|
| Northern Fulmar | 70,249 / 90,409 | 6,355 / 11,432 | 193 / 4,379 | 119 / 1,345 | 597 / 12,746 | 77,513 / 120,311 | **64%** |
| Manx Shearwater | 24,628 / 29,363 | 4,459 / 6,552 | 127 / 1,357 | 157 / 1,134 | 68 / 1,027 | 29,439 / 39,433 | **75%** |
| European Storm-petrel | 4,354 / 5,511 | 1,127 / 1,344 | 13 / 157 | 28 / 169 | 10 / 259 | 5,532 / 7,440 | **74%** |
| Sooty Shearwater | 6,623 / 6,819 | 1,080 / 1,229 | 219 / 935 | 159 / 818 | 111 / 3,380 | 8,192 / 13,181 | **62%** |
| Great Shearwater | 2,130 / 2,251 | 498 / 556 | 0 / 3 | 0 / 0 | 2 / 14 | 2,630 / 2,824 | **93%** |

Dutch eBird share of all Dutch records: Fulmar 4%, Manx 9%, Storm-petrel 8%, Sooty 23%, Great about 0%.

eBird records exist in every year from 2010 to 2025 for all five species. Annual eBird record counts rise steeply over the period. For example, Fulmar GB records go from 634 in 2010 to 12,386 in 2025, and Storm-petrel from 67 to 831. This growth is mostly reporting effort, so any raw eBird count is non-stationary. The rolling validation (2015-2026) trains on earlier, much sparser years. An effort-unadjusted eBird feature would drift between training and test.

Each eBird record carries an `eventID` (checklist ID, e.g. `S125080867`), `eventDate`, `eventTime`, `individualCount`, an anonymised observer ID and a location ID. `samplingProtocol` and `samplingEffort` were empty in the sample I inspected, so duration and distance are not available via GBIF.

## Candidate features

Classification: **SAFE** = can be built leakage-free from data available at forecast time. **POSSIBLE** = safe only with specific controls or data not yet in the repository. **UNSAFE** = leaks or cannot be reproduced historically.

| # | Feature | Definition | Geographic coverage | Temporal coverage | Update frequency | Leakage risk | Class |
|---|---|---|---|---|---|---|---|
| 1 | Checklist frequency | Number of eBird checklists in a region on day *t-1* (any species), as an effort proxy | Needs the checklist table. GBIF has none. Source: eBird Basic Dataset (EBD) *sampling event* file (background) | EBD from 1900s, dense from about 2010 (background) | EBD: quarterly releases. API: live. | Low if lagged by at least 1 day and frozen. Back-filled and reviewed records change later totals. | **POSSIBLE** |
| 2 | Reporting rate | Share of checklists in a region on day *t-1* that list the species | Same as 1; needs the EBD sampling-event file with absences inferred from complete checklists (background) | Same as 1 | Same as 1 | Low if lagged and built only from records known at the cutoff. Same-day rate is **UNSAFE** (it is the target). | **POSSIBLE** |
| 3 | Abundance | Mean or total individuals per checklist on day *t-1* | GB, IE, DK, BE good; NL poor (table above) | 2010-2025 present | EBD quarterly | Medium. Counts are heavily right-skewed. Lagged abundance partly encodes the previous event. Target uses record counts from the same source. | **POSSIBLE** |
| 4 | Effort-adjusted occurrence | Detections per checklist over the last 7 days (rolling) | GB, IE strong; NL weak | 2010-2025 | EBD quarterly | Low-medium if the window ends at *t-1*. Needs checklist denominators, so not buildable from GBIF. | **POSSIBLE** |
| 5 | Recent regional activity (GBIF-derived) | Detection records or distinct observers per day in GB/IE over the previous 3 or 7 days, from GBIF eBird records | GB, IE only (eBird covers 70-90% of records; Fulmar IE 56%) | 2010-2025 | GBIF re-indexes eBird roughly monthly | Medium. Detections only, so it confounds activity with effort. Lagged versions are autoregressive in the label. | **POSSIBLE** |
| 6 | Species occurrence lag (any source) | Event or no event on day *t-1* | Whole target region | Full | n/a | High persistence. Adds apparent skill that a naive "yesterday" baseline already has. Must be compared with that baseline. | **POSSIBLE** (baseline only) |
| 7 | Same-day or future eBird data | Any eBird record dated *t* or later | n/a | n/a | n/a | Direct target leakage. | **UNSAFE** |
| 8 | Today's eBird snapshot used for past dates | Rebuilding historical features from the current GBIF/EBD release | n/a | n/a | n/a | Records are added late, reviewed and revised (GBIF `lastInterpreted` was 2026-11-06 for a 2023 record). A hindcast on today's data sees more than was known on day *t*. | **UNSAFE** unless frozen per cutoff |
| 9 | eBird Status & Trends abundance or range surfaces | Modelled weekly relative abundance maps | Global, 3 km (background) | Annual releases of full-year models (background) | Annual | The model is fitted on all years, including future years, and smooths seasonal patterns. It leaks future data into past dates. | **UNSAFE** |
| 10 | eBird API recent observations | `data/obs/{region}/recent` | GB, IE, BE, DE, DK (already integrated) | Last 30 days only | Live | Only usable for live forecasting, not for hindcast or validation. No history. | **UNSAFE** for validation, SAFE for live use |
| 11 | Hotspot or location-level counts | Records at named hotspots, e.g. seawatching points | Per location | Per site | EBD | Site coverage changes. Sparse. High-cardinality. | **UNSAFE** at first, because of overfitting and drift |
| 12 | Observer counts and effort time | Observers per day, hours watched | EBD only | EBD only | Quarterly | Needs EBD. `samplingEffort` is empty in GBIF. | **POSSIBLE** |

## Historical availability by species

Based on the table above and the date ranges in `validation/seabirds/observations.csv` (all five species have data from 2010).

| Species | eBird coverage of the target region | Event days (2015-2026) | Usable features | Verdict |
|---|---|---:|---|---|
| European Storm-petrel | GB 79%, IE 84%; NL 8% | 883 | Reporting rate, effort-adjusted occurrence (needs checklist data); GBIF activity as a fallback | **Best candidate** |
| Manx Shearwater | GB 84%, IE 68%; NL 9% | 1,050 | Same | **Good candidate** |
| Northern Fulmar | GB 78%, IE 56%; NL 4% | 1,108 | Same, but many Fulmar records come from non-eBird platforms; model currently has no skill over baseline | **Weak**: effort and activity confounded; check the baseline first |
| Sooty Shearwater | GB 97%, IE 88%, NL 23% | 33 | Very rare in the target region | **Insufficient events** (<50) |
| Great Shearwater | GB 95%, IE 90% | 15 | Almost entirely eBird, so the feature duplicates the label | **Insufficient events** (<50); high self-leakage |

## Recommended first feature set

Build only items that need no new data licence first, and add checklist-based features once EBD access exists.

**Phase 1: from data already in GBIF (no model change yet, test offline first)**
1. `ebird_gbif_records_7d_gb_ie`: eBird-dataset detection records for the species in GB and IE over days *t-7* to *t-1*, taken from a **frozen** GBIF snapshot per annual cutoff.
2. `ebird_gbif_observers_7d_gb_ie`: distinct anonymised observers reporting any of the five seabirds over the same window, as an effort proxy for the region.
3. Day-of-year-normalised version of both (divide by the training-period average for that week) to remove the strong growth trend.

**Phase 2: requires the EBD sampling-event file (request access first)**
4. `checklist_count_7d_region`: all eBird checklists in the region (effort).
5. `reporting_rate_7d_region`: share of checklists that include the species, ending at *t-1*.
6. `effort_adjusted_occurrence`: detections per checklist, 7-day window.
7. Abundance (items 3 and 12): add last and only if skewed counts are log-transformed and tested against item 6.

Do not use items 7-11 for validation.

## Leakage controls (required for any eBird feature)

1. Windows end at *t-1*. Forecast for day *t* never uses day *t* eBird data.
2. Use a **frozen archive per annual cutoff** matching `evaluate_rolling`'s expanding-window fits. Rebuilding features from today's data inflates results because eBird records arrive late and are revised.
3. Compute normalisation constants (means, trend, scaling) from training years only.
4. Handle effort growth: train and test years differ by about 10x in checklist volume. Prefer ratios and normalised features.
5. Compare against a **persistence baseline** (event yesterday) and a **weather-only baseline** (current model). An eBird feature has value only if it beats both in the existing rolling validation, on the same 2015-2026 period, using Brier skill and calibration, not just F1.
6. Keep the 0.20 threshold as is, and judge features on probability quality (Brier, ECE).
7. Report rare species (<50 events) separately and do not draw conclusions for them.

## Answer to the goal question

1. **Most likely to help:** lagged, effort-normalised **reporting rate / effort-adjusted occurrence** for **European Storm-petrel and Manx Shearwater** over GB and IE (Phase 2), with **regional activity** from GBIF as a cheaper Phase 1 proxy.
2. **Leakage-free only if** windows end at *t-1*, archives are frozen at each cutoff, and normalisation uses training years only.
3. **Do not expect large gains.** The labels are mostly eBird, so these features risk duplicating the target. The Netherlands, where the weather features apply, has little eBird data. The first test should show whether they beat a persistence baseline, not just the current model.
4. **Not worth pursuing now:** Status & Trends, same-day data, today's snapshot for past dates, hotspot counts, and anything for Sooty and Great Shearwater (too few events).

## Open items before building

- Request EBD access and confirm which products are available; confirm the background claims above.
- Decide how to define the target region (Netherlands only or the wider North Sea) because it determines whether eBird features can matter.
- Archive monthly GBIF snapshots going forward so future cutoffs can be reproduced.
