from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import validation_dashboard as vd

COLUMNS = [
    "species", "year", "start_date", "end_date", "evaluated_days", "event_days",
    "event_prevalence", "precision", "recall", "f1", "brier_score",
    "baseline_brier_score",
]


def _write(path: Path) -> Path:
    rows = [
        ["A", "2015", "2015-01-01", "2015-12-31", 365, 10, 0.03, 1, 1, 1, 0.1, 0.2],
        ["Weak sp", "all", "2015-01-01", "2026-08-11", 4000, 400, 0.1, 0.3, 0.2, 0.24, 0.2, 0.15],
        ["Strong sp", "all", "2015-01-01", "2026-08-11", 4000, 900, 0.225, 0.5, 0.8, 0.615, 0.1, 0.17],
        ["Rare sp", "all", "2015-01-01", "2026-08-11", 4000, 15, 0.004, 0.0, 0.0, 0.0, 0.004, 0.004],
        ["Mid sp", "all", "2015-01-01", "2026-08-11", 4000, 800, 0.2, 0.55, 0.45, 0.5, 0.1, 0.17],
    ]
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return path


@pytest.mark.parametrize(
    ("f1", "label"),
    [(0.60, "Strong"), (0.599, "Moderate"), (0.40, "Moderate"), (0.399, "Weak")],
)
def test_f1_classification_boundaries(f1: float, label: str) -> None:
    assert vd.classify_f1(f1) == label


def test_overall_rows_sorted_by_f1_and_yearly_rows_excluded(tmp_path: Path) -> None:
    overall = vd.load_overall(_write(tmp_path / "v.csv"))
    assert overall["species"].tolist() == ["Strong sp", "Mid sp", "Weak sp", "Rare sp"]
    assert overall["performance"].tolist() == ["Strong", "Moderate", "Weak", "Weak"]


def test_missing_file_returns_none_and_bad_schema_raises(tmp_path: Path) -> None:
    assert vd.load_overall(tmp_path / "none.csv") is None
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"species": ["x"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        vd.load_overall(bad)


def test_interpretation_flags_rare_events_and_baseline(tmp_path: Path) -> None:
    overall = vd.load_overall(_write(tmp_path / "v.csv")).set_index("species")
    assert "strong ability" in vd.interpret(overall.loc["Strong sp"])
    rare = vd.interpret(overall.loc["Rare sp"])
    assert "Only 15 event days" in rare
    assert "did not beat" in vd.interpret(overall.loc["Weak sp"])


def _page_script(csv: str, md: str) -> None:
    from pathlib import Path

    from src import validation_dashboard as vd

    vd.show_validation_dashboard(Path(csv), Path(md))


def test_page_renders_with_and_without_outputs(tmp_path: Path) -> None:
    csv = _write(tmp_path / "v.csv")
    md = tmp_path / "s.md"
    md.write_text("# Summary", encoding="utf-8")
    at = AppTest.from_function(_page_script, args=(str(csv), str(md)), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "📈 Seabird Model Validation"
    assert [h.value for h in at.header] == [
        "Overall performance", "Performance interpretation", "Visualisations", "Species detail",
    ]
    assert at.dataframe[0].value["Species"].tolist()[0] == "Strong sp"
    assert "2015-01-01 through 2026-08-11" in at.markdown[0].value

    missing = AppTest.from_function(
        _page_script, args=(str(tmp_path / "x.csv"), str(md)), default_timeout=30
    ).run()
    assert not missing.exception
    assert "No validation results found" in missing.info[0].value
