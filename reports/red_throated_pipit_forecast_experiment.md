# Red-throated Pipit Forecasting Experiment

## Objective and data

This experiment forecasts whether Dutch GBIF daily record counts reach ≥10, ≥25, or ≥50 records, 1, 3, 5, 7, or 14 days ahead. Pipit labels come from the archived GBIF Netherlands event-date facets; dates without a facet are assigned zero on the shared KNMI weather calendar. Four coastal KNMI stations and the existing weather-feature pipeline are used. Records are observation/reporting counts, not abundance estimates.

## Method

The method matches the shared Yellow-browed Warbler, Pallid Swift, and Manx Shearwater comparison in `reports/species_forecast_comparison.md`: expanding annual forward-chaining, first five calendar years for initial training, and 12 held-out test years. All species use identical forecast origins, target-date calendar features, and observed weather features available through the day before the forecast origin. Median imputation and model fitting are performed within each fold.

Models are the month-specific smoothed seasonal baseline, class-weighted Logistic Regression, balanced Random Forest, and class-weighted XGBoost. ROC-AUC and average-precision PR-AUC are computed from pooled out-of-fold predictions. Precision, recall, and F1 use a fixed 0.5 probability threshold. If early training folds have no positive examples, the weather models predict zero and the fold stays in evaluation.

## Pipit performance

All Pipit thresholds, horizons, and models are shown below. Positive test days are pooled across the same 4,226 held-out dates and 12 test years for every Pipit scenario.

| Target | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Seasonal PR-AUC | Positive test days |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ≥10 | 1 d | Logistic Regression | 0.6400 | 0.0188 | 0.0162 | 0.2917 | 0.0307 | 0.0455 | 48 |
| ≥10 | 1 d | Random Forest | 0.7969 | 0.0810 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 1 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 1 d | XGBoost | 0.7959 | 0.0982 | 0.0926 | 0.4167 | 0.1515 | 0.0455 | 48 |
| ≥10 | 3 d | Logistic Regression | 0.6352 | 0.0184 | 0.0175 | 0.3125 | 0.0331 | 0.0455 | 48 |
| ≥10 | 3 d | Random Forest | 0.8090 | 0.0818 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 3 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 3 d | XGBoost | 0.7814 | 0.0886 | 0.0905 | 0.3750 | 0.1457 | 0.0455 | 48 |
| ≥10 | 5 d | Logistic Regression | 0.6638 | 0.0193 | 0.0192 | 0.3125 | 0.0362 | 0.0455 | 48 |
| ≥10 | 5 d | Random Forest | 0.7939 | 0.0727 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 5 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 5 d | XGBoost | 0.7874 | 0.0983 | 0.0893 | 0.4167 | 0.1471 | 0.0455 | 48 |
| ≥10 | 7 d | Logistic Regression | 0.5543 | 0.0140 | 0.0163 | 0.3125 | 0.0310 | 0.0455 | 48 |
| ≥10 | 7 d | Random Forest | 0.7290 | 0.0543 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 7 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 7 d | XGBoost | 0.7658 | 0.0663 | 0.0661 | 0.3333 | 0.1103 | 0.0455 | 48 |
| ≥10 | 14 d | Logistic Regression | 0.5742 | 0.0141 | 0.0138 | 0.2917 | 0.0264 | 0.0455 | 48 |
| ≥10 | 14 d | Random Forest | 0.7443 | 0.0576 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 14 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 48 |
| ≥10 | 14 d | XGBoost | 0.7674 | 0.0853 | 0.0854 | 0.3542 | 0.1377 | 0.0455 | 48 |
| ≥25 | 1 d | Logistic Regression | 0.5919 | 0.0060 | 0.0073 | 0.1579 | 0.0139 | 0.0231 | 19 |
| ≥25 | 1 d | Random Forest | 0.6595 | 0.0097 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 1 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 1 d | XGBoost | 0.6134 | 0.0138 | 0.0189 | 0.0526 | 0.0278 | 0.0231 | 19 |
| ≥25 | 3 d | Logistic Regression | 0.5522 | 0.0069 | 0.0071 | 0.1579 | 0.0135 | 0.0231 | 19 |
| ≥25 | 3 d | Random Forest | 0.5897 | 0.0250 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 3 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 3 d | XGBoost | 0.5993 | 0.0136 | 0.0361 | 0.1579 | 0.0588 | 0.0231 | 19 |
| ≥25 | 5 d | Logistic Regression | 0.6050 | 0.0071 | 0.0072 | 0.1579 | 0.0137 | 0.0231 | 19 |
| ≥25 | 5 d | Random Forest | 0.7271 | 0.0738 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 5 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 19 |
| ≥25 | 5 d | XGBoost | 0.6658 | 0.0438 | 0.0488 | 0.2105 | 0.0792 | 0.0231 | 19 |
| ≥25 | 7 d | Logistic Regression | 0.4943 | 0.0052 | 0.0034 | 0.1053 | 0.0066 | 0.0233 | 19 |
| ≥25 | 7 d | Random Forest | 0.5994 | 0.0311 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 19 |
| ≥25 | 7 d | Seasonal baseline | 0.8706 | 0.0233 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 19 |
| ≥25 | 7 d | XGBoost | 0.6542 | 0.0474 | 0.0441 | 0.1579 | 0.0690 | 0.0233 | 19 |
| ≥25 | 14 d | Logistic Regression | 0.4520 | 0.0051 | 0.0053 | 0.1579 | 0.0103 | 0.0233 | 19 |
| ≥25 | 14 d | Random Forest | 0.5465 | 0.0085 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 19 |
| ≥25 | 14 d | Seasonal baseline | 0.8706 | 0.0233 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 19 |
| ≥25 | 14 d | XGBoost | 0.5700 | 0.0121 | 0.0286 | 0.0526 | 0.0370 | 0.0233 | 19 |
| ≥50 | 1 d | Logistic Regression | 0.4693 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 1 d | Random Forest | 0.4148 | 0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 1 d | Seasonal baseline | 0.8158 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 1 d | XGBoost | 0.5788 | 0.0024 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 3 d | Logistic Regression | 0.6512 | 0.0035 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 3 d | Random Forest | 0.7286 | 0.0060 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 3 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 3 d | XGBoost | 0.6902 | 0.0039 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 5 d | Logistic Regression | 0.6053 | 0.0030 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 5 d | Random Forest | 0.5316 | 0.0022 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 5 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 5 d | XGBoost | 0.4163 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 7 d | Logistic Regression | 0.5020 | 0.0020 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 7 d | Random Forest | 0.6029 | 0.0035 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 7 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 7 d | XGBoost | 0.5024 | 0.0020 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 8 |
| ≥50 | 14 d | Logistic Regression | 0.5749 | 0.0024 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 8 |
| ≥50 | 14 d | Random Forest | 0.4305 | 0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 8 |
| ≥50 | 14 d | Seasonal baseline | 0.8193 | 0.0142 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 8 |
| ≥50 | 14 d | XGBoost | 0.4916 | 0.0022 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 8 |

## Direct species comparison

For each species and target threshold, the row reports that species' highest-PR-AUC weather model across the five tested horizons. Horizon/model selection uses the same comparison grid for every species and is descriptive, not a new independent validation. Seasonal PR-AUC is from the matched threshold and horizon.

| Species | Target | Selected model | Horizon | ROC-AUC | PR-AUC | Seasonal PR-AUC | PR lift | Precision | Recall | F1 | Positive test days |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Red-throated Pipit | ≥10 | XGBoost | 5 d | 0.7874 | 0.0983 | 0.0455 | +0.0528 | 0.0893 | 0.4167 | 0.1471 | 48 |
| Yellow-browed Warbler | ≥10 | XGBoost | 14 d | 0.9396 | 0.7502 | 0.6008 | +0.1495 | 0.6282 | 0.8449 | 0.7206 | 374 |
| Pallid Swift | ≥10 | XGBoost | 3 d | 0.9583 | 0.1900 | 0.0751 | +0.1149 | 0.1959 | 0.5135 | 0.2836 | 37 |
| Manx Shearwater | ≥10 | XGBoost | 1 d | 0.7059 | 0.1446 | 0.0351 | +0.1095 | 0.1471 | 0.1852 | 0.1639 | 27 |
| Red-throated Pipit | ≥25 | Random Forest | 5 d | 0.7271 | 0.0738 | 0.0231 | +0.0508 | 0.0000 | 0.0000 | 0.0000 | 19 |
| Yellow-browed Warbler | ≥25 | XGBoost | 1 d | 0.9705 | 0.6783 | 0.4674 | +0.2108 | 0.5332 | 0.9283 | 0.6773 | 251 |
| Pallid Swift | ≥25 | XGBoost | 3 d | 0.9455 | 0.2211 | 0.0533 | +0.1678 | 0.1566 | 0.5200 | 0.2407 | 25 |
| Manx Shearwater | ≥25 | Random Forest | 1 d | 0.7418 | 0.0344 | 0.0048 | +0.0296 | 0.0000 | 0.0000 | 0.0000 | 11 |
| Red-throated Pipit | ≥50 | Random Forest | 3 d | 0.7286 | 0.0060 | 0.0141 | -0.0081 | 0.0000 | 0.0000 | 0.0000 | 8 |
| Yellow-browed Warbler | ≥50 | XGBoost | 1 d | 0.9807 | 0.5235 | 0.3131 | +0.2104 | 0.4311 | 0.9484 | 0.5927 | 155 |
| Pallid Swift | ≥50 | XGBoost | 1 d | 0.8898 | 0.3110 | 0.0417 | +0.2693 | 0.2400 | 0.4615 | 0.3158 | 13 |
| Manx Shearwater | ≥50 | Logistic Regression | 7 d | 0.5878 | 0.0058 | 0.0009 | +0.0049 | 0.0000 | 0.0000 | 0.0000 | 3 |

## Cross-species forecastability summary

For each of 15 threshold/horizon combinations, take the best weather-model PR-AUC and subtract the matched seasonal baseline PR-AUC; the table summarizes those descriptive lifts.

| Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Scenarios beating seasonality |
|---|---:|---:|---:|---:|
| Manx Shearwater | 0.0297 | 0.0137 | +0.0160 | 13/15 |
| Pallid Swift | 0.1431 | 0.0567 | +0.0864 | 14/15 |
| Red-throated Pipit | 0.0418 | 0.0276 | +0.0142 | 8/15 |
| Yellow-browed Warbler | 0.6195 | 0.4604 | +0.1591 | 15/15 |

## Feature importance and SHAP

The selected Pipit model is **XGBoost** for ≥10 records at 5 days (highest Pipit weather-model PR-AUC, 0.0983; ROC-AUC 0.7874). SHAP TreeExplainer values were computed separately on every annual held-out fold and pooled over 4,226 dates in 12 test years (48 positive target days). Importance is mean absolute SHAP on the model's raw output scale; it measures predictive contribution magnitude, not causal effects.

### Top 20 features

| Rank | Feature | Mean absolute SHAP | Category |
|---:|---|---:|---|
| 1 | `day_of_year_cos` | 1.046405 | Seasonality |
| 2 | `day_of_year` | 0.625639 | Seasonality |
| 3 | `TN_242` | 0.390740 | Temperature |
| 4 | `TN_235` | 0.359947 | Temperature |
| 5 | `temperature_lag_72h` | 0.339681 | Temperature |
| 6 | `temperature_lag_48h` | 0.257581 | Temperature |
| 7 | `wind_speed_lag_72h` | 0.251549 | Other |
| 8 | `wind_sin_310` | 0.246529 | Wind direction |
| 9 | `pressure_lag_72h` | 0.222539 | Pressure |
| 10 | `day_of_year_sin` | 0.221802 | Seasonality |
| 11 | `wind_change_48h` | 0.166534 | Other |
| 12 | `pressure_change_48h` | 0.161216 | Pressure change |
| 13 | `TX_242` | 0.147922 | Temperature |
| 14 | `wind_sin_242` | 0.136014 | Wind direction |
| 15 | `wind_sin_225` | 0.131001 | Wind direction |
| 16 | `TN_310` | 0.125598 | Temperature |
| 17 | `month` | 0.104974 | Seasonality |
| 18 | `TG_310` | 0.099773 | Temperature |
| 19 | `coast_TX_max` | 0.084780 | Temperature |
| 20 | `temp_change_48h` | 0.082374 | Temperature |

### SHAP importance by feature family

| Feature family | Total mean absolute SHAP | Share |
|---|---:|---:|
| Temperature | 2.206705 | 33.5% |
| Seasonality | 1.998821 | 30.3% |
| Wind direction | 0.845024 | 12.8% |
| Other | 0.838678 | 12.7% |
| Pressure | 0.492012 | 7.5% |
| Pressure change | 0.213055 | 3.2% |

## Biological interpretation

Seasonality accounts for 30.3% of pooled absolute SHAP importance, so the model's signal is not dominated by the calendar alone. The highest-ranked predictors are `day_of_year_cos`, `day_of_year`, `TN_242`, `TN_235`, `temperature_lag_72h`. Red-throated Pipits pass through the Netherlands during migration; a day-of-year signal is biologically plausible as migration timing. Weather signals may reflect conditions associated with migration, stopover, detectability, or observer activity. Their importance does not establish a causal response to wind, pressure, or temperature.

Seasonal share is 30.3%; the remaining 69.7% is distributed across weather and other predictor families. Absolute SHAP values do not reveal whether a weather condition raises or lowers predicted risk. GBIF counts are affected by uneven reporting effort and should not be interpreted as bird abundance.

The complete pooled held-out feature ranking is saved in `data/processed/red_throated_pipit_shap_importance.csv`.

## Recommendation

Red-throated Pipit is not the strongest species by the predefined grid summary: Yellow-browed Warbler ranks first (mean PR-AUC lift +0.1591 vs Pipit's +0.0142). For the ≥10 target, Pipit's strongest model is XGBoost at 5 days (PR-AUC 0.0983, seasonal PR-AUC 0.0455, F1 0.1471); it has only 48 positive test days. At ≥25 and ≥50 records, the best Pipit weather models have zero precision/recall/F1 at the fixed 0.5 threshold, and the ≥50 target has only eight positive held-out days.

**Recommendation:** retain Red-throated Pipit as an exploratory weather-driven candidate for the ≥10-record target, but do not promote it as the strongest Bird-Predict species or as an operational forecast. Yellow-browed Warbler and Pallid Swift show stronger and more consistent held-out performance in this comparison. The rare ≥25/≥50 Pipit targets need more independent positive events before their scores or feature explanations are stable enough for operational use.

## Limitations

- The 0.5 classification cutoff is fixed; it produces zero precision, recall, and F1 for some rare-event models despite ranking skill above baseline.
- Selecting the best model, horizon, and threshold on this same held-out grid is descriptive and can overstate performance; there is no independent final test period.
- High-count dates can cluster in migration/reporting episodes, so positive days are not necessarily independent events.
- GBIF facets and the KNMI date coverage can change; `country=NL` is a GBIF country-code filter, not a coordinate boundary.
- SHAP summarizes fitted model behavior, not causal effects; changing observer effort may be confounded with weather and season.

The complete shared performance grid is in `data/processed/species_forecast_metrics.csv`; the all-species method and full model results are in `reports/species_forecast_comparison.md`.
