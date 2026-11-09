# Bluetail Forecasting Experiment

## Objective and method

This experiment forecasts whether Dutch GBIF daily records for *Tarsiger cyanurus* reach ≥10, ≥25, or ≥50 at 1, 3, 5, 7, or 14 days ahead. Occurrence labels come from the archived GBIF Netherlands event-date facets; dates with no facet are zero on the shared KNMI weather calendar. The weather features are the same four-station coastal dataset and derived features used for Yellow-browed Warbler and Red-throated Pipit.

Validation is annual expanding-window forward chaining, with the first five years for initial training. Each test-year model trains only on examples whose target date precedes that year. Weather features use observations available through the day before the forecast origin; target-date calendar features are known in advance. Median imputation and model fitting occur within each fold. If a fold has no positive training examples, weather-model predictions are zero and the fold remains in evaluation.

The seasonal baseline uses month-specific training event rates smoothed with 30 prior-equivalent observations. Logistic Regression is class-weighted, Random Forest uses balanced subsampling, and XGBoost uses the training fold's negative-to-positive ratio. ROC-AUC and average-precision PR-AUC pool held-out predictions; precision, recall, and F1 use a fixed 0.5 cutoff.

## Bluetail performance

| Target | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Seasonal PR-AUC | Positive test days |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ≥10 | 1 d | Logistic Regression | 0.8328 | 0.0569 | 0.0485 | 0.5192 | 0.0887 | 0.0828 | 52 |
| ≥10 | 1 d | Random Forest | 0.8829 | 0.1353 | 0.1429 | 0.0192 | 0.0339 | 0.0828 | 52 |
| ≥10 | 1 d | Seasonal baseline | 0.8701 | 0.0828 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 1 d | XGBoost | 0.8951 | 0.1114 | 0.1345 | 0.4423 | 0.2063 | 0.0828 | 52 |
| ≥10 | 3 d | Logistic Regression | 0.8518 | 0.0573 | 0.0517 | 0.4808 | 0.0933 | 0.0828 | 52 |
| ≥10 | 3 d | Random Forest | 0.8539 | 0.1382 | 0.2500 | 0.0385 | 0.0667 | 0.0828 | 52 |
| ≥10 | 3 d | Seasonal baseline | 0.8701 | 0.0828 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 3 d | XGBoost | 0.8739 | 0.1442 | 0.1472 | 0.4615 | 0.2233 | 0.0828 | 52 |
| ≥10 | 5 d | Logistic Regression | 0.8408 | 0.0488 | 0.0464 | 0.4038 | 0.0832 | 0.0828 | 52 |
| ≥10 | 5 d | Random Forest | 0.8591 | 0.1370 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 5 d | Seasonal baseline | 0.8701 | 0.0828 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 5 d | XGBoost | 0.8664 | 0.0928 | 0.1139 | 0.3462 | 0.1714 | 0.0828 | 52 |
| ≥10 | 7 d | Logistic Regression | 0.8290 | 0.0440 | 0.0516 | 0.4615 | 0.0928 | 0.0828 | 52 |
| ≥10 | 7 d | Random Forest | 0.8457 | 0.0830 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 7 d | Seasonal baseline | 0.8703 | 0.0828 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 7 d | XGBoost | 0.8559 | 0.0809 | 0.1070 | 0.3846 | 0.1674 | 0.0828 | 52 |
| ≥10 | 14 d | Logistic Regression | 0.7842 | 0.0346 | 0.0362 | 0.4615 | 0.0671 | 0.0828 | 52 |
| ≥10 | 14 d | Random Forest | 0.8123 | 0.0616 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 14 d | Seasonal baseline | 0.8703 | 0.0828 | 0.0000 | 0.0000 | 0.0000 | 0.0828 | 52 |
| ≥10 | 14 d | XGBoost | 0.8684 | 0.0718 | 0.0786 | 0.3462 | 0.1281 | 0.0828 | 52 |
| ≥25 | 1 d | Logistic Regression | 0.7896 | 0.0263 | 0.0254 | 0.3611 | 0.0474 | 0.0510 | 36 |
| ≥25 | 1 d | Random Forest | 0.8413 | 0.1241 | 0.3333 | 0.0278 | 0.0513 | 0.0510 | 36 |
| ≥25 | 1 d | Seasonal baseline | 0.8374 | 0.0510 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 1 d | XGBoost | 0.8531 | 0.1136 | 0.1159 | 0.4444 | 0.1839 | 0.0510 | 36 |
| ≥25 | 3 d | Logistic Regression | 0.7926 | 0.0283 | 0.0331 | 0.4444 | 0.0617 | 0.0510 | 36 |
| ≥25 | 3 d | Random Forest | 0.8185 | 0.1109 | 0.2500 | 0.0278 | 0.0500 | 0.0510 | 36 |
| ≥25 | 3 d | Seasonal baseline | 0.8374 | 0.0510 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 3 d | XGBoost | 0.8308 | 0.0928 | 0.1095 | 0.4167 | 0.1734 | 0.0510 | 36 |
| ≥25 | 5 d | Logistic Regression | 0.8026 | 0.0308 | 0.0342 | 0.3889 | 0.0629 | 0.0510 | 36 |
| ≥25 | 5 d | Random Forest | 0.8232 | 0.0834 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 5 d | Seasonal baseline | 0.8374 | 0.0510 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 5 d | XGBoost | 0.8206 | 0.0500 | 0.0719 | 0.2778 | 0.1143 | 0.0510 | 36 |
| ≥25 | 7 d | Logistic Regression | 0.7987 | 0.0284 | 0.0388 | 0.4444 | 0.0714 | 0.0510 | 36 |
| ≥25 | 7 d | Random Forest | 0.7727 | 0.0633 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 7 d | Seasonal baseline | 0.8374 | 0.0510 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 7 d | XGBoost | 0.8304 | 0.0547 | 0.0938 | 0.4167 | 0.1531 | 0.0510 | 36 |
| ≥25 | 14 d | Logistic Regression | 0.7198 | 0.0178 | 0.0191 | 0.3056 | 0.0359 | 0.0510 | 36 |
| ≥25 | 14 d | Random Forest | 0.7893 | 0.0490 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 14 d | Seasonal baseline | 0.8374 | 0.0510 | 0.0000 | 0.0000 | 0.0000 | 0.0510 | 36 |
| ≥25 | 14 d | XGBoost | 0.8123 | 0.0775 | 0.0602 | 0.2778 | 0.0990 | 0.0510 | 36 |
| ≥50 | 1 d | Logistic Regression | 0.6617 | 0.0089 | 0.0096 | 0.2000 | 0.0183 | 0.0310 | 20 |
| ≥50 | 1 d | Random Forest | 0.8039 | 0.0342 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 1 d | Seasonal baseline | 0.8095 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 1 d | XGBoost | 0.7479 | 0.0313 | 0.0519 | 0.2000 | 0.0825 | 0.0310 | 20 |
| ≥50 | 3 d | Logistic Regression | 0.5841 | 0.0072 | 0.0115 | 0.2000 | 0.0217 | 0.0310 | 20 |
| ≥50 | 3 d | Random Forest | 0.7630 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 3 d | Seasonal baseline | 0.8095 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 3 d | XGBoost | 0.6423 | 0.0122 | 0.0167 | 0.0500 | 0.0250 | 0.0310 | 20 |
| ≥50 | 5 d | Logistic Regression | 0.6511 | 0.0102 | 0.0157 | 0.2500 | 0.0295 | 0.0310 | 20 |
| ≥50 | 5 d | Random Forest | 0.6677 | 0.0208 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 5 d | Seasonal baseline | 0.8095 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 5 d | XGBoost | 0.6903 | 0.0259 | 0.0333 | 0.1000 | 0.0500 | 0.0310 | 20 |
| ≥50 | 7 d | Logistic Regression | 0.6677 | 0.0090 | 0.0096 | 0.1500 | 0.0181 | 0.0310 | 20 |
| ≥50 | 7 d | Random Forest | 0.7502 | 0.0204 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 7 d | Seasonal baseline | 0.8095 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 7 d | XGBoost | 0.7471 | 0.0288 | 0.0141 | 0.0500 | 0.0220 | 0.0310 | 20 |
| ≥50 | 14 d | Logistic Regression | 0.5228 | 0.0059 | 0.0078 | 0.2000 | 0.0150 | 0.0310 | 20 |
| ≥50 | 14 d | Random Forest | 0.6725 | 0.0199 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 14 d | Seasonal baseline | 0.8095 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |
| ≥50 | 14 d | XGBoost | 0.6549 | 0.0119 | 0.0000 | 0.0000 | 0.0000 | 0.0310 | 20 |

## Direct comparison with Bird-Predict species

For each species and threshold, this table shows the highest-PR-AUC weather model across the five horizons. The matched seasonal baseline is shown for the selected horizon. Selection across this grid is descriptive, not an independent validation.

| Species | Target | Best model | Horizon | ROC-AUC | PR-AUC | Seasonal PR-AUC | Precision | Recall | F1 | Positive test days |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Yellow-browed Warbler | ≥10 | XGBoost | 14 d | 0.9396 | 0.7502 | 0.6008 | 0.6282 | 0.8449 | 0.7206 | 374 |
| Pallid Swift | ≥10 | XGBoost | 3 d | 0.9583 | 0.1900 | 0.0751 | 0.1959 | 0.5135 | 0.2836 | 37 |
| Red-throated Pipit | ≥10 | XGBoost | 5 d | 0.7874 | 0.0983 | 0.0455 | 0.0893 | 0.4167 | 0.1471 | 48 |
| Manx Shearwater | ≥10 | XGBoost | 1 d | 0.7059 | 0.1446 | 0.0351 | 0.1471 | 0.1852 | 0.1639 | 27 |
| Bluetail | ≥10 | XGBoost | 3 d | 0.8739 | 0.1442 | 0.0828 | 0.1472 | 0.4615 | 0.2233 | 52 |
| Yellow-browed Warbler | ≥25 | XGBoost | 1 d | 0.9705 | 0.6783 | 0.4674 | 0.5332 | 0.9283 | 0.6773 | 251 |
| Pallid Swift | ≥25 | XGBoost | 3 d | 0.9455 | 0.2211 | 0.0533 | 0.1566 | 0.5200 | 0.2407 | 25 |
| Red-throated Pipit | ≥25 | Random Forest | 5 d | 0.7271 | 0.0738 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 19 |
| Manx Shearwater | ≥25 | Random Forest | 1 d | 0.7418 | 0.0344 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 11 |
| Bluetail | ≥25 | Random Forest | 1 d | 0.8413 | 0.1241 | 0.0510 | 0.3333 | 0.0278 | 0.0513 | 36 |
| Yellow-browed Warbler | ≥50 | XGBoost | 1 d | 0.9807 | 0.5235 | 0.3131 | 0.4311 | 0.9484 | 0.5927 | 155 |
| Pallid Swift | ≥50 | XGBoost | 1 d | 0.8898 | 0.3110 | 0.0417 | 0.2400 | 0.4615 | 0.3158 | 13 |
| Red-throated Pipit | ≥50 | Random Forest | 3 d | 0.7286 | 0.0060 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 8 |
| Manx Shearwater | ≥50 | Logistic Regression | 7 d | 0.5878 | 0.0058 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 3 |
| Bluetail | ≥50 | Random Forest | 1 d | 0.8039 | 0.0342 | 0.0310 | 0.0000 | 0.0000 | 0.0000 | 20 |

## Forecastability ranking

Ranked by the mean best-weather-model PR-AUC lift over the matched seasonal baseline across all 15 threshold/horizon scenarios. Model selection is performed consistently for every species. PR-AUC depends on prevalence, and the ranking is descriptive, not a significance test.

| Rank | Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Scenarios beating seasonality |
|---:|---|---:|---:|---:|---:|
| 1 | Yellow-browed Warbler | 0.6195 | 0.4604 | +0.1591 | 15/15 |
| 2 | Pallid Swift | 0.1431 | 0.0567 | +0.0864 | 14/15 |
| 3 | Bluetail | 0.0780 | 0.0550 | +0.0231 | 10/15 |
| 4 | Manx Shearwater | 0.0297 | 0.0137 | +0.0160 | 13/15 |
| 5 | Red-throated Pipit | 0.0418 | 0.0276 | +0.0142 | 8/15 |

## Feature importance

Feature importance is averaged across each held-out annual fold for the selected XGBoost model, target ≥10, horizon 3 days. The selected experiment result has PR-AUC 0.1442 and ROC-AUC 0.8739. Random Forest/XGBoost built-in impurity or gain importances are averaged fold-wise; Logistic Regression uses absolute standardized coefficients.

| Rank | Feature | Mean model importance | Category |
|---:|---|---:|---|
| 1 | `day_of_year` | 0.100340 | Seasonality |
| 2 | `day_of_year_sin` | 0.068549 | Seasonality |
| 3 | `month` | 0.058093 | Seasonality |
| 4 | `coast_TG_mean` | 0.053522 | Temperature |
| 5 | `TX_310` | 0.041753 | Temperature |
| 6 | `TG_242` | 0.035795 | Temperature |
| 7 | `TN_310` | 0.030024 | Temperature |
| 8 | `coast_TX_mean` | 0.028234 | Temperature |
| 9 | `temperature_lag_24h` | 0.025643 | Temperature |
| 10 | `temperature_lag_48h` | 0.024145 | Temperature |
| 11 | `wind_cos_235` | 0.023515 | Wind direction |
| 12 | `coast_TX_max` | 0.022627 | Temperature |
| 13 | `TN_235` | 0.019602 | Temperature |
| 14 | `coast_PX_min` | 0.018521 | Pressure |
| 15 | `coast_wind_cos` | 0.017443 | Wind direction |
| 16 | `wind_cos_310` | 0.016014 | Wind direction |
| 17 | `TX_235` | 0.014137 | Temperature |
| 18 | `TG_310` | 0.013615 | Temperature |
| 19 | `day_of_year_cos` | 0.013440 | Seasonality |
| 20 | `TX_242` | 0.013251 | Temperature |

## SHAP importance

SHAP values were computed on held-out forecast dates for each annual fold and pooled across 4,226 dates, 12 test years, and 52 positive target days. Values are mean absolute SHAP on the model output scale; they describe predictive contribution magnitude, not causation.

| Rank | Feature | Mean absolute SHAP | Category |
|---:|---|---:|---|
| 1 | `day_of_year_sin` | 1.405374 | Seasonality |
| 2 | `day_of_year` | 1.329230 | Seasonality |
| 3 | `temperature_lag_48h` | 0.250570 | Temperature |
| 4 | `TN_310` | 0.215610 | Temperature |
| 5 | `pressure_lag_72h` | 0.202753 | Pressure |
| 6 | `TX_235` | 0.200648 | Temperature |
| 7 | `day_of_year_cos` | 0.194652 | Seasonality |
| 8 | `temperature_lag_24h` | 0.193549 | Temperature |
| 9 | `coast_TX_max` | 0.179696 | Temperature |
| 10 | `temperature_lag_72h` | 0.165565 | Temperature |
| 11 | `TN_235` | 0.147113 | Temperature |
| 12 | `wind_cos_310` | 0.143083 | Wind direction |
| 13 | `TX_310` | 0.130738 | Temperature |
| 14 | `TX_242` | 0.125280 | Temperature |
| 15 | `TN_242` | 0.118034 | Temperature |
| 16 | `coast_wind_cos` | 0.115407 | Wind direction |
| 17 | `wind_speed_lag_72h` | 0.099879 | Other |
| 18 | `coast_TX_mean` | 0.098234 | Temperature |
| 19 | `wind_sin_242` | 0.081881 | Wind direction |
| 20 | `FHX_242` | 0.081203 | Other |

### SHAP by feature family

| Feature family | Total mean absolute SHAP | Share |
|---|---:|---:|
| Seasonality | 3.010179 | 41.8% |
| Temperature | 2.117577 | 29.4% |
| Other | 0.875312 | 12.2% |
| Wind direction | 0.590704 | 8.2% |
| Pressure | 0.494595 | 6.9% |
| Pressure change | 0.110746 | 1.5% |

## Biological interpretation

Seasonality contributes 41.8% of total absolute SHAP importance. The most influential predictors are `day_of_year_sin`, `day_of_year`, `temperature_lag_48h`, `TN_310`, `pressure_lag_72h`. A day-of-year contribution is consistent with Bluetail migration and seasonal passage through the Netherlands. Temperature, wind, and pressure associations may reflect migration conditions, stopover, detectability, or observer effort; this observational experiment cannot distinguish these mechanisms or infer causal weather effects.

SHAP magnitude does not show whether a particular weather condition increases or decreases predicted records. GBIF observations reflect reporting effort and are not abundance estimates; event-date clusters may represent shared migration or reporting episodes rather than independent bird-level observations.

## Recommendation

No. Yellow-browed Warbler currently ranks first by mean best-weather-model PR-AUC lift across the predefined 15-scenario grid. This comparative score is evidence of relative held-out ranking performance, but not a formal significance test or proof of operational utility. The strongest ≥10 Bluetail scenario is XGBoost at 3 days (PR-AUC 0.1442); there are only 52 positive held-out days. The ≥25 and ≥50 thresholds have progressively less support, so their metrics should be treated as unstable when positive days are sparse.

**Recommendation:** retain Bluetail as an exploratory candidate and prioritize interpretation around the ≥10 target. Do not promote it as the strongest weather-driven Bird-Predict species unless its pooled lift and rare-event precision/recall remain competitive on a later, independent evaluation period.

## Limitations

- All species share the 2010-10-01 to 2026-08-10 KNMI calendar; historical occurrences outside it are not used.
- The 0.5 classification threshold is fixed and may yield zero precision, recall, or F1 for rare targets.
- The best model/horizon summaries use the same held-out grid for selection and comparison, so they may overstate general performance.
- GBIF reporting effort varies and is not controlled; counts are not measures of abundance.
- Absolute SHAP values and feature importance describe fitted model behavior and are not causal explanations.

Metrics: `data/processed/bluetail_forecast_metrics.csv`. Model importance: `data/processed/bluetail_feature_importance.csv`. SHAP importance: `data/processed/bluetail_shap_importance.csv`. Existing comparison results: `data/processed/species_forecast_metrics.csv`.
