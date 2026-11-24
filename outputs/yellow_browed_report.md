# Bird-Predict Daily Report: Yellow-browed Warbler

Generated: 2026-11-24 10:29 UTC

Forecast dates: 2026-11-25 to 2026-12-08

## Summary

- Mean predicted daily risk: 19.9%
- Highest predicted risk: 38.0% on 2026-11-30 (Low)
- Model: XGBoost; target is at least 10 records.
- Experiment reference: 14-day lead PR-AUC 0.7502, ROC-AUC 0.9396.
- Weather input: Open-Meteo Forecast API (best-match forecast model; hourly forecast aggregated to local daily values at four coastal grid points approximating KNMI stations).

## Daily forecast

| Date | Probability | Risk category |
|---|---:|---|
| 2026-11-25 | 6.5% | Very Low |
| 2026-11-26 | 4.5% | Very Low |
| 2026-11-27 | 3.6% | Very Low |
| 2026-11-28 | 6.0% | Very Low |
| 2026-11-29 | 6.2% | Very Low |
| 2026-11-30 | 38.0% | Low |
| 2026-12-01 | 22.1% | Low |
| 2026-12-02 | 35.0% | Low |
| 2026-12-03 | 30.7% | Low |
| 2026-12-04 | 26.6% | Low |
| 2026-12-05 | 25.3% | Low |
| 2026-12-06 | 35.2% | Low |
| 2026-12-07 | 28.7% | Low |
| 2026-12-08 | 9.8% | Very Low |

## Interpretation and limitations

Weather-source caveat: the production model was trained using KNMI station observations. This run uses Open-Meteo forecast-model grid points near the four KNMI coastal stations, with hourly values aggregated to local daily values and converted to the KNMI scaling. The sources, spatial representation, and aggregation are not identical, so this is a source-mismatched input and its probabilities have not been validated or recalibrated for Open-Meteo. KNMI `RH` means daily precipitation (0.1 mm), not relative humidity; the adapter maps Open-Meteo precipitation to `RH` and does not use relative humidity as that field.

This model was selected and evaluated as a fixed 14-day-ahead classifier. Applying it to daily dates one day after each weather-valid date is a lead-time shift from that experiment; probabilities for nearer dates are not separately calibrated or validated. Yellow-browed Warbler targets represent GBIF record counts, not abundance, and may reflect observer effort and detectability. Treat categories as model scores, not certainty.

Risk plot: `yellow_browed_forecast.png`
