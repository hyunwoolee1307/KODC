"""Preprocess KODC observations into station-depth anomaly tables."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import COLUMN_ALIASES, INTERIM_DATA_DIR, STANDARD_DEPTHS

REQUIRED_COLUMNS = ("sln_cde", "sta_cde", "lat", "lon", "obs_dtm", "wtr_dep", "wtr_tmp")


@dataclass(frozen=True)
class AnomalyResult:
    anomalies: pd.DataFrame
    metadata: pd.DataFrame


def read_kodc_csvs(input_dir: Path = INTERIM_DATA_DIR) -> pd.DataFrame:
    """Read and concatenate generated KODC CSV files."""

    csv_files = sorted(input_dir.glob("kodc*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No kodc*.csv files found in {input_dir}.")
    frames = (pd.read_csv(path, encoding="utf-8-sig") for path in csv_files)
    return pd.concat(frames, ignore_index=True)


def normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize KODC column names and dtypes used by the analysis pipeline."""

    df = dataframe.copy()
    df = df.rename(columns=COLUMN_ALIASES)
    df = df.loc[:, [column for column in df.columns if not str(column).startswith("Unnamed")]]

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required KODC columns: {', '.join(missing)}")

    df["obs_dtm"] = pd.to_datetime(df["obs_dtm"], errors="coerce")
    for column in ("sln_cde", "sta_cde", "lat", "lon", "wtr_dep", "wtr_tmp"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def regular_time_index(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    freq_months: int = 2,
    sample_day: int = 15,
) -> pd.DatetimeIndex:
    """Build the regular bimonthly analysis index."""

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    month_start = start.replace(day=1)
    dates = pd.date_range(month_start, end, freq=f"{freq_months}MS") + pd.DateOffset(
        days=sample_day - 1
    )
    return pd.DatetimeIndex(dates[(dates >= start) & (dates <= end)])


def _mode_or_nan(series: pd.Series) -> float:
    mode = series.dropna().mode()
    if mode.empty:
        return float("nan")
    return float(mode.iloc[0])


def _metadata_lookup(station_metadata: pd.DataFrame | None) -> dict[tuple[int, int], float]:
    if station_metadata is None or station_metadata.empty:
        return {}

    metadata = station_metadata.copy()
    metadata["sln_cde"] = pd.to_numeric(metadata["sln_cde"], errors="coerce")
    metadata["sta_cde"] = pd.to_numeric(metadata["sta_cde"], errors="coerce")
    metadata["max_depth_m"] = pd.to_numeric(metadata["max_depth_m"], errors="coerce")
    metadata = metadata.dropna(subset=["sln_cde", "sta_cde", "max_depth_m"])
    return {
        (int(row.sln_cde), int(row.sta_cde)): float(row.max_depth_m)
        for row in metadata.itertuples(index=False)
    }


def _station_depth_limit(
    *,
    line: float,
    station: float,
    observed_max_depth: float,
    station_depths: dict[tuple[int, int], float],
) -> tuple[float, float]:
    metadata_depth = station_depths.get((int(line), int(station)), float("nan"))
    if np.isfinite(metadata_depth) and metadata_depth >= 0:
        return min(float(observed_max_depth), metadata_depth), metadata_depth
    return float(observed_max_depth), float(observed_max_depth)


def _interpolate_profiles(
    group: pd.DataFrame,
    time_index: Iterable[pd.Timestamp],
    interp_depths: np.ndarray,
) -> pd.DataFrame:
    rows: list[np.ndarray] = []
    index: list[pd.Timestamp] = []

    for timestamp in sorted(pd.to_datetime(list(time_index))):
        profile = (
            group.loc[group["obs_dtm"] == timestamp, ["wtr_dep", "wtr_tmp"]]
            .dropna()
            .groupby("wtr_dep", as_index=True)["wtr_tmp"]
            .mean()
            .sort_index()
        )
        index.append(timestamp)
        if profile.empty:
            rows.append(np.full(len(interp_depths), np.nan))
            continue
        rows.append(
            np.interp(
                interp_depths,
                profile.index.to_numpy(dtype=float),
                profile.to_numpy(dtype=float),
                left=np.nan,
                right=np.nan,
            )
        )

    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=interp_depths).sort_index()


def _monthly_anomalies(
    dataframe: pd.DataFrame,
    *,
    baseline_start: str,
    baseline_end: str,
) -> pd.DataFrame:
    reference = dataframe.loc[pd.Timestamp(baseline_start) : pd.Timestamp(baseline_end)]
    if reference.empty:
        raise ValueError("The climatology reference period contains no data.")

    climatology = reference.groupby(reference.index.month).mean()
    pieces: list[pd.DataFrame] = []
    for month, group in dataframe.groupby(dataframe.index.month):
        if month in climatology.index:
            pieces.append(group - climatology.loc[month])
        else:
            pieces.append(group * np.nan)
    return pd.concat(pieces).sort_index()


def process_anomaly_with_filter(
    dataframe: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    baseline_start: str,
    baseline_end: str,
    min_observations: int,
    standard_depths: Iterable[int] = STANDARD_DEPTHS,
    station_metadata: pd.DataFrame | None = None,
    freq_months: int = 2,
    sample_day: int = 15,
    fill_value: float = 0.0,
) -> AnomalyResult:
    """Create station-depth anomaly columns for stations with sufficient observations."""

    df = normalize_columns(dataframe)
    df = df.dropna(subset=["obs_dtm", "sln_cde", "sta_cde", "wtr_dep", "wtr_tmp"])
    df = df[(df["obs_dtm"] >= pd.Timestamp(start_date)) & (df["obs_dtm"] <= pd.Timestamp(end_date))]
    if df.empty:
        raise ValueError("No observations remain after date and quality filtering.")

    target_index = regular_time_index(
        start_date,
        end_date,
        freq_months=freq_months,
        sample_day=sample_day,
    )
    if target_index.empty:
        raise ValueError("The requested analysis time index is empty.")

    depths = np.asarray(tuple(standard_depths), dtype=float)
    station_depths = _metadata_lookup(station_metadata)
    all_series: list[pd.Series] = []
    metadata_rows: list[dict] = []

    for (line, station), group in df.groupby(["sln_cde", "sta_cde"], sort=True):
        n_valid_dates = group["obs_dtm"].nunique()
        if n_valid_dates < min_observations:
            continue

        observed_max_depth = float(group["wtr_dep"].max())
        depth_limit, station_max_depth = _station_depth_limit(
            line=line,
            station=station,
            observed_max_depth=observed_max_depth,
            station_depths=station_depths,
        )
        interp_depths = depths[depths <= depth_limit]
        if len(interp_depths) == 0:
            continue

        profile_df = _interpolate_profiles(group, group["obs_dtm"].unique(), interp_depths)
        filled = (
            profile_df.reindex(profile_df.index.union(target_index))
            .sort_index()
            .interpolate(method="time", limit_area="inside")
        )
        regular_df = filled.loc[target_index]

        try:
            anomaly_df = _monthly_anomalies(
                regular_df,
                baseline_start=baseline_start,
                baseline_end=baseline_end,
            )
        except ValueError:
            continue

        lat = _mode_or_nan(group["lat"])
        lon = _mode_or_nan(group["lon"])
        for depth in interp_depths:
            depth_int = int(depth)
            column = f"Sln{int(line)}_Sta{int(station)}_{depth_int}m"
            all_series.append(anomaly_df[depth].rename(column))
            metadata_rows.append(
                {
                    "column": column,
                    "sln_cde": int(line),
                    "sta_cde": int(station),
                    "lat": lat,
                    "lon": lon,
                    "depth_m": depth_int,
                    "max_depth_m": station_max_depth,
                    "observed_max_depth_m": observed_max_depth,
                    "n_observation_dates": int(n_valid_dates),
                }
            )

    if not all_series:
        raise ValueError(
            f"No stations satisfied min_observations={min_observations} for the requested period."
        )

    anomalies = pd.concat(all_series, axis=1).sort_index().dropna(how="all")
    anomalies = anomalies.fillna(fill_value)
    metadata = pd.DataFrame(metadata_rows).sort_values(["sln_cde", "sta_cde", "depth_m"])
    return AnomalyResult(anomalies=anomalies, metadata=metadata.reset_index(drop=True))
