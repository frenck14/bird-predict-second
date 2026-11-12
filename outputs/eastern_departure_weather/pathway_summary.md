# Eastern migration pathway study

Question: do combinations of departure and transport weather explain eastern-vagrant arrivals in the Netherlands better than source-region weather alone?

## Method

- Regions: Finland, Baltics, NW Russia (departure/transport) and the Netherlands (arrival), ERA5 daily data.
- Features per region: cold-front indicator (24 h temperature drop of 4 C or more), tailwind toward the Netherlands (toward the west for Dutch weather, i.e. easterly flow), crosswind, 24 h pressure change and precipitation anomaly; wind and precipitation are day-of-year anomalies. All standardised.
- Lags 1-5 days, each tested on its own and all together (`1-5`). Weather at lag k is observed k days before the target day.
- Models: A departure alone; B Dutch alone; C departure + Dutch; D departure plus departure x transport interactions (front, pressure change and precipitation anomaly x regional tailwind; regional tailwind x Dutch easterly flow of the previous day).
- Evaluation: leave-one-autumn-out L2 logistic regression (C=0.05, balanced), days 15 Sep-20 Nov 2011-2025, same event labels as the departure audit (top decile of Dutch records). Every model also has a seasonal term; `auc_gain` is the out-of-sample AUC above a seasonal-only baseline, with a 95% bootstrap interval over autumns.
- Species with fewer than 30 event days are flagged uncertain and excluded from the summaries.

## Mean AUC gain over seasonal baseline (reliable species, single lags 1-5)

| Model | Mean gain |
|---|---:|
| A departure alone | -0.012 |
| B Dutch alone | -0.007 |
| C departure + Dutch | -0.017 |
| D departure x transport | -0.020 |

## Mean AUC gain by lag setting

| Lag | A departure alone | B Dutch alone | C departure + Dutch | D departure x transport |
|---|---:|---:|---:|---:|
| 1 | -0.007 | -0.002 | -0.011 | -0.014 |
| 1-5 | -0.049 | -0.017 | -0.062 | -0.080 |
| 2 | -0.012 | -0.003 | -0.015 | -0.022 |
| 3 | -0.002 | -0.012 | -0.012 | -0.013 |
| 4 | -0.011 | -0.014 | -0.020 | -0.018 |
| 5 | -0.026 | -0.005 | -0.029 | -0.034 |

## Best result per species

| Species | Model | Lag | AUC | Gain | 95% CI |
|---|---|---|---:|---:|---|
| Blyth's Reed Warbler | D departure x transport | 3 | 0.510 | +0.089 | [-0.043, +0.193] |
| Dusky Warbler | B Dutch alone | 1 | 0.711 | +0.003 | [-0.015, +0.017] |
| Eastern guild (all species) | B Dutch alone | 1 | 0.780 | +0.010 | [-0.000, +0.022] |
| Olive-backed Pipit | B Dutch alone | 1-5 | 0.746 | +0.016 | [-0.013, +0.040] |
| Pallas's Warbler | B Dutch alone | 5 | 0.763 | +0.001 | [-0.014, +0.015] |
| Red-flanked Bluetail | B Dutch alone | 2 | 0.714 | -0.008 | [-0.034, +0.014] |
| Siberian Chiffchaff | A departure alone | 2 | 0.717 | +0.016 | [-0.019, +0.057] |
| Yellow-browed Warbler | A departure alone | 1 | 0.852 | +0.005 | [-0.015, +0.023] |

## Answer

Interaction model D beats departure-alone model A in 22% of species-lag cells (mean gain -0.020 vs -0.012). The best model on average is B Dutch alone. 0 of 160 single-lag fits have a bootstrap interval above zero.

Pathway interactions do not carry a clearly stronger signal than source weather alone; extra predictors mostly add noise with ~100 event days.

Caveats: exploratory, many comparisons, weak signals; Dutch weather is ERA5 at one point; event labels are GBIF record-count based, not validated influx labels; anomalies use whole-archive climatology (not cutoff-safe).
