"""Probability calibration analysis of rolling seabird event predictions.

Reads the persisted raw one-day-ahead probabilities; nothing is retrained and
no probability is recalibrated or thresholded.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/seabird_validation"
PREDICTIONS_PATH = OUT / "rolling_event_predictions.csv"
METRICS_PATH = OUT / "calibration_metrics.csv"
BINS_PATH = OUT / "calibration_bins.csv"
SUMMARY_PATH = OUT / "calibration_summary.md"
BIN_EDGES = np.linspace(0.0, 1.0, 11)
# Tolerances for the verdicts: ECE and mean signed gap (predicted - observed).
WELL_CALIBRATED_ECE = 0.03
MIN_EVENTS_FOR_VERDICT = 20
SPECIES_ORDER = [
    "Northern Fulmar",
    "Manx Shearwater",
    "European Storm-petrel",
    "Sooty Shearwater",
    "Great Shearwater",
]


def assign_bins(probability: pd.Series) -> pd.Series:
    """Bin index 0-9 for [0,.1), ..., [.9,1.0]; probability 1.0 joins the last bin."""
    return pd.Series(
        np.minimum((probability.to_numpy() * 10).astype(int), 9), index=probability.index
    )


def calibration_bins(probability: pd.Series, actual: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame(
        {"p": probability.to_numpy(float), "y": actual.to_numpy(float)}
    )
    frame["bin"] = assign_bins(frame["p"]).to_numpy()
    rows = []
    for index in range(10):
        part = frame.loc[frame["bin"].eq(index)]
        last = index == 9
        rows.append(
            {
                "bin": f"{BIN_EDGES[index]:.2f}-{BIN_EDGES[index + 1]:.2f}",
                "bin_lower": BIN_EDGES[index],
                "bin_upper": BIN_EDGES[index + 1],
                "interval": "closed" if last else "left-closed",
                "forecast_count": len(part),
                "mean_predicted_probability": part["p"].mean() if len(part) else np.nan,
                "observed_event_frequency": part["y"].mean() if len(part) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def calibration_metrics(probability: pd.Series, actual: pd.Series) -> dict[str, float]:
    """Brier decomposition (Murphy): BS = reliability - resolution + uncertainty.

    The decomposition is exact only when forecasts within a bin are identical;
    with binned forecasts it differs by a within-bin variance term, reported as
    ``decomposition_residual``.
    """
    p = probability.to_numpy(float)
    y = actual.to_numpy(float)
    n = len(p)
    if n == 0:
        raise ValueError("No forecasts to evaluate.")
    base_rate = y.mean()
    brier = float(np.mean((p - y) ** 2))
    uncertainty = float(base_rate * (1 - base_rate))
    bins = calibration_bins(probability, actual)
    populated = bins.loc[bins["forecast_count"].gt(0)]
    weight = populated["forecast_count"].to_numpy() / n
    gap = (
        populated["mean_predicted_probability"] - populated["observed_event_frequency"]
    ).to_numpy()
    reliability = float(np.sum(weight * gap**2))
    resolution = float(
        np.sum(weight * (populated["observed_event_frequency"].to_numpy() - base_rate) ** 2)
    )
    ece = float(np.sum(weight * np.abs(gap)))
    mce = float(np.max(np.abs(gap)))
    prevalence_brier = uncertainty  # constant forecast of the pooled event rate
    return {
        "forecast_days": n,
        "event_days": int(y.sum()),
        "event_prevalence": float(base_rate),
        "mean_predicted_probability": float(p.mean()),
        "brier_score": brier,
        "prevalence_baseline_brier": prevalence_brier,
        "brier_skill_score": (
            float(1 - brier / prevalence_brier) if prevalence_brier > 0 else np.nan
        ),
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "decomposition_residual": float(brier - (reliability - resolution + uncertainty)),
        "ece": ece,
        "mce": mce,
        "signed_calibration_gap": float(p.mean() - base_rate),
        "weighted_slope_gap": _slope_gap(populated),
    }


def _slope_gap(populated: pd.DataFrame) -> float:
    """Weighted regression slope of observed frequency on predicted probability.

    Slope < 1 means high forecasts verify less often than stated (overconfident).
    """
    if len(populated) < 2:
        return np.nan
    x = populated["mean_predicted_probability"].to_numpy(float)
    y = populated["observed_event_frequency"].to_numpy(float)
    w = populated["forecast_count"].to_numpy(float)
    if np.ptp(x) == 0:
        return np.nan
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    return float(np.sum(w * (x - mx) * (y - my)) / np.sum(w * (x - mx) ** 2))


def classify(metrics: dict[str, float]) -> str:
    if metrics.get("event_days", MIN_EVENTS_FOR_VERDICT) < MIN_EVENTS_FOR_VERDICT:
        return "insufficient events"
    slope = metrics["weighted_slope_gap"]
    if metrics["ece"] <= WELL_CALIBRATED_ECE and (np.isnan(slope) or 0.8 <= slope <= 1.2):
        return "well calibrated"
    if not np.isnan(slope) and slope < 1:
        return "overconfident"
    if not np.isnan(slope) and slope > 1:
        return "underconfident"
    return "miscalibrated"


def analyse(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_rows, bin_frames = [], []
    for species in SPECIES_ORDER:
        part = predictions.loc[predictions["species"].eq(species)]
        if part.empty:
            raise ValueError(f"No predictions for {species}.")
        actual = part["actual_event"].astype(int)
        metrics = calibration_metrics(part["probability"], actual)
        metrics["start_date"] = part["date"].min()
        metrics["end_date"] = part["date"].max()
        metrics["verdict"] = classify(metrics)
        metric_rows.append({"species": species, **metrics})
        bin_frames.append(
            calibration_bins(part["probability"], actual).assign(species=species)
        )
    bins = pd.concat(bin_frames, ignore_index=True)
    first = ["species"]
    return (
        pd.DataFrame(metric_rows),
        bins[first + [c for c in bins.columns if c not in first]],
    )


def write_figures(predictions: pd.DataFrame, bins: pd.DataFrame, out: Path = OUT) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 5, figsize=(22, 4.5), sharex=True, sharey=True)
    for ax, species in zip(axes, SPECIES_ORDER):
        part = bins.loc[bins["species"].eq(species) & bins["forecast_count"].gt(0)]
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
        ax.plot(
            part["mean_predicted_probability"],
            part["observed_event_frequency"],
            "o-",
            label="model",
        )
        ax.set_title(species)
        ax.set_xlabel("Mean predicted probability")
    axes[0].set_ylabel("Observed event frequency")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(out / "calibration_reliability.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(1, 5, figsize=(22, 4.5), sharex=True)
    for ax, species in zip(axes, SPECIES_ORDER):
        part = predictions.loc[predictions["species"].eq(species), "probability"]
        ax.hist(part, bins=BIN_EDGES, color="#4477aa")
        ax.set_yscale("log")
        ax.set_title(species)
        ax.set_xlabel("Predicted probability")
    axes[0].set_ylabel("Forecast days (log)")
    fig.tight_layout()
    fig.savefig(out / "calibration_histograms.png", dpi=110)
    plt.close(fig)


def _pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.1%}"


def answer_lines(metrics: pd.DataFrame) -> list[str]:
    under = metrics.loc[metrics["verdict"].eq("underconfident"), "species"].tolist()
    over = metrics.loc[metrics["verdict"].eq("overconfident"), "species"].tolist()
    thin = metrics.loc[metrics["verdict"].eq("insufficient events"), "species"].tolist()
    return [
        "**No: a stated probability of X% should not be read as an X% chance of an",
        "influx event, for any of the five species.** Ranking is informative but the",
        "absolute values are not calibrated:",
        "",
        f"- Underconfident (observed event frequency exceeds the stated probability): {', '.join(under) or 'none'}.",
        "  Event rates rise with the forecast, but a 10-20% forecast verified roughly",
        "  22-42% of the time, so read these as lower bounds. Northern Fulmar has",
        "  negative Brier skill and little resolution, so even the ordering is weak.",
        f"- Overconfident (stated probability exceeds observed frequency): {', '.join(over) or 'none'}.",
        "  Sooty Shearwater forecasts of 10-60% verified 1-12% of the time, and",
        "  its Brier score is worse than a constant prevalence forecast.",
        f"- Insufficient events for a verdict: {', '.join(thin) or 'none'}.",
        "  Great Shearwater has too few events to say anything beyond that its",
        "  near-zero forecasts are close to its near-zero base rate.",
        "",
        "European Storm-petrel is the closest to usable (ECE about 0.05, positive",
        "skill), and Manx Shearwater has the best resolution, but both still",
        "understate event frequency at 10-50%. Quoting these raw values as",
        "percentage chances would mislead. Any such use would need a separate,",
        "out-of-sample recalibration step, which this analysis deliberately did not",
        "perform. Event labels are GBIF record counts against a per-year P90",
        "threshold, so the 'event frequency' itself depends on reporting effort.",
    ]


def write_summary(metrics: pd.DataFrame, bins: pd.DataFrame, path: Path = SUMMARY_PATH) -> None:
    lines = [
        "# Seabird probability calibration",
        "",
        "## Method",
        "",
        "Raw one-day-ahead probabilities from the rolling strict-cutoff event",
        "validation (annual expanding-window fits, "
        f"{metrics['start_date'].min()} through {metrics['end_date'].max()}) are",
        "pooled per species and compared with aligned influx-event labels. No model",
        "was refit for this analysis, thresholds are unchanged, and probabilities",
        "are neither recalibrated nor thresholded. Ten equal-width bins are used;",
        "the last bin includes 1.00. ECE and MCE are the count-weighted and maximum",
        "absolute gap between mean predicted probability and observed frequency",
        "over non-empty bins. The Brier decomposition (reliability, resolution,",
        "uncertainty) uses the same bins and so carries a small within-bin residual",
        "(`decomposition_residual` in the CSV). Brier Skill Score is relative to a",
        "constant forecast of the pooled event prevalence, which is an in-sample,",
        "hindsight baseline and therefore a demanding one (the annual",
        "training-prevalence baseline in the rolling validation is the fairer",
        "operational comparison). Labels are GBIF record counts at or above each",
        "year's training P90 threshold, so event definitions carry reporting",
        "effort and are not proven absence.",
        "",
        "## Metrics",
        "",
        "| Species | Days | Events | Prevalence | Mean forecast | Brier | BSS vs prevalence | Reliability | Resolution | Uncertainty | ECE | MCE | Slope | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in metrics.itertuples(index=False):
        lines.append(
            f"| {r.species} | {r.forecast_days} | {r.event_days} | {_pct(r.event_prevalence)} | "
            f"{_pct(r.mean_predicted_probability)} | {r.brier_score:.4f} | "
            f"{r.brier_skill_score:+.3f} | {r.reliability:.4f} | {r.resolution:.4f} | "
            f"{r.uncertainty:.4f} | {r.ece:.3f} | {r.mce:.3f} | "
            f"{r.weighted_slope_gap:.2f} | {r.verdict} |"
        )
    lines += [
        "",
        "Slope is the count-weighted regression slope of observed frequency on",
        "predicted probability across bins: below 1 means high forecasts verify",
        "less often than stated (overconfident), above 1 means they verify more",
        "often (underconfident). A species is called well calibrated only if",
        f"ECE <= {WELL_CALIBRATED_ECE} and slope is within 0.8-1.2.",
        "",
        "## Calibration bins",
        "",
    ]
    for species in SPECIES_ORDER:
        lines += [
            f"### {species}",
            "",
            "| Bin | Forecasts | Mean predicted | Observed frequency |",
            "|---|---:|---:|---:|",
        ]
        part = bins.loc[bins["species"].eq(species)]
        for r in part.itertuples(index=False):
            lines.append(
                f"| {r.bin} | {r.forecast_count} | {_pct(r.mean_predicted_probability)} | "
                f"{_pct(r.observed_event_frequency)} |"
            )
        lines.append("")
    groups = {
        label: metrics.loc[metrics["verdict"].eq(label), "species"].tolist()
        for label in (
            "well calibrated",
            "overconfident",
            "underconfident",
            "miscalibrated",
            "insufficient events",
        )
    }
    lines += ["## Classification", ""]
    for label, names in groups.items():
        lines.append(f"- {label.capitalize()}: {', '.join(names) or 'none'}")
    lines += [
        "",
        "## Answer",
        "",
        *answer_lines(metrics),
        "",
        "Figures: `calibration_reliability.png`, `calibration_histograms.png`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS_PATH, parse_dates=["date"])
    metrics, bins = analyse(predictions)
    metrics = metrics.assign(
        start_date=metrics["start_date"].dt.date.astype(str),
        end_date=metrics["end_date"].dt.date.astype(str),
    )
    metrics.to_csv(METRICS_PATH, index=False)
    bins.to_csv(BINS_PATH, index=False)
    write_figures(predictions, bins)
    write_summary(metrics, bins)
    print(metrics.drop(columns=["start_date", "end_date"]).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
