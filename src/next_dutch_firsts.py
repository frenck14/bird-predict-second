"""Atlantic Vagrant Watch: rank North American passerines by Dutch-rarity potential.

Corvo (Azores) and western-European records act as leading indicators. The
bundled record counts are ILLUSTRATIVE DEMO VALUES, not verified data. Real
sources plug in by implementing ``CandidateSource`` (see the stubs below).
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATA_FILE = ROOT / "data/next_dutch_firsts_demo.csv"

COUNTRIES = ("corvo", "ireland", "uk", "france", "spain", "portugal")
COUNTRY_LABELS = {
    "corvo": "Corvo",
    "ireland": "Ireland",
    "uk": "UK",
    "france": "France",
    "spain": "Spain",
    "portugal": "Portugal",
}
# Weights sum to 1. France/Spain/Portugal share a single component.
WEIGHTS = {
    "corvo": 0.30,
    "uk": 0.20,
    "ireland": 0.10,
    "iberia_france": 0.10,
    "recency": 0.10,
    "dutch_rarity": 0.10,
    "momentum": 0.10,
}
# Momentum points (max 20): recent presence per region plus a surge bonus.
MOMENTUM_POINTS = {"corvo": 8, "ireland": 5, "uk": 5, "surge": 2}
MOMENTUM_MAX = sum(MOMENTUM_POINTS.values())
MOMENTUM_WINDOW_YEARS = 2
HISTORY_YEARS = 20
RISING_FAST_THRESHOLD = 13
HIGH_MOMENTUM = 13
MODERATE_MOMENTUM = 8
# (max Dutch records, label, rarity bonus 0-1); fewer Dutch records = bigger bonus.
RARITY_CATEGORIES = (
    (0, NOT_RECORDED := "Not Recorded", 1.0),
    (5, "1-5 Records", 0.8),
    (10, "6-10 Records", 0.6),
    (25, "11-25 Records", 0.3),
    (None, "25+ Records", 0.0),
)
RARITY_LABELS = [label for _, label, _ in RARITY_CATEGORIES]
MEGA_RARITY_THRESHOLD = 10
FILTERS = (
    "All Species",
    "Potential Dutch Firsts",
    "Mega-Rarities (<10 Dutch records)",
    "Corvo Pipeline",
    "🚨 Long Overdue",
    "🚀 Rising Fast",
)
OVERDUE_YEARS = 10
RECENT_ATLANTIC_YEARS = 3


def rarity_category(dutch_record_count: int) -> str:
    for limit, label, _ in RARITY_CATEGORIES:
        if limit is None or dutch_record_count <= limit:
            return label
    raise AssertionError("unreachable")


def rarity_bonus(dutch_record_count: int) -> float:
    label = rarity_category(dutch_record_count)
    return next(bonus for _, name, bonus in RARITY_CATEGORIES if name == label)

RECENCY_WINDOW_YEARS = 10


@dataclass
class Candidate:
    common_name: str
    scientific_name: str
    corvo_records: int
    ireland_records: int
    uk_records: int
    france_records: int
    spain_records: int
    portugal_records: int
    dutch_record_count: int = 0
    corvo_latest_year: int | None = None
    ireland_latest_year: int | None = None
    uk_latest_year: int | None = None
    dutch_latest_year: int | None = None
    recent_records: int = 0
    momentum_score: int = 0
    momentum_regions: tuple[str, ...] = ()
    prediction_score: float = 0.0
    score_breakdown: dict[str, int] | None = None
    rationale: str = ""

    def records(self, country: str) -> int:
        return getattr(self, f"{country}_records")

    @property
    def dutch_status(self) -> str:
        return rarity_category(self.dutch_record_count)

    @property
    def latest_record_year(self) -> int | None:
        """Most recent Atlantic (pre-Netherlands) record year."""
        years = [y for y in (self.corvo_latest_year, self.ireland_latest_year, self.uk_latest_year) if y]
        return max(years) if years else None

    @property
    def momentum_label(self) -> str:
        if self.momentum_score >= HIGH_MOMENTUM:
            return "🚀 High Momentum"
        if self.momentum_score >= MODERATE_MOMENTUM:
            return "🔥 Moderate Momentum"
        return "○ Low Momentum"

    def is_surging(self) -> bool:
        """Recent-window records exceed the historical average for that window."""
        total = self.corvo_records + self.ireland_records + self.uk_records
        expected = total / HISTORY_YEARS * MOMENTUM_WINDOW_YEARS
        return self.recent_records > expected

    def years_since_last_dutch_record(self, today: date | None = None) -> int | None:
        if not self.dutch_latest_year:
            return None
        return (today or date.today()).year - self.dutch_latest_year

    def is_long_overdue(self, today: date | None = None) -> bool:
        """Dutch record 10+ years ago, yet still turning up on Corvo/Ireland/UK."""
        since = self.years_since_last_dutch_record(today)
        recent = self.latest_record_year
        return (
            since is not None
            and since >= OVERDUE_YEARS
            and recent is not None
            and (today or date.today()).year - recent <= RECENT_ATLANTIC_YEARS
        )

    @property
    def iberia_france_records(self) -> int:
        return self.france_records + self.spain_records + self.portugal_records


class CandidateSource(Protocol):
    """Anything that can supply candidate records (eBird, Corvo lists, ...)."""

    def load(self) -> list[Candidate]: ...


def _year(value: str) -> int | None:
    return int(value) if value else None


class CsvDemoSource:
    def __init__(self, path: Path = DEMO_DATA_FILE) -> None:
        self.path = path

    def load(self) -> list[Candidate]:
        with self.path.open(newline="", encoding="utf-8") as handle:
            return [
                Candidate(
                    common_name=row["common_name"],
                    scientific_name=row["scientific_name"],
                    corvo_records=int(row["corvo_records"]),
                    ireland_records=int(row["ireland_records"]),
                    uk_records=int(row["uk_records"]),
                    france_records=int(row["france_records"]),
                    spain_records=int(row["spain_records"]),
                    portugal_records=int(row["portugal_records"]),
                    dutch_record_count=int(row["dutch_record_count"]),
                    recent_records=int(row.get("recent_records") or 0),
                    corvo_latest_year=_year(row["corvo_latest_year"]),
                    ireland_latest_year=_year(row["ireland_latest_year"]),
                    uk_latest_year=_year(row["uk_latest_year"]),
                    dutch_latest_year=_year(row["dutch_latest_year"]),
                )
                for row in csv.DictReader(handle)
            ]


class EBirdExportSource:
    """Future: ingest eBird exports (per-country counts and latest dates)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Candidate]:
        raise NotImplementedError("eBird export ingestion is not implemented yet")


class CorvoRarityListSource(EBirdExportSource):
    """Future: ingest Corvo (Azores) rarity lists."""


class UKRarityDataSource(EBirdExportSource):
    """Future: ingest UK rarity data (e.g. BBRC/BOURC-style records)."""


class IrishRarityReportsSource(EBirdExportSource):
    """Future: ingest Irish rarity reports."""


class DutchStatusSource:
    """Future: map scientific name to Dutch record count from Dutch Avifauna / CDNA."""

    def record_count_for(self, scientific_name: str) -> int:
        raise NotImplementedError("Dutch Avifauna/CDNA status ingestion is not implemented yet")


def _scaled(value: int, maximum: int) -> float:
    return value / maximum if maximum else 0.0


def recency_factor(latest_year: int | None, today: date | None = None) -> float:
    """1.0 for a record this year, falling linearly to 0 over the window."""
    if latest_year is None:
        return 0.0
    age = (today or date.today()).year - latest_year
    return max(0.0, min(1.0, 1 - age / RECENCY_WINDOW_YEARS))


def integer_breakdown(points: dict[str, float]) -> dict[str, int]:
    """Round component points to integers that sum to the rounded total.

    Largest-remainder rounding, so the displayed parts add up exactly.
    """
    target = round(sum(points.values()))
    floors = {k: int(v) for k, v in points.items()}
    shortfall = target - sum(floors.values())
    by_remainder = sorted(points, key=lambda k: points[k] - floors[k], reverse=True)
    for key in by_remainder[:shortfall]:
        floors[key] += 1
    return floors


def compute_momentum(c: Candidate, today: date | None = None) -> None:
    year = (today or date.today()).year
    regions = []
    points = 0
    for region, latest in (
        ("corvo", c.corvo_latest_year),
        ("ireland", c.ireland_latest_year),
        ("uk", c.uk_latest_year),
    ):
        if latest and year - latest <= MOMENTUM_WINDOW_YEARS:
            regions.append(region)
            points += MOMENTUM_POINTS[region]
    if c.is_surging():
        points += MOMENTUM_POINTS["surge"]
    c.momentum_score = points
    c.momentum_regions = tuple(regions)


def score_candidates(
    candidates: Iterable[Candidate], today: date | None = None
) -> list[Candidate]:
    """Fill prediction_score (0-100) and rationale; return a ranked list.

    Species already on the Dutch list stay in, with a smaller rarity bonus.
    """
    pool = list(candidates)
    if not pool:
        return []
    maxima = {country: max(c.records(country) for c in pool) for country in COUNTRIES}
    max_iberia = max(c.iberia_france_records for c in pool)
    for c in pool:
        compute_momentum(c, today)
        parts = {
            "corvo": _scaled(c.corvo_records, maxima["corvo"]),
            "uk": _scaled(c.uk_records, maxima["uk"]),
            "ireland": _scaled(c.ireland_records, maxima["ireland"]),
            "iberia_france": _scaled(c.iberia_france_records, max_iberia),
            "recency": recency_factor(c.latest_record_year, today),
            "dutch_rarity": rarity_bonus(c.dutch_record_count),
            "momentum": c.momentum_score / MOMENTUM_MAX,
        }
        c.score_breakdown = integer_breakdown(
            {k: 100 * WEIGHTS[k] * v for k, v in parts.items()}
        )
        c.prediction_score = float(sum(c.score_breakdown.values()))
        c.rationale = build_rationale(c, parts)
    return sorted(pool, key=lambda c: (-c.prediction_score, c.common_name))


def build_rationale(c: Candidate, parts: dict[str, float]) -> str:
    contributions = sorted(
        ((WEIGHTS[k] * v, k) for k, v in parts.items()), reverse=True
    )
    names = {
        "corvo": f"{c.corvo_records} Corvo records",
        "uk": f"{c.uk_records} UK records",
        "ireland": f"{c.ireland_records} Irish records",
        "iberia_france": f"{c.iberia_france_records} France/Spain/Portugal records",
        "dutch_rarity": f"Dutch rarity: {c.dutch_status}",
        "momentum": f"momentum {c.momentum_score}/{MOMENTUM_MAX}",
        "recency": (
            f"latest Atlantic record in {c.latest_record_year}"
            if c.latest_record_year
            else "no dated recent record"
        ),
    }
    top = [names[k] for value, k in contributions[:3] if value > 0]
    text = "Ranked on " + (", ".join(top) if top else "limited Atlantic evidence") + "."
    if c.momentum_regions:
        places = [COUNTRY_LABELS[r] for r in c.momentum_regions]
        where = places[0] if len(places) == 1 else ", ".join(places[:-1]) + " and " + places[-1]
        text += (
            f" This species has been recorded recently in {where}, suggesting "
            "active movement through the Atlantic vagrant pipeline."
        )
        if c.is_surging():
            text += " Recent records exceed its historical average."
    else:
        text += " No records in the last 2 years in Corvo, Ireland or the UK: low current momentum."
    if c.dutch_record_count == 0:
        text += " Potential Dutch first."
    if c.corvo_records and c.uk_records + c.ireland_records == 0:
        text += " Corvo-only evidence: not yet seen further east."
    elif c.corvo_records == 0:
        text += " No Corvo precedent, so a lower leading-indicator signal."
    return text


def apply_filter(ranked: list[Candidate], name: str) -> list[Candidate]:
    if name == "Potential Dutch Firsts":
        return [c for c in ranked if c.dutch_record_count == 0]
    if name.startswith("Mega-Rarities"):
        return [c for c in ranked if c.dutch_record_count < MEGA_RARITY_THRESHOLD]
    if name == "Corvo Pipeline":
        return [
            c for c in ranked
            if c.corvo_records > 0 and c.dutch_record_count < MEGA_RARITY_THRESHOLD
        ]
    if name == FILTERS[4]:
        return sorted(
            (c for c in ranked if c.is_long_overdue()),
            key=lambda c: (-(c.years_since_last_dutch_record() or 0), -c.prediction_score),
        )
    if name == FILTERS[5]:
        return sorted(
            (c for c in ranked if c.momentum_score >= RISING_FAST_THRESHOLD),
            key=lambda c: (-c.momentum_score, -c.prediction_score),
        )
    return list(ranked)


def top_rising(ranked: list[Candidate], n: int = 5) -> list[Candidate]:
    """Species with momentum >= threshold, by momentum then score; may be < n."""
    return rising_species(ranked)[:n]


def timeline(
    c: Candidate, today: date | None = None
) -> list[tuple[str, int | None, int | None]]:
    """Corvo -> Ireland -> UK -> Netherlands: (region, latest year, years ago)."""
    year = (today or date.today()).year
    stages = [
        ("Corvo", c.corvo_latest_year),
        ("Ireland", c.ireland_latest_year),
        ("UK", c.uk_latest_year),
        ("Netherlands", c.dutch_latest_year),
    ]
    return [(region, y, year - y if y else None) for region, y in stages]


def timeline_label(region: str, latest: int | None, years_ago: int | None) -> str:
    if not latest:
        return f"{region} (never)"
    return f"{region} ({latest}, {years_ago}y ago)"


def rising_species(ranked: list[Candidate]) -> list[Candidate]:
    return apply_filter(ranked, FILTERS[5])


def summary_counts(ranked: list[Candidate]) -> dict[str, int]:
    names = (FILTERS[1], FILTERS[2], FILTERS[4], FILTERS[5], FILTERS[3])
    return {name: len(apply_filter(ranked, name)) for name in names}


BREAKDOWN_LABELS = {
    "corvo": "Corvo",
    "uk": "UK",
    "ireland": "Ireland",
    "iberia_france": "France/Iberia",
    "dutch_rarity": "Dutch rarity",
    "recency": "Recency",
    "momentum": "Momentum",
}
# Darkest (rarest) to lightest (most frequent in the Netherlands).
RARITY_COLORS = ["#14463a", "#2a7f66", "#5fa892", "#98c9bb", "#cfe4dd"]

DATA_PROVENANCE = (
    "All current record counts and dates are illustrative demo values and have "
    "not yet been verified against Dutch Avifauna/CDNA."
)
# TODO placeholders for live data; each maps to a source class above.
PLANNED_SOURCES = (
    ("Dutch Avifauna", "TODO", "Dutch record counts and last-record years"),
    ("CDNA", "TODO", "Official Dutch list status and accepted records"),
    ("Corvo rarity reports", "TODO", "Corvo (Azores) records and latest years"),
    ("Irish rarity reports", "TODO", "Irish records and latest years"),
    ("UK rarity reports", "TODO", "UK records and latest years"),
    ("eBird export", "TODO", "Per-country counts, dates and recent-record totals"),
)


def candidates_frame(ranked: list[Candidate]):
    import pandas as pd

    frame = pd.DataFrame([asdict(c) for c in ranked])
    frame.insert(0, "rank", range(1, len(frame) + 1))
    return frame


def load_ranked(source: CandidateSource | None = None) -> list[Candidate]:
    return score_candidates((source or CsvDemoSource()).load())
