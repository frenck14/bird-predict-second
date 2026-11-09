# Bird-Predict Daily Report: Yellow-browed Warbler

Generated: 2026-10-13 20:26 UTC

**Input note:** This is an illustrative synthetic weather scenario, not an official weather forecast.

Forecast dates: 2026-10-14 to 2026-10-27

## Summary

- Mean predicted daily risk: 92.2%
- Highest predicted risk: 96.9% on 2026-10-14 (Very High)
- Model: XGBoost; target is at least 10 records.
- Experiment reference: 14-day lead PR-AUC 0.7502, ROC-AUC 0.9396.

## Daily forecast

| Date | Probability | Risk category |
|---|---:|---|
| 2026-10-14 | 96.9% | Very High |
| 2026-10-15 | 96.9% | Very High |
| 2026-10-16 | 96.8% | Very High |
| 2026-10-17 | 96.6% | Very High |
| 2026-10-18 | 96.9% | Very High |
| 2026-10-19 | 96.9% | Very High |
| 2026-10-20 | 94.3% | Very High |
| 2026-10-21 | 93.3% | Very High |
| 2026-10-22 | 91.2% | Very High |
| 2026-10-23 | 89.8% | Very High |
| 2026-10-24 | 90.4% | Very High |
| 2026-10-25 | 84.7% | Very High |
| 2026-10-26 | 85.8% | Very High |
| 2026-10-27 | 80.9% | Very High |

## Interpretation and limitations

This model was selected and evaluated as a fixed 14-day-ahead classifier. Applying it to daily dates one day after each weather-valid date is a lead-time shift from that experiment; probabilities for nearer dates are not separately calibrated or validated. Yellow-browed Warbler targets represent GBIF record counts, not abundance, and may reflect observer effort and detectability. Treat categories as model scores, not certainty.

Risk plot: `scenario_c_forecast.png`
