"""Pathway study: do departure x transport weather combinations explain eastern vagrant arrivals
better than source-region weather alone? Exploratory; production models are untouched.

Models are evaluated out of sample with leave-one-autumn-out logistic regression. Every model includes a
seasonal baseline (day-of-year terms) so the reported gain is the added value of weather.
Dutch weather comes from the same ERA5 archive (one point) and is cached once.
"""

from __future__ import annotations

import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from . import eastern_departure_weather as edw

ROOT = edw.ROOT
OUT = edw.OUT
DUTCH_CACHE = ROOT / "data/cache/dutch_era5_weather_daily.csv"
CSV_PATH = OUT / "pathway_analysis.csv"
MD_PATH = OUT / "pathway_summary.md"
LAGS = (1, 2, 3, 4, 5)
ALL_LAGS = "1-5"
BASE_FEATURES = ["cold_front", "tailwind", "crosswind", "pressure_change", "precip_anomaly"]
DEPARTURE_REGIONS = list(edw.REGIONS)
DUTCH = "Netherlands"
MODELS = ["A departure alone", "B Dutch alone", "C departure + Dutch", "D departure x transport"]
SEASONAL = "seasonal baseline"
C_REG = 0.05
BOOTSTRAPS = 300


def fetch_dutch(cache: Path = DUTCH_CACHE) -> pd.DataFrame:
    if cache.is_file():
        return pd.read_csv(cache, parse_dates=["date"])
    frames = []
    for year in range(int(edw.START[:4]), int(edw.END[:4]) + 1):
        payload = edw._request([edw.NETHERLANDS], f"{max(edw.START, f'{year}-01-01')}", f"{min(edw.END, f'{year}-12-31')}")[0]
        frames.append(pd.DataFrame(payload["daily"]).rename(columns={"time": "date"}).assign(region=DUTCH))
    weather = pd.concat(frames, ignore_index=True)
    weather["date"] = pd.to_datetime(weather["date"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(cache, index=False)
    return weather


def wind_components(speed: pd.Series, direction_from: pd.Series, track: float) -> tuple[pd.Series, pd.Series]:
    """Along-track (tailwind) and absolute cross-track wind for a travel bearing."""
    angle = np.radians((direction_from + 180) % 360 - track)
    return speed * np.cos(angle), (speed * np.sin(angle)).abs()


def pathway_features(daily: pd.DataFrame, track: float) -> pd.DataFrame:
    tail, cross = wind_components(daily["speed"], daily["direction_from"], track)
    return pd.DataFrame({
        "cold_front": daily["temperature"].diff().le(edw.COLD_FRONT_DROP_C).astype(float),
        "tailwind": edw.climatology_anomaly(tail),
        "crosswind": edw.climatology_anomaly(cross),
        "pressure_change": daily["pressure"].diff(),
        "precip_anomaly": edw.climatology_anomaly(daily["precipitation"]),
    })


def build_features(weather: pd.DataFrame, dutch: pd.DataFrame) -> pd.DataFrame:
    frames = {}
    for region, box in edw.REGIONS.items():
        track = edw.bearing(edw.region_centre(box), edw.NETHERLANDS)
        frames[region] = pathway_features(edw.region_daily(weather, region), track)
    # In the Netherlands "toward Western Europe" is easterly flow, i.e. a track toward the west.
    frames[DUTCH] = pathway_features(edw.region_daily(dutch, DUTCH), 270.0)
    out = pd.concat(frames, axis=1)
    return (out - out.mean()) / out.std()


def design(features: pd.DataFrame, model: str, lags: tuple[int, ...]) -> pd.DataFrame:
    """Lagged predictor matrix for one model; lag k means weather observed k days before the target."""
    cols: dict[str, pd.Series] = {}
    for lag in lags:
        for region, name in product(DEPARTURE_REGIONS, BASE_FEATURES):
            if model in ("A", "C", "D"):
                cols[f"{region}:{name}@{lag}"] = features[(region, name)].shift(lag)
        for name in BASE_FEATURES:
            if model in ("B", "C"):
                cols[f"{DUTCH}:{name}@{lag}"] = features[(DUTCH, name)].shift(lag)
        if model == "D":
            arrival = features[(DUTCH, "tailwind")].shift(1)
            for region in DEPARTURE_REGIONS:
                tail = features[(region, "tailwind")].shift(lag)
                for name in ("cold_front", "pressure_change", "precip_anomaly"):
                    cols[f"{region}:{name}x tailwind@{lag}"] = features[(region, name)].shift(lag) * tail
                cols[f"{region}:tailwind x Dutch easterly@{lag}"] = tail * arrival
    return pd.DataFrame(cols)


def seasonal_terms(index: pd.DatetimeIndex) -> pd.DataFrame:
    phase = 2 * np.pi * (index.dayofyear - 258) / 66
    return pd.DataFrame({"s1": np.sin(phase), "c1": np.cos(phase)}, index=index)


def cross_validated_scores(x: pd.DataFrame, y: pd.Series, seed: int = 0) -> pd.Series:
    """Leave-one-autumn-out predicted probabilities."""
    scores = pd.Series(np.nan, index=y.index)
    years = y.index.year
    for year in np.unique(years):
        test = years == year
        train = ~test
        if y[train].nunique() < 2:
            continue
        scaler = StandardScaler().fit(x[train])
        model = LogisticRegression(C=C_REG, max_iter=500, class_weight="balanced", random_state=seed)
        model.fit(scaler.transform(x[train]), y[train])
        scores[test] = model.predict_proba(scaler.transform(x[test]))[:, 1]
    return scores


def year_block_gain(y: pd.Series, base: pd.Series, test: pd.Series, draws: int = BOOTSTRAPS, seed: int = 0) -> tuple[float, float, float]:
    """Delta AUC (weather model - seasonal baseline) with a bootstrap over autumns."""
    frame = pd.DataFrame({"y": y, "b": base, "t": test})
    groups = [g for _, g in frame.groupby(frame.index.year)]
    rng = np.random.default_rng(seed)
    gains = []
    for _ in range(draws):
        sample = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        if sample["y"].nunique() == 2:
            gains.append(roc_auc_score(sample["y"], sample["t"]) - roc_auc_score(sample["y"], sample["b"]))
    point = roc_auc_score(frame["y"], frame["t"]) - roc_auc_score(frame["y"], frame["b"])
    low, high = np.percentile(gains, [2.5, 97.5]) if gains else (np.nan, np.nan)
    return float(point), float(low), float(high)


def evaluate(features: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    warnings.filterwarnings("ignore")
    for target in counts.columns:
        flags = edw.event_flags(counts[target])
        flags = flags.loc[flags.index >= features.index.min() + pd.Timedelta(days=max(LAGS))]
        y = flags.astype(int)
        season = seasonal_terms(y.index)
        base = cross_validated_scores(season, y)
        base_auc = roc_auc_score(y, base)
        for lag_label, lags in [*[(str(lag), (lag,)) for lag in LAGS], (ALL_LAGS, LAGS)]:
            for model in MODELS:
                letter = model[0]
                x = design(features, letter, lags).reindex(y.index)
                x = pd.concat([season, x], axis=1)
                valid = x.notna().all(axis=1)
                yy, xx, bb = y[valid], x[valid], base[valid]
                scores = cross_validated_scores(xx, yy)
                gain, low, high = year_block_gain(yy, bb, scores)
                rows.append({
                    "species": target, "model": model, "lag_days": lag_label, "n_predictors": x.shape[1] - 2,
                    "event_days": int(yy.sum()), "n_days": len(yy), "auc": float(roc_auc_score(yy, scores)),
                    "seasonal_baseline_auc": float(base_auc), "auc_gain": gain, "gain_ci_low": low,
                    "gain_ci_high": high, "uncertain": int(yy.sum()) < edw.MIN_EVENT_DAYS,
                })
    return pd.DataFrame(rows)


def summarise(table: pd.DataFrame) -> pd.DataFrame:
    """Mean AUC gain per model over reliable species, per lag setting."""
    reliable = table.loc[~table["uncertain"]]
    return reliable.pivot_table(index="lag_days", columns="model", values="auc_gain", aggfunc="mean")


def lag_table(table: pd.DataFrame) -> list[str]:
    wide = summarise(table)[MODELS]
    rows = ["| Lag | " + " | ".join(MODELS) + " |", "|---|" + "---:|" * len(MODELS)]
    rows += [f"| {lag} | " + " | ".join(f"{v:+.3f}" for v in values) + " |" for lag, values in wide.iterrows()]
    return rows


def verdict(table: pd.DataFrame) -> dict[str, float | bool]:
    reliable = table.loc[~table["uncertain"] & table["lag_days"].ne(ALL_LAGS)]
    mean_gain = reliable.groupby("model")["auc_gain"].mean()
    wide = reliable.pivot_table(index=["species", "lag_days"], columns="model", values="auc_gain")
    beats = float((wide[MODELS[3]] > wide[MODELS[0]]).mean())
    significant = reliable.loc[reliable["gain_ci_low"] > 0]
    return {"mean": mean_gain.to_dict(), "interaction_beats_departure_share": beats,
            "n_significant": len(significant), "significant": significant}


def write_report(table: pd.DataFrame, path: Path = MD_PATH) -> None:
    reliable = table.loc[~table["uncertain"]]
    info = verdict(table)
    mean = info["mean"]
    lines = [
        "# Eastern migration pathway study", "",
        "Question: do combinations of departure and transport weather explain eastern-vagrant arrivals in the "
        "Netherlands better than source-region weather alone?", "",
        "## Method", "",
        "- Regions: Finland, Baltics, NW Russia (departure/transport) and the Netherlands (arrival), ERA5 daily data.",
        "- Features per region: cold-front indicator (24 h temperature drop of 4 C or more), tailwind toward the "
        "Netherlands (toward the west for Dutch weather, i.e. easterly flow), crosswind, 24 h pressure change and "
        "precipitation anomaly; wind and precipitation are day-of-year anomalies. All standardised.",
        "- Lags 1-5 days, each tested on its own and all together (`1-5`). Weather at lag k is observed k days before the target day.",
        "- Models: A departure alone; B Dutch alone; C departure + Dutch; D departure plus departure x transport interactions "
        "(front, pressure change and precipitation anomaly x regional tailwind; regional tailwind x Dutch easterly flow of the previous day).",
        "- Evaluation: leave-one-autumn-out L2 logistic regression (C=0.05, balanced), days 15 Sep-20 Nov 2011-2025, "
        "same event labels as the departure audit (top decile of Dutch records). Every model also has a seasonal term; "
        "`auc_gain` is the out-of-sample AUC above a seasonal-only baseline, with a 95% bootstrap interval over autumns.",
        "- Species with fewer than 30 event days are flagged uncertain and excluded from the summaries.", "",
        "## Mean AUC gain over seasonal baseline (reliable species, single lags 1-5)", "",
        "| Model | Mean gain |", "|---|---:|",
    ]
    lines += [f"| {m} | {mean[m]:+.3f} |" for m in MODELS]
    lines += ["", "## Mean AUC gain by lag setting", "", *lag_table(table), "",
              "## Best result per species", "",
              "| Species | Model | Lag | AUC | Gain | 95% CI |", "|---|---|---|---:|---:|---|"]
    for species, part in reliable.groupby("species"):
        top = part.loc[part["auc_gain"].idxmax()]
        lines.append(f"| {species} | {top['model']} | {top['lag_days']} | {top['auc']:.3f} | {top['auc_gain']:+.3f} | "
                     f"[{top['gain_ci_low']:+.3f}, {top['gain_ci_high']:+.3f}] |")
    lines += ["", "## Answer", ""]
    best = max(MODELS, key=lambda m: mean[m])
    lines.append(
        f"Interaction model D beats departure-alone model A in {info['interaction_beats_departure_share']:.0%} of "
        f"species-lag cells (mean gain {mean[MODELS[3]]:+.3f} vs {mean[MODELS[0]]:+.3f}). The best model on average is {best}. "
        f"{info['n_significant']} of {len(reliable[reliable['lag_days'].ne(ALL_LAGS)])} single-lag fits have a bootstrap interval above zero."
    )
    lines.append("")
    stronger = mean[MODELS[3]] > mean[MODELS[0]] + 0.01 and info["interaction_beats_departure_share"] > 0.6
    lines.append(
        "Pathway interactions carry a stronger signal than source weather alone." if stronger else
        "Pathway interactions do not carry a clearly stronger signal than source weather alone; extra predictors mostly add noise with ~100 event days."
    )
    lines += ["", "Caveats: exploratory, many comparisons, weak signals; Dutch weather is ERA5 at one point; event labels are "
              "GBIF record-count based, not validated influx labels; anomalies use whole-archive climatology (not cutoff-safe)."]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    from .build_eastern_vagrancy_dataset import load_all_occurrences

    features = build_features(edw.fetch_weather(), fetch_dutch())
    counts = edw.load_event_labels(load_all_occurrences(compact=True))
    table = evaluate(features, counts)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(CSV_PATH, index=False)
    write_report(table)
    print(summarise(table).round(3))


if __name__ == "__main__":
    main()
