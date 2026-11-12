"""Forecast Seabird Index hotspots on the shared 10 km North Sea grid."""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from . import forecast_atlantic_locations as framework
    from .build_seabird_dataset import load_all_occurrences
    from .predict_seabird import DEFAULT_OUTPUT, risk_level
    from .seabird_features import add_seabird_features
    from .build_dataset_v2 import add_coastal_features
else:
    import forecast_atlantic_locations as framework
    from build_seabird_dataset import load_all_occurrences
    from predict_seabird import DEFAULT_OUTPUT, risk_level
    from seabird_features import add_seabird_features
    from build_dataset_v2 import add_coastal_features


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
SEABIRD_LOCATION_FORECAST_FILE = ROOT / "outputs/seabird_location_forecast_detail.csv"
SIMPLE_LOCATION_FORECAST_FILE = ROOT / "outputs/seabird_location_forecast.csv"
LOCATION_MAP_FILE = ROOT / "outputs/seabird_location_forecast.png"
SEABIRD_DAILY_COUNTS_FILE = ROOT / "outputs/seabird_daily_counts.csv"

SEABIRD_EXPOSURE_SCALE_KM = 300.0
SEABIRD_KIND_WEIGHTS = {
    "island": 1.0,
    "headland": 1.0,
    "seawatch": 0.95,
    "seafront": 0.8,
    "trap": 0.9,
}
SEABIRD_BOOSTS = {
    "Scilly Isles": 1.45,
    "Fair Isle": 1.55,
    "Shetland": 1.5,
    "North Ronaldsay": 1.3,
    "Outer Hebrides": 1.35,
    "Norfolk coast": 1.2,
    "Flamborough Head": 1.25,
    "Spurn": 1.25,
    "Blåvand": 1.2,
    "Skagen": 1.25,
    "Texel": 1.2,
    "Den Helder": 1.15,
    "Petten": 1.15,
    "Camperduin": 1.15,
    "IJmuiden": 1.15,
    "Bloemendaal aan Zee": 1.1,
    "Maasvlakte": 1.2,
    "Neeltje Jans": 1.15,
    "Westkapelle": 1.2,
    "Schiermonnikoog": 1.15,
    "Terschelling": 1.15,
    "Vlieland": 1.15,
}

SEABIRD_SITES = [
    framework.Site("Texel", "NL", 53.06, 4.76, "island", 28, west_facing=True, boost_group="Texel"),
    framework.Site("Den Helder", "NL", 52.96, 4.76, "seafront", 12, west_facing=True, boost_group="Den Helder"),
    framework.Site("Petten", "NL", 52.76, 4.66, "seafront", 10, west_facing=True, boost_group="Petten"),
    framework.Site("Camperduin", "NL", 52.75, 4.64, "seafront", 10, west_facing=True, boost_group="Camperduin"),
    framework.Site("IJmuiden", "NL", 52.46, 4.57, "seafront", 12, west_facing=True, boost_group="IJmuiden"),
    framework.Site("Bloemendaal aan Zee", "NL", 52.39, 4.53, "seafront", 12, west_facing=True, boost_group="Bloemendaal aan Zee"),
    framework.Site("Maasvlakte", "NL", 51.96, 4.01, "seafront", 15, west_facing=True, boost_group="Maasvlakte"),
    framework.Site("Neeltje Jans", "NL", 51.63, 3.69, "seafront", 14, west_facing=True, boost_group="Neeltje Jans"),
    framework.Site("Westkapelle", "NL", 51.53, 3.43, "headland", 12, west_facing=True, boost_group="Westkapelle"),
    framework.Site("Schiermonnikoog", "NL", 53.48, 6.19, "island", 18, boost_group="Schiermonnikoog"),
    framework.Site("Terschelling", "NL", 53.37, 5.29, "island", 18, boost_group="Terschelling"),
    framework.Site("Vlieland", "NL", 53.29, 5.08, "island", 18, boost_group="Vlieland"),
    framework.Site("Fair Isle", "GB", 59.53, -1.63, "island", 16, boost_group="Fair Isle"),
    framework.Site("Shetland", "GB", 60.24, -1.21, "island", 16, boost_group="Shetland"),
    framework.Site("North Ronaldsay", "GB", 59.37, -2.42, "island", 16, boost_group="North Ronaldsay"),
    framework.Site("Scilly Isles", "GB", 49.92, -6.30, "island", 18, west_facing=True, boost_group="Scilly Isles"),
    framework.Site("Norfolk coast", "GB", 52.95, 1.37, "seafront", 16, boost_group="Norfolk coast"),
    framework.Site("Flamborough Head", "GB", 54.11, -0.11, "headland", 14, west_facing=True, boost_group="Flamborough Head"),
    framework.Site("Spurn", "GB", 53.58, 0.12, "headland", 12, boost_group="Spurn"),
    framework.Site("Outer Hebrides", "GB", 58.20, -6.70, "island", 18, west_facing=True, boost_group="Outer Hebrides"),
    framework.Site("Blåvand", "DK", 55.55, 8.08, "seafront", 12, west_facing=True, boost_group="Blåvand"),
    framework.Site("Skagen", "DK", 57.72, 10.58, "headland", 12, boost_group="Skagen"),
]


def _build_seabird_features(weather: pd.DataFrame) -> pd.DataFrame:
    return add_seabird_features(add_coastal_features(weather))


def _best_dutch_rationale(weather: pd.DataFrame | None, target_date: pd.Timestamp) -> str:
    if weather is None:
        return "Strong west-facing exposure and high modelled coastal suitability."
    engineered = _build_seabird_features(weather)
    weather_date = target_date - pd.Timedelta(days=1)
    if "date" not in engineered:
        return "Strong west-facing exposure and high modelled coastal suitability."
    row = engineered.loc[pd.to_datetime(engineered["date"]).dt.normalize().eq(weather_date)]
    if row.empty:
        return "Strong west-facing exposure and high modelled coastal suitability."
    row = row.iloc[0]
    wind = float(row.get("coast_wind_speed", np.nan))
    pressure = float(row.get("coast_pressure_tendency_24h", np.nan))
    storm = float(row.get("coast_cumulative_storm_score", np.nan))
    pieces = []
    if np.isfinite(wind):
        direction = math.degrees(
            math.atan2(
                float(row.get("coast_wind_sin", np.nan)),
                float(row.get("coast_wind_cos", np.nan)),
            )
        ) % 360
        if np.isfinite(direction):
            compass = (
                "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
            )
            direction_label = compass[int((direction + 11.25) // 22.5) % 16]
            pieces.append(f"{direction_label} airflow at {wind:.1f} m/s")
        else:
            pieces.append(f"variable airflow at {wind:.1f} m/s")
    if np.isfinite(pressure):
        direction = "falling" if pressure < 0 else "rising"
        pieces.append(f"{direction} pressure")
    if np.isfinite(storm) and storm > 0:
        pieces.append(f"storm score {storm:.1f}")
    if not pieces:
        return "Strong west-facing exposure and high modelled coastal suitability."
    return "Strong " + ", ".join(pieces) + " favouring an exposed Dutch seawatching site."


def build_seabird_location_forecast(
    national_forecast: pd.DataFrame,
    *,
    analysis_date: date | None = None,
    output_path: Path = SEABIRD_LOCATION_FORECAST_FILE,
    daily_counts_path: Path = SEABIRD_DAILY_COUNTS_FILE,
    simple_output_path: Path | None = None,
    map_path: Path | None = None,
    weather: pd.DataFrame | None = None,
    occurrences: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if not daily_counts_path.is_file():
        raise FileNotFoundError(f"Daily counts not found: {daily_counts_path}")
    if analysis_date is not None:
        first_target = pd.to_datetime(national_forecast["date"]).min().date()
        if first_target != analysis_date + timedelta(days=1):
            raise ValueError(
                "Seabird location forecast must begin the day after analysis_date."
            )
    cells = framework.add_suitability(
        framework.build_grid(
            load_all_occurrences() if occurrences is None else occurrences,
            sites=SEABIRD_SITES,
        ),
        kind_weights=SEABIRD_KIND_WEIGHTS,
        west_facing_bonus=0.15,
        anchors=[
            (51.44, -9.50),
            (53.61, -10.22),
            (55.27, -8.25),
            (57.81, -8.58),
            (49.92, -6.30),
            (59.53, -1.63),
            (54.50, 2.00),
        ],
        exposure_scale_km=SEABIRD_EXPOSURE_SCALE_KM,
        boosts=SEABIRD_BOOSTS,
        sites=SEABIRD_SITES,
    )
    cells["regional_suitability"] /= cells["regional_suitability"].max()
    LOGGER.info("Seabird hotspot grid: %d cells", len(cells))
    result = framework.calculate_atlantic_location_forecast(
        cells,
        pd.read_csv(daily_counts_path),
        national_forecast,
        risk_function=risk_level,
        sites=SEABIRD_SITES,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    if simple_output_path is not None:
        framework.simple_location_forecast(result).to_csv(
            simple_output_path, index=False, date_format="%Y-%m-%d"
        )
    if map_path is not None:
        framework.save_location_map(result, map_path, title="Seabird hotspots")
    return result


def best_dutch_site(
    result: pd.DataFrame,
    weather: pd.DataFrame | None = None,
    analysis_date: date | None = None,
) -> dict[str, object]:
    tomorrow_date = (
        pd.Timestamp(analysis_date + timedelta(days=1))
        if analysis_date is not None
        else framework.horizon_dates(result["date"])[1]
    )
    tomorrow = result.loc[pd.to_datetime(result["date"]).dt.normalize().eq(tomorrow_date)]
    dutch = tomorrow.loc[tomorrow["country"].eq("NL")].sort_values("rank")
    if dutch.empty:
        raise ValueError("Seabird location forecast has no Dutch sites for tomorrow.")
    else:
        strongest = dutch.iloc[0]
    target_date = pd.to_datetime(strongest["date"])
    return {
        "location": str(strongest["location"]),
        "country": str(strongest["country"]),
        "probability": float(strongest["forecast_probability"]),
        "risk_level": str(strongest["risk_level"]),
        "rationale": _best_dutch_rationale(weather, target_date),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = build_seabird_location_forecast(
        pd.read_csv(DEFAULT_OUTPUT),
        simple_output_path=SIMPLE_LOCATION_FORECAST_FILE,
        map_path=LOCATION_MAP_FILE,
    )
    for horizon, frame in framework.top_hotspots(result).items():
        print(f"\n{framework.HORIZONS[horizon]}")
        print(
            frame[["rank", "location", "country", "forecast_probability"]].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
