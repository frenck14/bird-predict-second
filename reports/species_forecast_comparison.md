# Bird-Predict Species Forecast Comparison

## Method

All four species use the shared four-station coastal weather dataset and the exact same daily forecast origins, train/test folds, features, models, and decision threshold. Each target is whether the species has at least the specified number of GBIF records on the target date.

Expanding annual folds use the first five calendar years as the initial training window. Each test-origin year is predicted from training examples whose target dates precede that year. The common forecast-origin window ends 14 days before the final shared weather date, so every horizon uses the same held-out dates. Predictors match the Pallid Swift full-feature scenario: station weather (excluding raw wind direction), circular wind components, coastal summaries, and weather lag/change features. They are shifted to observations available through the day before the forecast origin; target-date calendar features are known in advance. Imputation and model fitting occur inside each fold.

The seasonal baseline is the month-specific training event rate, smoothed with 30 prior-equivalent observations. Logistic Regression is class-weighted; Random Forest uses balanced subsampling; XGBoost uses the fold's negative-to-positive ratio. Precision, recall, and F1 use a fixed probability threshold of 0.5. ROC-AUC and PR-AUC are pooled across forward-held-out predictions (PR-AUC is average precision).

A horizon is called **useful beyond seasonality** if at least one weather model has higher pooled PR-AUC than the seasonal baseline. This is a descriptive comparison, not a significance test.

GBIF date-facet targets (Red-throated Pipit and Manx Shearwater) aggregate buckets with complete calendar dates and use zero counts for unobserved dates. If an early training fold contains no positive examples for a target threshold, weather models predict zero for that fold; the fold remains in pooled evaluation rather than being silently removed.

## Results

### Target: at least 10 GBIF records

| Species | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Baseline PR-AUC | Test prevalence | Positive test days |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Manx Shearwater | 1 d | Logistic Regression | 0.6036 | 0.0261 | 0.0336 | 0.3333 | 0.0610 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 1 d | Random Forest | 0.7527 | 0.0914 | 0.3333 | 0.0370 | 0.0667 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 1 d | Seasonal baseline | 0.9020 | 0.0351 | 0.0000 | 0.0000 | 0.0000 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 1 d | XGBoost | 0.7059 | 0.1446 | 0.1471 | 0.1852 | 0.1639 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 3 d | Logistic Regression | 0.6411 | 0.0474 | 0.0244 | 0.2963 | 0.0451 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 3 d | Random Forest | 0.7844 | 0.0823 | 0.0000 | 0.0000 | 0.0000 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 3 d | Seasonal baseline | 0.9020 | 0.0351 | 0.0000 | 0.0000 | 0.0000 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 3 d | XGBoost | 0.7340 | 0.0657 | 0.1163 | 0.1852 | 0.1429 | 0.0351 | 0.0064 | 27 |
| Manx Shearwater | 5 d | Logistic Regression | 0.6563 | 0.0122 | 0.0157 | 0.2222 | 0.0293 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 5 d | Random Forest | 0.6422 | 0.0190 | 0.0000 | 0.0000 | 0.0000 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 5 d | Seasonal baseline | 0.9009 | 0.0348 | 0.0000 | 0.0000 | 0.0000 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 5 d | XGBoost | 0.6532 | 0.0329 | 0.0877 | 0.1852 | 0.1190 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 7 d | Logistic Regression | 0.7603 | 0.0257 | 0.0289 | 0.3333 | 0.0533 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 7 d | Random Forest | 0.7642 | 0.0301 | 0.0000 | 0.0000 | 0.0000 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 7 d | Seasonal baseline | 0.9012 | 0.0348 | 0.0000 | 0.0000 | 0.0000 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 7 d | XGBoost | 0.7699 | 0.0376 | 0.0769 | 0.1481 | 0.1013 | 0.0348 | 0.0064 | 27 |
| Manx Shearwater | 14 d | Logistic Regression | 0.7003 | 0.0144 | 0.0125 | 0.1852 | 0.0234 | 0.0365 | 0.0064 | 27 |
| Manx Shearwater | 14 d | Random Forest | 0.7280 | 0.0334 | 0.0000 | 0.0000 | 0.0000 | 0.0365 | 0.0064 | 27 |
| Manx Shearwater | 14 d | Seasonal baseline | 0.9062 | 0.0365 | 0.0000 | 0.0000 | 0.0000 | 0.0365 | 0.0064 | 27 |
| Manx Shearwater | 14 d | XGBoost | 0.8567 | 0.0361 | 0.0233 | 0.0370 | 0.0286 | 0.0365 | 0.0064 | 27 |
| Pallid Swift | 1 d | Logistic Regression | 0.9387 | 0.1150 | 0.0936 | 0.6757 | 0.1645 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 1 d | Random Forest | 0.9307 | 0.1610 | 0.2500 | 0.0270 | 0.0488 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 1 d | Seasonal baseline | 0.9327 | 0.0751 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 1 d | XGBoost | 0.9422 | 0.1895 | 0.2121 | 0.5676 | 0.3088 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 3 d | Logistic Regression | 0.8785 | 0.0889 | 0.0700 | 0.4865 | 0.1224 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 3 d | Random Forest | 0.9316 | 0.1845 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 3 d | Seasonal baseline | 0.9327 | 0.0751 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 3 d | XGBoost | 0.9583 | 0.1900 | 0.1959 | 0.5135 | 0.2836 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 5 d | Logistic Regression | 0.9079 | 0.0697 | 0.0671 | 0.5946 | 0.1205 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 5 d | Random Forest | 0.9034 | 0.1087 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 5 d | Seasonal baseline | 0.9327 | 0.0751 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 5 d | XGBoost | 0.9284 | 0.1258 | 0.1364 | 0.4054 | 0.2041 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 7 d | Logistic Regression | 0.9152 | 0.0611 | 0.0704 | 0.5405 | 0.1246 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 7 d | Random Forest | 0.9007 | 0.1460 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 7 d | Seasonal baseline | 0.9327 | 0.0751 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 7 d | XGBoost | 0.9396 | 0.1486 | 0.1667 | 0.5405 | 0.2548 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 14 d | Logistic Regression | 0.8985 | 0.0468 | 0.0558 | 0.6216 | 0.1024 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 14 d | Random Forest | 0.8874 | 0.1595 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 14 d | Seasonal baseline | 0.9327 | 0.0751 | 0.0000 | 0.0000 | 0.0000 | 0.0751 | 0.0088 | 37 |
| Pallid Swift | 14 d | XGBoost | 0.9314 | 0.1308 | 0.1546 | 0.4054 | 0.2239 | 0.0751 | 0.0088 | 37 |
| Red-throated Pipit | 1 d | Logistic Regression | 0.6400 | 0.0188 | 0.0162 | 0.2917 | 0.0307 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 1 d | Random Forest | 0.7969 | 0.0810 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 1 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 1 d | XGBoost | 0.7959 | 0.0982 | 0.0926 | 0.4167 | 0.1515 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 3 d | Logistic Regression | 0.6352 | 0.0184 | 0.0175 | 0.3125 | 0.0331 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 3 d | Random Forest | 0.8090 | 0.0818 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 3 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 3 d | XGBoost | 0.7814 | 0.0886 | 0.0905 | 0.3750 | 0.1457 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 5 d | Logistic Regression | 0.6638 | 0.0193 | 0.0192 | 0.3125 | 0.0362 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 5 d | Random Forest | 0.7939 | 0.0727 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 5 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 5 d | XGBoost | 0.7874 | 0.0983 | 0.0893 | 0.4167 | 0.1471 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 7 d | Logistic Regression | 0.5543 | 0.0140 | 0.0163 | 0.3125 | 0.0310 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 7 d | Random Forest | 0.7290 | 0.0543 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 7 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 7 d | XGBoost | 0.7658 | 0.0663 | 0.0661 | 0.3333 | 0.1103 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 14 d | Logistic Regression | 0.5742 | 0.0141 | 0.0138 | 0.2917 | 0.0264 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 14 d | Random Forest | 0.7443 | 0.0576 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 14 d | Seasonal baseline | 0.8071 | 0.0455 | 0.0000 | 0.0000 | 0.0000 | 0.0455 | 0.0114 | 48 |
| Red-throated Pipit | 14 d | XGBoost | 0.7674 | 0.0853 | 0.0854 | 0.3542 | 0.1377 | 0.0455 | 0.0114 | 48 |
| Yellow-browed Warbler | 1 d | Logistic Regression | 0.9044 | 0.4756 | 0.3272 | 0.9011 | 0.4801 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 1 d | Random Forest | 0.9444 | 0.7314 | 0.7379 | 0.7754 | 0.7562 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 1 d | Seasonal baseline | 0.9135 | 0.6007 | 0.7126 | 0.6497 | 0.6797 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 1 d | XGBoost | 0.9531 | 0.7469 | 0.6275 | 0.8556 | 0.7240 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 3 d | Logistic Regression | 0.9095 | 0.5019 | 0.3411 | 0.9011 | 0.4949 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 3 d | Random Forest | 0.9470 | 0.7304 | 0.7348 | 0.7781 | 0.7558 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 3 d | Seasonal baseline | 0.9135 | 0.6007 | 0.7126 | 0.6497 | 0.6797 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 3 d | XGBoost | 0.9464 | 0.7486 | 0.6299 | 0.8556 | 0.7256 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 5 d | Logistic Regression | 0.9071 | 0.5119 | 0.3320 | 0.8904 | 0.4837 | 0.6006 | 0.0885 | 374 |
| Yellow-browed Warbler | 5 d | Random Forest | 0.9343 | 0.7405 | 0.7273 | 0.7701 | 0.7481 | 0.6006 | 0.0885 | 374 |
| Yellow-browed Warbler | 5 d | Seasonal baseline | 0.9128 | 0.6006 | 0.7126 | 0.6497 | 0.6797 | 0.6006 | 0.0885 | 374 |
| Yellow-browed Warbler | 5 d | XGBoost | 0.9452 | 0.7299 | 0.6404 | 0.8476 | 0.7296 | 0.6006 | 0.0885 | 374 |
| Yellow-browed Warbler | 7 d | Logistic Regression | 0.9135 | 0.5397 | 0.3397 | 0.9037 | 0.4938 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 7 d | Random Forest | 0.9297 | 0.7154 | 0.7247 | 0.7674 | 0.7455 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 7 d | Seasonal baseline | 0.9131 | 0.6007 | 0.7126 | 0.6497 | 0.6797 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 7 d | XGBoost | 0.9397 | 0.7207 | 0.6389 | 0.8422 | 0.7266 | 0.6007 | 0.0885 | 374 |
| Yellow-browed Warbler | 14 d | Logistic Regression | 0.9100 | 0.5463 | 0.3337 | 0.8984 | 0.4866 | 0.6008 | 0.0885 | 374 |
| Yellow-browed Warbler | 14 d | Random Forest | 0.9259 | 0.7220 | 0.7150 | 0.7914 | 0.7513 | 0.6008 | 0.0885 | 374 |
| Yellow-browed Warbler | 14 d | Seasonal baseline | 0.9134 | 0.6008 | 0.7126 | 0.6497 | 0.6797 | 0.6008 | 0.0885 | 374 |
| Yellow-browed Warbler | 14 d | XGBoost | 0.9396 | 0.7502 | 0.6282 | 0.8449 | 0.7206 | 0.6008 | 0.0885 | 374 |

### Target: at least 25 GBIF records

| Species | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Baseline PR-AUC | Test prevalence | Positive test days |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Manx Shearwater | 1 d | Logistic Regression | 0.6970 | 0.0095 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 1 d | Random Forest | 0.7418 | 0.0344 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 1 d | Seasonal baseline | 0.4251 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 1 d | XGBoost | 0.7596 | 0.0216 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 3 d | Logistic Regression | 0.6668 | 0.0074 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 3 d | Random Forest | 0.6907 | 0.0191 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 3 d | Seasonal baseline | 0.4251 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 3 d | XGBoost | 0.6771 | 0.0175 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 5 d | Logistic Regression | 0.6583 | 0.0083 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 5 d | Random Forest | 0.5793 | 0.0037 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 5 d | Seasonal baseline | 0.4251 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 5 d | XGBoost | 0.5500 | 0.0080 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 7 d | Logistic Regression | 0.7195 | 0.0073 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 7 d | Random Forest | 0.5880 | 0.0050 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 7 d | Seasonal baseline | 0.4251 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 7 d | XGBoost | 0.6885 | 0.0096 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 14 d | Logistic Regression | 0.6055 | 0.0042 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 14 d | Random Forest | 0.5891 | 0.0069 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 14 d | Seasonal baseline | 0.4289 | 0.0048 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Manx Shearwater | 14 d | XGBoost | 0.6084 | 0.0249 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0026 | 11 |
| Pallid Swift | 1 d | Logistic Regression | 0.9445 | 0.1122 | 0.0888 | 0.7600 | 0.1590 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 1 d | Random Forest | 0.9800 | 0.1771 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 1 d | Seasonal baseline | 0.9288 | 0.0533 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 1 d | XGBoost | 0.9504 | 0.1377 | 0.1829 | 0.6000 | 0.2804 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 3 d | Logistic Regression | 0.9312 | 0.1249 | 0.0671 | 0.4400 | 0.1164 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 3 d | Random Forest | 0.9256 | 0.1554 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 3 d | Seasonal baseline | 0.9288 | 0.0533 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 3 d | XGBoost | 0.9455 | 0.2211 | 0.1566 | 0.5200 | 0.2407 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 5 d | Logistic Regression | 0.8996 | 0.0359 | 0.0420 | 0.4000 | 0.0760 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 5 d | Random Forest | 0.9104 | 0.0807 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 5 d | Seasonal baseline | 0.9288 | 0.0533 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 5 d | XGBoost | 0.8841 | 0.1160 | 0.0933 | 0.2800 | 0.1400 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 7 d | Logistic Regression | 0.8906 | 0.0387 | 0.0465 | 0.4000 | 0.0833 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 7 d | Random Forest | 0.9313 | 0.0623 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 7 d | Seasonal baseline | 0.9288 | 0.0533 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 7 d | XGBoost | 0.9405 | 0.0923 | 0.0862 | 0.2000 | 0.1205 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 14 d | Logistic Regression | 0.8956 | 0.0371 | 0.0495 | 0.5600 | 0.0909 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 14 d | Random Forest | 0.8499 | 0.0763 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 14 d | Seasonal baseline | 0.9288 | 0.0533 | 0.0000 | 0.0000 | 0.0000 | 0.0533 | 0.0059 | 25 |
| Pallid Swift | 14 d | XGBoost | 0.9298 | 0.0837 | 0.0893 | 0.2000 | 0.1235 | 0.0533 | 0.0059 | 25 |
| Red-throated Pipit | 1 d | Logistic Regression | 0.5919 | 0.0060 | 0.0073 | 0.1579 | 0.0139 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 1 d | Random Forest | 0.6595 | 0.0097 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 1 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 1 d | XGBoost | 0.6134 | 0.0138 | 0.0189 | 0.0526 | 0.0278 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 3 d | Logistic Regression | 0.5522 | 0.0069 | 0.0071 | 0.1579 | 0.0135 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 3 d | Random Forest | 0.5897 | 0.0250 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 3 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 3 d | XGBoost | 0.5993 | 0.0136 | 0.0361 | 0.1579 | 0.0588 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 5 d | Logistic Regression | 0.6050 | 0.0071 | 0.0072 | 0.1579 | 0.0137 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 5 d | Random Forest | 0.7271 | 0.0738 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 5 d | Seasonal baseline | 0.8694 | 0.0231 | 0.0000 | 0.0000 | 0.0000 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 5 d | XGBoost | 0.6658 | 0.0438 | 0.0488 | 0.2105 | 0.0792 | 0.0231 | 0.0045 | 19 |
| Red-throated Pipit | 7 d | Logistic Regression | 0.4943 | 0.0052 | 0.0034 | 0.1053 | 0.0066 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 7 d | Random Forest | 0.5994 | 0.0311 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 7 d | Seasonal baseline | 0.8706 | 0.0233 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 7 d | XGBoost | 0.6542 | 0.0474 | 0.0441 | 0.1579 | 0.0690 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 14 d | Logistic Regression | 0.4520 | 0.0051 | 0.0053 | 0.1579 | 0.0103 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 14 d | Random Forest | 0.5465 | 0.0085 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 14 d | Seasonal baseline | 0.8706 | 0.0233 | 0.0000 | 0.0000 | 0.0000 | 0.0233 | 0.0045 | 19 |
| Red-throated Pipit | 14 d | XGBoost | 0.5700 | 0.0121 | 0.0286 | 0.0526 | 0.0370 | 0.0233 | 0.0045 | 19 |
| Yellow-browed Warbler | 1 d | Logistic Regression | 0.9517 | 0.5249 | 0.3166 | 0.9562 | 0.4757 | 0.4674 | 0.0594 | 251 |
| Yellow-browed Warbler | 1 d | Random Forest | 0.9690 | 0.6574 | 0.6147 | 0.8327 | 0.7073 | 0.4674 | 0.0594 | 251 |
| Yellow-browed Warbler | 1 d | Seasonal baseline | 0.9366 | 0.4674 | 0.5207 | 0.4502 | 0.4829 | 0.4674 | 0.0594 | 251 |
| Yellow-browed Warbler | 1 d | XGBoost | 0.9705 | 0.6783 | 0.5332 | 0.9283 | 0.6773 | 0.4674 | 0.0594 | 251 |
| Yellow-browed Warbler | 3 d | Logistic Regression | 0.9520 | 0.5283 | 0.3109 | 0.9402 | 0.4673 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 3 d | Random Forest | 0.9634 | 0.6431 | 0.6358 | 0.8207 | 0.7165 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 3 d | Seasonal baseline | 0.9371 | 0.4676 | 0.4645 | 0.2869 | 0.3547 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 3 d | XGBoost | 0.9672 | 0.6077 | 0.5326 | 0.9124 | 0.6725 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 5 d | Logistic Regression | 0.9544 | 0.5264 | 0.3206 | 0.9681 | 0.4817 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 5 d | Random Forest | 0.9611 | 0.5993 | 0.5971 | 0.8088 | 0.6870 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 5 d | Seasonal baseline | 0.9371 | 0.4676 | 0.4645 | 0.2869 | 0.3547 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 5 d | XGBoost | 0.9680 | 0.5800 | 0.5455 | 0.9323 | 0.6882 | 0.4676 | 0.0594 | 251 |
| Yellow-browed Warbler | 7 d | Logistic Regression | 0.9528 | 0.5295 | 0.3166 | 0.9562 | 0.4757 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 7 d | Random Forest | 0.9556 | 0.5930 | 0.5927 | 0.7769 | 0.6724 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 7 d | Seasonal baseline | 0.9380 | 0.4677 | 0.4645 | 0.2869 | 0.3547 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 7 d | XGBoost | 0.9663 | 0.6371 | 0.5406 | 0.9283 | 0.6833 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 14 d | Logistic Regression | 0.9524 | 0.5083 | 0.3209 | 0.9602 | 0.4810 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 14 d | Random Forest | 0.9574 | 0.6191 | 0.6070 | 0.8247 | 0.6993 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 14 d | Seasonal baseline | 0.9380 | 0.4677 | 0.4645 | 0.2869 | 0.3547 | 0.4677 | 0.0594 | 251 |
| Yellow-browed Warbler | 14 d | XGBoost | 0.9642 | 0.6369 | 0.5276 | 0.9124 | 0.6686 | 0.4677 | 0.0594 | 251 |

### Target: at least 50 GBIF records

| Species | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Baseline PR-AUC | Test prevalence | Positive test days |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Manx Shearwater | 1 d | Logistic Regression | 0.5728 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 1 d | Random Forest | 0.4933 | 0.0007 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 1 d | Seasonal baseline | 0.5392 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 1 d | XGBoost | 0.5744 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 3 d | Logistic Regression | 0.5556 | 0.0012 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 3 d | Random Forest | 0.4899 | 0.0007 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 3 d | Seasonal baseline | 0.5392 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 3 d | XGBoost | 0.5786 | 0.0023 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 5 d | Logistic Regression | 0.5839 | 0.0035 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 5 d | Random Forest | 0.4893 | 0.0007 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 5 d | Seasonal baseline | 0.5392 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 5 d | XGBoost | 0.5642 | 0.0014 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 7 d | Logistic Regression | 0.5878 | 0.0058 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 7 d | Random Forest | 0.4919 | 0.0007 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 7 d | Seasonal baseline | 0.5392 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 7 d | XGBoost | 0.5618 | 0.0013 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 14 d | Logistic Regression | 0.5715 | 0.0017 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 14 d | Random Forest | 0.4905 | 0.0007 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 14 d | Seasonal baseline | 0.5392 | 0.0009 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Manx Shearwater | 14 d | XGBoost | 0.5744 | 0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.0009 | 0.0007 | 3 |
| Pallid Swift | 1 d | Logistic Regression | 0.9181 | 0.0572 | 0.0423 | 0.4615 | 0.0774 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 1 d | Random Forest | 0.9787 | 0.2259 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 1 d | Seasonal baseline | 0.9527 | 0.0417 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 1 d | XGBoost | 0.8898 | 0.3110 | 0.2400 | 0.4615 | 0.3158 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 3 d | Logistic Regression | 0.8828 | 0.0354 | 0.0360 | 0.3846 | 0.0658 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 3 d | Random Forest | 0.9302 | 0.1557 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 3 d | Seasonal baseline | 0.9527 | 0.0417 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 3 d | XGBoost | 0.9523 | 0.1338 | 0.1463 | 0.4615 | 0.2222 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 5 d | Logistic Regression | 0.8873 | 0.0206 | 0.0183 | 0.2308 | 0.0339 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 5 d | Random Forest | 0.8506 | 0.0636 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 5 d | Seasonal baseline | 0.9527 | 0.0417 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 5 d | XGBoost | 0.9094 | 0.0503 | 0.0455 | 0.1538 | 0.0702 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 7 d | Logistic Regression | 0.8724 | 0.0173 | 0.0163 | 0.1538 | 0.0294 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 7 d | Random Forest | 0.8607 | 0.0222 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 7 d | Seasonal baseline | 0.9530 | 0.0417 | 0.0000 | 0.0000 | 0.0000 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 7 d | XGBoost | 0.9002 | 0.0299 | 0.0312 | 0.0769 | 0.0444 | 0.0417 | 0.0031 | 13 |
| Pallid Swift | 14 d | Logistic Regression | 0.8692 | 0.0318 | 0.0267 | 0.3077 | 0.0491 | 0.0418 | 0.0031 | 13 |
| Pallid Swift | 14 d | Random Forest | 0.8829 | 0.0514 | 0.0000 | 0.0000 | 0.0000 | 0.0418 | 0.0031 | 13 |
| Pallid Swift | 14 d | Seasonal baseline | 0.9533 | 0.0418 | 0.0000 | 0.0000 | 0.0000 | 0.0418 | 0.0031 | 13 |
| Pallid Swift | 14 d | XGBoost | 0.9304 | 0.0825 | 0.1250 | 0.2308 | 0.1622 | 0.0418 | 0.0031 | 13 |
| Red-throated Pipit | 1 d | Logistic Regression | 0.4693 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 1 d | Random Forest | 0.4148 | 0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 1 d | Seasonal baseline | 0.8158 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 1 d | XGBoost | 0.5788 | 0.0024 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 3 d | Logistic Regression | 0.6512 | 0.0035 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 3 d | Random Forest | 0.7286 | 0.0060 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 3 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 3 d | XGBoost | 0.6902 | 0.0039 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 5 d | Logistic Regression | 0.6053 | 0.0030 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 5 d | Random Forest | 0.5316 | 0.0022 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 5 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 5 d | XGBoost | 0.4163 | 0.0018 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 7 d | Logistic Regression | 0.5020 | 0.0020 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 7 d | Random Forest | 0.6029 | 0.0035 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 7 d | Seasonal baseline | 0.8184 | 0.0141 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 7 d | XGBoost | 0.5024 | 0.0020 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0019 | 8 |
| Red-throated Pipit | 14 d | Logistic Regression | 0.5749 | 0.0024 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 0.0019 | 8 |
| Red-throated Pipit | 14 d | Random Forest | 0.4305 | 0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 0.0019 | 8 |
| Red-throated Pipit | 14 d | Seasonal baseline | 0.8193 | 0.0142 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 0.0019 | 8 |
| Red-throated Pipit | 14 d | XGBoost | 0.4916 | 0.0022 | 0.0000 | 0.0000 | 0.0000 | 0.0142 | 0.0019 | 8 |
| Yellow-browed Warbler | 1 d | Logistic Regression | 0.9642 | 0.4428 | 0.2373 | 0.9677 | 0.3812 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 1 d | Random Forest | 0.9771 | 0.5028 | 0.4969 | 0.5161 | 0.5063 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 1 d | Seasonal baseline | 0.9493 | 0.3131 | 0.0000 | 0.0000 | 0.0000 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 1 d | XGBoost | 0.9807 | 0.5235 | 0.4311 | 0.9484 | 0.5927 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 3 d | Logistic Regression | 0.9611 | 0.3839 | 0.2432 | 0.9742 | 0.3892 | 0.3116 | 0.0367 | 155 |
| Yellow-browed Warbler | 3 d | Random Forest | 0.9735 | 0.4681 | 0.4845 | 0.5032 | 0.4937 | 0.3116 | 0.0367 | 155 |
| Yellow-browed Warbler | 3 d | Seasonal baseline | 0.9491 | 0.3116 | 0.0000 | 0.0000 | 0.0000 | 0.3116 | 0.0367 | 155 |
| Yellow-browed Warbler | 3 d | XGBoost | 0.9775 | 0.4894 | 0.4286 | 0.9290 | 0.5866 | 0.3116 | 0.0367 | 155 |
| Yellow-browed Warbler | 5 d | Logistic Regression | 0.9632 | 0.4017 | 0.2271 | 0.9935 | 0.3697 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 5 d | Random Forest | 0.9741 | 0.4237 | 0.4323 | 0.4323 | 0.4323 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 5 d | Seasonal baseline | 0.9493 | 0.3131 | 0.0000 | 0.0000 | 0.0000 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 5 d | XGBoost | 0.9746 | 0.4316 | 0.4139 | 0.9613 | 0.5786 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 7 d | Logistic Regression | 0.9612 | 0.3739 | 0.2284 | 0.9742 | 0.3701 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 7 d | Random Forest | 0.9743 | 0.4574 | 0.4755 | 0.4387 | 0.4564 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 7 d | Seasonal baseline | 0.9493 | 0.3131 | 0.0000 | 0.0000 | 0.0000 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 7 d | XGBoost | 0.9762 | 0.4817 | 0.4073 | 0.9355 | 0.5675 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 14 d | Logistic Regression | 0.9567 | 0.3586 | 0.2345 | 0.9548 | 0.3766 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 14 d | Random Forest | 0.9740 | 0.4388 | 0.4866 | 0.5871 | 0.5322 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 14 d | Seasonal baseline | 0.9493 | 0.3131 | 0.0000 | 0.0000 | 0.0000 | 0.3131 | 0.0367 | 155 |
| Yellow-browed Warbler | 14 d | XGBoost | 0.9756 | 0.4642 | 0.4056 | 0.9419 | 0.5670 | 0.3131 | 0.0367 | 155 |

## Maximum useful forecasting horizon

| Species | Target threshold | Maximum horizon beating seasonal PR-AUC |
|---|---:|---:|
| Pallid Swift | >= 10 | 14 days |
| Pallid Swift | >= 25 | 14 days |
| Pallid Swift | >= 50 | 14 days |
| Yellow-browed Warbler | >= 10 | 14 days |
| Yellow-browed Warbler | >= 25 | 14 days |
| Yellow-browed Warbler | >= 50 | 14 days |
| Manx Shearwater | >= 10 | 7 days |
| Manx Shearwater | >= 25 | 14 days |
| Manx Shearwater | >= 50 | 14 days |
| Red-throated Pipit | >= 10 | 14 days |
| Red-throated Pipit | >= 25 | 7 days |
| Red-throated Pipit | >= 50 | None |

## Which species is more forecastable?

Across the 15 threshold/horizon combinations, the table below averages the highest-PR-AUC weather model in each combination. Model selection here is descriptive and is not a separate validation procedure.

| Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Mean test prevalence | Mean F1 | Scenarios beating seasonality |
|---|---:|---:|---:|---:|---:|---:|
| Pallid Swift | 0.1431 | 0.0567 | 0.0864 | 0.0059 | 0.1466 | 14/15 |
| Yellow-browed Warbler | 0.6195 | 0.4604 | 0.1591 | 0.0615 | 0.6647 | 15/15 |
| Manx Shearwater | 0.0297 | 0.0137 | 0.0160 | 0.0032 | 0.0275 | 13/15 |
| Red-throated Pipit | 0.0418 | 0.0276 | 0.0142 | 0.0059 | 0.0551 | 8/15 |

**Conclusion:** Yellow-browed Warbler ranks first by mean best-model PR-AUC lift over the seasonal baseline in this comparison (0.1591; 15/15 scenarios beating seasonality). Red-throated Pipit has mean lift 0.0142 and beats seasonality in 8/15 scenarios. Therefore the results do not establish Red-throated Pipit as the most meteorologically forecastable species unless it ranks first by this measure. This model-grid summary is descriptive, not a significance test or independent validation; PR-AUC also depends on event prevalence, and GBIF counts reflect reporting effort rather than abundance.

The full metric grid, including per-horizon model results, is saved in `data/processed/species_forecast_metrics.csv`.

Caveats: GBIF reporting effort is not controlled, records are not abundance estimates, high-count days cluster in episodes, and the latest year is incomplete. A PR-AUC improvement over seasonality alone does not establish prospective operational utility.
