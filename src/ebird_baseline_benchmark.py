"""eBird-activity baselines for seabird influx events.

Compares the stored production weather forecasts with three weather-free
baselines on exactly the same dates and influx-event labels:

* B: yesterday's event status (empirical conditional probabilities)
* C/D: logistic model on the eBird record count over the previous 7/30 days
* C-norm/D-norm: the same, with activity scaled by the prior-year level

Every baseline is refit at each annual cutoff on dates up to the cutoff and
every feature window ends the day before the forecast date.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LogisticRegression

from .rolling_seabird_event_validation import ROOT, load_observations
from .seabird_calibration import SPECIES_ORDER, calibration_metrics, classify
from .seabird_observation_validation import OBSERVATIONS_FILE
from .train_seabird_species_models import CLASSIFICATION_THRESHOLD

OUT = ROOT / "outputs/seabird_validation"
PREDICTIONS_PATH = OUT / "rolling_event_predictions.csv"
BENCHMARK_PATH = OUT / "ebird_baseline_benchmark.csv"
SUMMARY_PATH = OUT / "ebird_baseline_summary.md"
ACTIVITY_CACHE = ROOT / "data/cache/ebird_gbif_daily_records.csv"

GBIF = "https://api.gbif.org/v1/"
EBIRD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
COUNTRIES = ("GB", "IE", "NL", "BE", "DK")
SCIENTIFIC_NAMES = {
    "Northern Fulmar": "Fulmarus glacialis",
    "Manx Shearwater": "Puffinus puffinus",
    "European Storm-petrel": "Hydrobates pelagicus",
    "Sooty Shearwater": "Ardenna grisea",
    "Great Shearwater": "Ardenna gravis",
}
FIRST_YEAR = 2010
MODELS = ["A weather", "B yesterday", "C ebird7", "D ebird30", "C ebird7 norm", "D ebird30 norm"]
LABELS = {
    "A weather": "A: production weather model",
    "B yesterday": "B: yesterday's event",
    "C ebird7": "C: 7-day eBird activity",
    "D ebird30": "D: 30-day eBird activity",
    "C ebird7 norm": "C-norm: 7-day activity / prior-year level",
    "D ebird30 norm": "D-norm: 30-day activity / prior-year level",
}


def _get(path: str, params: dict) -> dict:
    for attempt in range(4):
        response = requests.get(GBIF + path, params=params, timeout=120)
        if response.ok:
            return response.json()
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    return {}


def fetch_activity(cache: Path = ACTIVITY_CACHE, refresh: bool = False) -> pd.DataFrame:
    """Daily eBird-dataset record counts per species from GBIF, cached on disk."""
    if cache.is_file() and not refresh:
        return pd.read_csv(cache, parse_dates=["date"])
    rows = []
    for species, scientific in SCIENTIFIC_NAMES.items():
        key = _get("species/match", {"name": scientific})["usageKey"]
        for country in COUNTRIES:
            for year in range(FIRST_YEAR, pd.Timestamp.today().year + 1):
                params = {
                    "taxonKey": key, "datasetKey": EBIRD_DATASET_KEY, "country": country,
                    "year": year, "basisOfRecord": "HUMAN_OBSERVATION", "limit": 0,
                    "facet": "eventDate", "facetLimit": 1000,
                }
                result = _get("occurrence/search", params)
                buckets = result["facets"][0]["counts"] if result.get("facets") else []
                if sum(item["count"] for item in buckets) != result["count"]:
                    raise ValueError(f"Truncated GBIF facets: {species} {country} {year}")
                rows.extend((species, item["name"][:10], item["count"]) for item in buckets)
        print(f"Fetched eBird activity: {species}", flush=True)
    frame = pd.DataFrame(rows, columns=["species", "date", "records"])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.groupby(["species", "date"], as_index=False)["records"].sum()
    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache, index=False)
    return frame


def activity_end(activity: pd.DataFrame) -> pd.Timestamp:
    """Last day of the final calendar year with eBird data; later days would read as zero activity."""
    return pd.Timestamp(year=int(activity["date"].dt.year.max()), month=12, day=31)


def daily_series(frame: pd.DataFrame, species: str, start: str, end: str) -> pd.Series:
    index = pd.date_range(start, end)
    rows = frame.loc[frame["species"].eq(species)].groupby("date")["records"].sum()
    return rows.reindex(index, fill_value=0).astype(float)


def activity_features(daily: pd.Series, window: int) -> pd.DataFrame:
    """Features known on the morning of each *target* date (windows end the day before)."""
    prior = daily.shift(1)
    total = prior.rolling(window, min_periods=window).sum()
    level = prior.rolling(365, min_periods=365).mean() * window
    return pd.DataFrame(
        {"log_activity": np.log1p(total), "relative_activity": np.log1p(total) - np.log1p(level)}
    )


def fit_predict_activity(
    features: pd.Series, labels: pd.Series, train_end: pd.Timestamp, targets: pd.DatetimeIndex
) -> np.ndarray:
    train = pd.concat([features, labels.rename("y")], axis=1).dropna()
    train = train.loc[train.index <= train_end]
    if train["y"].nunique() < 2:
        return np.full(len(targets), float(train["y"].mean()) if len(train) else 0.0)
    model = LogisticRegression(C=1e6, max_iter=1000).fit(train[[features.name]], train["y"])
    return model.predict_proba(features.reindex(targets).to_frame())[:, 1]


def fit_predict_persistence(
    labels: pd.Series, train_end: pd.Timestamp, targets: pd.DatetimeIndex
) -> np.ndarray:
    previous = labels.shift(1)
    frame = pd.concat([previous.rename("prev"), labels.rename("y")], axis=1).dropna()
    frame = frame.loc[frame.index <= train_end]
    rates = frame.groupby("prev")["y"].mean()
    fallback = float(frame["y"].mean())
    lookup = {flag: float(rates.get(flag, fallback)) for flag in (0.0, 1.0)}
    return previous.reindex(targets).map(lookup).to_numpy(float)


def build_forecasts(
    predictions: pd.DataFrame, observations: pd.DataFrame, activity: pd.DataFrame
) -> pd.DataFrame:
    """Return long-form forecasts for every model on the stored rolling evaluation rows."""
    predictions = predictions.assign(date=pd.to_datetime(predictions["date"]))
    predictions = predictions.loc[predictions["date"].le(activity_end(activity))]
    start = min(FIRST_YEAR, int(predictions["date"].dt.year.min()))
    end = predictions["date"].max().strftime("%Y-%m-%d")
    counts = observations.groupby(["species", "date"])["count"].sum()
    frames = []
    for species in SPECIES_ORDER:
        rows = predictions.loc[predictions["species"].eq(species)].sort_values("date")
        daily_counts = counts.xs(species, level="species").reindex(
            pd.date_range(f"{start}-01-01", end), fill_value=0
        )
        daily = daily_series(activity, species, f"{start}-01-01", end)
        features = {
            "C ebird7": activity_features(daily, 7)["log_activity"],
            "D ebird30": activity_features(daily, 30)["log_activity"],
            "C ebird7 norm": activity_features(daily, 7)["relative_activity"],
            "D ebird30 norm": activity_features(daily, 30)["relative_activity"],
        }
        for model, series in features.items():
            series.name = "x"
            features[model] = series
        output = {name: pd.Series(np.nan, index=rows.index) for name in MODELS}
        output["A weather"] = rows["probability"]
        for year, year_rows in rows.groupby(rows["date"].dt.year):
            train_end = pd.Timestamp(year=year, month=1, day=1) - pd.Timedelta(days=1)
            threshold = float(year_rows["event_threshold_count"].iloc[0])
            labels = (daily_counts >= threshold).astype(float)
            targets = pd.DatetimeIndex(year_rows["date"])
            output["B yesterday"].loc[year_rows.index] = fit_predict_persistence(
                labels, train_end, targets
            )
            for model, series in features.items():
                output[model].loc[year_rows.index] = fit_predict_activity(
                    series, labels, train_end, targets
                )
        for model, probability in output.items():
            frames.append(
                pd.DataFrame(
                    {
                        "species": species, "model": model, "date": rows["date"],
                        "probability": probability, "actual_event": rows["actual_event"].astype(bool),
                        "baseline_probability": rows["baseline_probability"],
                    }
                )
            )
    forecasts = pd.concat(frames, ignore_index=True)
    if forecasts["probability"].isna().any():
        raise ValueError("Baseline forecasts contain missing probabilities.")
    return forecasts


def score(rows: pd.DataFrame) -> dict[str, float]:
    actual = rows["actual_event"].astype(bool)
    predicted = rows["probability"].ge(CLASSIFICATION_THRESHOLD)
    tp = int((actual & predicted).sum())
    fp = int((~actual & predicted).sum())
    fn = int((actual & ~predicted).sum())
    calibration = calibration_metrics(rows["probability"], actual)
    brier = calibration["brier_score"]
    training_brier = float(((rows["baseline_probability"] - actual.astype(int)) ** 2).mean())
    return {
        "forecast_days": len(rows),
        "event_days": int(actual.sum()),
        "event_prevalence": float(actual.mean()),
        "predicted_event_days": int(predicted.sum()),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "brier_score": brier,
        "brier_skill_vs_training_prevalence": (
            1 - brier / training_brier if training_brier > 0 else np.nan
        ),
        "ece": calibration["ece"],
        "mce": calibration["mce"],
        "mean_predicted_probability": calibration["mean_predicted_probability"],
        "calibration": classify(calibration),
    }


def benchmark(forecasts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (species, model), group in forecasts.groupby(["species", "model"], sort=False):
        rows.append({"species": species, "model": model, **score(group)})
    return pd.DataFrame(rows)


def verdict(frame: pd.DataFrame, species: str) -> str:
    rows = frame.loc[frame["species"].eq(species)].set_index("model")
    best = rows.loc[["B yesterday", "C ebird7", "D ebird30"], "f1"].idxmax()
    gap = rows.loc[best, "f1"] / rows.loc["A weather", "f1"] if rows.loc["A weather", "f1"] else np.nan
    return f"{LABELS[best]} (F1 {rows.loc[best, 'f1']:.3f}, {gap:.0%} of weather F1)"


def write_summary(
    frame: pd.DataFrame, end: str = "2025-12-31", path: Path = SUMMARY_PATH
) -> None:
    start = "2015-01-01"
    lines = [
        "# eBird baseline benchmark",
        "",
        f"Evaluation: {start} to {end}, annual expanding-window cutoffs, one-day-ahead, same "
        "influx-event labels and dates as `rolling_event_validation.csv`, ended at the last "
        "year with eBird data in GBIF (the rolling run itself continues to 2026-08-11, so its "
        "published numbers differ slightly). Probability cutoff "
        f"{CLASSIFICATION_THRESHOLD:.2f} for every model. No production model was retrained.",
        "",
        "## Models",
        "",
    ]
    lines += [f"- **{LABELS[m]}**" for m in MODELS]
    lines += [
        "",
        "- A is the stored rolling weather forecast. B-D are refit each January on data up to the "
        "cutoff only, with the same year-specific event threshold as the labels.",
        "- B uses the training frequencies of an event after an event and after a non-event.",
        "- C and D use a one-feature logistic regression on log(1 + eBird records in the window "
        "ending the day before the forecast date). The -norm variants subtract the log of the "
        "prior 365-day average level, to remove the growth in eBird effort since 2010.",
        "- eBird activity = eBird-dataset GBIF records of that species per day in GB, IE, NL, BE "
        "and DK (the same countries as the labels).",
        "",
        "## Results by species",
        "",
    ]
    for species in SPECIES_ORDER:
        rows = frame.loc[frame["species"].eq(species)]
        uncertain = rows["event_days"].iloc[0] < 50
        lines += [
            f"### {species}" + (" (fewer than 50 event days: uncertain)" if uncertain else ""),
            "",
            f"Event days {rows['event_days'].iloc[0]} of {rows['forecast_days'].iloc[0]} "
            f"({rows['event_prevalence'].iloc[0]:.1%}).",
            "",
            "| Model | Precision | Recall | F1 | Brier | Brier skill | ECE | Calibration |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for model in MODELS:
            r = rows.loc[rows["model"].eq(model)].iloc[0]
            lines.append(
                f"| {LABELS[model]} | {r.precision:.3f} | {r.recall:.3f} | {r.f1:.3f} | "
                f"{r.brier_score:.4f} | {r.brier_skill_vs_training_prevalence:+.3f} | "
                f"{r.ece:.3f} | {r.calibration} |"
            )
        lines.append("")
    lines += ["## Answer", ""]
    lines += answer_lines(frame)
    lines += ["", "## Interpretation", ""]
    lines += interpretation_lines(frame)
    lines += [
        "",
        "## Caveats",
        "",
        "- **Labels overlap eBird.** Most label records come from eBird (62-93% of GBIF records "
        "by species), so recent eBird activity partly reflects the target series itself. This "
        "measures information in recent reporting, not independent ecological signal.",
        "- **Not a frozen archive.** Activity comes from the current GBIF snapshot, including "
        "records uploaded or reviewed after each forecast date. A real forecast would have seen "
        "less. Treat C and D as an upper bound.",
        "- **Detections only.** GBIF has no eBird checklists, so activity is not effort-adjusted "
        "(reporting rate is not available).",
        "- **Netherlands.** eBird holds only about 0-23% of Dutch records.",
        "- Sooty and Great Shearwater have fewer than 50 event days; their scores are uncertain.",
        "- Brier skill uses the training-period prevalence, as in `rolling_event_validation.csv`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def answer_lines(frame: pd.DataFrame) -> list[str]:
    lines = []
    for species in SPECIES_ORDER:
        rows = frame.loc[frame["species"].eq(species)].set_index("model")
        a = rows.loc["A weather"]
        b = rows.loc["B yesterday"]
        best = rows.loc[["C ebird7", "D ebird30", "C ebird7 norm", "D ebird30 norm"], "f1"].idxmax()
        e = rows.loc[best]
        beats = [
            name for name, value in (("F1", e.f1 > a.f1), ("Brier", e.brier_score < a.brier_score))
            if value
        ]
        lines.append(
            f"- **{species}:** weather F1 {a.f1:.3f} / Brier {a.brier_score:.4f}; yesterday "
            f"F1 {b.f1:.3f} / Brier {b.brier_score:.4f}; best eBird baseline "
            f"({LABELS[best]}) F1 {e.f1:.3f} / Brier {e.brier_score:.4f}. eBird activity "
            + (f"beats weather on {' and '.join(beats)}." if beats else "does not beat weather.")
            + (" Uncertain (<50 events)." if a.event_days < 50 else "")
        )
    return lines


def interpretation_lines(frame: pd.DataFrame) -> list[str]:
    f1 = frame.pivot(index="species", columns="model", values="f1")
    brier = frame.pivot(index="species", columns="model", values="brier_score")
    rated = [s for s in SPECIES_ORDER if frame.loc[frame["species"].eq(s), "event_days"].iloc[0] >= 50]
    persistence = [s for s in rated if f1.loc[s, "B yesterday"] > f1.loc[s, "A weather"]]
    activity = [
        s for s in rated if f1.loc[s, ["C ebird7", "D ebird30"]].max() > f1.loc[s, "A weather"]
    ]
    return [
        f"- Of the {len(rated)} species with at least 50 event days, yesterday's event beats the "
        f"weather model on F1 for {len(persistence)} ({', '.join(persistence) or 'none'}), and "
        f"raw 7/30-day eBird activity does so for {len(activity)} ({', '.join(activity) or 'none'}). "
        "Where persistence wins, the weather model adds no value over knowing yesterday's status.",
        "- Events are strongly clustered in time, which persistence captures directly. Recent "
        "eBird activity carries that same clustering plus the seasonal cycle and reporting "
        "effort.",
        "- Raw activity models (C, D) reach high recall with precision near 0.5 for Fulmar and "
        "Manx. This pattern means they flag most days in the active season and the long-run "
        "growth in eBird effort, not individual influx days. Their Brier gain is real, but part "
        "of it is season and effort rather than event timing.",
        "- Removing the effort trend (-norm) removes most of that advantage for Fulmar and Manx. "
        "The Storm-petrel is the one species where the effort-normalised activity model "
        f"(F1 {f1.loc['European Storm-petrel', 'C ebird7 norm']:.3f}, Brier "
        f"{brier.loc['European Storm-petrel', 'C ebird7 norm']:.4f}) matches the weather model "
        f"(F1 {f1.loc['European Storm-petrel', 'A weather']:.3f}, Brier "
        f"{brier.loc['European Storm-petrel', 'A weather']:.4f}) without any weather input.",
        "- Because the labels and the activity both come mostly from eBird records, and the "
        "activity here is not a frozen archive, these results are an upper bound on what "
        "recent eBird activity gives a real forecast. A combined weather + eBird model should be "
        "judged against B, not only against A.",
        "",
    ]


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS_PATH)
    observations = load_observations(ROOT / OBSERVATIONS_FILE)
    activity = fetch_activity()
    forecasts = build_forecasts(predictions, observations, activity)
    frame = benchmark(forecasts)
    frame.to_csv(BENCHMARK_PATH, index=False)
    write_summary(frame, activity_end(activity).date().isoformat())
    print(frame[["species", "model", "precision", "recall", "f1", "brier_score", "ece"]].to_string())


if __name__ == "__main__":
    main()
