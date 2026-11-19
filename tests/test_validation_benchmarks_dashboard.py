from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


def _script(seabird_output: str, departure_output: str) -> None:
    from pathlib import Path

    from src.validation_benchmarks_dashboard import show_validation_benchmarks

    show_validation_benchmarks(Path(seabird_output), Path(departure_output))


def _repository_script() -> None:
    from src.validation_benchmarks_dashboard import show_validation_benchmarks

    show_validation_benchmarks()


def test_saved_benchmarks_render_in_streamlit_tabs(tmp_path: Path) -> None:
    seabird = tmp_path / "seabird"
    departure = tmp_path / "departure"
    seabird.mkdir()
    departure.mkdir()
    csv_files = {
        seabird: [
            "weather_persistence_comparison.csv",
            "weather_vs_persistence.csv",
            "ebird_baseline_benchmark.csv",
        ],
        departure: ["departure_feature_audit.csv", "pathway_analysis.csv"],
    }
    for directory, names in csv_files.items():
        for name in names:
            pd.DataFrame({"species": ["Test species"], "score": [0.5]}).to_csv(
                directory / name, index=False
            )
    report_files = {
        seabird: [
            "weather_persistence_summary.md",
            "weather_vs_persistence.md",
            "ebird_baseline_summary.md",
            "ebird_feasibility.md",
        ],
        departure: ["departure_feature_summary.md", "pathway_summary.md"],
    }
    for directory, names in report_files.items():
        for name in names:
            (directory / name).write_text("# Test report", encoding="utf-8")

    at = AppTest.from_function(
        _script, args=(str(seabird), str(departure)), default_timeout=30
    ).run()

    assert not at.exception
    assert at.title[0].value == "🧪 Validation Benchmarks"
    assert [tab.label for tab in at.tabs] == [
        "Weather & persistence",
        "eBird baselines",
        "Eastern migration weather",
    ]
    assert len(at.dataframe) == 5
    assert all(frame.value["species"].tolist() == ["Test species"] for frame in at.dataframe)
    assert len(at.get("expander")) == 6


def test_repository_benchmarks_render() -> None:
    at = AppTest.from_function(_repository_script, default_timeout=30).run()

    assert not at.exception
    assert len(at.dataframe) == 5
    assert all(not frame.value.empty for frame in at.dataframe)


def test_missing_benchmark_outputs_show_notices(tmp_path: Path) -> None:
    at = AppTest.from_function(
        _script, args=(str(tmp_path / "seabird"), str(tmp_path / "departure"))
    ).run()

    assert not at.exception
    assert len(at.info) == 5
    assert len(at.caption) >= 1
