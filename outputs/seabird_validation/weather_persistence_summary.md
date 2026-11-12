# Weather + persistence model comparison

Same strict-cutoff, annual expanding-window, one-day-ahead validation as the rolling event validation (2015-01-01 to 2026-08-11), same aligned influx-event labels, same 0.20 probability threshold. Raw probabilities are scored.

- **Weather:** the stored production-model forecasts (`rolling_event_predictions.csv`).
- **Persistence:** P(event | yesterday's status) from training days only, refit each January.
- **Weather + Persistence:** the same Random Forest and weather/calendar predictors, plus yesterday-event, 3-day event count and 7-day event count. Persistence inputs cover days strictly before the target, use the cutoff's event threshold, and training rows end at the cutoff.

## Overall

| Species | Events | Model | Precision | Recall | F1 | Brier | AUC | ECE |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Northern Fulmar | 1108 | Weather | 0.444 | 0.317 | 0.370 | 0.197 | 0.733 | 0.147 |
| Northern Fulmar | 1108 | Persistence | 0.752 | 0.752 | 0.752 | 0.117 | 0.870 | 0.077 |
| Northern Fulmar | 1108 | Weather + Persistence | 0.682 | 0.814 | 0.742 | 0.112 | 0.912 | 0.076 |
| Manx Shearwater | 1050 | Weather | 0.587 | 0.602 | 0.594 | 0.156 | 0.863 | 0.129 |
| Manx Shearwater | 1050 | Persistence | 0.730 | 0.730 | 0.730 | 0.118 | 0.852 | 0.071 |
| Manx Shearwater | 1050 | Weather + Persistence | 0.681 | 0.852 | 0.757 | 0.107 | 0.933 | 0.085 |
| European Storm-petrel | 883 | Weather | 0.520 | 0.780 | 0.624 | 0.117 | 0.875 | 0.055 |
| European Storm-petrel | 883 | Persistence | 0.623 | 0.623 | 0.623 | 0.122 | 0.792 | 0.040 |
| European Storm-petrel | 883 | Weather + Persistence | 0.536 | 0.837 | 0.653 | 0.104 | 0.902 | 0.044 |
| Sooty Shearwater | 33 | Weather | 0.033 | 0.515 | 0.061 | 0.021 | 0.814 | 0.067 |
| Sooty Shearwater | 33 | Persistence | 0.303 | 0.303 | 0.303 | 0.009 | 0.800 | 0.037 |
| Sooty Shearwater | 33 | Weather + Persistence | 0.059 | 0.455 | 0.105 | 0.013 | 0.867 | 0.044 |
| Great Shearwater | 15 | Weather | 0.000 | 0.000 | 0.000 | 0.004 | 0.733 | 0.003 |
| Great Shearwater | 15 | Persistence | 0.400 | 0.400 | 0.400 | 0.003 | 0.715 | 0.002 |
| Great Shearwater | 15 | Weather + Persistence | 0.333 | 0.067 | 0.111 | 0.003 | 0.805 | 0.003 |

## Verdict per species

- **Northern Fulmar:** Combined has the best Brier (+0.005) but not the best F1 (-0.009); Persistence leads F1
- **Manx Shearwater:** Combined is best on F1 and Brier (F1 +0.027, Brier +0.011 vs the better single model)
- **European Storm-petrel:** Combined is best on F1 and Brier (F1 +0.029, Brier +0.013 vs the better single model)
- **Sooty Shearwater:** Combined does not beat the best single model (F1 -0.198, Brier -0.004); Persistence leads F1 (uncertain: fewer than 50 event days)
- **Great Shearwater:** Combined does not beat the best single model (F1 -0.289, Brier -0.000); Persistence leads F1 (uncertain: fewer than 50 event days)

## F1 by season

| Species | Season | Events | Weather | Persistence | Weather + Persistence |
|---|---|---:|---:|---:|---:|
| Northern Fulmar | Spring | 361 | 0.377 | 0.794 | 0.779 |
| Northern Fulmar | Summer | 552 | 0.416 | 0.819 | 0.818 |
| Northern Fulmar | Autumn | 140 | 0.303 | 0.585 | 0.585 |
| Northern Fulmar | Winter | 55 | 0.117 | 0.234 | 0.210 |
| Manx Shearwater | Spring | 160 | 0.174 | 0.513 | 0.517 |
| Manx Shearwater | Summer | 644 | 0.646 | 0.796 | 0.817 |
| Manx Shearwater | Autumn | 245 | 0.623 | 0.703 | 0.731 |
| Manx Shearwater | Winter | 1 | 0.000 | 0.000 | 0.000 |
| European Storm-petrel | Spring | 71 | 0.243 | 0.304 | 0.344 |
| European Storm-petrel | Summer | 575 | 0.696 | 0.718 | 0.725 |
| European Storm-petrel | Autumn | 230 | 0.544 | 0.502 | 0.567 |
| European Storm-petrel | Winter | 7 | 0.000 | 0.000 | 0.000 |
| Sooty Shearwater | Spring | 0 | 0.000 | 0.000 | 0.000 |
| Sooty Shearwater | Summer | 4 | 0.000 | 0.250 | 0.000 |
| Sooty Shearwater | Autumn | 28 | 0.075 | 0.327 | 0.127 |
| Sooty Shearwater | Winter | 1 | 0.000 | 0.000 | 0.000 |
| Great Shearwater | Spring | 0 | 0.000 | 0.000 | 0.000 |
| Great Shearwater | Summer | 0 | 0.000 | 0.000 | 0.000 |
| Great Shearwater | Autumn | 15 | 0.000 | 0.400 | 0.111 |
| Great Shearwater | Winter | 0 | 0.000 | 0.000 | 0.000 |

## Reading

- Northern Fulmar: F1 weather 0.370, persistence 0.752, combined 0.742; Brier 0.197 / 0.117 / 0.112.
- Manx Shearwater: F1 weather 0.594, persistence 0.730, combined 0.757; Brier 0.156 / 0.118 / 0.107.
- European Storm-petrel: F1 weather 0.624, persistence 0.623, combined 0.653; Brier 0.117 / 0.122 / 0.104.
- The combined model has the best F1 for 2 of the 3 species with enough events (Manx Shearwater, European Storm-petrel).

Sooty Shearwater (33 event days) and Great Shearwater (15) are flagged uncertain; their differences are not reliable.
