# bird-predict-second

## Bird-Predict v2 coastal weather data

`src/build_dataset.py` exposes `load_knmi_station(filepath, station_id)` for
loading an individual KNMI daily-data download. The v2 builder expects data
covering matching dates for stations 235 (De Kooy), 242 (Vlieland), 225
(IJmuiden), and 310 (Vlissingen). By default, it reads:

- `data/raw/result (1).txt` for station 235
- `data/raw/result (3).txt` for stations 242, 225, and 310

The files may contain other stations; the builder extracts each configured
station by its KNMI station ID. The builder stops with an explicit error if a
source file or matching date coverage is missing; it does not substitute
another station or silently use a partial coastline.

After adding the KNMI daily data files, build the v2 dataset from the repository
root:

```bash
python src/build_dataset_v2.py
```

The output is `data/processed/bird_predict_dataset_v2.csv`. Lag names refer to
calendar days in daily KNMI records. The forecasting notebook uses weather
available through the preceding day for each target date, while retaining the
target date's known calendar variables.

KNMI's `RH` field in these files is daily precipitation (0.1 mm units), not
relative humidity; `PX` is the maximum hourly sea-level pressure (0.1 hPa
units). Other KNMI values retain the source's documented scaling. Direction
value 0 is treated as calm/variable and excluded from circular averages; the
KNMI trace-precipitation code `RH=-1` is represented as zero.

## Forward-chaining influx forecasts

Run the forecasting experiment from the repository root:

```bash
python src/forecast_influx_experiment.py
```

The experiment predicts whether `n_records >= 10` at 1, 3, 5, 7, and 14 days
ahead with Random Forest and XGBoost. It uses annual expanding-window
validation: each test year is predicted using only examples whose target dates
precede that year. Weather features are limited to observations through the
day before the forecast origin; target-date calendar features are included
because they are known in advance. Imputation and feature availability
selection are fitted within each training fold.

The reported PR-AUC is average precision pooled across forward-held-out dates.
The script marks a horizon useful if at least one model's PR-AUC exceeds the
pooled held-out influx prevalence, the no-skill PR-AUC baseline. Interpret
results cautiously: influx days are rare and GBIF record counts reflect
observer reporting effort rather than confirmed bird abundance.

## Yellow-browed Warbler daily counts

Build a Pallid Swift-style daily-count dataset for Yellow-browed Warbler
(*Phylloscopus inornatus*) in the Netherlands:

```bash
python src/build_yellow_browed_warbler_dataset.py
```

The script queries GBIF for species taxon key `2493095` and country code `NL`,
archives GBIF's event-date facet counts under `data/raw/`, and writes
`data/processed/yellow_browed_warbler_daily_counts.csv`. As in the Pallid Swift
analysis, date parsing uses the first 10 characters of `eventDate`, and the
daily series spans the available KNMI calendar with unobserved dates set to
zero. Yearly counts and unique days include every GBIF record with a valid
parsed event date; the script reports dated records outside the KNMI calendar
separately.

## Eastern Vagrancy Index

Replaces the former Yellow-browed Warbler proxy in the dashboard. It pools
GBIF `HUMAN_OBSERVATION` records of eastern Palearctic vagrants in GB, IE, NL,
BE and DK (registry: `EASTERN_VAGRANCY_SPECIES` in
`src/build_eastern_vagrancy_dataset.py`; 6 core and 7 optional taxa, including
Siberian Chiffchaff as the subspecies `Phylloscopus collybita tristis`).
Optional taxa that GBIF cannot resolve are skipped with a warning. The raw
cache is shared with the Atlantic builder in `data/raw/atlantic_vagrancy_occurrences/`.

```bash
python src/build_eastern_vagrancy_dataset.py   # eastern_vagrancy_{species_summary,events,daily_counts}.csv
python src/train_eastern_vagrancy_model.py     # model, evaluation, feature importance
python src/predict_eastern_vagrancy.py         # imported by run_daily_forecast.py
python src/forecast_eastern_locations.py       # eastern_location_forecast.{csv,png}
```

The target is an **influx day**: `event = daily pooled count >= P90`, where P90 is
the 90th percentile of daily counts over the training days (recomputed inside each
forward-chaining fold, so test years never inform the threshold; at least 1). The
Eastern Influx Index represents the top 10% of eastern-vagrant days. The original
`count > 0` target was 60.9% prevalent and mostly learned autumn seasonality.
Features match the Atlantic Index (weather, rolling, lag, seasonal, synoptic).

Results (full period): P90 threshold 48 records/day, 584 positive days in 5,792
weather dates (10.08% prevalence). Forward-chained: ROC-AUC 0.859, PR-AUC 0.630
(held-out prevalence 11.2%). Old `count > 0` target: ROC 0.797, PR 0.881, but its
PR-AUC is inflated by 64% prevalence. `outputs/eastern_influx_threshold.json` and
`outputs/eastern_target_comparison.csv` (rows `count_gt_0`, `count_ge_p90`) record
these; the threshold is also stored in the model artifact. Risk bands are
0.10 / 0.25 / 0.50. Seasonal day-of-year features still dominate importance, and
counts grow with observer effort over time, so the threshold partly reflects reporting.

Hotspots reuse the Atlantic framework with eastern landfall anchors, no
west-facing bonus and boosts for Fair Isle, Shetland, Orkney, Isle of May, East
Yorkshire, Norfolk, the Wadden islands, Blåvand and Skagen (the requested list
was truncated after Shetland, so the later entries are assumptions in
`EASTERN_BONUS_BOOSTS`). Suitability weights are heuristics, not validated.
`run_daily_forecast.py` also writes an `eastern_hotspots` block to the run metadata.

## Atlantic Vagrancy Index

Build the North Sea Nearctic guild dataset:

```bash
python src/build_atlantic_vagrancy_dataset.py
```

The editable `ATLANTIC_VAGRANCY_SPECIES` registry includes five core and four
optional Nearctic passerines; Dark-eyed Junco is explicitly excluded. Each
species is queried separately for GB, IE, NL, BE, and DK. GBIF
`HUMAN_OBSERVATION` records with coordinates and no geospatial issue are
cached in raw form by species and country. Local validation requires the
expected ISO country code, accepted species taxon, in-range coordinates, and a
complete valid calendar date, and excludes records explicitly marked
captive/managed. Records without an explicit captive designation are treated
as wild observations; GBIF does not guarantee this field is populated.
Duplicate GBIF keys (or exact observation tuples when keys are absent) are
removed. Page progress is logged while fetching and cache totals reported.

Outputs are the per-species counts and country coverage in
`outputs/atlantic_vagrancy_species_summary.csv`, per-day counts and
contributing-species counts in `outputs/atlantic_vagrancy_events.csv`, and the
model target's `date,count` series in
`outputs/atlantic_vagrancy_daily_counts.csv`.

Train and evaluate the one-day-ahead event classifier:

```bash
python src/train_atlantic_vagrancy_model.py
```

This saves `outputs/atlantic_vagrancy_model.joblib`, forward-chained ROC-AUC,
PR-AUC, confusion matrices, prevalence, and a like-for-like evaluation of the
previous Netherlands-only prototype in
`outputs/atlantic_vagrancy_evaluation.csv`, plus
`outputs/atlantic_vagrancy_feature_importance.csv`. The evaluation labels
prediction data as sufficient only when there are at least 50 event days over
the full weather period and at least 20 positive days in the held-out years;
this is an operational screening rule, not a universal statistical standard.

The feature pipeline reuses KNMI coastal station values and adds pressure
gradient, low-pressure/high-wind storm indicators, west/south wind components,
three- and seven-day rolling means and anomalies, lag/change features, and
seasonal variables. These synoptic indicators are simple KNMI-derived proxies,
not a reanalysis-based North Atlantic circulation diagnosis.

## Atlantic Vagrancy hotspot forecast

`src/forecast_atlantic_locations.py` writes
`outputs/atlantic_vagrancy_location_forecast.csv`: 10 km EPSG:3035 cells for
GB, IE, NL, BE and DK (cells with GBIF history of the guild, plus every cell
holding a registered site).

```text
forecast_probability = Atlantic Index probability
                       x coastal_suitability x regional_suitability  (clipped to 0-1)
expected_probability = seasonal Atlantic event rate (+/-7 days, 2010 onwards)
                       x the same suitability terms
anomaly_score        = forecast_probability - expected_probability
```

- `coastal_suitability` (0.25-1): Gaussian proximity to registered islands,
  headlands and migration traps (`SITES`), with a small west-facing bonus.
- `regional_suitability` (0.4-1 before boost): exposure that decays with
  distance from Atlantic-facing anchor points, multiplied by landfall bonuses
  (`BONUS_BOOSTS`: Scilly 1.6, Fair Isle 1.6, Shetland 1.5, Outer Hebrides 1.4).
- Cells are ranked per date (`rank`) and given the Atlantic `risk_level` bands.
- Run with `python src/forecast_atlantic_locations.py`; `run_daily_forecast.py`
  and the dashboard run and display it too.

Outputs of `python src/forecast_atlantic_locations.py` (also run daily):

- `outputs/atlantic_vagrancy_location_forecast.csv`: detailed cells, used by the
  dashboard and the species layers.
- `outputs/atlantic_location_forecast.csv`: `date, location, country, latitude,
  longitude, probability, anomaly_score, rank`. Neighbouring cells of a site get
  a compass suffix, for example `Scilly Isles (SW)`.
- `outputs/atlantic_location_forecast.png`: tomorrow, +3, +7 and +14 day maps
  (red = strongest, yellow = moderate, blue = low) with each top 10.
- `outputs/yellow_browed_run.json` gains `atlantic_hotspots`
  (`strongest_location`, `strongest_probability`, `top10_locations`,
  `generated_at`) for tomorrow's hotspots.
- Bonus regions: Scilly Isles, Fair Isle, Shetland, Outer Hebrides (1.4-1.6) and
  Norfolk coast, East Yorkshire coast, Zeeland coast, Belgian coast, Skagen
  (1.25-1.3). The east-coast values are my choice; edit `BONUS_BOOSTS`.

Caveats: weights are expert heuristics, not trained or validated; with no
coastline dataset, coastal character comes from the site registry, so unlisted
coast scores as inland; GBIF reporting effort biases which cells exist.
Add sites by extending `SITES`.

## Seabird Index

The Seabird Index asks whether today or the next few days are worth a
seawatching trip along the North Sea coast. It is a guild model for exceptional
seabird-event days rather than a single species, using pooled GBIF counts for
Northern Fulmar, storm-petrels, shearwaters, skuas and Sabine's Gull.

Build the dataset and target series:

```bash
python src/build_seabird_dataset.py
```

The registry is cached per species and country, filtered to wild human
observations with valid coordinates, dates and countries, and pooled into
`outputs/seabird_species_summary.csv`, `outputs/seabird_events.csv`, and
`outputs/seabird_daily_counts.csv`; per-taxon date counts are also written to
`outputs/seabird_species_daily_counts.csv`. Occurrences are limited to 2010 onward,
matching the available daily weather calendar; this also keeps the large
GBIF requests practical. The raw cache names include the requested year range.

Train the model and evaluation artifacts:

```bash
python src/train_seabird_model.py
```

This writes `outputs/seabird_model.joblib`, `outputs/seabird_evaluation.csv`,
`outputs/seabird_feature_importance.csv`, `outputs/seabird_threshold.json`, and
`outputs/index_comparison.csv`. The target is the top 10% of seabird-event
days, so the model focuses on genuinely favourable seawatching conditions
rather than routine seabird occurrence.

Train the independent species event models after building the dataset:

```bash
python src/train_seabird_species_models.py
```

Each model predicts whether the species' daily count reaches its own training
period P90 count threshold. Forward-chained evaluation uses a threshold fitted
on each fold's training data. The script writes one model artifact per species
under `outputs/{storm_petrel,fulmar,sooty_shearwater,manx_shearwater,great_shearwater}_model.joblib`,
plus `outputs/seabird_species_evaluation.csv` and
`outputs/seabird_species_feature_importance.csv`. Great Shearwater currently
has very sparse coverage (61 records on 26 unique dates in the GBIF snapshot)
and is marked insufficient for meaningful prediction; its forecast is
exploratory, not a reliable event probability. Sooty Shearwater's P90 threshold
is also one record/day, so its positive-day prevalence is below 10% because
many dates have no qualifying records.

### Strict Cutoff Validation

The Seawatching page's primary validation framework is **Strict Cutoff
Validation**. Select an analysis date and a 1-, 3-, 7-, or 14-day holdout
window. Each lead-specific model is fitted only on weather and occurrence
records dated on or before that analysis date; occurrence records after the
date are isolated to the holdout scores. Weather features, occurrence history,
and hotspot history are all checked against the cutoff before forecasting.
Predictions use only the same-day weather snapshot available at the cutoff,
with known calendar features for each target date. If required cutoff inputs or
holdout observations are unavailable, the page reports “Strict validation
unavailable for this date.” rather than substituting future weather.

Archived weather-forecast issuances are not available, so historical observed
weather through the analysis date is used as the available-weather proxy.
Realized weather observations after the analysis date never enter the model.
This is a strict cutoff hindcast, not a replay of the exact forecast issued
then, and the frozen weather snapshot can limit forecast accuracy. Archived
forecast products may support a future, stricter forecast-replay mode.

To audit the Backtest species-presence metrics at thresholds 0.05, 0.10,
0.15 and 0.20, run:

```bash
python -m src.seabird_threshold_analysis 2024-10-15
```

The command rebuilds the strict-cutoff 14-day hindcast, reads
`validation/seabirds/observations.csv`, and writes
`outputs/seabird_validation/threshold_analysis.csv`. A species is predicted
when its maximum daily probability in the window meets the threshold, and is
observed if it appears at least once. Precision, recall and F1 use those
window-level species sets; undefined ratios are reported as zero, as in the
Backtest. All tied maximum-F1 thresholds are marked. The model probability
is for a high-count influx event, not simple presence, so this comparison is
not a direct measure of influx-event skill. Selecting a threshold on the same
window being evaluated can overfit; verify it on other independent windows.

For rolling, event-aligned evaluation across the available years:

```bash
python -m src.rolling_seabird_event_validation
```

This fits one expanding-window, cutoff-safe model per species and calendar
year, then scores daily one-day-ahead forecasts using the previous day's
observed weather. It follows the existing five-calendar-year minimum, including
partial years; this is not daily model refitting or archived forecast replay.
The evaluation uses `validation/seabirds/observations.csv` counts and each
year's training-derived P90 count threshold. It writes annual and pooled
results to `outputs/seabird_validation/rolling_event_validation.csv` and a
methodology summary to `outputs/seabird_validation/event_validation_summary.md`.

The daily runner writes independent 14-day probability forecasts and location
rankings for European Storm-petrel, Northern Fulmar, Sooty Shearwater, Manx
Shearwater and Great Shearwater. Per species, it produces
`outputs/<species>_forecast.csv`,
`outputs/<species>_location_forecast.csv`,
`outputs/<species>_hotspots.csv` (top 10 for Tomorrow, +3, +7 and +14 days),
`outputs/<species>_location_forecast_detail.csv`, and an interactive-dashboard
location map image at `outputs/<species>_location_forecast.png`. In the dashboard,
select the product under **Seabird Product** to inspect its forecast,
species-specific hotspots and map. Location scores combine that species'
forecast probability, its historical cell occupancy and seasonal curve, and
the shared expert-heuristic coastal suitability profile; the location
downscaling is not independently trained or validated.

To run a forecast directly from a prepared daily weather input:

```bash
python src/predict_seabird.py --weather-forecast path/to/weather_forecast.csv
```

The forecast writes `outputs/seabird_forecast.csv` and
`outputs/seabird_forecast.png`, and the location downscaling writes
`outputs/seabird_location_forecast.csv` (the requested compact schema) and
`outputs/seabird_location_forecast.png`. The dashboard's full scoring grid is
also saved to `outputs/seabird_location_forecast_detail.csv`. The shared daily
runner generates these forecasts along with all other products:

```bash
python src/run_daily_forecast.py
```

The dashboard also shows a “Best Dutch Seawatch Site” card based on the top
Dutch hotspot for tomorrow.

The **Seawatch Day Rating** combines the General Seabird Index (40%),
European Storm-petrel (30%), Manx Shearwater (20%) and Sooty Shearwater (10%)
probabilities, then applies up to 30 points of explicit weather/season bonuses.
It writes `outputs/seawatch_day_rating.csv`,
`outputs/seawatch_day_hotspots.csv` (top 10 grid locations for tomorrow,
+3, +7 and +14 days), and `outputs/seawatch_day_rating.json`. Rating bands
are Poor (0-24), Fair (25-49), Good (50-69), Excellent (70-84), and Major
Seawatch Day (85-100). Weather bonuses use forecast-day wind direction/speed,
minimum coastal pressure and wind change; the deep-low cutoff is 1000 hPa,
and 20 kt is converted to 10.29 m/s. The weighted result is rounded to the
nearest integer after bonuses, then capped at 100.

### Rarity Index

The Rarity Index is a separate product from the Seawatch Day Rating: it
measures weighted potential for unusually rare seabird records, not overall
seawatching activity or weather suitability. It combines the five existing
species-model probabilities using the central `RARITY_WEIGHTS` in
`src/rarity_index.py` (Fulmar 0.5, Manx Shearwater 1, European Storm-petrel 2,
Sooty Shearwater 3, Great Shearwater 6). Each day's weighted raw score is
scaled against the historical raw-score P5–P95 range, clipped to 0–100. That
range is recorded with the forecast so the score scale is inspectable and can
change when the historical model-output distribution changes.

The daily runner writes `outputs/rarity_index.csv` and
`outputs/rarity_index.json`. The dashboard displays the index separately with
species contribution breakdowns for tomorrow, +3, +7 and +14 days. A higher
score means stronger relative rarity potential under the fitted species
models; it is not a calibrated probability of a rare bird being reported.

As with the other indices, the seawatching weights are heuristics and the
daily weather inputs are KNMI-derived proxies rather than direct hourly
observations.

## Species-specific Atlantic hotspot layers

`src/forecast_atlantic_species_locations.py` builds one layer per entry in
`SPECIES_LAYERS` (Yellow-browed Warbler, Red-eyed Vireo, Blackpoll Warbler,
American Redstart, Blackburnian Warbler, Northern Parula, Tennessee Warbler,
Bobolink, American Robin, Dark-eyed Junco). Add a species by appending a dict
with `species`, `scientific_name`, `slug` and an optional `profile`.
Dark-eyed Junco is a stand-alone layer only; it stays out of the Atlantic guild.

```text
forecast_probability = Atlantic Index probability
                       x species_suitability
                       x coastal_suitability x regional_suitability
```

- GBIF records for GB, IE, NL, BE and DK use the same cache and filters as the
  guild. Queries over 5,000 records are fetched in per-year partitions
  because GBIF deep offsets are very slow.
- `species_suitability` = the cell's share of years with a record since 2000
  (relative to the best cell) x the species' smoothed seasonal curve for the
  forecast date (peak = 1, floor 0.02).
- Coastal and landfall suitability reuse the site registry with per-species
  profiles (kind weights, west-facing bonus, exposure scale, bonus strength).
  Yellow-browed Warbler uses eastern landfall anchors instead of Atlantic ones.
- Outputs per species: `outputs/<slug>_location_forecast.csv`,
  `<slug>_hotspots.csv` (top 20 `HOTSPOT` and `COLDSPOT` per date) and
  `<slug>_anomalies.csv` (top 20 `POSITIVE_ANOMALY` per date; empty when no cell
  is above its seasonal baseline). `atlantic_vagrancy_species_layers_summary.csv`
  reports records, years, cells and `data_quality`.
- `run_daily_forecast.py` builds all layers and the dashboard has a layer
  selector (guild or species).

Caveats: profiles are expert heuristics, not trained or validated. Species with
`data_quality = sparse` (under 200 records or 5 years since 2000) rest on a few
cells, so occupancy is unreliable. The Atlantic Index probability is a guild
signal, so it is a weak driver for Yellow-browed Warbler (an eastern vagrant),
American Robin and Dark-eyed Junco. GBIF effort biases occupancy.

## Forward-chained species comparison

To run the full Yellow-browed Warbler forecast and compare it with Pallid
Swift, Manx Shearwater, and Red-throated Pipit using the same dates, models,
and validation folds:

```bash
python src/forecast_species_comparison.py
```

This evaluates `>=10`, `>=25`, and `>=50` record targets at 1-, 3-, 5-, 7-,
and 14-day horizons with a seasonal baseline, Logistic Regression, Random
Forest, and XGBoost. The Pipit and Manx Shearwater labels use the archived
complete-date GBIF event-date facets generated by their feasibility scripts;
their dates are joined to the common weather calendar, with unobserved dates
set to zero. If a rare target has no positive observations in an early
training fold, weather models predict zero for that fold, which remains in
held-out evaluation. Results for all four species are written to
`data/processed/species_forecast_metrics.csv` and
`reports/species_forecast_comparison.md`. The maximum useful horizon is
defined in the report as the longest tested horizon where a weather model's
pooled PR-AUC exceeds the seasonal baseline. The report also ranks species by
mean best-weather-model PR-AUC lift over the seasonal baseline across the
threshold/horizon grid; this descriptive comparison is not a significance
test.

## Yellow-browed Warbler feature importance

After building the forecast metrics, calculate forward-held-out SHAP
importance for the top-performing Yellow-browed Warbler model:

```bash
python src/feature_importance_yellow_browed.py
```

This explains the highest-PR-AUC weather model across the threshold/horizon
grid using the same expanding-window folds. It writes the full feature ranking
to `data/processed/yellow_browed_warbler_shap_importance.csv` and a top-20,
predictor-family summary, and biological interpretation to
`reports/yellow_browed_warbler_feature_importance.md`. Install dependencies
from `requirements.txt` if needed.

## Red-throated Pipit forecast experiment

The shared species comparison above evaluates Red-throated Pipit against
Yellow-browed Warbler, Pallid Swift, and Manx Shearwater at all three record
thresholds and five forecast horizons. After running it, calculate pooled
forward-held-out SHAP importance for the strongest Pipit weather model:

```bash
python src/feature_importance_red_throated_pipit.py
```

This writes the full feature ranking to
`data/processed/red_throated_pipit_shap_importance.csv` and the Pipit
performance grid, direct species comparison, SHAP analysis, biological
interpretation, and recommendation to
`reports/red_throated_pipit_forecast_experiment.md`.

## Bluetail forecasting experiment

Run the isolated Bluetail (Blauwstaart, *Tarsiger cyanurus*) forward-chained
experiment without overwriting the existing all-species metrics:

```bash
python src/forecast_bluetail.py
```

The experiment evaluates all three record thresholds and five horizons
against the seasonal baseline, Logistic Regression, Random Forest, and
XGBoost. It writes the metric grid, fold-averaged feature importance,
held-out SHAP rankings, and the comparison/interpretation report to
`data/processed/bluetail_forecast_metrics.csv`,
`data/processed/bluetail_feature_importance.csv`,
`data/processed/bluetail_shap_importance.csv`, and
`reports/bluetail_forecast_experiment.md`.

## Bird-Predict candidate-species assessment

Assess GBIF event-date support for Blauwstaart, Citroenkwikstaart, Kleine
Spotvogel, and Veldrietzanger against Yellow-browed Warbler, Pallid Swift,
Red-throated Pipit, and Manx Shearwater with:

```bash
python src/assess_candidate_species.py
```

The script queries GBIF's exact species match and Netherlands event-date
facets for all eight taxa, archives the four new candidate facet files under
`data/raw/`, and writes annual counts, top-20 days, record thresholds, and a
common-weather-window feasibility ranking to
`reports/candidate_species_assessment.md`. The ranking reflects date-level
data support only; the separate forward-chained experiment is required to
establish forecast skill.

## Winter Goose Module

Forecasts winter goose movements for the Netherlands (Oct–Mar). Existing products are untouched.

Products (horizons Tomorrow, +3, +7, +14 days):

- **Goose Activity Index** (0-100): probability of an above-normal day for pooled Greater White-fronted, Tundra Bean, Barnacle, Greylag, Brent and Pink-footed Goose. Bands: Quiet / Moderate / Good / Strong / Major Goose Day.
- **Rare Goose Potential** (0-100): `Σ probability × RARE_GOOSE_WEIGHTS` over Red-breasted, Lesser White-fronted, Snow, Ross's Goose and Black Brant, scaled historical P5-P95 and clipped.
- **Target Geese**: species ranked by `probability × rarity_weight`.
- **Goose Day Rating**: 70% activity + 30% rare potential.
- **Hotspots** (top 10 sites per horizon) and **Best Goose Regions** (Lauwersmeer, Friesland, Groningen, Texel, Noord-Holland, Flevoland, IJsselmeergebied, Zeeland).
- **Historical percentiles** (out-of-fold winter history) and a 🟢 GO / 🟡 MAYBE / 🔴 STAY HOME call (GO: rating ≥ 70 or rare ≥ 80; MAYBE: rating ≥ 40).

```bash
python src/build_goose_dataset.py   # GBIF daily record counts -> outputs/goose_daily_counts.csv, site counts
python src/train_goose_models.py    # 6 models, evaluation, feature importance, historical scores
python src/goose_module.py          # forecast outputs from inputs/open_meteo_forecast_current.csv
```

`run_daily_forecast.py` runs the module automatically when the trained models exist (skipped otherwise). The dashboard shows it as **🪿 Goose Forecast**, including a **European Goose Influx** panel.

Outputs: `goose_activity_index.csv`, `rare_goose_potential.csv`, `goose_day_rating.csv`, `goose_hotspots.csv`, `goose_region_ranking.csv`, `target_geese.csv`, `european_goose_influx.csv` (species probabilities and European percentiles), `rare_goose_europe_index.csv` (index, historical percentile, and +7/+14-day change from Tomorrow), `goose_module.json`, `goose_model_evaluation.csv` (ROC-AUC, PR-AUC, training records, positive events, data sufficiency, Production/Beta/Experimental), `goose_model_comparison.csv` (before/after ROC-AUC and PR-AUC), and `goose_feature_importance.csv`.

Method notes and limitations:

- Labels are winter-relative: a day is positive when the GBIF record count reaches the P75 (activity) or P80 (each rare species) of that winter's own daily counts. This removes observer-growth trends and the near-universal presence of rare geese.
- GBIF record counts are an effort-affected proxy for abundance. Common geese use NL only. Red-breasted Goose uses NL, BE, DE, DK, SE, FI and PL; Snow and Ross's Goose use UK (GB in GBIF), IE, NL, BE, DE, DK and FR. Lesser White-fronted Goose and Black Brant retain NL, BE, DE and DK.
- The Rare Goose Europe Index is the equal-weight mean of the five rare species' probabilities converted to percentiles against their own out-of-fold historical probabilities. The +7/+14-day changes are the index differences from the Tomorrow forecast, in points.
- The model comparison report preserves the first available pre-expansion evaluation as its `*_before` baseline, so repeat training does not erase the original comparison.
- Red-breasted, Snow and Ross's Goose now have wider target geographies, so their winter-relative event labels changed. Their before/after metric differences reflect both the broader target definition and retraining; they are not a controlled model-only comparison.
- Validation is forward-chaining by winter. Ross's Goose has no skill (ROC-AUC ≈ 0.5) and is flagged Experimental.
- Hotspot site factors come from historical GBIF density; the cold-weather regional modifiers are expert priors, not fitted.
- Consecutive frost days are counted from the first supplied weather day, so a 14-day window can under-count earlier frost runs.

## Daily inference

Train and persist the best-performing Yellow-browed Warbler model from the
forecast comparison:

```bash
python src/train_yellow_browed_model.py
```

This saves `outputs/yellow_browed_model.joblib`. To predict from station
weather forecasts, provide a CSV with one row per date and station, with these
columns:

```text
date,station_id,DDVEC,FG,FHX,TG,TN,TX,RH,PX
```

`station_id` must include 235, 242, 225, and 310 for each of the final 14
consecutive dates in the file. The dates are the weather-valid dates used as
the previous-day predictors; output target dates are each input date plus one
day. Extra earlier dates may be included to provide context for lagged
features. Values must use the KNMI units/scaling used by the processed dataset.
Including the three calendar days before the 14 forecast dates lets the
pipeline derive the earliest lagged features; without them, missing early
lags are imputed by the saved training pipeline.

Run inference with:

```bash
python src/predict_yellow_browed.py --weather-forecast path/to/weather_forecast.csv
```

The script writes the 14-row `outputs/yellow_browed_forecast.csv` (probability
is in the 0–1 range), `outputs/yellow_browed_forecast.png`, and
`outputs/yellow_browed_report.md`. Risk labels use half-open probability
bands: `[0, 20%)` Very Low, `[20, 40%)` Low, `[40, 60%)` Moderate,
`[60, 80%)` High, and `[80, 100%]` Very High.

## Flagship-index dashboard

The dashboard presents three flagship products: the Eastern Vagrancy Index
(the Eastern Influx Index model), the Atlantic Vagrancy Index (the Nearctic
guild model), and the Seabird Index. Yellow-browed Warbler also remains as a
separate operational forecast. The shared daily runner downloads Open-Meteo
forecasts, aggregates weather at four coastal locations, and forecasts all
four products:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The Dutch BirdCast sidebar separates the dashboard, Rare Birds, Seawatching,
Migration, Species Explorer and Methods pages. Use the sidebar forecast button
to refresh the existing daily products. Forecast dates and a stale-output warning
are shown so previously generated data is not mistaken for current conditions.
Atlantic Vagrant Watch uses explicitly labelled illustrative demo data. The
Species Explorer lists the species with existing forecast layers; independent
skua, auk, duck and swan forecasts, and dedicated fetch and visibility products,
are not currently available.

The dashboard's Atlantic Vagrant Watch instead uses the highest current
species-layer cell probability from available Nearctic layers in the latest
completed run. It is not the illustrative watchlist score or an independently
trained species probability. Dashboard cards show forecast dates and identify
available leading species signals; a previous-day change is shown only when the
same product has a previous forecast date, not as a revision of yesterday's run.

The **Rare Birds** page has three top-level views—Atmospheric Indices,
Forecasts, and Hotspots—with a secondary selector in each view. Atmospheric
The Atlantic Index and Eastern Drift Index show transparent 0–100 component
scores, component contributions and sub-signal explanations. They are
experimental heuristic indices: four Dutch coastal weather stations and the
preceding ten complete years of GB, IE, NL, BE and DK event summaries are
equally weighted. Scandinavian blocking, Siberian/Atlantic transport pathways,
Azores arrivals and hurricane remnants are explicitly labelled proxies because
the current inputs do not cover those regions or feeds. These indices are
separate from the learned bird-record event forecasts. The Next Dutch Firsts
ranking uses illustrative historical records and is not a calibrated multi-year
forecast. Named hotspot tables show unavailable when a requested site is not
present in the current location forecast.

The transport score uses positive cosine alignment with 90° easterly or 270°
westerly winds, scaled by wind speed capped at 15 m/s. Persistence and
continuation are trailing and forward three-day means; station connectivity
measures directional agreement across the four coastal stations. Cyclone
support combines daily-maximum-pressure, wind-speed and station pressure
gradient proxies. Historical monthly activity uses log-scaled event or species
counts over the ten complete years before the forecast year. Sub-signals are
equally weighted inside each component; components are equally weighted inside
their index, and contribution is component score times component weight. The
dashboard's calculation expander describes these formulas and the limitations
of each regional proxy.

Rare Birds forecasts, hotspots, Seawatch Day Rating, Migration, and Species
Explorer views show a status badge and confidence label. Confidence reflects
model validation and data limitations; Seawatch Day Rating uses its forecast
lead-time confidence. Experimental means a product is exploratory or lacks a
validated forecast model, and low-confidence hotspot scores use heuristic
suitability. Species Explorer labels its historical summaries as descriptive
and identifies the separate forecast layers as model outputs.

When the current run skipped a product or its output does not match that run,
the card shows unavailable rather than an older score.

In Species Explorer, select Atlantic or Eastern vagrants to see a Dutch site
ranking and recommendation from that family's first-day guild location forecast.
Then browse the scrollable species leaderboard and select a species for its
own forecast and international rankings. The family overview is independent of
the selected species and uses the run's first forecast date; individual species
details use the date selected in that view.
Seabird species and the seabird Rarity Index are in Seawatching;
use Species & sites to browse the seabird leaderboard or search for a species.
Species without an independent model are explicitly marked unavailable.
Select a row or use the species selector to open the existing detail view.
Ranks use the first forecast day's highest cell probability for vagrants and the
national species-model probability for seabirds. Best region is the leading site
on that day; best date is the peak across the forecast period. Trend compares
the first two forecast days, not successive forecast runs: changes under 0.05
percentage points are stable. Missing products remain listed as unavailable.
Vagrant species detail prioritizes the selected day's scores for Texel,
Schiermonnikoog, Vlieland, Maasvlakte and IJmuiden, followed by international
hotspots. Each site uses its highest explicitly labelled cell; combined
Vlieland/Terschelling cells are not presented as a Vlieland-specific forecast.
Missing core sites are shown as unavailable. Additional Dutch maps and
site/coast rankings remain in the supporting section; seabird recommendations
remain in Seawatching for each available horizon. The full site table ranks Dutch location
names by their best cell; the map shows all Dutch cells with coordinates.
Coast scores average the best cell per represented named site using the
seawatch coast groupings. Cells identified only by coordinates are shown in
the table and map but are not assigned to a coast. These are relative model
scores, not confirmations of bird presence.

No API key or weather-source configuration is required for the initial MVP.
The downloader queries the Open-Meteo Forecast API for locations near KNMI
stations 235 (De Kooy), 242 (Vlieland), 225 (IJmuiden), and 310 (Vlissingen),
then writes the daily `date`, `station_id`, `DDVEC`, `FG`, `FHX`, `TG`, `TN`,
`TX`, `RH`, and `PX` CSV expected by the existing predictor. Hourly wind,
temperature, precipitation, and pressure values are aggregated by local
calendar day and converted to the KNMI feature scaling.

**Source-mismatch caveat:** the production model was trained on KNMI station
observations, not Open-Meteo forecast-model grid data. The queried locations
approximate those stations but are not the actual station observations, and
hourly-to-daily aggregation and forecast-model bias differ from the training
data. KNMI `RH` means daily precipitation in 0.1 mm units (not relative
humidity), so the adapter maps Open-Meteo precipitation to `RH`; it does not
map the relative-humidity variable to `RH`. Likewise, Open-Meteo daily maximum
pressure is used for KNMI `PX`. These forecasts are therefore source-mismatched
model inputs and have not been validated or recalibrated against Open-Meteo.
The generated report repeats this caveat.

Run the full download → prediction → chart → report pipeline manually with:

```bash
python src/run_daily_forecast.py
```

The daily runner requires all four trained model artifacts: Yellow-browed
Warbler, Eastern Influx, Atlantic Vagrancy, and Seabird. It writes the Eastern
forecast as `outputs/yellow_browed_forecast.csv` and the Atlantic forecast as
`outputs/atlantic_vagrancy_forecast.csv` and the Seabird forecast as
`outputs/seabird_forecast.csv`, each with companion plots. Eastern and Seabird
risk bands use 10%, 25%, and 50% cut points; Atlantic uses 5%, 10%, and 20%.
Their evaluation confusion matrices use model-specific decision thresholds:
20% for Eastern and Seabird, 5% for Atlantic. Run the Atlantic, Eastern, and
Seabird builders and trainers above before the first daily run. The dashboard's
button runs the same pipeline. For unattended daily runs on Linux, install
`deployment/bird-predict-daily.service` and
`deployment/bird-predict-daily.timer` and enable the timer with systemd. The
service runs daily at 06:00 UTC.

The production model artifact was trained on data through
`2026-08-10`; retrain and redeploy it as new validated observation/weather
data become available. Its experiment is for a 14-day lead. The existing
dashboard shows daily next-day dates by shifting the supplied weather-valid
dates; these daily probabilities are not separately calibrated or validated.

An illustrative synthetic input is available at
`inputs/example_forecast.csv`. Run it with `--synthetic-example` so the report
labels its results as a scenario rather than an official forecast:

```bash
python src/predict_yellow_browed.py \
  --weather-forecast inputs/example_forecast.csv \
  --synthetic-example
```

The selected model was trained and evaluated specifically at a 14-day lead.
Applying it to all daily dates one day after the supplied weather dates is a
lead-time shift; shorter-lead probabilities are not separately calibrated or
validated. The generated report repeats this limitation.

Three matched synthetic October scenarios and their outputs are included under
`inputs/` and `outputs/`. The comparison, including daily probabilities and
the weather-sensitivity interpretation, is in
`outputs/yellow_browed_scenario_comparison.md`. Scenario weather is illustrative
and must not be treated as an operational forecast.

## Yellow-browed Warbler anomaly forecasts

Run the expanding-window experiment comparing seasonality-only, weather-only,
and combined models for anomaly ratios `>=2`, `>=4`, and `>=8`:

```bash
python src/forecast_yellow_browed_anomalies.py
```

Expected counts use a forward-only climatology from prior calendar years:
observations within ±7 calendar days of the target date, smoothed with 30
prior-equivalent observations at the prior-history daily mean. Anomaly is
observed minus expected; anomaly ratio is observed divided by expected.
Metrics quantify incremental weather PR-AUC as combined minus
seasonality-only for each matching model, horizon, and threshold. The run
writes the daily anomaly fields to
`data/processed/yellow_browed_daily_anomalies.csv`, pooled metrics to
`data/processed/yellow_browed_anomaly_forecast_metrics.csv`, forward-held-out
SHAP ranks to `data/processed/yellow_browed_anomaly_shap_importance.csv`, and
the interpretation to `reports/yellow_browed_anomaly_forecast.md`.

## Manx Shearwater feasibility

Refresh the Dutch GBIF event-date facets for Manx Shearwater, Yellow-browed
Warbler, and Pallid Swift, and regenerate the target-species volume comparison:

```bash
python src/assess_manx_shearwater_feasibility.py
```

The script archives Manx Shearwater's GBIF event-date facet counts at
`data/raw/manx_shearwater_event_date_facets.csv` and writes the assessment to
`reports/manx_shearwater_feasibility.md`. It reports complete-date yearly and
daily counts separately from the total occurrence count, which may include
records without a usable day-level date.

To run the same assessment for Red-throated Pipit, with side-by-side
comparisons to Yellow-browed Warbler, Pallid Swift, and Manx Shearwater:

```bash
python src/assess_red_throated_pipit_feasibility.py
```

This archives the Pipit event-date facets at
`data/raw/red_throated_pipit_event_date_facets.csv` and writes
`reports/red_throated_pipit_feasibility.md`.

## Bird-Predict location forecast

The Streamlit dashboard adds a 10 km location outlook for each date in the
daily Yellow-browed Warbler forecast. Run the dashboard as usual:

```bash
streamlit run app.py
```

On the first forecast run, Bird-Predict fetches coordinate-bearing,
dated Yellow-browed Warbler occurrences for the European Netherlands from
GBIF and caches them in `data/cache/`. The cache is refreshed every 30 days.
Locations are assigned to exact 10,000 m square cells in EPSG:28992; records
with dates or coordinates outside the European Netherlands bounds, or stated
coordinate uncertainty greater than 10 km, are excluded.

For each target date, the cell's expected probability is its fraction of
earlier GBIF-history years with a dated report in a ±7-day calendar window,
smoothed with a Jeffreys prior. The existing nationwide model probability is
compared with the historical nationwide probability of reaching the model's
record-count threshold in the same seasonal window. The resulting log-odds
shift is applied to each cell's expected probability; anomaly score is
forecast probability minus expected probability. The dashboard shows forecast
and anomaly maps with tooltips for forecast probability, baseline probability,
anomaly score, and the nearest curated town with distance. A summary panel
shows national probability and risk class, the best hotspot, the strongest
anomaly, and inland availability. Positive anomalies appear above the hotspot
rankings. Top-10 hotspot, positive-anomaly, and coldspot tables appear directly
below the summary panel. A forecast-horizon selector switches the summary,
rankings, and maps together between tomorrow and the +3, +7, and +14 day
forecasts. Town labels are nearby reference points, not exact
cell-locality names; an inland ranking is not shown without coastline data.

These are transparent spatially downscaled scores, not independent
cell-level weather-model predictions or detection-corrected occupancy
probabilities. GBIF reporting effort affects the historical rates, and blank
cells without dated coordinates are unknown rather than confirmed absences.
The generated cell forecasts are written to
`outputs/yellow_browed_location_forecast.csv`.
## Birder decision support

- **GO / MAYBE / STAY HOME** banner (`src/seabird_guidance.py`): GO if Seawatch Day Rating ≥ 70, or ≥ 50 with Rarity Index ≥ 70; MAYBE if rating 35–69 or Rarity 50–69; otherwise STAY HOME.
- **Dutch coast ranking** (`outputs/dutch_coast_ranking.csv`: `date, horizon_days, coast, score, rank`): mean best site score per region. Assumed groups: Wadden Islands (Texel, Vlieland, Terschelling, Schiermonnikoog), North Holland (Den Helder, Petten, Camperduin, IJmuiden, Bloemendaal aan Zee), South Holland (Maasvlakte), Delta (Neeltje Jans, Westkapelle).
- **Score drivers**: `seawatch_day_rating.json` horizons gain `positive_drivers` and `negative_drivers`, plus `coast_ranking`. A species signal is "elevated" at ≥ 25% probability; negative points are score forgone.

## Historical percentile context

`src/historical_percentiles.py` ranks each forecast against the **entire** historical model-output distribution (all 5,792 historical weather days, all seasons; forecast-period values are excluded). `historical_percentile` is the percentage of historical days with a strictly lower score. Seawatch uses the unrounded 0–100 rating (including weather bonuses, computed with the same flags as the live rating); Rarity uses the unclipped raw score. Labels: <50 Common Conditions, 50–75 Above Average, 75–90 Strong, 90–95 Exceptional, 95+ Historic. Results are written to `outputs/historical_percentiles.csv`, to `seawatch_day_rating.json` and `rarity_index.json` (`historical_percentile`, `historical_label`, `historical_rank_text`) and to the run metadata.
