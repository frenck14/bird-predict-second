# Yellow-browed Warbler Synthetic Weather Scenario Comparison

All three scenarios use the same 14 target dates (2026-10-14 through
2026-10-27). Only the station-level weather inputs vary. Values are
illustrative synthetic weather, not official forecast data.

## Scenario definitions

- **A — Typical calm October:** light westerly flow, low winds, near-normal
  temperatures, and mostly dry conditions.
- **B — Strong easterly:** easterly flow, strong winds, falling low pressure,
  and intermittent precipitation.
- **C — Unfavourable westerly:** westerly flow, moderate/light winds, dry
  conditions, and persistent stable high pressure.

Predictions use the production model selected for the `>=10 records` target
at a 14-day forecast lead. Its experiment PR-AUC was 0.7502. Since daily
scenario predictions are applied one day after the weather-valid date, this
is a lead-time shift and has not been separately calibrated or validated.

## Summary

| Scenario | Mean probability | Probability range | Risk categories | Days Very High |
|---|---:|---:|---|---:|
| A — Typical calm October | 92.29% | 78.44–96.94% | High, Very High | 13 |
| B — Strong easterly, low pressure, high winds | 94.84% | 85.84–97.72% | Very High | 14 |
| C — Unfavourable westerly, stable high pressure | 92.24% | 80.85–96.94% | Very High | 14 |

Mean risk differs by 2.60 percentage points between scenarios B and C.
Comparing the three predictions on the same date, their mean spread is
2.97 percentage points; the largest spread is 7.40 points on 2026-10-27.

## Daily probabilities

| Target date | A probability / risk | B probability / risk | C probability / risk |
|---|---|---|---|
| 2026-10-14 | 96.9% / Very High | 96.9% / Very High | 96.9% / Very High |
| 2026-10-15 | 96.8% / Very High | 97.3% / Very High | 96.9% / Very High |
| 2026-10-16 | 96.6% / Very High | 97.1% / Very High | 96.8% / Very High |
| 2026-10-17 | 96.6% / Very High | 97.1% / Very High | 96.6% / Very High |
| 2026-10-18 | 96.9% / Very High | 97.6% / Very High | 96.9% / Very High |
| 2026-10-19 | 96.9% / Very High | 97.7% / Very High | 96.9% / Very High |
| 2026-10-20 | 93.7% / Very High | 97.0% / Very High | 94.3% / Very High |
| 2026-10-21 | 92.1% / Very High | 95.9% / Very High | 93.3% / Very High |
| 2026-10-22 | 92.1% / Very High | 95.1% / Very High | 91.2% / Very High |
| 2026-10-23 | 91.9% / Very High | 94.4% / Very High | 89.8% / Very High |
| 2026-10-24 | 92.7% / Very High | 94.9% / Very High | 90.4% / Very High |
| 2026-10-25 | 85.2% / Very High | 91.2% / Very High | 84.7% / Very High |
| 2026-10-26 | 85.2% / Very High | 89.7% / Very High | 85.8% / Very High |
| 2026-10-27 | 78.4% / High | 85.8% / Very High | 80.9% / Very High |

## Interpretation

The model responds to weather changes, but these runs indicate that the
predictions are primarily driven by seasonality for this October window.
All scenarios retain very high risk on nearly every date despite sharply
different wind and pressure patterns. Scenario B is generally higher later
in the period, but the average scenario probability changes only 2.60 points.

This agrees with the model's forward-held-out SHAP summary: calendar
seasonality features accounted for 63.9% of total mean absolute SHAP
importance, compared with 4.2% for wind direction, 6.7% for pressure, and
0.7% for pressure change. SHAP values are global predictive attributions,
not causal effects. Weather scenario comparisons are not a controlled
intervention or a calibration test, and the chosen category thresholds make
moderate probability changes invisible when predictions remain in the same
category. These synthetic outputs are not reliable operational forecasts.

## Inputs and outputs

| Scenario | Synthetic input | Forecast CSV | Plot | Daily report |
|---|---|---|---|---|
| A | `inputs/scenario_a_typical_calm_october.csv` | `outputs/scenario_a_forecast.csv` | `outputs/scenario_a_forecast.png` | `outputs/scenario_a_report.md` |
| B | `inputs/scenario_b_strong_easterly.csv` | `outputs/scenario_b_forecast.csv` | `outputs/scenario_b_forecast.png` | `outputs/scenario_b_report.md` |
| C | `inputs/scenario_c_unfavourable_westerly.csv` | `outputs/scenario_c_forecast.csv` | `outputs/scenario_c_forecast.png` | `outputs/scenario_c_report.md` |
