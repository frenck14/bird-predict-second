import json
from pathlib import Path


notebook_path = Path("bird_predict_v2.ipynb")
notebook = json.loads(notebook_path.read_text())
cells = {cell["id"]: cell for cell in notebook["cells"]}

markdown_updates = {
    "v2-intro": """# Bird-Predict v2: Forward-Chaining Evaluation

This notebook evaluates the `n_records >= 10` GBIF-report target using coastal KNMI weather and seasonal features. Forecast validation uses expanding training windows: the first five calendar years (2010-2014) train the first model, and each subsequent calendar year is tested using only earlier years. Weather predictors for date *t* are shifted so the latest input is observed on *t-1*; date-*t* seasonality is known in advance. Imputation, scaling, and model fitting occur within each training fold.

A legacy leave-one-year-out (LOYO) evaluation is retained only as a historical comparator; unlike forward chaining, it can train on years after the test year. GBIF record counts are affected by observer effort and are not confirmed abundance or absences. The final dataset year may be incomplete.

**KNMI field note:** in this source, `RH` is daily precipitation (not relative humidity), while `PX` is maximum hourly sea-level pressure. Values retain KNMI scaling. KNMI also cautions that the station series may be inhomogeneous.""",
    "v2-validation-heading": """## Expanding-window forward-chaining evaluation

The first five calendar years form the initial training window; each following year is predicted using all and only earlier years. The seasonal baseline is a smoothed month-specific event rate. Logistic regression is class-weighted, random forest uses balanced subsampling, and XGBoost uses the training-fold negative/positive ratio. Precision, recall, and F1 use the prespecified probability threshold of 0.5. Fold ROC-AUC and average precision are undefined when a test year contains only one target class; pooled scores use all forward-held-out dates. The LOYO table below is a historical reference evaluated over the same test years, but it is not prospective because some folds train on later years.""",
    "v2-interpret-heading": """## Feature importance and interpretation

The leading full-feature model is selected by pooled forward-chaining average precision. Built-in importance is averaged across forward-training folds; held-out permutation importance measures the change in average precision when a test-year feature is permuted. These rankings are exploratory with few events and correlated weather variables. SHAP is attempted only when the package is installed and a tree model is selected.""",
    "v2-conclusion-heading": """## Forward-chaining conclusions and alert recommendation

Interpret the pooled forward-chaining scores as the primary prospective-style evidence. Compare them with the LOYO reference over the same held-out years, remembering that LOYO has access to later years during training. The final year in the dataset is incomplete. These analyses predict a reporting-count proxy and do not establish abundance or causality.""",
}

for cell_id, markdown in markdown_updates.items():
    cells[cell_id]["source"] = markdown.splitlines(keepends=True)

evaluation_code = '''from xgboost import XGBClassifier

MODEL_NAMES = ["Seasonal baseline", "Logistic Regression", "Random Forest", "XGBoost"]
THRESHOLD = 0.5
MIN_TRAIN_YEARS = 5
full_scenario = "Coastal + temporal changes + seasonality"
full_features = feature_scenarios[full_scenario]
unique_years = np.sort(np.unique(years))
if len(unique_years) <= MIN_TRAIN_YEARS:
    raise ValueError("Forward chaining requires years beyond the initial training window.")
forward_test_years = unique_years[MIN_TRAIN_YEARS:]
first_forward_test_year = int(forward_test_years[0])
evaluation_mask = np.isin(years, forward_test_years)

def make_estimator(name, positive_count, negative_count):
    if positive_count == 0:
        raise ValueError("A training fold has no positive examples.")
    if name == "Logistic Regression":
        model = LogisticRegression(class_weight="balanced", max_iter=3000, C=0.5)
        steps = [("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                 ("scale", StandardScaler()), ("model", model)]
    elif name == "Random Forest":
        model = RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                       class_weight="balanced_subsample",
                                       random_state=42, n_jobs=-1)
        steps = [("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                 ("model", model)]
    elif name == "XGBoost":
        model = XGBClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                              subsample=0.8, colsample_bytree=0.8,
                              min_child_weight=3, reg_lambda=2,
                              scale_pos_weight=negative_count / positive_count,
                              eval_metric="logloss", n_jobs=1, random_state=42,
                              verbosity=0)
        steps = [("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                 ("model", model)]
    else:
        raise ValueError(f"Unknown model: {name}")
    return Pipeline(steps)

def calculate_metrics(y_true, probabilities, threshold=THRESHOLD):
    predicted = probabilities >= threshold
    has_positive = np.any(y_true == 1)
    has_both_classes = np.unique(y_true).size == 2
    return {
        "PR-AUC": average_precision_score(y_true, probabilities) if has_positive else np.nan,
        "ROC-AUC": roc_auc_score(y_true, probabilities) if has_both_classes else np.nan,
        "Precision": precision_score(y_true, predicted, zero_division=0),
        "Recall": recall_score(y_true, predicted, zero_division=0),
        "F1": f1_score(y_true, predicted, zero_division=0),
    }

forward_predictions = {
    name: np.full(len(data), np.nan, dtype=float) for name in MODEL_NAMES
}
fold_models = {name: [] for name in MODEL_NAMES if name != "Seasonal baseline"}
forward_fold_rows = []

for test_year in forward_test_years:
    train = years < test_year
    test = years == test_year
    train_years = np.sort(np.unique(years[train]))
    if not train_years.size or not test.any() or train_years.max() >= test_year:
        raise RuntimeError(f"Invalid forward-chaining fold for test year {test_year}.")
    train_positive_days = int(y[train].sum())
    test_positive_days = int(y[test].sum())
    train_years_text = ", ".join(map(str, train_years))

    train_frame = data.loc[train, ["month", "influx"]]
    overall_rate = train_frame["influx"].mean()
    month_rates = train_frame.groupby("month")["influx"].agg(["sum", "count"])
    seasonal_rates = (month_rates["sum"] + 30 * overall_rate) / (month_rates["count"] + 30)
    forward_predictions["Seasonal baseline"][test] = (
        data.loc[test, "month"].map(seasonal_rates).fillna(overall_rate).to_numpy()
    )

    for model_name in MODEL_NAMES[1:]:
        estimator = make_estimator(
            model_name, train_positive_days, int(train.sum() - train_positive_days)
        )
        X_train = X.loc[train, full_features]
        X_test = X.loc[test, full_features]
        estimator.fit(X_train, y[train])
        probabilities = estimator.predict_proba(X_test)[:, 1]
        forward_predictions[model_name][test] = probabilities
        fold_models[model_name].append(
            (int(test_year), estimator, X_test.copy(), y[test].copy())
        )

    for model_name in MODEL_NAMES:
        fold_probabilities = forward_predictions[model_name][test]
        forward_fold_rows.append({
            "Model": model_name,
            "Train years": train_years_text,
            "Test year": int(test_year),
            "Influx days in train": train_positive_days,
            "Influx days in test": test_positive_days,
            **calculate_metrics(y[test], fold_probabilities),
        })

forward_fold_metrics = pd.DataFrame(forward_fold_rows)
if forward_fold_metrics.empty or not np.isfinite(
    np.column_stack([forward_predictions[name][evaluation_mask] for name in MODEL_NAMES])
).all():
    raise RuntimeError("Forward chaining did not generate a prediction for every test date.")

print(f"Expanding-window validation: train starts with {unique_years[:MIN_TRAIN_YEARS].tolist()}, "
      f"test years {int(forward_test_years[0])}-{int(forward_test_years[-1])}.")
print("One row per model and forward test year; fold AUCs are undefined for single-class test years.")
display(forward_fold_metrics.round(4))

forward_comparison_table = pd.DataFrame(
    {
        model_name: calculate_metrics(
            y[evaluation_mask], forward_predictions[model_name][evaluation_mask]
        )
        for model_name in MODEL_NAMES
    }
).T
forward_comparison_table.index.name = "Model"
forward_comparison_table = forward_comparison_table[
    ["PR-AUC", "ROC-AUC", "Precision", "Recall", "F1"]
]
print(f"Pooled forward-chaining comparison (fixed threshold = {THRESHOLD:.2f}):")
display(forward_comparison_table.round(4))

fold_score_columns = ["PR-AUC", "ROC-AUC", "Precision", "Recall", "F1"]
fold_score_summary = (
    forward_fold_metrics.groupby("Model")[fold_score_columns]
    .agg(["mean", "std"])
    .reindex(MODEL_NAMES)
)
print("Mean and standard deviation across annual forward test folds (undefined AUCs excluded):")
display(fold_score_summary.round(4))

loyo_predictions = {name: np.full(len(data), np.nan, dtype=float) for name in MODEL_NAMES}
for test_year in unique_years:
    test = years == test_year
    train = years != test_year
    if not train.any() or not test.any():
        continue
    train_positive_days = int(y[train].sum())
    train_frame = data.loc[train, ["month", "influx"]]
    overall_rate = train_frame["influx"].mean()
    month_rates = train_frame.groupby("month")["influx"].agg(["sum", "count"])
    seasonal_rates = (month_rates["sum"] + 30 * overall_rate) / (month_rates["count"] + 30)
    loyo_predictions["Seasonal baseline"][test] = (
        data.loc[test, "month"].map(seasonal_rates).fillna(overall_rate).to_numpy()
    )
    estimator = make_estimator(
        "Logistic Regression", train_positive_days, int(train.sum() - train_positive_days)
    )
    estimator.fit(X.loc[train, full_features], y[train])
    loyo_predictions["Logistic Regression"][test] = estimator.predict_proba(
        X.loc[test, full_features]
    )[:, 1]
    estimator = make_estimator(
        "Random Forest", train_positive_days, int(train.sum() - train_positive_days)
    )
    estimator.fit(X.loc[train, full_features], y[train])
    loyo_predictions["Random Forest"][test] = estimator.predict_proba(
        X.loc[test, full_features]
    )[:, 1]
    estimator = make_estimator(
        "XGBoost", train_positive_days, int(train.sum() - train_positive_days)
    )
    estimator.fit(X.loc[train, full_features], y[train])
    loyo_predictions["XGBoost"][test] = estimator.predict_proba(
        X.loc[test, full_features]
    )[:, 1]

loyo_comparison_table = pd.DataFrame(
    {
        model_name: calculate_metrics(
            y[evaluation_mask], loyo_predictions[model_name][evaluation_mask]
        )
        for model_name in MODEL_NAMES
    }
).T
loyo_comparison_table.index.name = "Model"
loyo_comparison_table = loyo_comparison_table[forward_comparison_table.columns]
side_by_side = pd.concat(
    {"Forward chaining": forward_comparison_table,
     "LOYO reference (same test years)": loyo_comparison_table},
    names=["Evaluation"],
)
print("Historical LOYO comparison over the same test years (LOYO can train on future years):")
display(side_by_side.round(4))

forward_plot_dates = data.loc[evaluation_mask, "date"]
fig, ax = plt.subplots(figsize=(14, 5))
for model_name in MODEL_NAMES:
    ax.plot(
        forward_plot_dates,
        forward_predictions[model_name][evaluation_mask],
        linewidth=1.1,
        label=f"{model_name} probability",
    )
event_dates = data.loc[evaluation_mask & (y == 1), "date"]
ax.scatter(
    event_dates,
    np.full(len(event_dates), 1.04),
    marker="|",
    s=90,
    color="black",
    label="Observed influx day",
    clip_on=False,
)
ax.set(
    title="Observed influx days and forward-chained predicted probabilities",
    xlabel="Date",
    ylabel="Predicted probability (observed events marked at top)",
    ylim=(-0.02, 1.08),
)
ax.grid(alpha=0.25)
ax.legend(ncol=2)
fig.tight_layout()
plt.show()
'''

report_code = '''baseline_ap = float(forward_comparison_table.loc["Seasonal baseline", "PR-AUC"])
ml_forward = forward_comparison_table.drop(index="Seasonal baseline")
best_model_name = ml_forward["PR-AUC"].idxmax()
best_model_ap = float(forward_comparison_table.loc[best_model_name, "PR-AUC"])
best_model_threshold_metrics = forward_comparison_table.loc[best_model_name]
loyo_best_model_ap = float(loyo_comparison_table.loc[best_model_name, "PR-AUC"])
mean_fold_ap = float(fold_score_summary.loc[best_model_name, ("PR-AUC", "mean")])
std_fold_ap = float(fold_score_summary.loc[best_model_name, ("PR-AUC", "std")])
test_positive_days = int(y[evaluation_mask].sum())
test_days = int(evaluation_mask.sum())
alert_rate = float(
    np.mean(forward_predictions[best_model_name][evaluation_mask] >= THRESHOLD)
)
weather_beats_baseline = bool((ml_forward["PR-AUC"] > baseline_ap).any())

print("Primary pooled forward-chaining comparison:")
display(forward_comparison_table.round(4))
print(f"Forward test period: {int(forward_test_years[0])}-{int(forward_test_years[-1])} "
      f"({test_days:,} dates, {test_positive_days} influx days).")
print(
    f"Leading model by pooled forward PR-AUC: {best_model_name} "
    f"(AP={best_model_ap:.4f}; mean annual AP={mean_fold_ap:.4f}, "
    f"SD={std_fold_ap:.4f}; same-period LOYO AP={loyo_best_model_ap:.4f})."
)

performance_conclusion = (
    f"At least one weather-based model exceeded the seasonal baseline in pooled forward PR-AUC "
    f"({best_model_ap:.4f} versus {baseline_ap:.4f} for {best_model_name})."
    if weather_beats_baseline
    else f"No weather-based model exceeded the seasonal baseline in pooled forward PR-AUC "
         f"(baseline AP={baseline_ap:.4f})."
)
weather_conclusion = (
    "This is evidence that weather features add predictive value beyond the smoothed seasonal benchmark "
    "in this historical forward-chaining exercise, not evidence of a causal weather effect."
    if weather_beats_baseline
    else "These results do not show added predictive value from weather beyond the seasonal benchmark."
)
report_text = f"""### Scientific interpretation

- **Forward performance versus the seasonal baseline:** {performance_conclusion}
- **Weather contribution:** {weather_conclusion} Model selection among three algorithms on this evaluation is exploratory and may overstate the best score.
- **Forward versus LOYO:** the same-period LOYO AP for {best_model_name} was {loyo_best_model_ap:.4f}, compared with forward-chaining AP {best_model_ap:.4f}. The forward estimate is the relevant prospective-style estimate because no fold uses future years for training.
- **Fold-to-fold uncertainty:** {best_model_name} had mean annual PR-AUC {mean_fold_ap:.4f} (SD {std_fold_ap:.4f}); some test years have no influx days, so their fold PR-AUC and ROC-AUC are undefined and are excluded from these averages.
- **Operational suitability:** the model is not yet suitable for unattended operational alerts. There are only {test_positive_days} forward-held-out influx days across {len(forward_test_years)} test years, observations are serially dependent, GBIF reporting effort is unmeasured, and the class-weighted model scores have not been calibrated prospectively.

### Provisional alert threshold

For a **shadow-mode pilot only**, use a probability threshold of **{THRESHOLD:.2f}** for {best_model_name}, matching the prespecified evaluation threshold rather than tuning on held-out outcomes. At this threshold the forward pooled precision is {best_model_threshold_metrics["Precision"]:.3f}, recall is {best_model_threshold_metrics["Recall"]:.3f}, F1 is {best_model_threshold_metrics["F1"]:.3f}, and {alert_rate:.1%} of evaluated days would trigger an alert. Do not treat this as a validated production threshold: first calibrate scores and select a threshold against an explicit false-alert capacity and missed-event cost using prospective, effort-aware data.

The target is a reporting-count proxy, not confirmed abundance; daily scores and event counts also do not represent independent migration events. The last test year ({int(forward_test_years[-1])}) is incomplete. A prospective monitoring period with observer-effort covariates and event-level evaluation is needed before deployment."""
display(Markdown(report_text))
'''

cells["v2-models"]["source"] = evaluation_code.splitlines(keepends=True)
cells["v2-models"]["outputs"] = []
cells["v2-models"]["execution_count"] = None
importance_code = "".join(cells["v2-importance"]["source"])
importance_code = importance_code.replace(
    "full_scores = metrics_table.loc[full_scenario, 'PR-AUC (AP)'].dropna()",
    'full_scores = forward_comparison_table.loc[MODEL_NAMES[1:], "PR-AUC"]',
)
importance_code = importance_code.replace(
    "best_models = fold_models[(full_scenario, best_model_name)]",
    "best_models = fold_models[best_model_name]",
)
importance_code = importance_code.replace(
    "Best full-feature model by pooled LOYO AP:",
    "Best full-feature model by pooled forward-chaining AP:",
)
importance_code = importance_code.replace(
    "pdp_data = X.loc[:, best_features].dropna(how='all').sample(\n"
    "    n=min(1000, len(X)), random_state=42)",
    "pdp_training_data = X.loc[years < first_forward_test_year, best_features]\n"
    "pdp_data = pdp_training_data.dropna(how='all').sample(\n"
    "    n=min(1000, len(pdp_training_data)), random_state=42)",
)
cells["v2-importance"]["source"] = importance_code.splitlines(keepends=True)
cells["v2-importance"]["outputs"] = []
cells["v2-importance"]["execution_count"] = None
cells["v2-report"]["source"] = report_code.splitlines(keepends=True)
cells["v2-report"]["outputs"] = []
cells["v2-report"]["execution_count"] = None

for cell_id in ("v2-load", "v2-importance", "v2-effects"):
    cells[cell_id]["outputs"] = []
    cells[cell_id]["execution_count"] = None

notebook_path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
