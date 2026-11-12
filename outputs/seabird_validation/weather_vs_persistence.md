# Weather vs persistence audit

A = stored rolling weather forecast. B = yesterday-event baseline: probability that an event follows an event (or a non-event), estimated from training years only, refit each January. Same labels, dates (2015-01-01 to 2026-08-11) and 0.20 cutoff.

## 1. Confusion matrices and scores

| Species | Model | TP | FP | FN | TN | Precision | Recall | F1 | Brier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Northern Fulmar | A weather | 351 | 439 | 757 | 2694 | 0.444 | 0.317 | 0.370 | 0.1969 |
| Northern Fulmar | B persistence | 833 | 275 | 275 | 2858 | 0.752 | 0.752 | 0.752 | 0.1173 |
| Manx Shearwater | A weather | 632 | 445 | 418 | 2746 | 0.587 | 0.602 | 0.594 | 0.1559 |
| Manx Shearwater | B persistence | 767 | 283 | 283 | 2908 | 0.730 | 0.730 | 0.730 | 0.1179 |
| European Storm-petrel | A weather | 689 | 637 | 194 | 2721 | 0.520 | 0.780 | 0.624 | 0.1173 |
| European Storm-petrel | B persistence | 550 | 333 | 333 | 3025 | 0.623 | 0.623 | 0.623 | 0.1217 |
| Sooty Shearwater | A weather | 17 | 506 | 16 | 3702 | 0.033 | 0.515 | 0.061 | 0.0208 |
| Sooty Shearwater | B persistence | 10 | 23 | 23 | 4185 | 0.303 | 0.303 | 0.303 | 0.0088 |
| Great Shearwater | A weather | 0 | 1 | 15 | 4225 | 0.000 | 0.000 | 0.000 | 0.0036 |
| Great Shearwater | B persistence | 6 | 9 | 9 | 4217 | 0.400 | 0.400 | 0.400 | 0.0030 |

## 2. Who finds which events

| Species | Events | Both | Weather only | Persistence only | Neither | Weather false alarms | Persistence false alarms | In both |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Northern Fulmar | 1108 | 286 | 65 | 547 | 210 | 439 | 275 | 50 |
| Manx Shearwater | 1050 | 500 | 132 | 267 | 151 | 445 | 283 | 133 |
| European Storm-petrel | 883 | 478 | 211 | 72 | 122 | 637 | 333 | 200 |
| Sooty Shearwater | 33 | 5 | 12 | 5 | 11 | 506 | 23 | 13 |
| Great Shearwater | 15 | 0 | 0 | 6 | 9 | 1 | 9 | 0 |

## 3. Seasonal differences (F1 / Brier)

| Species | Season | Events | A F1 | B F1 | A Brier | B Brier |
|---|---|---:|---:|---:|---:|---:|
| Northern Fulmar | Winter | 55 | 0.117 | 0.234 | 0.0518 | 0.0531 |
| Northern Fulmar | Spring | 361 | 0.377 | 0.794 | 0.2471 | 0.1344 |
| Northern Fulmar | Summer | 552 | 0.416 | 0.819 | 0.3673 | 0.1890 |
| Northern Fulmar | Autumn | 140 | 0.303 | 0.585 | 0.1097 | 0.0882 |
| Manx Shearwater | Winter | 1 | 0.000 | 0.000 | 0.0010 | 0.0046 |
| Manx Shearwater | Spring | 160 | 0.174 | 0.513 | 0.1224 | 0.1006 |
| Manx Shearwater | Summer | 644 | 0.646 | 0.796 | 0.3521 | 0.2396 |
| Manx Shearwater | Autumn | 245 | 0.623 | 0.703 | 0.1431 | 0.1245 |
| European Storm-petrel | Winter | 7 | 0.000 | 0.000 | 0.0073 | 0.0136 |
| European Storm-petrel | Spring | 71 | 0.243 | 0.304 | 0.0549 | 0.0592 |
| European Storm-petrel | Summer | 575 | 0.696 | 0.718 | 0.2550 | 0.2576 |
| European Storm-petrel | Autumn | 230 | 0.544 | 0.502 | 0.1528 | 0.1571 |
| Sooty Shearwater | Winter | 1 | 0.000 | 0.000 | 0.0028 | 0.0033 |
| Sooty Shearwater | Spring | 0 | 0.000 | 0.000 | 0.0007 | 0.0019 |
| Sooty Shearwater | Summer | 4 | 0.000 | 0.250 | 0.0152 | 0.0053 |
| Sooty Shearwater | Autumn | 28 | 0.075 | 0.327 | 0.0679 | 0.0260 |
| Great Shearwater | Winter | 0 | 0.000 | 0.000 | 0.0002 | 0.0000 |
| Great Shearwater | Spring | 0 | 0.000 | 0.000 | 0.0001 | 0.0000 |
| Great Shearwater | Summer | 0 | 0.000 | 0.000 | 0.0001 | 0.0000 |
| Great Shearwater | Autumn | 15 | 0.000 | 0.400 | 0.0149 | 0.0126 |

## 4. Multi-day event clustering (recall by event-run length)

| Species | Run type | Event days | A recall | B recall |
|---|---|---:|---:|---:|
| Northern Fulmar | isolated event (run of 1) | 142 | 0.225 | 0.000 |
| Northern Fulmar | short run (2-3 days) | 181 | 0.210 | 0.591 |
| Northern Fulmar | long run (4+ days) | 785 | 0.358 | 0.925 |
| Manx Shearwater | isolated event (run of 1) | 130 | 0.362 | 0.000 |
| Manx Shearwater | short run (2-3 days) | 209 | 0.507 | 0.589 |
| Manx Shearwater | long run (4+ days) | 711 | 0.674 | 0.906 |
| European Storm-petrel | isolated event (run of 1) | 195 | 0.564 | 0.000 |
| European Storm-petrel | short run (2-3 days) | 193 | 0.637 | 0.580 |
| European Storm-petrel | long run (4+ days) | 495 | 0.921 | 0.885 |
| Sooty Shearwater | isolated event (run of 1) | 15 | 0.533 | 0.000 |
| Sooty Shearwater | short run (2-3 days) | 18 | 0.500 | 0.556 |
| Great Shearwater | isolated event (run of 1) | 4 | 0.000 | 0.000 |
| Great Shearwater | short run (2-3 days) | 11 | 0.000 | 0.545 |

## 5. Starts of influxes (events after a non-event day)

| Species | Onset days | Found by weather | Found by persistence | Weather AUC after non-event | Weather AUC after event |
|---|---:|---:|---:|---:|---:|
| Northern Fulmar | 275 | 65 | 0 | 0.66 | 0.65 |
| Manx Shearwater | 283 | 132 | 0 | 0.85 | 0.62 |
| European Storm-petrel | 333 | 211 | 0 | 0.85 | 0.71 |
| Sooty Shearwater | 23 | 12 | 0 | 0.81 | 0.47 |
| Great Shearwater | 9 | 0 | 0 | 0.82 | 0.24 |

Within-season AUC of the weather model on days after a non-event (seasons with at least 10 events):

| Species | Season | Events | Weather AUC |
|---|---|---:|---:|
| Northern Fulmar | Spring | 77 | 0.60 |
| Northern Fulmar | Summer | 99 | 0.41 |
| Northern Fulmar | Autumn | 57 | 0.74 |
| Northern Fulmar | Winter | 42 | 0.64 |
| Manx Shearwater | Spring | 79 | 0.76 |
| Manx Shearwater | Summer | 133 | 0.48 |
| Manx Shearwater | Autumn | 70 | 0.85 |
| European Storm-petrel | Spring | 50 | 0.82 |
| European Storm-petrel | Summer | 163 | 0.53 |
| European Storm-petrel | Autumn | 113 | 0.76 |
| Sooty Shearwater | Autumn | 19 | 0.61 |

## Verdict by species

- **Northern Fulmar:** persistence beats weather; weather AUC 0.66 on days after a non-event, 0.57 within season (little skill beyond seasonality); finds 65/275 onsets.
- **Manx Shearwater:** persistence beats weather; weather AUC 0.85 on days after a non-event, 0.65 within season (independent skill beyond seasonality); finds 132/283 onsets.
- **European Storm-petrel:** weather beats persistence; weather AUC 0.85 on days after a non-event, 0.65 within season (independent skill beyond seasonality); finds 211/333 onsets.
- **Sooty Shearwater:** Too few event days to judge.
- **Great Shearwater:** Too few event days to judge.

## Reading the results

- Summer holds most event days, and there the weather model's within-season AUC after a non-event is Northern Fulmar 0.41, Manx Shearwater 0.48, European Storm-petrel 0.53. Its extra skill comes from spring and autumn, not the main season.
- Weather-only finds are events that persistence cannot flag, which are overwhelmingly onsets. Persistence-only finds are continuation days where weather probability stays below 0.20.
- Within days that follow a non-event, weather ranks event days above quiet days with AUC Northern Fulmar 0.66, Manx Shearwater 0.85, European Storm-petrel 0.85 overall, and Northern Fulmar 0.57, Manx Shearwater 0.65, European Storm-petrel 0.65 within season (0.50 = no skill).
- Onsets found by weather: Northern Fulmar 65/275; Manx Shearwater 132/283; European Storm-petrel 211/333.

## Caveats

- Persistence at a 0.20 cutoff flags every day after an event (the training chance of another event is well above 0.20) and almost never anything else, so it cannot find a new onset by construction.
- Sooty and Great Shearwater have fewer than 50 event days; treat them as uncertain.
- The weather model also receives calendar inputs, so whole-period AUC after a non-event partly reflects the seasonal cycle. The within-season AUC removes that.
- AUC is rank-based and ignores the cutoff; it measures whether weather ranks event days above quiet days within a persistence state.
