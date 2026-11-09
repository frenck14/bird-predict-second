# Yellow-browed Warbler Feature Importance

## Model selection and method

The selected model is **XGBoost**, predicting the **>= 10 records** target at a **14-day horizon**. It was the highest-PR-AUC non-baseline Yellow-browed Warbler result in the completed forward-chaining experiment (PR-AUC 0.7502; ROC-AUC 0.9396).

SHAP TreeExplainer values were calculated on each annual held-out fold, using the same expanding-window training rules, target-date alignment, one-day-lagged weather features, known target-date calendar features, XGBoost settings, and fold-specific imputation as the forecast experiment. Mean absolute SHAP values are pooled over 4,226 held-out forecast dates across 12 test years (374 positive target dates). Features are ranked by pooled mean absolute SHAP value. Values indicate contribution magnitude on the model's raw output scale; they do not establish causation.

## Top 20 predictors

| Rank | Feature | Mean absolute SHAP | Category |
|---:|---|---:|---|
| 1 | `day_of_year_sin` | 1.569740 | Seasonality |
| 2 | `day_of_year` | 0.975348 | Seasonality |
| 3 | `day_of_year_cos` | 0.716518 | Seasonality |
| 4 | `TN_242` | 0.165944 | Temperature |
| 5 | `wind_speed_lag_72h` | 0.139963 | Other |
| 6 | `pressure_lag_24h` | 0.128927 | Pressure |
| 7 | `TN_310` | 0.094995 | Temperature |
| 8 | `temperature_lag_72h` | 0.088475 | Temperature |
| 9 | `coast_TX_max` | 0.074384 | Temperature |
| 10 | `pressure_lag_48h` | 0.072952 | Pressure |
| 11 | `temperature_lag_48h` | 0.068423 | Temperature |
| 12 | `TN_235` | 0.062066 | Temperature |
| 13 | `PX_310` | 0.057926 | Pressure |
| 14 | `wind_speed_lag_48h` | 0.053426 | Other |
| 15 | `coast_wind_cos` | 0.050242 | Wind direction |
| 16 | `wind_cos_310` | 0.046413 | Wind direction |
| 17 | `TG_242` | 0.042676 | Temperature |
| 18 | `temp_change_48h` | 0.034261 | Temperature |
| 19 | `FG_310` | 0.034248 | Other |
| 20 | `FG_235` | 0.034047 | Other |

## Importance by predictor group

Group totals sum mean absolute SHAP values across all features in that group; shares are relative to the total across groups.

| Predictor group | Total mean absolute SHAP | Share |
|---|---:|---:|
| Seasonality | 3.271126 | 63.9% |
| Temperature | 0.810305 | 15.8% |
| Other | 0.443492 | 8.7% |
| Pressure | 0.341425 | 6.7% |
| Wind direction | 0.214547 | 4.2% |
| Pressure change | 0.035315 | 0.7% |

## Requested predictor families

| Predictor family | Rank by group total | Share of total importance | In top 20 |
|---|---:|---:|---|
| Wind direction | 5 | 4.2% | Yes |
| Pressure | 4 | 6.7% | Yes |
| Pressure change | 6 | 0.7% | No |
| Temperature | 2 | 15.8% | Yes |
| Seasonality | 1 | 63.9% | Yes |

## Biological interpretation

Seasonality is the dominant predictor family (63.9% of total absolute SHAP); the three highest-ranked individual predictors are the annual sine, day-of-year, and annual cosine features. This is consistent with Yellow-browed Warbler occurrence/reporting being strongly concentrated in its migration season. Temperature is the second largest family (15.8%), while pressure (6.7%), wind direction (4.2%), and pressure change (0.7%) contribute less. The temperature signal could reflect migration timing, weather conditions, or observer activity; pressure and wind may add information about weather systems and migration-supporting flow. These are plausible ecological interpretations, not causal findings.

In this run, the top 20 include Wind direction, Pressure, Temperature, Seasonality. Pressure change accounts for 0.7% of group importance and has no feature in the top 20. Absolute SHAP values describe magnitude but not whether a value raises or lowers the prediction; signed dependence analysis would be needed to infer that direction. Yellow-browed Warbler records are occurrence/reporting counts, not direct measures of abundance; weather may also affect detectability and reporting effort.

The complete feature ranking is saved in `data/processed/yellow_browed_warbler_shap_importance.csv`.
