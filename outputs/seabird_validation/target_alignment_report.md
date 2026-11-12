# Seabird training and validation target alignment

## Conclusion

The five models are trained as **daily influx-event classifiers**: their
positive class is a daily species-specific occurrence-record count at or above
the 90th percentile of training daily counts, with a minimum threshold of one
record. For Sooty Shearwater and Great Shearwater, that minimum is one, so
their daily positive class is equivalent to recorded daily presence. For the
other three species, presence alone is not enough.

The **Backtest** and the threshold analysis score *presence at any time in a
14-day window*, not the daily influx-event target. Therefore their reported
precision, recall and F1 do not measure the trained target. The separate
**Strict Cutoff Validation** page scores daily counts against the
corresponding lead's training-derived influx threshold and is aligned with
the modeled event definition.

## Species-specific thresholds and target alignment

Counts are GBIF occurrence **records**, pooled across the configured five
countries, not individual birds. “Backtest actual” means at least one
positive-count observation for the species anywhere in the 14-day window.
The 0.20 probability cutoff is a classification decision threshold and is
distinct from the occurrence-count thresholds below.

| Species | Training target and positive class | 2024-10-15 backtest threshold (records/day) | Stored production model threshold (records/day) | Backtest actual | Aligned? |
|---|---|---:|---:|---|---|
| Northern Fulmar | Daily count >= training P90, minimum 1 | 47 | 44 | Recorded presence in window | No: 1–46 daily records are non-events in the backtest model; window vs day also differs. |
| Manx Shearwater | Daily count >= training P90, minimum 1 | 18 | 17 | Recorded presence in window | No: 1–17 daily records are non-events in the backtest model; window vs day also differs. |
| European Storm-petrel | Daily count >= training P90, minimum 1 | 3 | 3 | Recorded presence in window | No: 1–2 daily records are non-events; window vs day also differs. |
| Sooty Shearwater | Daily count >= training P90, minimum 1 | 1 | 1 | Recorded presence in window | Partly: daily event equals daily recorded presence, but the Backtest scores window-level presence rather than each daily event. |
| Great Shearwater | Daily count >= training P90, minimum 1 | 1 | 1 | Recorded presence in window | Partly: daily event equals daily recorded presence, but the Backtest scores window-level presence rather than each daily event. |

The backtest values are from a rebuilt strict-cutoff forecast for analysis date
2024-10-15; each of its 14 lead-specific models has the listed threshold.
Thresholds are recalculated from each lead's eligible training rows, and can
change with the cutoff date or lead. Production values are metadata read from
the locally stored species model artifacts; those artifacts report one-day
training targets from 2010-10-02 through 2026-08-10. They are **not** the
historical cutoff models and should not be substituted for their thresholds.

## What each evaluation actually measures

- **Backtest / threshold analysis:** for each species, the maximum daily
  probability in the window is compared with the selected probability cutoff;
  that predicted flag is compared with whether the species was recorded on
  any day in the window. Precision, recall and F1 are calculated across the
  five species. A peak forecast and an observation can occur on different
  days. The hit-rate calculation is daily, but also uses recorded presence
  rather than the event-count threshold. See
  [`match_species` and `calculate_metrics`](../../src/seabird_observation_validation.py)
  and [`analyze_thresholds`](../../src/seabird_threshold_analysis.py).
- **Strict Cutoff Validation:** a product/date is an observed positive when
  its daily occurrence-record count is at least that forecast row's
  `event_threshold_count`; a predicted positive is a daily forecast
  probability >= 0.20. Counts are obtained from the occurrence cache and
  missing species/date combinations are represented as zero. See
  [`load_validation_observations` and `calculate_validation_metrics`](../../src/seabird_validation.py).
  This is aligned with the per-lead model label, subject to incomplete
  observation coverage.
- **Stored production-model forward-chaining evaluation:** each fold
  computes P90 on its own training counts and applies that same count cutoff
  to its held-out daily counts. Thus it also targets the daily influx label,
  rather than window-level presence. See
  [`_evaluate_forward_chaining`](../../src/train_atlantic_vagrancy_model.py).

## Example: 2024-10-16 through 2024-10-29

Aggregating the country rows in
[`observations.csv`](../../validation/seabirds/observations.csv) by species
and day gives the following against the 2024-10-15 lead-specific thresholds:

| Species | Recorded in window? | Highest daily record count | Days meeting daily event threshold |
|---|---|---:|---:|
| Northern Fulmar | Yes | 7 | 0 |
| Manx Shearwater | Yes | 18 | 1 |
| European Storm-petrel | Yes | 4 | 2 |
| Sooty Shearwater | No | 0 | 0 |
| Great Shearwater | No | 0 | 0 |

At the 0.20 forecast-probability cutoff, the rebuilt forecast flagged one
Sooty Shearwater day and no other species-days. Against the daily
influx-event labels above, that is **0 true positives, 1 false positive and 3
false negatives**. This is a different evaluation unit and outcome from the
window-level species-presence threshold audit.

## Evidence and limitations

1. [`train_species_model`](../../src/train_seabird_species_models.py) merges
   daily counts with weather, fills missing counts with zero, computes P90 on
   supervised training targets, and labels counts `>=` that cutoff.
   [`influx_cutoff`](../../src/train_atlantic_vagrancy_model.py) floors the
   threshold at one. The historical
   [`_fit_cutoff_model`](../../src/seabird_validation.py) applies the same
   rule separately for each lead using pre-cutoff data.
2. [`build_seabird_observations`](../../src/build_seabird_observations.py)
   aggregates the same occurrence cache by date, species and country; its
   `count` is the number of records. The training counts pool countries.
   Zero records mean **no qualifying record in the cache**, not proof of
   biological absence, and reporting effort and archive completeness can
   vary.
3. Great Shearwater's stored artifact has only 25 positive training days; its
   [production evaluation](../seabird_species_evaluation.csv) marks the
   data insufficient for meaningful prediction. A threshold of one for
   sparse species is a consequence of the floor, not evidence that a
   single record constitutes a biological influx.
4. The 2024 example is one holdout window. The mismatch prevents interpreting
   the Backtest presence metrics as model influx skill; it does not, by
   itself, establish whether the model is strong or weak. Assess skill using
   daily event-aligned labels over multiple later cutoff windows, retaining
   each forecast lead's own threshold and checking observation coverage.
