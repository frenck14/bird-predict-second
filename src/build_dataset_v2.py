from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .build_dataset import load_knmi_station
else:
    from build_dataset import load_knmi_station


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_FILE = ROOT / "data/raw/0019564-260928105237408.csv"
OUTPUT_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
STATION_FILES = {
    235: ROOT / "data/raw/result (1).txt",
    242: ROOT / "data/raw/result (3).txt",
    225: ROOT / "data/raw/result (3).txt",
    310: ROOT / "data/raw/result (3).txt",
}
STATION_NAMES = {
    235: "De Kooy",
    242: "Vlieland",
    225: "IJmuiden",
    310: "Vlissingen",
}
WEATHER_VARIABLES = ["DDVEC", "FG", "FHX", "TG", "TN", "TX", "RH", "PX"]


def load_and_merge_stations(station_files):
    station_data = {}
    for station_id, filepath in station_files.items():
        station = load_knmi_station(filepath, station_id)
        station_data[station_id] = station
        print(
            f"Station {station_id} ({STATION_NAMES.get(station_id, 'unknown')}): "
            f"{len(station)} days, {station['date'].min().date()} to "
            f"{station['date'].max().date()}"
        )

    common_dates = None
    for station in station_data.values():
        station_dates = pd.Index(station["date"])
        common_dates = (
            station_dates
            if common_dates is None
            else common_dates.intersection(station_dates)
        )

    if common_dates is None or common_dates.empty:
        raise ValueError("KNMI stations have no dates in common.")

    common_dates = common_dates.sort_values()
    print(
        f"Overlap start date: {common_dates.min().date()}\n"
        f"Overlap end date: {common_dates.max().date()}\n"
        f"Retained days: {len(common_dates)}"
    )

    merged = None
    for station_id, station in station_data.items():
        station = station.loc[station["date"].isin(common_dates)]
        station = station[["date", *WEATHER_VARIABLES]].rename(
            columns={
                column: f"{column}_{station_id}"
                for column in WEATHER_VARIABLES
            }
        )
        merged = (
            station
            if merged is None
            else merged.merge(
                station,
                on="date",
                how="inner",
                validate="one_to_one",
            )
        )

    if merged is None or merged["date"].duplicated().any():
        raise ValueError("Merged KNMI data must contain unique dates.")

    return merged.sort_values("date").reset_index(drop=True)


def add_coastal_features(weather):
    dataset = weather.copy()
    for variable in ["FG", "FHX", "TG", "TX", "PX", "RH"]:
        columns = [f"{variable}_{station_id}" for station_id in STATION_FILES]
        dataset[f"coast_{variable}_mean"] = dataset[columns].mean(axis=1)

    for variable, operation in [
        ("FG", "max"),
        ("FHX", "max"),
        ("TX", "max"),
        ("PX", "min"),
    ]:
        columns = [f"{variable}_{station_id}" for station_id in STATION_FILES]
        dataset[f"coast_{variable}_{operation}"] = getattr(
            dataset[columns], operation
        )(axis=1)

    wind_sin_columns = []
    wind_cos_columns = []
    for station_id in STATION_FILES:
        direction = dataset[f"DDVEC_{station_id}"].where(
            dataset[f"DDVEC_{station_id}"] != 0
        )
        radians = np.deg2rad(direction)
        sin_column = f"wind_sin_{station_id}"
        cos_column = f"wind_cos_{station_id}"
        dataset[sin_column] = np.sin(radians)
        dataset[cos_column] = np.cos(radians)
        wind_sin_columns.append(sin_column)
        wind_cos_columns.append(cos_column)

    dataset["coast_wind_sin"] = dataset[wind_sin_columns].mean(axis=1)
    dataset["coast_wind_cos"] = dataset[wind_cos_columns].mean(axis=1)
    pressure_columns = [f"PX_{station_id}" for station_id in STATION_FILES]
    dataset["coast_pressure_gradient"] = (
        dataset[pressure_columns].max(axis=1)
        - dataset[pressure_columns].min(axis=1)
    )
    west_components = []
    south_components = []
    for station_id in STATION_FILES:
        direction = dataset[f"DDVEC_{station_id}"].where(
            dataset[f"DDVEC_{station_id}"] != 0
        )
        angle = np.deg2rad(direction)
        west_components.append(dataset[f"FG_{station_id}"] * np.sin(angle))
        south_components.append(-dataset[f"FG_{station_id}"] * np.cos(angle))
    dataset["coast_west_wind_component"] = pd.concat(
        west_components, axis=1
    ).mean(axis=1)
    dataset["coast_south_wind_component"] = pd.concat(
        south_components, axis=1
    ).mean(axis=1)
    dataset["coast_atlantic_storm_pressure"] = (
        dataset["coast_PX_min"].lt(9900).astype(float)
    )
    dataset["coast_atlantic_storm_wind"] = (
        dataset["coast_FG_max"].ge(150).astype(float)
    )

    daily_grid = pd.date_range(
        dataset["date"].min(), dataset["date"].max(), freq="D", name="date"
    )
    dataset = dataset.set_index("date").reindex(daily_grid).rename_axis("date")

    lag_sources = {
        "pressure": "coast_PX_mean",
        "temperature": "coast_TG_mean",
        "wind_speed": "coast_FG_mean",
        "precipitation": "coast_RH_mean",
        "wind_direction_west": "coast_west_wind_component",
        "wind_direction_south": "coast_south_wind_component",
    }
    for feature, source in lag_sources.items():
        for lag_days in (1, 2, 3):
            dataset[f"{feature}_lag_{lag_days * 24}h"] = dataset[source].shift(
                lag_days
            )

    rolling_sources = {
        "pressure": "coast_PX_mean",
        "temperature": "coast_TG_mean",
        "wind_speed": "coast_FG_mean",
        "precipitation": "coast_RH_mean",
        "wind_direction_west": "coast_west_wind_component",
        "wind_direction_south": "coast_south_wind_component",
    }
    for feature, source in rolling_sources.items():
        for window_days in (3, 7):
            rolling_mean = (
                dataset[source]
                .rolling(window=window_days, min_periods=window_days)
                .mean()
            )
            dataset[f"{feature}_rolling_mean_{window_days}d"] = rolling_mean
            dataset[f"{feature}_rolling_anomaly_{window_days}d"] = (
                dataset[source] - rolling_mean
            )

    for feature, source in {
        "pressure": "coast_PX_mean",
        "temp": "coast_TG_mean",
        "wind": "coast_FG_mean",
    }.items():
        for lag_days in (1, 2):
            dataset[f"{feature}_change_{lag_days * 24}h"] = (
                dataset[source] - dataset[source].shift(lag_days)
            )

    return dataset.reset_index()


def build_dataset():
    stations_by_file = {}
    for station_id, filepath in STATION_FILES.items():
        stations_by_file.setdefault(filepath, []).append(station_id)

    missing_files = [
        f"{filepath} (stations {', '.join(map(str, station_ids))})"
        for filepath, station_ids in stations_by_file.items()
        if not filepath.is_file()
    ]
    if missing_files:
        missing_text = "\n".join(f"  - {item}" for item in missing_files)
        raise FileNotFoundError(
            "Missing KNMI station files required for dataset v2:\n"
            f"{missing_text}\n"
            "Provide the configured source files listed above before rebuilding."
        )

    weather = add_coastal_features(load_and_merge_stations(STATION_FILES))

    observations = pd.read_csv(OBSERVATION_FILE, sep="\t")
    observations["date"] = pd.to_datetime(
        observations["eventDate"].astype("string").str[:10],
        errors="coerce",
    )
    daily_counts = (
        observations.dropna(subset=["date"])
        .groupby("date")
        .size()
        .rename("n_records")
        .reset_index()
    )

    dataset = weather.merge(
        daily_counts,
        on="date",
        how="left",
        validate="one_to_one",
    )
    dataset["n_records"] = dataset["n_records"].fillna(0).astype(int)
    dataset["influx"] = (dataset["n_records"] >= 10).astype(int)
    dataset["month"] = dataset["date"].dt.month
    dataset["day_of_year"] = dataset["date"].dt.dayofyear
    annual_phase = 2 * np.pi * dataset["day_of_year"] / 365.2425
    dataset["day_of_year_sin"] = np.sin(annual_phase)
    dataset["day_of_year_cos"] = np.cos(annual_phase)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUTPUT_FILE, index=False)

    excluded = {"date", "n_records", "influx"}
    feature_columns = [column for column in dataset.columns if column not in excluded]
    missing_report = (
        dataset[feature_columns]
        .isna()
        .sum()
        .loc[lambda counts: counts > 0]
        .sort_values(ascending=False)
    )

    print(f"\nSaved {OUTPUT_FILE.relative_to(ROOT)}")
    print(f"Shape: {dataset.shape}")
    print(f"Date range: {dataset['date'].min().date()} to {dataset['date'].max().date()}")
    print(
        f"Target: n_records >= 10; {int(dataset['influx'].sum())} positive days "
        f"({dataset['influx'].mean():.2%})"
    )
    print(f"Feature columns ({len(feature_columns)}): {feature_columns}")
    print("Missing values by feature:")
    print(missing_report.to_string() if not missing_report.empty else "None")

    return dataset


if __name__ == "__main__":
    build_dataset()
