"""Read-only dashboard for the latest seabird and migration benchmarks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SEABIRD_OUTPUT = ROOT / "outputs/seabird_validation"
DEPARTURE_OUTPUT = ROOT / "outputs/eastern_departure_weather"


def _show_csv(title: str, path: Path) -> None:
    st.subheader(title)
    if not path.is_file():
        st.info(f"Results are not available (`{path.name}` not found).")
        return
    st.dataframe(pd.read_csv(path), hide_index=True, width="stretch")


def _show_report(title: str, path: Path) -> None:
    if path.is_file():
        with st.expander(title):
            st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.caption(f"{title} is not available (`{path.name}` not found).")


def show_validation_benchmarks(
    seabird_output: Path = SEABIRD_OUTPUT,
    departure_output: Path = DEPARTURE_OUTPUT,
) -> None:
    st.title("🧪 Validation Benchmarks")
    st.caption(
        "Read-only view of saved benchmark outputs. This page does not retrain "
        "models or download data."
    )

    weather_tab, ebird_tab, departure_tab = st.tabs(
        ["Weather & persistence", "eBird baselines", "Eastern migration weather"]
    )
    with weather_tab:
        _show_csv(
            "Weather, persistence, and combined models",
            seabird_output / "weather_persistence_comparison.csv",
        )
        _show_report(
            "Full model comparison and caveats",
            seabird_output / "weather_persistence_summary.md",
        )
        _show_csv(
            "Weather vs persistence audit",
            seabird_output / "weather_vs_persistence.csv",
        )
        _show_report(
            "Full persistence audit and caveats",
            seabird_output / "weather_vs_persistence.md",
        )

    with ebird_tab:
        _show_csv(
            "eBird activity baselines",
            seabird_output / "ebird_baseline_benchmark.csv",
        )
        _show_report(
            "Benchmark results and interpretation",
            seabird_output / "ebird_baseline_summary.md",
        )
        _show_report(
            "eBird feature feasibility and leakage controls",
            seabird_output / "ebird_feasibility.md",
        )

    with departure_tab:
        _show_csv(
            "Departure-weather feature audit",
            departure_output / "departure_feature_audit.csv",
        )
        _show_report(
            "Feature audit method and findings",
            departure_output / "departure_feature_summary.md",
        )
        _show_csv(
            "Migration pathway analysis",
            departure_output / "pathway_analysis.csv",
        )
        _show_report(
            "Pathway method and findings",
            departure_output / "pathway_summary.md",
        )
