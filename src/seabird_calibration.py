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
MIN_EVENTS_UNCERTAIN = 50
STRONG_ECE = 0.10
STRONG_SLOPE_GAP = 0.5
OPERATING_THRESHOLD = 0.20
CHECK_PROBABILITIES = (0.20, 0.50, 0.80)
CHECK_HALF_WIDTH = 0.05
MIN_CHECK_FORECASTS = 20
THRESHOLD_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
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
    """Five-level calibration class from ECE and the reliability slope.

    Over/underconfident refer to stated probabilities being higher/lower than
    the observed event frequency (slope below/above 1). Strength is "strongly"
    when ECE >= 0.10 or the slope is at least 0.5 from 1.
    """
    slope = metrics["weighted_slope_gap"]
    ece = metrics["ece"]
    if ece <= WELL_CALIBRATED_ECE and (np.isnan(slope) or abs(slope - 1) <= 0.2):
        return "well calibrated"
    if np.isnan(slope) or slope == 1:
        return "strongly overconfident" if ece >= STRONG_ECE else "mildly overconfident"
    strong = ece >= STRONG_ECE or abs(slope - 1) >= STRONG_SLOPE_GAP
    direction = "overconfident" if slope < 1 else "underconfident"
    return f"{'strongly' if strong else 'mildly'} {direction}"


def probability_check(
    probability: pd.Series, actual: pd.Series, target: float,
    half_width: float = CHECK_HALF_WIDTH,
) -> dict[str, float]:
    """Observed event frequency among forecasts within target +/- half_width."""
    mask = (probability - target).abs() <= half_width + 1e-12
    count = int(mask.sum())
    return {
        "target": target,
        "forecast_count": count,
        "observed_event_frequency": float(actual[mask].mean()) if count else np.nan,
    }


def threshold_table(probability: pd.Series, actual: pd.Series) -> pd.DataFrame:
    """Diagnostic only: precision/recall/F1 at fixed cutoffs. Nothing is changed."""
    y = actual.to_numpy(bool)
    rows = []
    for cutoff in THRESHOLD_GRID:
        flagged = probability.to_numpy() >= cutoff - 1e-12
        tp = int((flagged & y).sum())
        fp = int((flagged & ~y).sum())
        fn = int((~flagged & y).sum())
        rows.append(
            {
                "threshold": cutoff,
                "flagged_days": int(flagged.sum()),
                "precision": tp / (tp + fp) if tp + fp else 0.0,
                "recall": tp / (tp + fn) if tp + fn else 0.0,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
            }
        )
    return pd.DataFrame(rows)


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
        metrics["uncertain"] = metrics["event_days"] < MIN_EVENTS_UNCERTAIN
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


def slug(species: str) -> str:
    return species.lower().replace(" ", "_").replace("-", "_")


def write_figures(predictions: pd.DataFrame, bins: pd.DataFrame, out: Path = OUT) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for species in SPECIES_ORDER:
        part = bins.loc[bins["species"].eq(species)]
        used = part.loc[part["forecast_count"].gt(0)]
        fig, (ax, counts) = plt.subplots(
            2, 1, figsize=(5.5, 6.5), sharex=True, height_ratios=(3, 1)
        )
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
        ax.plot(
            used["mean_predicted_probability"], used["observed_event_frequency"],
            "o-", label="Model",
        )
        ax.set_ylabel("Observed event frequency")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend(loc="upper left")
        events = int(
            predictions.loc[predictions["species"].eq(species), "actual_event"].sum()
        )
        flag = " (uncertain: <50 events)" if events < MIN_EVENTS_UNCERTAIN else ""
        ax.set_title(f"{species}{flag}")
        centres = (part["bin_lower"] + part["bin_upper"]) / 2
        counts.bar(centres, part["forecast_count"], width=0.09, color="#888888")
        counts.set_yscale("log")
        counts.set_ylabel("Forecasts (log)")
        counts.set_xlabel("Predicted probability")
        for x, n in zip(centres, part["forecast_count"]):
            if n:
                counts.text(x, n, str(int(n)), ha="center", va="bottom", fontsize=7)
        fig.tight_layout()
        fig.savefig(out / f"calibration_reliability_{slug(species)}.png", dpi=110)
        plt.close(fig)

        rows = predictions.loc[predictions["species"].eq(species)]
        fig, ax = plt.subplots(figsize=(6, 4))
        for flagged, label, colour in ((True, "Event days", "#cc3311"), (False, "Non-event days", "#4477aa")):
            values = rows.loc[rows["actual_event"].astype(bool).eq(flagged), "probability"]
            ax.hist(
                values, bins=BIN_EDGES, weights=np.full(len(values), 1 / max(len(values), 1)),
                alpha=0.6, label=f"{label} (n={len(values)})", color=colour,
            )
        ax.axvline(OPERATING_THRESHOLD, color="k", ls=":", lw=1, label="0.20 cutoff")
        ax.set_xlabel("Forecast probability")
        ax.set_ylabel("Share of days in group")
        ax.set_title(f"{species}{flag}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / f"calibration_histogram_{slug(species)}.png", dpi=110)
        plt.close(fig)


def _pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.1%}"


def explain(row: pd.Series) -> str:
    text = (
        f"Mean forecast {_pct(row['mean_predicted_probability'])} against an event rate of "
        f"{_pct(row['event_prevalence'])}; ECE {row['ece']:.3f}, slope {row['weighted_slope_gap']:.2f}. "
    )
    if row["verdict"].endswith("underconfident"):
        text += "Observed frequency exceeds the stated probability, so forecasts are too low."
    elif row["verdict"].endswith("overconfident"):
        text += "Stated probabilities exceed the observed frequency, so forecasts are too high."
    else:
        text += "Stated probabilities match observed frequency closely."
    if row["uncertain"]:
        text += f" Only {int(row['event_days'])} event days: treat as uncertain."
    return text


def write_summary(
    metrics: pd.DataFrame,
    bins: pd.DataFrame,
    predictions: pd.DataFrame,
    path: Path = SUMMARY_PATH,
) -> None:
    metrics = metrics.copy()
    lines = [
        "# Seabird probability calibration",
        "",
        "## Method",
        "",
        "Raw one-day-ahead probabilities stored from the rolling strict-cutoff event",
        f"validation ({metrics['start_date'].min()} through {metrics['end_date'].max()}) are pooled per",
        "species and compared with the aligned influx-event labels described in",
        "`target_alignment_report.md` (record count at or above that year's",
        "training-only P90 threshold; not presence). No model was refit, thresholds",
        "are unchanged and probabilities are neither recalibrated nor thresholded",
        "for the calibration metrics. Ten equal-width bins are used and the last",
        "includes 1.00. ECE and MCE are the count-weighted and maximum absolute gap",
        "between mean forecast and observed frequency over non-empty bins. The Brier",
        "decomposition uses the same bins, so it has a small within-bin residual",
        "(`decomposition_residual`). Brier Skill Score is against a constant forecast",
        "of the pooled event prevalence (an in-sample hindsight baseline).",
        "",
        "Overconfident means stated probabilities exceed observed frequency;",
        "underconfident means they fall below it (reliability slope below/above 1).",
        "Well calibrated needs ECE <= 0.03 and a slope within 0.8-1.2; the strength",
        "is strong when ECE >= 0.10 or the slope is at least 0.5 from 1.",
        f"Species with fewer than {MIN_EVENTS_UNCERTAIN} event days are flagged uncertain and",
        "are reported separately.",
        "",
    ]
    columns = (
        "| Species | Days | Events | Prevalence | Mean forecast | Brier | BSS | Reliability | "
        "Resolution | Uncertainty | ECE | MCE | Slope | Class |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    ).split("\n")

    def metric_row(r) -> str:
        return (
            f"| {r.species} | {r.forecast_days} | {r.event_days} | {_pct(r.event_prevalence)} | "
            f"{_pct(r.mean_predicted_probability)} | {r.brier_score:.4f} | {r.brier_skill_score:+.3f} | "
            f"{r.reliability:.4f} | {r.resolution:.4f} | {r.uncertainty:.4f} | {r.ece:.3f} | "
            f"{r.mce:.3f} | {r.weighted_slope_gap:.2f} | {r.verdict} |"
        )

    ordinary = metrics.loc[~metrics["uncertain"]]
    rare = metrics.loc[metrics["uncertain"]]
    lines += ["## Metrics: species with at least 50 event days", "", *columns]
    lines += [metric_row(r) for r in ordinary.itertuples(index=False)]
    lines += [
        "",
        f"## Metrics: rare-event species (fewer than {MIN_EVENTS_UNCERTAIN} event days, uncertain)",
        "",
        *columns,
    ]
    lines += [metric_row(r) for r in rare.itertuples(index=False)]
    lines += [
        "",
        "With so few events, bin frequencies and the slope for these species swing",
        "on a handful of days. Their classes are provisional.",
        "",
        "## Interpretation by species",
        "",
    ]
    for r in metrics.itertuples(index=False):
        flag = " (uncertain)" if r.uncertain else ""
        lines.append(f"- **{r.species}** is {r.verdict}{flag}. {explain(pd.Series(r._asdict()))}")
    lines += ["", "## Calibration bins", ""]
    for species in SPECIES_ORDER:
        lines += [
            f"### {species}",
            "",
            "| Bin | Forecasts | Mean predicted | Observed frequency |",
            "|---|---:|---:|---:|",
        ]
        for r in bins.loc[bins["species"].eq(species)].itertuples(index=False):
            lines.append(
                f"| {r.bin} | {r.forecast_count} | {_pct(r.mean_predicted_probability)} | "
                f"{_pct(r.observed_event_frequency)} |"
            )
        lines.append("")

    lines += [
        "## Does a stated X% mean an X% chance?",
        "",
        f"Observed event frequency among forecasts within +/-{CHECK_HALF_WIDTH:.0%} of X "
        f"(`n/a` where fewer than {MIN_CHECK_FORECASTS} forecasts exist).",
        "",
        "| Species | " + " | ".join(f"Forecast ~{x:.0%}" for x in CHECK_PROBABILITIES) + " |",
        "|---|" + "---:|" * len(CHECK_PROBABILITIES),
    ]
    for species in SPECIES_ORDER:
        part = predictions.loc[predictions["species"].eq(species)]
        cells = []
        for x in CHECK_PROBABILITIES:
            c = probability_check(part["probability"], part["actual_event"].astype(int), x)
            cells.append(
                "n/a (n=%d)" % c["forecast_count"]
                if c["forecast_count"] < MIN_CHECK_FORECASTS
                else f"{_pct(c['observed_event_frequency'])} (n={c['forecast_count']})"
            )
        lines.append(f"| {species} | " + " | ".join(cells) + " |")
    lines += ["", *answer_lines(metrics), ""]

    lines += [
        "## Is the 0.20 threshold reasonable?",
        "",
        "Diagnostic only: the threshold was not changed. F1 at each cutoff:",
        "",
        "| Species | " + " | ".join(f"{t:.2f}" for t in THRESHOLD_GRID) + " | Best cutoff |",
        "|---|" + "---:|" * (len(THRESHOLD_GRID) + 1),
    ]
    for species in SPECIES_ORDER:
        part = predictions.loc[predictions["species"].eq(species)]
        table = threshold_table(part["probability"], part["actual_event"].astype(int))
        best = table.loc[table["f1"].idxmax()]
        lines.append(
            f"| {species} | " + " | ".join(f"{v:.3f}" for v in table["f1"]) + f" | {best['threshold']:.2f} |"
        )
    lines += [
        "",
        *threshold_lines(predictions),
        "",
        "Figures per species: `calibration_reliability_<species>.png` (with forecast",
        "counts per bin) and `calibration_histogram_<species>.png` (event versus",
        "non-event days).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def threshold_lines(predictions: pd.DataFrame) -> list[str]:
    near, away = [], []
    for species in SPECIES_ORDER:
        part = predictions.loc[predictions["species"].eq(species)]
        table = threshold_table(part["probability"], part["actual_event"].astype(int))
        events = int(part["actual_event"].sum())
        if events < MIN_EVENTS_UNCERTAIN:
            continue
        best = table.loc[table["f1"].idxmax()]
        at = table.loc[table["threshold"].eq(OPERATING_THRESHOLD)].iloc[0]
        gain = best["f1"] - at["f1"]
        (near if gain <= 0.02 else away).append(f"{species} (best {best['threshold']:.2f}, F1 gain {gain:+.3f})")
    return [
        f"- Within 0.02 F1 of the best cutoff at 0.20: {', '.join(near) or 'none'}.",
        f"- Clearly better at a different cutoff: {', '.join(away) or 'none'}.",
        "- Rare-event species (Sooty, Great Shearwater) have too few events for a",
        "  reliable cutoff choice; F1 stays very low at every cutoff.",
        "- Because probabilities are systematically low or high rather than",
        "  calibrated, 0.20 is best read as an alert level tuned to F1, not as a",
        "  20% event chance.",
    ]


def answer_lines(metrics: pd.DataFrame) -> list[str]:
    def names(pattern: str, uncertain: bool | None = None) -> str:
        sel = metrics["verdict"].str.contains(pattern)
        if uncertain is not None:
            sel &= metrics["uncertain"].eq(uncertain)
        return ", ".join(metrics.loc[sel, "species"]) or "none"

    return [
        "**No: for none of the five species can a stated X% be read as an X%",
        "chance of an influx event.** The probabilities rank days usefully for the",
        "three common species but their absolute level is off, and it differs by",
        "species:",
        "",
        f"- Trustworthy as probabilities: {names('well calibrated')}.",
        f"- Need calibration, underconfident (true chance higher than stated): {names('underconfident', False)}.",
        f"- Need calibration, overconfident (true chance lower than stated): {names('overconfident', False)}.",
        f"- Uncertain (<{MIN_EVENTS_UNCERTAIN} events): {names('.', True)}.",
        "",
        "European Storm-petrel is the closest to usable (mildly underconfident);",
        "Manx Shearwater and Northern Fulmar are strongly underconfident, and",
        "Northern Fulmar also lacks skill. Sooty Shearwater is strongly",
        "overconfident. Any use of the numbers as percentage chances would need a",
        "separate out-of-sample recalibration, which this analysis did not perform.",
    ]


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS_PATH, parse_dates=["date"])
    metrics, bins = analyse(predictions)
    metrics = metrics.assign(
        start_date=metrics["start_date"].dt.date.astype(str),
        end_date=metrics["end_date"].dt.date.astype(str),
    )
    metrics.to_csv(METRICS_PATH, index=False)
    bins.to_csv(BINS_PATH, index=False)
    for old in OUT.glob("calibration_*.png"):
        old.unlink()
    write_figures(predictions, bins)
    write_summary(metrics, bins, predictions)
    print(metrics[["species", "event_days", "ece", "weighted_slope_gap", "verdict", "uncertain"]].to_string(index=False))


if __name__ == "__main__":
    main()
