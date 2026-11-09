# Bird-Predict Daily Report: Yellow-browed Warbler

Generated: 2026-11-09 08:27 UTC

Forecast dates: 2026-11-10 to 2026-11-23

## Summary

- Mean predicted daily risk: 25.7%
- Highest predicted risk: 41.5% on 2026-11-10 (Moderate)
- Model: XGBoost; target is at least 10 records.
- Experiment reference: 14-day lead PR-AUC 0.7502, ROC-AUC 0.9396.
- Weather input: Open-Meteo Forecast API (best-match forecast model; hourly forecast aggregated to local daily values at four coastal grid points approximating KNMI stations).

## Daily forecast

| Date | Probability | Risk category |
|---|---:|---|
| 2026-11-10 | 41.5% | Moderate |
| 2026-11-11 | 33.3% | Low |
| 2026-11-12 | 20.8% | Low |
| 2026-11-13 | 25.2% | Low |
| 2026-11-14 | 29.7% | Low |
| 2026-11-15 | 29.0% | Low |
| 2026-11-16 | 36.8% | Low |
| 2026-11-17 | 21.0% | Low |
| 2026-11-18 | 21.6% | Low |
| 2026-11-19 | 19.6% | Very Low |
| 2026-11-20 | 21.7% | Low |
| 2026-11-21 | 23.9% | Low |
| 2026-11-22 | 21.8% | Low |
| 2026-11-23 | 13.3% | Very Low |

## Interpretation and limitations

Weather-source caveat: the production model was trained using KNMI station observations. This run uses Open-Meteo forecast-model grid points near the four KNMI coastal stations, with hourly values aggregated to local daily values and converted to the KNMI scaling. The sources, spatial representation, and aggregation are not identical, so this is a source-mismatched input and its probabilities have not been validated or recalibrated for Open-Meteo. KNMI `RH` means daily precipitation (0.1 mm), not relative humidity; the adapter maps Open-Meteo precipitation to `RH` and does not use relative humidity as that field.

This model was selected and evaluated as a fixed 14-day-ahead classifier. Applying it to daily dates one day after each weather-valid date is a lead-time shift from that experiment; probabilities for nearer dates are not separately calibrated or validated. Yellow-browed Warbler targets represent GBIF record counts, not abundance, and may reflect observer effort and detectability. Treat categories as model scores, not certainty.

Risk plot: `yellow_browed_forecast.png`
