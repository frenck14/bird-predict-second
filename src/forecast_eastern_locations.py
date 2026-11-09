"""Forecast Eastern Vagrancy hotspots on the shared 10 km North Sea grid.

Per-cell probability = Eastern Index probability x coastal suitability
x regional vagrancy suitability, clipped to [0, 1]. Suitability uses the
Atlantic hotspot framework with eastern landfall anchors (Shetland, Fair Isle,
Spurn, Norfolk, Texel, Blavand, Skagen) and east-coast boosts. The weights are
expert heuristics, not trained or validated against observations.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pandas as pd

if __package__:
    from . import forecast_atlantic_locations as framework
    from .build_eastern_vagrancy_dataset import load_all_occurrences
    from .forecast_atlantic_species_locations import EASTERN_ANCHORS
    from .predict_eastern_vagrancy import DEFAULT_OUTPUT, risk_level
else:
    import forecast_atlantic_locations as framework
    from build_eastern_vagrancy_dataset import load_all_occurrences
    from forecast_atlantic_species_locations import EASTERN_ANCHORS
    from predict_eastern_vagrancy import DEFAULT_OUTPUT, risk_level

hotspot_metadata = framework.hotspot_metadata
top_hotspots = framework.top_hotspots
simple_location_forecast = framework.simple_location_forecast
HORIZONS = framework.HORIZONS

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
EASTERN_LOCATION_FORECAST_FILE = ROOT / "outputs/eastern_vagrancy_location_forecast.csv"
SIMPLE_LOCATION_FORECAST_FILE = ROOT / "outputs/eastern_location_forecast.csv"
LOCATION_MAP_FILE = ROOT / "outputs/eastern_location_forecast.png"
EASTERN_DAILY_COUNTS_FILE = ROOT / "outputs/eastern_vagrancy_daily_counts.csv"
EASTERN_EXPOSURE_SCALE_KM = 400.0
EASTERN_KIND_WEIGHTS = {"island": 0.9, "headland": 0.8, "trap": 0.95}

# Multiplicative boosts for classic eastern landfall areas. Fair Isle and
# Shetland were requested; the remaining entries are assumed east-coast
# migration traps and can be edited freely.
EASTERN_BONUS_BOOSTS = {
    "Fair Isle": 1.6,
    "Shetland": 1.5,
    "Orkney": 1.3,
    "Isle of May": 1.25,
    "East Yorkshire coast": 1.35,
    "Norfolk coast": 1.3,
    "Wadden islands": 1.2,
    "Blavand": 1.25,
    "Skagen": 1.25,
}
_SITE_GROUPS = {
    "North Ronaldsay": "Orkney",
    "Orkney Mainland": "Orkney",
    "Isle of May": "Isle of May",
    "Texel": "Wadden islands",
    "Vlieland and Terschelling": "Wadden islands",
    "Schiermonnikoog": "Wadden islands",
    "Blavand": "Blavand",
}
# Western Atlantic groups are dropped; eastern groups keep the registry value.
EASTERN_SITES = [
    replace(
        site,
        boost_group=_SITE_GROUPS.get(
            site.name,
            site.boost_group if site.boost_group in EASTERN_BONUS_BOOSTS else None,
        ),
    )
    for site in framework.SITES
]


def build_eastern_location_forecast(
    national_forecast: pd.DataFrame,
    *,
    output_path: Path = EASTERN_LOCATION_FORECAST_FILE,
    daily_counts_path: Path = EASTERN_DAILY_COUNTS_FILE,
    simple_output_path: Path | None = None,
    map_path: Path | None = None,
) -> pd.DataFrame:
    """Load GBIF history, calculate hotspots and write the CSV and map outputs."""
    if not daily_counts_path.is_file():
        raise FileNotFoundError(f"Daily counts not found: {daily_counts_path}")
    cells = framework.add_suitability(
        framework.build_grid(load_all_occurrences()),
        kind_weights=EASTERN_KIND_WEIGHTS,
        west_facing_bonus=0.0,
        anchors=EASTERN_ANCHORS,
        exposure_scale_km=EASTERN_EXPOSURE_SCALE_KM,
        boosts=EASTERN_BONUS_BOOSTS,
        sites=EASTERN_SITES,
    )
    # Eastern national probabilities approach 1 in autumn, so boosts above 1
    # would clip every top cell at 1.0. Scaling to a peak of 1 keeps the ranking.
    cells["regional_suitability"] /= cells["regional_suitability"].max()
    LOGGER.info("Eastern hotspot grid: %d cells", len(cells))
    result = framework.calculate_atlantic_location_forecast(
        cells,
        pd.read_csv(daily_counts_path),
        national_forecast,
        risk_function=risk_level,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    if simple_output_path is not None:
        simple_location_forecast(result).to_csv(
            simple_output_path, index=False, date_format="%Y-%m-%d"
        )
    if map_path is not None:
        framework.save_location_map(result, map_path, title="Eastern Vagrancy hotspots")
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = build_eastern_location_forecast(
        pd.read_csv(DEFAULT_OUTPUT),
        simple_output_path=SIMPLE_LOCATION_FORECAST_FILE,
        map_path=LOCATION_MAP_FILE,
    )
    for horizon, frame in top_hotspots(result).items():
        print(f"\n{HORIZONS[horizon]}")
        print(
            frame[["rank", "location", "country", "forecast_probability"]].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
