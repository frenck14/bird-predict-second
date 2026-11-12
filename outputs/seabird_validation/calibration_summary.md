# Seabird probability calibration

## Method

Raw one-day-ahead probabilities from the rolling strict-cutoff event
validation (annual expanding-window fits, 2015-01-01 through 2026-08-11) are
pooled per species and compared with aligned influx-event labels. No model
was refit for this analysis, thresholds are unchanged, and probabilities
are neither recalibrated nor thresholded. Ten equal-width bins are used;
the last bin includes 1.00. ECE and MCE are the count-weighted and maximum
absolute gap between mean predicted probability and observed frequency
over non-empty bins. The Brier decomposition (reliability, resolution,
uncertainty) uses the same bins and so carries a small within-bin residual
(`decomposition_residual` in the CSV). Brier Skill Score is relative to a
constant forecast of the pooled event prevalence, which is an in-sample,
hindsight baseline and therefore a demanding one (the annual
training-prevalence baseline in the rolling validation is the fairer
operational comparison). Labels are GBIF record counts at or above each
year's training P90 threshold, so event definitions carry reporting
effort and are not proven absence.

## Metrics

| Species | Days | Events | Prevalence | Mean forecast | Brier | BSS vs prevalence | Reliability | Resolution | Uncertainty | ECE | MCE | Slope | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Northern Fulmar | 4241 | 1108 | 26.1% | 11.7% | 0.1969 | -0.020 | 0.0285 | 0.0227 | 0.1930 | 0.147 | 0.665 | 1.48 | underconfident |
| Manx Shearwater | 4241 | 1050 | 24.8% | 11.9% | 0.1559 | +0.163 | 0.0280 | 0.0562 | 0.1863 | 0.129 | 0.287 | 1.52 | underconfident |
| European Storm-petrel | 4241 | 883 | 20.8% | 15.3% | 0.1173 | +0.288 | 0.0060 | 0.0523 | 0.1649 | 0.055 | 0.151 | 1.22 | underconfident |
| Sooty Shearwater | 4241 | 33 | 0.8% | 7.5% | 0.0208 | -1.689 | 0.0126 | 0.0001 | 0.0077 | 0.067 | 0.620 | 0.11 | overconfident |
| Great Shearwater | 4241 | 15 | 0.4% | 0.7% | 0.0036 | -0.020 | 0.0000 | 0.0000 | 0.0035 | 0.003 | 0.203 | 0.50 | insufficient events |

Slope is the count-weighted regression slope of observed frequency on
predicted probability across bins: below 1 means high forecasts verify
less often than stated (overconfident), above 1 means they verify more
often (underconfident). A species is called well calibrated only if
ECE <= 0.03 and slope is within 0.8-1.2.

## Calibration bins

### Northern Fulmar

| Bin | Forecasts | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| 0.00-0.10 | 2166 | 4.6% | 11.6% |
| 0.10-0.20 | 1285 | 14.5% | 39.4% |
| 0.20-0.30 | 617 | 24.1% | 45.2% |
| 0.30-0.40 | 144 | 33.8% | 45.1% |
| 0.40-0.50 | 23 | 42.7% | 26.1% |
| 0.50-0.60 | 4 | 56.8% | 25.0% |
| 0.60-0.70 | 2 | 66.5% | 0.0% |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-1.00 | 0 | n/a | n/a |

### Manx Shearwater

| Bin | Forecasts | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| 0.00-0.10 | 2526 | 1.7% | 5.9% |
| 0.10-0.20 | 638 | 14.8% | 42.2% |
| 0.20-0.30 | 472 | 24.6% | 53.4% |
| 0.30-0.40 | 307 | 34.6% | 58.0% |
| 0.40-0.50 | 195 | 44.2% | 63.1% |
| 0.50-0.60 | 70 | 53.8% | 74.3% |
| 0.60-0.70 | 26 | 64.4% | 84.6% |
| 0.70-0.80 | 6 | 73.5% | 66.7% |
| 0.80-0.90 | 1 | 84.8% | 100.0% |
| 0.90-1.00 | 0 | n/a | n/a |

### European Storm-petrel

| Bin | Forecasts | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| 0.00-0.10 | 2399 | 2.0% | 3.2% |
| 0.10-0.20 | 516 | 14.6% | 22.7% |
| 0.20-0.30 | 387 | 25.0% | 37.7% |
| 0.30-0.40 | 374 | 34.7% | 49.7% |
| 0.40-0.50 | 244 | 45.1% | 55.7% |
| 0.50-0.60 | 194 | 54.2% | 68.0% |
| 0.60-0.70 | 93 | 64.3% | 64.5% |
| 0.70-0.80 | 34 | 72.9% | 85.3% |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-1.00 | 0 | n/a | n/a |

### Sooty Shearwater

| Bin | Forecasts | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| 0.00-0.10 | 3133 | 2.4% | 0.3% |
| 0.10-0.20 | 585 | 14.6% | 1.0% |
| 0.20-0.30 | 299 | 24.3% | 2.0% |
| 0.30-0.40 | 144 | 34.5% | 3.5% |
| 0.40-0.50 | 60 | 44.4% | 6.7% |
| 0.50-0.60 | 17 | 54.3% | 11.8% |
| 0.60-0.70 | 3 | 62.0% | 0.0% |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-1.00 | 0 | n/a | n/a |

### Great Shearwater

| Bin | Forecasts | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| 0.00-0.10 | 4226 | 0.7% | 0.3% |
| 0.10-0.20 | 14 | 11.7% | 7.1% |
| 0.20-0.30 | 1 | 20.3% | 0.0% |
| 0.30-0.40 | 0 | n/a | n/a |
| 0.40-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-1.00 | 0 | n/a | n/a |

## Classification

- Well calibrated: none
- Overconfident: Sooty Shearwater
- Underconfident: Northern Fulmar, Manx Shearwater, European Storm-petrel
- Miscalibrated: none
- Insufficient events: Great Shearwater

## Answer

**No: a stated probability of X% should not be read as an X% chance of an
influx event, for any of the five species.** Ranking is informative but the
absolute values are not calibrated:

- Underconfident (observed event frequency exceeds the stated probability): Northern Fulmar, Manx Shearwater, European Storm-petrel.
  Event rates rise with the forecast, but a 10-20% forecast verified roughly
  22-42% of the time, so read these as lower bounds. Northern Fulmar has
  negative Brier skill and little resolution, so even the ordering is weak.
- Overconfident (stated probability exceeds observed frequency): Sooty Shearwater.
  Sooty Shearwater forecasts of 10-60% verified 1-12% of the time, and
  its Brier score is worse than a constant prevalence forecast.
- Insufficient events for a verdict: Great Shearwater.
  Great Shearwater has too few events to say anything beyond that its
  near-zero forecasts are close to its near-zero base rate.

European Storm-petrel is the closest to usable (ECE about 0.05, positive
skill), and Manx Shearwater has the best resolution, but both still
understate event frequency at 10-50%. Quoting these raw values as
percentage chances would mislead. Any such use would need a separate,
out-of-sample recalibration step, which this analysis deliberately did not
perform. Event labels are GBIF record counts against a per-year P90
threshold, so the 'event frequency' itself depends on reporting effort.

Figures: `calibration_reliability.png`, `calibration_histograms.png`.
