# eBird baseline benchmark

Evaluation: 2015-01-01 to 2025-12-31, annual expanding-window cutoffs, one-day-ahead, same influx-event labels and dates as `rolling_event_validation.csv`, ended at the last year with eBird data in GBIF (the rolling run itself continues to 2026-08-11, so its published numbers differ slightly). Probability cutoff 0.20 for every model. No production model was retrained.

## Models

- **A: production weather model**
- **B: yesterday's event**
- **C: 7-day eBird activity**
- **D: 30-day eBird activity**
- **C-norm: 7-day activity / prior-year level**
- **D-norm: 30-day activity / prior-year level**

- A is the stored rolling weather forecast. B-D are refit each January on data up to the cutoff only, with the same year-specific event threshold as the labels.
- B uses the training frequencies of an event after an event and after a non-event.
- C and D use a one-feature logistic regression on log(1 + eBird records in the window ending the day before the forecast date). The -norm variants subtract the log of the prior 365-day average level, to remove the growth in eBird effort since 2010.
- eBird activity = eBird-dataset GBIF records of that species per day in GB, IE, NL, BE and DK (the same countries as the labels).

## Results by species

### Northern Fulmar

Event days 1107 of 4018 (27.6%).

| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |
|---|---:|---:|---:|---:|---:|---:|---|
| A: production weather model | 0.481 | 0.317 | 0.382 | 0.2063 | +0.101 | 0.162 | strongly underconfident |
| B: yesterday's event | 0.752 | 0.752 | 0.752 | 0.1234 | +0.462 | 0.083 | mildly underconfident |
| C: 7-day eBird activity | 0.483 | 0.867 | 0.620 | 0.1566 | +0.318 | 0.118 | strongly underconfident |
| D: 30-day eBird activity | 0.476 | 0.900 | 0.622 | 0.1601 | +0.302 | 0.131 | strongly underconfident |
| C-norm: 7-day activity / prior-year level | 0.669 | 0.159 | 0.257 | 0.2053 | +0.105 | 0.170 | strongly underconfident |
| D-norm: 30-day activity / prior-year level | 0.664 | 0.145 | 0.237 | 0.2065 | +0.100 | 0.170 | strongly underconfident |

### Manx Shearwater

Event days 1047 of 4018 (26.1%).

| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |
|---|---:|---:|---:|---:|---:|---:|---|
| A: production weather model | 0.623 | 0.601 | 0.612 | 0.1622 | +0.248 | 0.141 | strongly underconfident |
| B: yesterday's event | 0.733 | 0.733 | 0.733 | 0.1234 | +0.428 | 0.077 | mildly underconfident |
| C: 7-day eBird activity | 0.512 | 0.972 | 0.671 | 0.1202 | +0.442 | 0.048 | mildly overconfident |
| D: 30-day eBird activity | 0.505 | 0.971 | 0.664 | 0.1262 | +0.415 | 0.045 | mildly overconfident |
| C-norm: 7-day activity / prior-year level | 0.614 | 0.617 | 0.616 | 0.1618 | +0.250 | 0.142 | strongly underconfident |
| D-norm: 30-day activity / prior-year level | 0.580 | 0.605 | 0.592 | 0.1646 | +0.237 | 0.144 | strongly underconfident |

### European Storm-petrel

Event days 874 of 4018 (21.8%).

| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |
|---|---:|---:|---:|---:|---:|---:|---|
| A: production weather model | 0.542 | 0.780 | 0.640 | 0.1204 | +0.314 | 0.063 | mildly underconfident |
| B: yesterday's event | 0.627 | 0.627 | 0.627 | 0.1261 | +0.282 | 0.044 | mildly underconfident |
| C: 7-day eBird activity | 0.488 | 0.872 | 0.626 | 0.1131 | +0.356 | 0.038 | mildly overconfident |
| D: 30-day eBird activity | 0.448 | 0.911 | 0.600 | 0.1198 | +0.318 | 0.029 | well calibrated |
| C-norm: 7-day activity / prior-year level | 0.567 | 0.712 | 0.631 | 0.1194 | +0.320 | 0.066 | mildly underconfident |
| D-norm: 30-day activity / prior-year level | 0.520 | 0.747 | 0.613 | 0.1251 | +0.287 | 0.067 | mildly underconfident |

### Sooty Shearwater (fewer than 50 event days: uncertain)

Event days 33 of 4018 (0.8%).

| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |
|---|---:|---:|---:|---:|---:|---:|---|
| A: production weather model | 0.033 | 0.515 | 0.061 | 0.0219 | -0.744 | 0.070 | strongly overconfident |
| B: yesterday's event | 0.303 | 0.303 | 0.303 | 0.0093 | +0.262 | 0.038 | mildly overconfident |
| C: 7-day eBird activity | 0.024 | 0.576 | 0.047 | 0.0319 | -1.544 | 0.104 | strongly overconfident |
| D: 30-day eBird activity | 0.023 | 0.636 | 0.044 | 0.0349 | -1.781 | 0.110 | strongly overconfident |
| C-norm: 7-day activity / prior-year level | 0.026 | 0.273 | 0.047 | 0.0178 | -0.418 | 0.058 | strongly overconfident |
| D-norm: 30-day activity / prior-year level | 0.038 | 0.515 | 0.070 | 0.0183 | -0.460 | 0.060 | strongly overconfident |

### Great Shearwater (fewer than 50 event days: uncertain)

Event days 15 of 4018 (0.4%).

| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |
|---|---:|---:|---:|---:|---:|---:|---|
| A: production weather model | 0.000 | 0.000 | 0.000 | 0.0038 | -0.018 | 0.003 | strongly overconfident |
| B: yesterday's event | 0.400 | 0.400 | 0.400 | 0.0032 | +0.152 | 0.002 | well calibrated |
| C: 7-day eBird activity | 0.000 | 0.000 | 0.000 | 0.0038 | -0.010 | 0.003 | well calibrated |
| D: 30-day eBird activity | 0.000 | 0.000 | 0.000 | 0.0038 | -0.015 | 0.004 | well calibrated |
| C-norm: 7-day activity / prior-year level | 0.000 | 0.000 | 0.000 | 0.0037 | -0.004 | 0.002 | well calibrated |
| D-norm: 30-day activity / prior-year level | 0.000 | 0.000 | 0.000 | 0.0037 | -0.001 | 0.002 | well calibrated |

## Answer

- **Northern Fulmar:** weather F1 0.382 / Brier 0.2063; yesterday F1 0.752 / Brier 0.1234; best eBird baseline (D: 30-day eBird activity) F1 0.622 / Brier 0.1601. eBird activity beats weather on F1 and Brier.
- **Manx Shearwater:** weather F1 0.612 / Brier 0.1622; yesterday F1 0.733 / Brier 0.1234; best eBird baseline (C: 7-day eBird activity) F1 0.671 / Brier 0.1202. eBird activity beats weather on F1 and Brier.
- **European Storm-petrel:** weather F1 0.640 / Brier 0.1204; yesterday F1 0.627 / Brier 0.1261; best eBird baseline (C-norm: 7-day activity / prior-year level) F1 0.631 / Brier 0.1194. eBird activity beats weather on Brier.
- **Sooty Shearwater:** weather F1 0.061 / Brier 0.0219; yesterday F1 0.303 / Brier 0.0093; best eBird baseline (D-norm: 30-day activity / prior-year level) F1 0.070 / Brier 0.0183. eBird activity beats weather on F1 and Brier. Uncertain (<50 events).
- **Great Shearwater:** weather F1 0.000 / Brier 0.0038; yesterday F1 0.400 / Brier 0.0032; best eBird baseline (C: 7-day eBird activity) F1 0.000 / Brier 0.0038. eBird activity beats weather on Brier. Uncertain (<50 events).

## Interpretation

- Of the 3 species with at least 50 event days, yesterday's event beats the weather model on F1 for 2 (Northern Fulmar, Manx Shearwater), and raw 7/30-day eBird activity does so for 2 (Northern Fulmar, Manx Shearwater). Where persistence wins, the weather model adds no value over knowing yesterday's status.
- Events are strongly clustered in time, which persistence captures directly. Recent eBird activity carries that same clustering plus the seasonal cycle and reporting effort.
- Raw activity models (C, D) reach high recall with precision near 0.5 for Fulmar and Manx. This pattern means they flag most days in the active season and the long-run growth in eBird effort, not individual influx days. Their Brier gain is real, but part of it is season and effort rather than event timing.
- Removing the effort trend (-norm) removes most of that advantage for Fulmar and Manx. The Storm-petrel is the one species where the effort-normalised activity model (F1 0.631, Brier 0.1194) matches the weather model (F1 0.640, Brier 0.1204) without any weather input.
- Because the labels and the activity both come mostly from eBird records, and the activity here is not a frozen archive, these results are an upper bound on what recent eBird activity gives a real forecast. A combined weather + eBird model should be judged against B, not only against A.


## Caveats

- **Labels overlap eBird.** Most label records come from eBird (62-93% of GBIF records by species), so recent eBird activity partly reflects the target series itself. This measures information in recent reporting, not independent ecological signal.
- **Not a frozen archive.** Activity comes from the current GBIF snapshot, including records uploaded or reviewed after each forecast date. A real forecast would have seen less. Treat C and D as an upper bound.
- **Detections only.** GBIF has no eBird checklists, so activity is not effort-adjusted (reporting rate is not available).
- **Netherlands.** eBird holds only about 0-23% of Dutch records.
- Sooty and Great Shearwater have fewer than 50 event days; their scores are uncertain.
- Brier skill uses the training-period prevalence, as in `rolling_event_validation.csv`.
