# Rolling seabird influx-event validation

## Method

Annual expanding-window models are trained through December 31 before each
evaluation year, using the existing strict-cutoff one-day-lead model and
training-only P90 occurrence-count threshold (minimum one record). Each
day's prediction uses the preceding day's historical observed weather;
model parameters and the event threshold remain frozen for that year.
This is a hindcast with observed-weather proxy inputs, not archived
operational forecast replay. The probability decision cutoff is 0.20.

The existing five-calendar-year convention counts partial calendar years,
so it does not necessarily require five full years of training data.
Evaluated dates are 2015-01-01 through 2026-08-11.
The last evaluation year is partial. The last evaluated date is bounded
by the earlier of one day after the last available weather date and the
last date in the observation file; a last record date does not prove
complete reporting through that date.

The observations are GBIF occurrence-record counts, summed across
countries. No qualifying record is treated as zero, not proven absence.
Archive completeness and reporting effort may vary over time and by
species. Training uses the historical occurrence cache and evaluation
uses the derived observations file; this is temporal holdout, not an
independent data source. Thresholds, and hence event definitions, can
change between annual folds.

## Overall results

| Species | Days | Event days | Prevalence | Precision | Recall | F1 | Brier | Training-prevalence baseline Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| European Storm-petrel | 4241 | 883 | 0.208 | 0.520 | 0.780 | 0.624 | 0.11734 | 0.16868 |
| Northern Fulmar | 4241 | 1108 | 0.261 | 0.444 | 0.317 | 0.370 | 0.19694 | 0.21814 |
| Sooty Shearwater | 4241 | 33 | 0.008 | 0.033 | 0.515 | 0.061 | 0.02076 | 0.01198 |
| Manx Shearwater | 4241 | 1050 | 0.248 | 0.587 | 0.602 | 0.594 | 0.15588 | 0.20542 |
| Great Shearwater | 4241 | 15 | 0.004 | 0.000 | 0.000 | 0.000 | 0.00360 | 0.00353 |

## Interpretation

- Lower Brier than the annual training-prevalence baseline: European Storm-petrel, Northern Fulmar, Manx Shearwater.
- Not lower than that baseline: Sooty Shearwater, Great Shearwater.
- F1 ranges from 0.000 to 0.624
  at the common 0.20 probability cutoff. The differing scores suggest
  performance varies by species rather than being uniformly poor.
- This comparison alone cannot isolate model weakness from probability
  calibration or the decision threshold. In particular, rare-event
  precision and F1 depend heavily on event prevalence.

Overall precision, recall and F1 use pooled daily confusion counts,
not an average of yearly scores. Brier is the mean squared error of
daily event probabilities. The baseline uses each year's training
event prevalence as a constant probability on that year's holdout
days. A lower Brier score is better. Undefined precision or recall
is reported as zero, matching the existing validation convention.

The CSV includes yearly folds and pooled `all` rows, confusion counts,
date coverage and training event-count threshold ranges. Comparing
F1 between species without considering prevalence can mislead;
rare events and incomplete records make sparse-species estimates
especially uncertain. These results measure the 0.20 operating point,
not performance at every possible probability threshold.
