# Seabird probability calibration

## Method

Raw one-day-ahead probabilities stored from the rolling strict-cutoff event
validation (2015-01-01 through 2026-08-11) are pooled per
species and compared with the aligned influx-event labels described in
`target_alignment_report.md` (record count at or above that year's
training-only P90 threshold; not presence). No model was refit, thresholds
are unchanged and probabilities are neither recalibrated nor thresholded
for the calibration metrics. Ten equal-width bins are used and the last
includes 1.00. ECE and MCE are the count-weighted and maximum absolute gap
between mean forecast and observed frequency over non-empty bins. The Brier
decomposition uses the same bins, so it has a small within-bin residual
(`decomposition_residual`). Brier Skill Score is against a constant forecast
of the pooled event prevalence (an in-sample hindsight baseline).

Overconfident means stated probabilities exceed observed frequency;
underconfident means they fall below it (reliability slope below/above 1).
Well calibrated needs ECE <= 0.03 and a slope within 0.8-1.2; the strength
is strong when ECE >= 0.10 or the slope is at least 0.5 from 1.
Species with fewer than 50 event days are flagged uncertain and
are reported separately.

## Metrics: species with at least 50 event days

| Species | Days | Events | Prevalence | Mean forecast | Brier | BSS | Reliability | Resolution | Uncertainty | ECE | MCE | Slope | Class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Northern Fulmar | 4241 | 1108 | 26.1% | 11.7% | 0.1969 | -0.020 | 0.0285 | 0.0227 | 0.1930 | 0.147 | 0.665 | 1.48 | strongly underconfident |
| Manx Shearwater | 4241 | 1050 | 24.8% | 11.9% | 0.1559 | +0.163 | 0.0280 | 0.0562 | 0.1863 | 0.129 | 0.287 | 1.52 | strongly underconfident |
| European Storm-petrel | 4241 | 883 | 20.8% | 15.3% | 0.1173 | +0.288 | 0.0060 | 0.0523 | 0.1649 | 0.055 | 0.151 | 1.22 | mildly underconfident |

## Metrics: rare-event species (fewer than 50 event days, uncertain)

| Species | Days | Events | Prevalence | Mean forecast | Brier | BSS | Reliability | Resolution | Uncertainty | ECE | MCE | Slope | Class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Sooty Shearwater | 4241 | 33 | 0.8% | 7.5% | 0.0208 | -1.689 | 0.0126 | 0.0001 | 0.0077 | 0.067 | 0.620 | 0.11 | strongly overconfident |
| Great Shearwater | 4241 | 15 | 0.4% | 0.7% | 0.0036 | -0.020 | 0.0000 | 0.0000 | 0.0035 | 0.003 | 0.203 | 0.50 | strongly overconfident |

With so few events, bin frequencies and the slope for these species swing
on a handful of days. Their classes are provisional.

## Interpretation by species

- **Northern Fulmar** is strongly underconfident. Mean forecast 11.7% against an event rate of 26.1%; ECE 0.147, slope 1.48. Observed frequency exceeds the stated probability, so forecasts are too low.
- **Manx Shearwater** is strongly underconfident. Mean forecast 11.9% against an event rate of 24.8%; ECE 0.129, slope 1.52. Observed frequency exceeds the stated probability, so forecasts are too low.
- **European Storm-petrel** is mildly underconfident. Mean forecast 15.3% against an event rate of 20.8%; ECE 0.055, slope 1.22. Observed frequency exceeds the stated probability, so forecasts are too low.
- **Sooty Shearwater** is strongly overconfident (uncertain). Mean forecast 7.5% against an event rate of 0.8%; ECE 0.067, slope 0.11. Stated probabilities exceed the observed frequency, so forecasts are too high. Only 33 event days: treat as uncertain.
- **Great Shearwater** is strongly overconfident (uncertain). Mean forecast 0.7% against an event rate of 0.4%; ECE 0.003, slope 0.50. Stated probabilities exceed the observed frequency, so forecasts are too high. Only 15 event days: treat as uncertain.

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

## Does a stated X% mean an X% chance?

Observed event frequency among forecasts within +/-5% of X (`n/a` where fewer than 20 forecasts exist).

| Species | Forecast ~20% | Forecast ~50% | Forecast ~80% |
|---|---:|---:|---:|
| Northern Fulmar | 45.2% (n=939) | n/a (n=5) | n/a (n=0) |
| Manx Shearwater | 47.5% (n=571) | 65.0% (n=117) | n/a (n=3) |
| European Storm-petrel | 29.2% (n=435) | 60.2% (n=251) | n/a (n=5) |
| Sooty Shearwater | 1.2% (n=433) | 5.4% (n=37) | n/a (n=0) |
| Great Shearwater | n/a (n=1) | n/a (n=0) | n/a (n=0) |

**No: for none of the five species can a stated X% be read as an X%
chance of an influx event.** The probabilities rank days usefully for the
three common species but their absolute level is off, and it differs by
species:

- Trustworthy as probabilities: none.
- Need calibration, underconfident (true chance higher than stated): Northern Fulmar, Manx Shearwater, European Storm-petrel.
- Need calibration, overconfident (true chance lower than stated): none.
- Uncertain (<50 events): Sooty Shearwater, Great Shearwater.

European Storm-petrel is the closest to usable (mildly underconfident);
Manx Shearwater and Northern Fulmar are strongly underconfident, and
Northern Fulmar also lacks skill. Sooty Shearwater is strongly
overconfident. Any use of the numbers as percentage chances would need a
separate out-of-sample recalibration, which this analysis did not perform.

## Is the 0.20 threshold reasonable?

Diagnostic only: the threshold was not changed. F1 at each cutoff:

| Species | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 | 0.40 | 0.50 | Best cutoff |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Northern Fulmar | 0.538 | 0.490 | 0.370 | 0.233 | 0.112 | 0.012 | 0.002 | 0.10 |
| Manx Shearwater | 0.652 | 0.633 | 0.594 | 0.537 | 0.459 | 0.300 | 0.137 | 0.10 |
| European Storm-petrel | 0.592 | 0.612 | 0.624 | 0.618 | 0.596 | 0.493 | 0.367 | 0.20 |
| Sooty Shearwater | 0.040 | 0.044 | 0.061 | 0.069 | 0.086 | 0.106 | 0.075 | 0.40 |
| Great Shearwater | 0.067 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.10 |

- Within 0.02 F1 of the best cutoff at 0.20: European Storm-petrel (best 0.20, F1 gain +0.000).
- Clearly better at a different cutoff: Northern Fulmar (best 0.10, F1 gain +0.169), Manx Shearwater (best 0.10, F1 gain +0.057).
- Rare-event species (Sooty, Great Shearwater) have too few events for a
  reliable cutoff choice; F1 stays very low at every cutoff.
- Because probabilities are systematically low or high rather than
  calibrated, 0.20 is best read as an alert level tuned to F1, not as a
  20% event chance.

Figures per species: `calibration_reliability_<species>.png` (with forecast
counts per bin) and `calibration_histogram_<species>.png` (event versus
non-event days).
