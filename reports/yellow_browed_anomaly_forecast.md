# Yellow-browed Warbler Anomaly Forecasting

## Anomaly definition

Expected count is a smoothed, prior-calendar-year day-of-year climatology: observed counts from dates within ±7 calendar days are pooled, with 30 prior-equivalent observations at the prior-year overall daily mean. The current calendar year is excluded from its own expectation. Anomaly is observed count minus expected count; anomaly ratio is observed count divided by expected count. Thus ratio 2 means twice expected, not 200% above expected. Dates without prior-year history have undefined expected counts and are excluded.

The output anomaly table covers 2010-10-01 to 2026-08-10 and 5,701 dates with a valid forward-only expected count.

| Anomaly label | Positive dates | Prevalence |
|---|---:|---:|
| anomaly ratio >= 2 | 293 | 5.14% |
| anomaly ratio >= 4 | 132 | 2.32% |
| anomaly ratio >= 8 | 49 | 0.86% |

## Evaluation design

Evaluation follows the existing species comparison: expanding calendar-year forward chaining, the first five usable calendar years as initial history, 1/3/5/7/14-day horizons, and the same Logistic Regression, Random Forest, and XGBoost configurations. Labels use the forward-only expected-count series; target-date calendar features are known in advance, and weather features are shifted to weather available through the day before the forecast origin. Metrics pool held-out annual predictions. Precision, recall, and F1 use a 0.5 probability threshold; PR-AUC is average precision.

## Pooled results

### Anomaly ratio >= 2

| Horizon | Feature set | Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Test prevalence | Test positives |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 d | Seasonality + weather | Logistic Regression | 0.1096 | 0.6700 | 0.0997 | 0.6123 | 0.1715 | 0.0537 | 227 |
| 1 d | Seasonality + weather | Random Forest | 0.1425 | 0.7064 | 0.2292 | 0.0969 | 0.1362 | 0.0537 | 227 |
| 1 d | Seasonality + weather | XGBoost | 0.1685 | 0.7076 | 0.1545 | 0.4670 | 0.2322 | 0.0537 | 227 |
| 1 d | Seasonality only | Logistic Regression | 0.1576 | 0.7039 | 0.1024 | 0.7445 | 0.1801 | 0.0537 | 227 |
| 1 d | Seasonality only | Random Forest | 0.1249 | 0.6668 | 0.1547 | 0.4097 | 0.2246 | 0.0537 | 227 |
| 1 d | Seasonality only | XGBoost | 0.1701 | 0.7085 | 0.1492 | 0.4890 | 0.2286 | 0.0537 | 227 |
| 1 d | Weather only | Logistic Regression | 0.0647 | 0.5501 | 0.0676 | 0.4581 | 0.1178 | 0.0537 | 227 |
| 1 d | Weather only | Random Forest | 0.1022 | 0.6071 | 0.2500 | 0.0088 | 0.0170 | 0.0537 | 227 |
| 1 d | Weather only | XGBoost | 0.1000 | 0.6170 | 0.0991 | 0.4626 | 0.1632 | 0.0537 | 227 |
| 3 d | Seasonality + weather | Logistic Regression | 0.1069 | 0.6679 | 0.0969 | 0.6035 | 0.1670 | 0.0537 | 227 |
| 3 d | Seasonality + weather | Random Forest | 0.1337 | 0.7049 | 0.1758 | 0.0705 | 0.1006 | 0.0537 | 227 |
| 3 d | Seasonality + weather | XGBoost | 0.1566 | 0.7055 | 0.1522 | 0.4626 | 0.2290 | 0.0537 | 227 |
| 3 d | Seasonality only | Logistic Regression | 0.1558 | 0.7000 | 0.1013 | 0.7357 | 0.1781 | 0.0537 | 227 |
| 3 d | Seasonality only | Random Forest | 0.1242 | 0.6645 | 0.1533 | 0.4053 | 0.2225 | 0.0537 | 227 |
| 3 d | Seasonality only | XGBoost | 0.1692 | 0.7031 | 0.1482 | 0.4846 | 0.2270 | 0.0537 | 227 |
| 3 d | Weather only | Logistic Regression | 0.0708 | 0.5751 | 0.0741 | 0.5154 | 0.1296 | 0.0537 | 227 |
| 3 d | Weather only | Random Forest | 0.0861 | 0.6018 | 0.0000 | 0.0000 | 0.0000 | 0.0537 | 227 |
| 3 d | Weather only | XGBoost | 0.0955 | 0.6166 | 0.0893 | 0.4317 | 0.1480 | 0.0537 | 227 |
| 5 d | Seasonality + weather | Logistic Regression | 0.1069 | 0.6586 | 0.0910 | 0.5463 | 0.1560 | 0.0537 | 227 |
| 5 d | Seasonality + weather | Random Forest | 0.1388 | 0.7311 | 0.1758 | 0.0705 | 0.1006 | 0.0537 | 227 |
| 5 d | Seasonality + weather | XGBoost | 0.1520 | 0.7097 | 0.1591 | 0.4802 | 0.2390 | 0.0537 | 227 |
| 5 d | Seasonality only | Logistic Regression | 0.1544 | 0.6974 | 0.1009 | 0.7313 | 0.1773 | 0.0537 | 227 |
| 5 d | Seasonality only | Random Forest | 0.1234 | 0.6606 | 0.1536 | 0.4053 | 0.2228 | 0.0537 | 227 |
| 5 d | Seasonality only | XGBoost | 0.1683 | 0.6979 | 0.1486 | 0.4846 | 0.2275 | 0.0537 | 227 |
| 5 d | Weather only | Logistic Regression | 0.0693 | 0.5627 | 0.0690 | 0.4758 | 0.1205 | 0.0537 | 227 |
| 5 d | Weather only | Random Forest | 0.0787 | 0.5865 | 0.0000 | 0.0000 | 0.0000 | 0.0537 | 227 |
| 5 d | Weather only | XGBoost | 0.0872 | 0.6003 | 0.0883 | 0.4185 | 0.1458 | 0.0537 | 227 |
| 7 d | Seasonality + weather | Logistic Regression | 0.1011 | 0.6553 | 0.0923 | 0.5815 | 0.1593 | 0.0537 | 227 |
| 7 d | Seasonality + weather | Random Forest | 0.1425 | 0.7069 | 0.2020 | 0.0881 | 0.1227 | 0.0537 | 227 |
| 7 d | Seasonality + weather | XGBoost | 0.1597 | 0.6970 | 0.1624 | 0.4802 | 0.2428 | 0.0537 | 227 |
| 7 d | Seasonality only | Logistic Regression | 0.1538 | 0.6955 | 0.1004 | 0.7269 | 0.1764 | 0.0537 | 227 |
| 7 d | Seasonality only | Random Forest | 0.1230 | 0.6585 | 0.1538 | 0.4053 | 0.2230 | 0.0537 | 227 |
| 7 d | Seasonality only | XGBoost | 0.1678 | 0.6946 | 0.1491 | 0.4846 | 0.2280 | 0.0537 | 227 |
| 7 d | Weather only | Logistic Regression | 0.0640 | 0.5406 | 0.0655 | 0.4626 | 0.1148 | 0.0537 | 227 |
| 7 d | Weather only | Random Forest | 0.0868 | 0.5642 | 0.5000 | 0.0044 | 0.0087 | 0.0537 | 227 |
| 7 d | Weather only | XGBoost | 0.1023 | 0.5879 | 0.0997 | 0.3965 | 0.1593 | 0.0537 | 227 |
| 14 d | Seasonality + weather | Logistic Regression | 0.1128 | 0.6513 | 0.0962 | 0.5859 | 0.1653 | 0.0537 | 227 |
| 14 d | Seasonality + weather | Random Forest | 0.1516 | 0.7093 | 0.2202 | 0.1057 | 0.1429 | 0.0537 | 227 |
| 14 d | Seasonality + weather | XGBoost | 0.1644 | 0.6986 | 0.1711 | 0.4846 | 0.2529 | 0.0537 | 227 |
| 14 d | Seasonality only | Logistic Regression | 0.1539 | 0.6958 | 0.1008 | 0.7269 | 0.1770 | 0.0537 | 227 |
| 14 d | Seasonality only | Random Forest | 0.1230 | 0.6589 | 0.1541 | 0.4053 | 0.2233 | 0.0537 | 227 |
| 14 d | Seasonality only | XGBoost | 0.1679 | 0.6949 | 0.1499 | 0.4846 | 0.2289 | 0.0537 | 227 |
| 14 d | Weather only | Logistic Regression | 0.0790 | 0.5536 | 0.0688 | 0.4537 | 0.1194 | 0.0537 | 227 |
| 14 d | Weather only | Random Forest | 0.0890 | 0.5590 | 0.0000 | 0.0000 | 0.0000 | 0.0537 | 227 |
| 14 d | Weather only | XGBoost | 0.0881 | 0.5457 | 0.0767 | 0.3084 | 0.1228 | 0.0537 | 227 |

### Anomaly ratio >= 4

| Horizon | Feature set | Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Test prevalence | Test positives |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 d | Seasonality + weather | Logistic Regression | 0.0383 | 0.6094 | 0.0340 | 0.3922 | 0.0625 | 0.0241 | 102 |
| 1 d | Seasonality + weather | Random Forest | 0.0511 | 0.6501 | 0.1000 | 0.0098 | 0.0179 | 0.0241 | 102 |
| 1 d | Seasonality + weather | XGBoost | 0.0439 | 0.6597 | 0.0558 | 0.2549 | 0.0915 | 0.0241 | 102 |
| 1 d | Seasonality only | Logistic Regression | 0.0696 | 0.6727 | 0.0413 | 0.6275 | 0.0775 | 0.0241 | 102 |
| 1 d | Seasonality only | Random Forest | 0.0366 | 0.5900 | 0.0501 | 0.2745 | 0.0847 | 0.0241 | 102 |
| 1 d | Seasonality only | XGBoost | 0.0606 | 0.6609 | 0.0509 | 0.3333 | 0.0883 | 0.0241 | 102 |
| 1 d | Weather only | Logistic Regression | 0.0257 | 0.4996 | 0.0260 | 0.3725 | 0.0485 | 0.0241 | 102 |
| 1 d | Weather only | Random Forest | 0.0410 | 0.6123 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 1 d | Weather only | XGBoost | 0.0389 | 0.6001 | 0.0438 | 0.2843 | 0.0759 | 0.0241 | 102 |
| 3 d | Seasonality + weather | Logistic Regression | 0.0415 | 0.5920 | 0.0323 | 0.3725 | 0.0595 | 0.0241 | 102 |
| 3 d | Seasonality + weather | Random Forest | 0.0433 | 0.6611 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 3 d | Seasonality + weather | XGBoost | 0.0462 | 0.6619 | 0.0575 | 0.2549 | 0.0939 | 0.0241 | 102 |
| 3 d | Seasonality only | Logistic Regression | 0.0654 | 0.6633 | 0.0401 | 0.6078 | 0.0752 | 0.0241 | 102 |
| 3 d | Seasonality only | Random Forest | 0.0360 | 0.5850 | 0.0485 | 0.2647 | 0.0819 | 0.0241 | 102 |
| 3 d | Seasonality only | XGBoost | 0.0596 | 0.6482 | 0.0495 | 0.3235 | 0.0859 | 0.0241 | 102 |
| 3 d | Weather only | Logistic Regression | 0.0269 | 0.5027 | 0.0247 | 0.3431 | 0.0461 | 0.0241 | 102 |
| 3 d | Weather only | Random Forest | 0.0317 | 0.5784 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 3 d | Weather only | XGBoost | 0.0344 | 0.6010 | 0.0313 | 0.1863 | 0.0536 | 0.0241 | 102 |
| 5 d | Seasonality + weather | Logistic Regression | 0.0416 | 0.6085 | 0.0348 | 0.4118 | 0.0642 | 0.0241 | 102 |
| 5 d | Seasonality + weather | Random Forest | 0.0534 | 0.6823 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 5 d | Seasonality + weather | XGBoost | 0.0464 | 0.6693 | 0.0497 | 0.2255 | 0.0814 | 0.0241 | 102 |
| 5 d | Seasonality only | Logistic Regression | 0.0649 | 0.6634 | 0.0401 | 0.6078 | 0.0752 | 0.0241 | 102 |
| 5 d | Seasonality only | Random Forest | 0.0360 | 0.5852 | 0.0486 | 0.2647 | 0.0821 | 0.0241 | 102 |
| 5 d | Seasonality only | XGBoost | 0.0596 | 0.6475 | 0.0497 | 0.3235 | 0.0862 | 0.0241 | 102 |
| 5 d | Weather only | Logistic Regression | 0.0281 | 0.5315 | 0.0275 | 0.3824 | 0.0512 | 0.0241 | 102 |
| 5 d | Weather only | Random Forest | 0.0331 | 0.5750 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 5 d | Weather only | XGBoost | 0.0393 | 0.6004 | 0.0400 | 0.2451 | 0.0688 | 0.0241 | 102 |
| 7 d | Seasonality + weather | Logistic Regression | 0.0334 | 0.6025 | 0.0339 | 0.3824 | 0.0623 | 0.0241 | 102 |
| 7 d | Seasonality + weather | Random Forest | 0.0631 | 0.6502 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 7 d | Seasonality + weather | XGBoost | 0.0522 | 0.6766 | 0.0637 | 0.2843 | 0.1041 | 0.0241 | 102 |
| 7 d | Seasonality only | Logistic Regression | 0.0650 | 0.6636 | 0.0402 | 0.6078 | 0.0753 | 0.0241 | 102 |
| 7 d | Seasonality only | Random Forest | 0.0360 | 0.5854 | 0.0486 | 0.2647 | 0.0822 | 0.0241 | 102 |
| 7 d | Seasonality only | XGBoost | 0.0596 | 0.6477 | 0.0498 | 0.3235 | 0.0864 | 0.0241 | 102 |
| 7 d | Weather only | Logistic Regression | 0.0251 | 0.4950 | 0.0194 | 0.2451 | 0.0359 | 0.0241 | 102 |
| 7 d | Weather only | Random Forest | 0.0280 | 0.5324 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 7 d | Weather only | XGBoost | 0.0327 | 0.5862 | 0.0398 | 0.2059 | 0.0667 | 0.0241 | 102 |
| 14 d | Seasonality + weather | Logistic Regression | 0.0491 | 0.6114 | 0.0430 | 0.4510 | 0.0786 | 0.0241 | 102 |
| 14 d | Seasonality + weather | Random Forest | 0.0623 | 0.6595 | 0.1250 | 0.0098 | 0.0182 | 0.0241 | 102 |
| 14 d | Seasonality + weather | XGBoost | 0.0657 | 0.6676 | 0.0525 | 0.2451 | 0.0865 | 0.0241 | 102 |
| 14 d | Seasonality only | Logistic Regression | 0.0652 | 0.6643 | 0.0403 | 0.6078 | 0.0757 | 0.0241 | 102 |
| 14 d | Seasonality only | Random Forest | 0.0360 | 0.5857 | 0.0488 | 0.2647 | 0.0824 | 0.0241 | 102 |
| 14 d | Seasonality only | XGBoost | 0.0597 | 0.6484 | 0.0502 | 0.3235 | 0.0870 | 0.0241 | 102 |
| 14 d | Weather only | Logistic Regression | 0.0331 | 0.5409 | 0.0303 | 0.3922 | 0.0562 | 0.0241 | 102 |
| 14 d | Weather only | Random Forest | 0.0329 | 0.5316 | 0.0000 | 0.0000 | 0.0000 | 0.0241 | 102 |
| 14 d | Weather only | XGBoost | 0.0300 | 0.5314 | 0.0294 | 0.1569 | 0.0495 | 0.0241 | 102 |

### Anomaly ratio >= 8

| Horizon | Feature set | Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Test prevalence | Test positives |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 d | Seasonality + weather | Logistic Regression | 0.0144 | 0.6070 | 0.0104 | 0.1667 | 0.0196 | 0.0099 | 42 |
| 1 d | Seasonality + weather | Random Forest | 0.0147 | 0.5739 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 1 d | Seasonality + weather | XGBoost | 0.0168 | 0.6669 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 1 d | Seasonality only | Logistic Regression | 0.0156 | 0.6513 | 0.0169 | 0.5714 | 0.0328 | 0.0099 | 42 |
| 1 d | Seasonality only | Random Forest | 0.0107 | 0.5049 | 0.0111 | 0.0476 | 0.0180 | 0.0099 | 42 |
| 1 d | Seasonality only | XGBoost | 0.0198 | 0.6929 | 0.0183 | 0.1667 | 0.0329 | 0.0099 | 42 |
| 1 d | Weather only | Logistic Regression | 0.0114 | 0.5637 | 0.0108 | 0.2381 | 0.0207 | 0.0099 | 42 |
| 1 d | Weather only | Random Forest | 0.0154 | 0.6277 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 1 d | Weather only | XGBoost | 0.0162 | 0.6404 | 0.0109 | 0.0238 | 0.0149 | 0.0099 | 42 |
| 3 d | Seasonality + weather | Logistic Regression | 0.0104 | 0.5468 | 0.0050 | 0.0714 | 0.0093 | 0.0099 | 42 |
| 3 d | Seasonality + weather | Random Forest | 0.0129 | 0.6035 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 3 d | Seasonality + weather | XGBoost | 0.0175 | 0.6813 | 0.0118 | 0.0238 | 0.0157 | 0.0099 | 42 |
| 3 d | Seasonality only | Logistic Regression | 0.0158 | 0.6580 | 0.0169 | 0.5714 | 0.0328 | 0.0099 | 42 |
| 3 d | Seasonality only | Random Forest | 0.0107 | 0.5050 | 0.0112 | 0.0476 | 0.0181 | 0.0099 | 42 |
| 3 d | Seasonality only | XGBoost | 0.0199 | 0.6919 | 0.0184 | 0.1667 | 0.0331 | 0.0099 | 42 |
| 3 d | Weather only | Logistic Regression | 0.0090 | 0.4842 | 0.0046 | 0.0952 | 0.0088 | 0.0099 | 42 |
| 3 d | Weather only | Random Forest | 0.0118 | 0.5883 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 3 d | Weather only | XGBoost | 0.0161 | 0.6851 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 5 d | Seasonality + weather | Logistic Regression | 0.0135 | 0.6234 | 0.0124 | 0.1905 | 0.0234 | 0.0099 | 42 |
| 5 d | Seasonality + weather | Random Forest | 0.0167 | 0.6420 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 5 d | Seasonality + weather | XGBoost | 0.0225 | 0.7077 | 0.0120 | 0.0238 | 0.0160 | 0.0099 | 42 |
| 5 d | Seasonality only | Logistic Regression | 0.0158 | 0.6582 | 0.0169 | 0.5714 | 0.0329 | 0.0099 | 42 |
| 5 d | Seasonality only | Random Forest | 0.0107 | 0.5050 | 0.0112 | 0.0476 | 0.0181 | 0.0099 | 42 |
| 5 d | Seasonality only | XGBoost | 0.0199 | 0.6922 | 0.0185 | 0.1667 | 0.0333 | 0.0099 | 42 |
| 5 d | Weather only | Logistic Regression | 0.0119 | 0.5837 | 0.0113 | 0.2143 | 0.0214 | 0.0099 | 42 |
| 5 d | Weather only | Random Forest | 0.0146 | 0.6437 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 5 d | Weather only | XGBoost | 0.0216 | 0.6986 | 0.0085 | 0.0238 | 0.0126 | 0.0099 | 42 |
| 7 d | Seasonality + weather | Logistic Regression | 0.0135 | 0.6140 | 0.0142 | 0.1905 | 0.0265 | 0.0099 | 42 |
| 7 d | Seasonality + weather | Random Forest | 0.0109 | 0.5574 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 7 d | Seasonality + weather | XGBoost | 0.0192 | 0.7118 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 7 d | Seasonality only | Logistic Regression | 0.0158 | 0.6583 | 0.0169 | 0.5714 | 0.0329 | 0.0099 | 42 |
| 7 d | Seasonality only | Random Forest | 0.0107 | 0.5053 | 0.0113 | 0.0476 | 0.0183 | 0.0099 | 42 |
| 7 d | Seasonality only | XGBoost | 0.0199 | 0.6922 | 0.0186 | 0.1667 | 0.0334 | 0.0099 | 42 |
| 7 d | Weather only | Logistic Regression | 0.0124 | 0.5816 | 0.0096 | 0.1429 | 0.0181 | 0.0099 | 42 |
| 7 d | Weather only | Random Forest | 0.0108 | 0.5501 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 7 d | Weather only | XGBoost | 0.0160 | 0.6760 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 14 d | Seasonality + weather | Logistic Regression | 0.0117 | 0.5868 | 0.0054 | 0.0714 | 0.0100 | 0.0099 | 42 |
| 14 d | Seasonality + weather | Random Forest | 0.0162 | 0.6062 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 14 d | Seasonality + weather | XGBoost | 0.0190 | 0.6954 | 0.0115 | 0.0238 | 0.0155 | 0.0099 | 42 |
| 14 d | Seasonality only | Logistic Regression | 0.0158 | 0.6588 | 0.0170 | 0.5714 | 0.0331 | 0.0099 | 42 |
| 14 d | Seasonality only | Random Forest | 0.0107 | 0.5054 | 0.0114 | 0.0476 | 0.0183 | 0.0099 | 42 |
| 14 d | Seasonality only | XGBoost | 0.0200 | 0.6932 | 0.0188 | 0.1667 | 0.0338 | 0.0099 | 42 |
| 14 d | Weather only | Logistic Regression | 0.0103 | 0.5423 | 0.0073 | 0.1190 | 0.0138 | 0.0099 | 42 |
| 14 d | Weather only | Random Forest | 0.0100 | 0.5260 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |
| 14 d | Weather only | XGBoost | 0.0121 | 0.5917 | 0.0000 | 0.0000 | 0.0000 | 0.0099 | 42 |

## Extra predictive value of weather beyond seasonality

The key incremental comparison is (seasonality + weather) PR-AUC minus seasonality-only PR-AUC for the same threshold, horizon, and model. Weather-only versus seasonality-only deltas are also included in the metrics CSV.

| Anomaly ratio | Mean weather-only minus seasonality PR-AUC | Mean combined-minus-seasonality PR-AUC | Median combined delta | Positive combined comparisons |
|---:|---:|---:|---:|---:|
| >= 2 | -0.0649 | -0.0126 | -0.0081 | 5/15 |
| >= 4 | -0.0219 | -0.0052 | -0.0132 | 6/15 |
| >= 8 | -0.0022 | -0.0001 | -0.0010 | 6/15 |

Across all 45 paired model/horizon/threshold comparisons, mean combined-minus-seasonality PR-AUC was -0.0060; weather helped in 17/45 comparisons.

## SHAP explanation of the best combined model

Highest pooled PR-AUC combined model: anomaly ratio >= 2, 1-day horizon, XGBoost (PR-AUC 0.1685; ROC-AUC 0.7076). SHAP mean absolute values are pooled over forward-held-out folds. They show predictive contribution magnitude, not causal effects or contribution direction.

| Rank | Feature | Mean absolute SHAP |
|---:|---|---:|
| 1 | `day_of_year_cos` | 1.004270 |
| 2 | `day_of_year_sin` | 0.649247 |
| 3 | `day_of_year` | 0.382938 |
| 4 | `temperature_lag_48h` | 0.272675 |
| 5 | `wind_sin_235` | 0.110807 |
| 6 | `TX_242` | 0.096898 |
| 7 | `wind_change_24h` | 0.091439 |
| 8 | `RH_235` | 0.082878 |
| 9 | `FG_225` | 0.081180 |
| 10 | `pressure_lag_48h` | 0.081017 |
| 11 | `coast_TX_max` | 0.073260 |
| 12 | `TN_310` | 0.064748 |
| 13 | `temperature_lag_24h` | 0.060396 |
| 14 | `temp_change_24h` | 0.054550 |
| 15 | `TX_235` | 0.052594 |
| 16 | `FG_310` | 0.051417 |
| 17 | `temperature_lag_72h` | 0.048226 |
| 18 | `wind_cos_235` | 0.047194 |
| 19 | `wind_cos_225` | 0.045758 |
| 20 | `wind_sin_242` | 0.041875 |

SHAP group contribution shares (sum of mean absolute values): seasonality 49.0%; weather 51.0%.

## Are exceptional influxes weather driven?

Weather does not improve the best combined configuration over its seasonality-only counterpart on pooled PR-AUC (delta -0.0016). Overall, combined models beat their seasonality-only counterparts in 17/45 paired comparisons, with mean PR-AUC change -0.0060. This is not evidence that exceptional influxes are reliably weather driven; seasonality remains the stronger baseline, and adding weather usually does not improve ranking skill. Individual SHAP weather contributions can be sizeable while adding little incremental skill because they may be redundant with seasonal information. This observational experiment does not establish that weather causes anomalies: migration timing, reporting effort, detectability, and shared seasonal conditions may all contribute.

## Artifacts

- Daily forward-only expectation, anomaly, ratio, and labels: `data/processed/yellow_browed_daily_anomalies.csv`
- Full fold-pooled metrics and paired PR-AUC deltas: `data/processed/yellow_browed_anomaly_forecast_metrics.csv`
- Full feature ranking: `data/processed/yellow_browed_anomaly_shap_importance.csv`
