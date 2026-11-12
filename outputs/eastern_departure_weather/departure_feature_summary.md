# Departure-weather feasibility: eastern vagrants arriving in the Netherlands

Exploratory audit only: no model was changed or retrained. Question: which source-region weather variables look most informative for eastern vagrant arrivals?

## Method

- **Weather source:** the local archive holds Dutch KNMI stations only, so source-region weather was downloaded once from the Open-Meteo ERA5 archive and cached at `data/cache/eastern_departure_weather_daily.csv` (2010-09-01 to 2025-12-31).
- **Regions (fixed boxes, south-north, west-east):** Finland 60.0-68.0N, 21.0-31.5E; Baltics 53.9-59.7N, 20.9-28.2E; NW Russia 57.0-67.0N, 31.6-45.0E. Each region is a mean over a 2x2 grid of box-quarter centres. Wind direction comes from the mean wind vector.
- **Features:** temperature, anomaly, pressure, 24h pressure change, precipitation, anomaly, wind speed, wind direction (the direction the wind blows toward), tailwind toward the Netherlands (wind component along the region-to-NL bearing), crosswind (absolute perpendicular component), and days since the last major cold front (a 24h drop in mean temperature of 4 C or more, capped at 30). Anomalies use a day-of-year climatology over the whole archive, which is acceptable for an audit but would need a cutoff-safe climatology in a production feature.
- **Events:** Dutch records per day from the cached GBIF eastern-guild files, 2011-2025, restricted to the autumn passage (09-15 to 11-20). An event day is in the top decile of that species' season-day counts, minimum 1 record, matching the pipeline's influx rule. The guild row sums all eastern-registry species with Dutch records.
- **Lags:** weather 1, 2, 3 days before the Dutch record date (departure precedes arrival).
- **Seasonal adjustment:** every feature is converted to its anomaly from the day-of-year climatology before correlating. Raw values (for example mean temperature) fall through autumn just as arrivals of late species rise, which would otherwise be a calendar effect, not a weather effect. The CSV keeps the raw correlation in `raw_mean_yearly_rho`.
- **Statistic:** Spearman correlation between a feature and the event flag is computed within each autumn and averaged across years. This avoids the shared seasonal trend and the strong day-to-day autocorrelation that would make a pooled p-value overconfident. P-values are t-tests across yearly correlations, Benjamini-Hochberg adjusted over all tests. Effect sizes are small, so |mean yearly rho| ranks potential, not significance alone.

## Event days

| Species | Event days (autumn 2011-2025) | Status |
|---|---:|---|
| Blyth's Reed Warbler | 61 | OK |
| Booted Warbler | 10 | uncertain (fewer than 30 event days) |
| Citrine Wagtail | 4 | uncertain (fewer than 30 event days) |
| Dusky Warbler | 106 | OK |
| Lanceolated Warbler | 2 | uncertain (fewer than 30 event days) |
| Olive-backed Pipit | 109 | OK |
| Paddyfield Warbler | 7 | uncertain (fewer than 30 event days) |
| Pallas's Warbler | 103 | OK |
| Pechora Pipit | 2 | uncertain (fewer than 30 event days) |
| Red-flanked Bluetail | 101 | OK |
| Siberian Chiffchaff | 112 | OK |
| Yellow-browed Warbler | 101 | OK |
| Eastern guild (all species) | 101 | OK |

## Feature ranking

Mean over the reliable species and the guild of each feature's best region and lag.

| Rank | Feature | Mean abs rho | Best abs rho | Significant tests (q<0.05) |
|---:|---|---:|---:|---:|
| 1 | days_since_cold_front | 0.081 | 0.161 | 0 |
| 2 | crosswind | 0.058 | 0.097 | 0 |
| 3 | precipitation_anomaly | 0.053 | 0.102 | 0 |
| 4 | precipitation | 0.052 | 0.104 | 0 |
| 5 | tailwind | 0.049 | 0.108 | 0 |
| 6 | temperature_anomaly | 0.049 | 0.139 | 1 |
| 7 | mean_temperature | 0.047 | 0.153 | 1 |
| 8 | mean_wind_speed | 0.047 | 0.081 | 0 |
| 9 | mean_wind_direction | 0.046 | 0.100 | 0 |
| 10 | pressure | 0.045 | 0.087 | 0 |
| 11 | pressure_change_24h | 0.043 | 0.129 | 1 |

## Eastern guild (all species): top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| NW Russia | days_since_cold_front | 2 | -0.113 | 73% | 0.367 | 0.811 |
| Finland | crosswind | 2 | -0.092 | 87% | 0.424 | 0.345 |
| Baltics | mean_wind_speed | 1 | -0.081 | 60% | 0.404 | 0.929 |
| NW Russia | precipitation_anomaly | 1 | +0.072 | 73% | 0.544 | 0.929 |
| NW Russia | precipitation | 1 | +0.069 | 73% | 0.540 | 0.941 |

## Blyth's Reed Warbler: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| Finland | pressure_change_24h | 1 | +0.129 | 92% | 0.624 | 0.014 |
| Finland | precipitation | 1 | -0.104 | 77% | 0.417 | 0.844 |
| Finland | precipitation_anomaly | 1 | -0.102 | 77% | 0.417 | 0.811 |
| NW Russia | days_since_cold_front | 1 | -0.098 | 62% | 0.341 | 0.894 |
| Finland | days_since_cold_front | 2 | -0.097 | 77% | 0.373 | 0.894 |

## Dusky Warbler: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| Finland | days_since_cold_front | 3 | +0.112 | 69% | 0.596 | 0.894 |
| Baltics | pressure | 1 | +0.081 | 62% | 0.579 | 0.952 |
| Finland | pressure | 3 | +0.073 | 62% | 0.553 | 0.990 |
| Finland | crosswind | 1 | -0.072 | 69% | 0.479 | 0.894 |
| Baltics | tailwind | 3 | +0.068 | 62% | 0.557 | 0.932 |

## Olive-backed Pipit: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| NW Russia | days_since_cold_front | 3 | -0.146 | 87% | 0.365 | 0.284 |
| Finland | crosswind | 2 | -0.095 | 73% | 0.402 | 0.659 |
| Finland | precipitation_anomaly | 3 | -0.094 | 73% | 0.427 | 0.894 |
| Finland | precipitation | 3 | -0.089 | 73% | 0.431 | 0.894 |
| Baltics | days_since_cold_front | 1 | +0.084 | 60% | 0.553 | 0.929 |

## Pallas's Warbler: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| Finland | days_since_cold_front | 1 | +0.151 | 93% | 0.641 | 0.266 |
| Finland | crosswind | 2 | -0.084 | 73% | 0.440 | 0.811 |
| Finland | mean_temperature | 3 | -0.075 | 60% | 0.493 | 0.947 |
| NW Russia | mean_wind_direction | 1 | +0.073 | 73% | 0.571 | 0.894 |
| NW Russia | precipitation_anomaly | 3 | +0.070 | 73% | 0.556 | 0.979 |

## Red-flanked Bluetail: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| NW Russia | days_since_cold_front | 3 | -0.161 | 75% | 0.364 | 0.811 |
| Baltics | days_since_cold_front | 1 | +0.161 | 83% | 0.637 | 0.811 |
| Baltics | mean_temperature | 2 | -0.153 | 100% | 0.445 | 0.014 |
| Baltics | temperature_anomaly | 2 | -0.139 | 100% | 0.457 | 0.014 |
| Finland | mean_temperature | 2 | -0.087 | 83% | 0.504 | 0.811 |

## Siberian Chiffchaff: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| Finland | days_since_cold_front | 1 | +0.108 | 71% | 0.513 | 0.811 |
| NW Russia | tailwind | 1 | -0.108 | 71% | 0.409 | 0.844 |
| Finland | tailwind | 1 | -0.103 | 71% | 0.394 | 0.844 |
| NW Russia | mean_wind_direction | 1 | +0.100 | 64% | 0.586 | 0.894 |
| NW Russia | crosswind | 1 | -0.097 | 79% | 0.429 | 0.781 |

## Yellow-browed Warbler: top region/feature/lag

| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |
|---|---|---:|---:|---:|---:|---:|
| NW Russia | days_since_cold_front | 1 | -0.121 | 80% | 0.343 | 0.811 |
| Finland | days_since_cold_front | 3 | -0.080 | 73% | 0.429 | 0.894 |
| NW Russia | precipitation_anomaly | 1 | +0.079 | 73% | 0.552 | 0.894 |
| NW Russia | precipitation | 1 | +0.076 | 73% | 0.547 | 0.894 |
| NW Russia | tailwind | 3 | +0.076 | 67% | 0.567 | 0.915 |

## Species with too little data

- Booted Warbler: 10 event days; results are in the CSV but flagged uncertain and excluded from the ranking.
- Citrine Wagtail: 4 event days; results are in the CSV but flagged uncertain and excluded from the ranking.
- Lanceolated Warbler: 2 event days; results are in the CSV but flagged uncertain and excluded from the ranking.
- Paddyfield Warbler: 7 event days; results are in the CSV but flagged uncertain and excluded from the ranking.
- Pechora Pipit: 2 event days; results are in the CSV but flagged uncertain and excluded from the ranking.

## Answer

Most informative variables by mean |yearly rho|: days_since_cold_front (0.081), crosswind (0.058), precipitation_anomaly (0.053).
Strongest guild signals: NW Russia days_since_cold_front lag 2 (rho -0.113); Finland crosswind lag 2 (rho -0.092); Baltics mean_wind_speed lag 1 (rho -0.081).
3 of the tests on reliable species and the guild pass q<0.05 after multiple-comparison control.
Each ranking value is the best of 9 region/lag combinations, so even pure noise gives roughly 0.04-0.06 with about 15 autumns; only values clearly above that are worth attention. The largest effect is |rho| of about 0.16, so no single variable explains much. The evidence is weak: source-region weather has at most modest, species-specific signal (cold-air and front timing, crosswind), and none for the guild as a whole. A fair next step is a strict-cutoff rolling test of a few lagged features, compared with the current model, before any claim of improvement.
