"""Spatial composite visualizations for KODC EOF analysis tables."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import (
    DEFAULT_LEAD_LAG_MONTHS,
    DEFAULT_LINE,
    OUTPUT_FIGURE_DIR,
    OUTPUT_TABLE_DIR,
    STANDARD_DEPTHS,
)

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class VisualizationOutputs:
    paths: list[Path]
    skipped: list[str]


def _read_indexed_csv(path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(path, parse_dates=["obs_dtm"])
    return dataframe.set_index("obs_dtm").sort_index()


def read_analysis_tables(
    *,
    table_dir: Path = OUTPUT_TABLE_DIR,
    line: int = DEFAULT_LINE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read anomaly, metadata, and PC tables produced by ``pixi run analyze``."""

    anomalies = _read_indexed_csv(table_dir / "all_station_anomalies.csv")
    metadata = pd.read_csv(table_dir / "station_metadata.csv")
    pcs = _read_indexed_csv(table_dir / f"line{line}_pcs.csv")
    return anomalies, metadata, pcs


def standardize_pc(pcs: pd.DataFrame, *, mode: int) -> pd.Series:
    """Return one standardized PC time series."""

    column = f"PC{mode}"
    if column not in pcs.columns:
        raise ValueError(f"{column} is not available in the PC table.")
    pc = pcs[column].astype(float)
    std = pc.std()
    if not np.isfinite(std) or std == 0:
        raise ValueError(f"{column} cannot be standardized because its standard deviation is zero.")
    return (pc - pc.mean()) / std


def lagged_event_dates(
    pc_standardized: pd.Series,
    *,
    lag_months: int,
    threshold: float,
) -> pd.DatetimeIndex:
    """Select PC event dates and shift them by ``lag_months``."""

    event_dates = pc_standardized.loc[pc_standardized >= threshold].index
    shifted = [timestamp + pd.DateOffset(months=lag_months) for timestamp in event_dates]
    return pd.DatetimeIndex(shifted)


def composite_for_lag(
    anomalies: pd.DataFrame,
    pc_standardized: pd.Series,
    *,
    lag_months: int,
    threshold: float,
) -> pd.Series:
    """Average all-station anomalies at dates shifted from PC events."""

    target_dates = lagged_event_dates(
        pc_standardized,
        lag_months=lag_months,
        threshold=threshold,
    )
    valid_dates = anomalies.index.intersection(target_dates)
    if valid_dates.empty:
        raise ValueError(f"No anomaly rows match lag {lag_months:+d} months.")
    return anomalies.loc[valid_dates].mean(axis=0)


def format_lag_for_title(lag_months: int) -> str:
    """Return a title suffix; lag 0 is intentionally omitted."""

    if lag_months == 0:
        return ""
    return f" | lag {lag_months:+d} months"


def _format_lag_for_filename(lag_months: int) -> str:
    if lag_months < 0:
        return f"m{abs(lag_months):02d}"
    if lag_months > 0:
        return f"p{lag_months:02d}"
    return "p00"


def _prepare_pyplot() -> tuple[Any, Any, Any, Any]:
    mplconfigdir = Path(os.environ.get("MPLCONFIGDIR", "/tmp/kodc-matplotlib"))
    mplconfigdir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mplconfigdir))

    import matplotlib

    matplotlib.use("Agg", force=True)
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri

    return plt, mtri, ccrs, cfeature


def _station_locations(metadata: pd.DataFrame) -> pd.DataFrame:
    return (
        metadata.dropna(subset=["sln_cde", "sta_cde", "lon", "lat"])
        .groupby(["sln_cde", "sta_cde"], as_index=False)
        .agg({"lon": "median", "lat": "median"})
        .sort_values(["sln_cde", "sta_cde"])
    )


def _prepare_depth_values(
    composite: pd.Series,
    metadata: pd.DataFrame,
    *,
    depth: int,
) -> pd.DataFrame:
    depth_meta = metadata.loc[metadata["depth_m"] == depth].copy()
    if "max_depth_m" in depth_meta.columns:
        depth_meta["max_depth_m"] = pd.to_numeric(depth_meta["max_depth_m"], errors="coerce")
        depth_meta = depth_meta.loc[
            depth_meta["max_depth_m"].isna() | (depth_meta["max_depth_m"] >= depth)
        ]
    depth_meta["value"] = composite.reindex(depth_meta["column"]).to_numpy()
    return depth_meta.dropna(subset=["lon", "lat", "value"])


def _distance_km(
    lon_a: np.ndarray,
    lat_a: np.ndarray,
    lon_b: np.ndarray,
    lat_b: np.ndarray,
) -> np.ndarray:
    lon_a_rad = np.radians(lon_a)
    lat_a_rad = np.radians(lat_a)
    lon_b_rad = np.radians(lon_b)
    lat_b_rad = np.radians(lat_b)
    delta_lon = lon_b_rad - lon_a_rad
    delta_lat = lat_b_rad - lat_a_rad
    h = (
        np.sin(delta_lat / 2.0) ** 2
        + np.cos(lat_a_rad) * np.cos(lat_b_rad) * np.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))


def _auto_max_edge_km(lon: np.ndarray, lat: np.ndarray) -> float:
    if len(lon) < 3:
        return 0.0

    distances = _distance_km(
        lon[:, np.newaxis],
        lat[:, np.newaxis],
        lon[np.newaxis, :],
        lat[np.newaxis, :],
    )
    np.fill_diagonal(distances, np.nan)
    nearest = np.nanmin(distances, axis=1)
    median_nearest = float(np.nanmedian(nearest))
    return max(120.0, median_nearest * 3.0)


def _triangulate_lon_lat(
    mtri: Any,
    depth_values: pd.DataFrame,
    *,
    max_edge_km: float | None,
) -> Any:
    lon = depth_values["lon"].to_numpy(dtype=float)
    lat = depth_values["lat"].to_numpy(dtype=float)
    if len(depth_values) < 3:
        raise ValueError("Fewer than three valid stations are available.")

    triangulation = mtri.Triangulation(lon, lat)
    triangles = triangulation.triangles
    threshold = _auto_max_edge_km(lon, lat) if max_edge_km is None else max_edge_km
    edge_lengths = np.stack(
        [
            _distance_km(
                lon[triangles[:, 0]],
                lat[triangles[:, 0]],
                lon[triangles[:, 1]],
                lat[triangles[:, 1]],
            ),
            _distance_km(
                lon[triangles[:, 1]],
                lat[triangles[:, 1]],
                lon[triangles[:, 2]],
                lat[triangles[:, 2]],
            ),
            _distance_km(
                lon[triangles[:, 2]],
                lat[triangles[:, 2]],
                lon[triangles[:, 0]],
                lat[triangles[:, 0]],
            ),
        ],
        axis=1,
    )
    triangulation.set_mask(np.max(edge_lengths, axis=1) > threshold)
    if triangulation.mask is not None and bool(np.all(triangulation.mask)):
        raise ValueError(f"All triangles were masked by max_edge_km={threshold:.1f}.")
    return triangulation


def _plot_line_network(ax: Any, metadata: pd.DataFrame, *, line: int, transform: Any) -> None:
    for current_line, group in _station_locations(metadata).groupby("sln_cde", sort=True):
        clean = group.sort_values("sta_cde")
        if len(clean) < 2:
            continue
        if int(current_line) == line:
            ax.plot(
                clean["lon"],
                clean["lat"],
                color="#111111",
                linewidth=2.6,
                transform=transform,
                zorder=5,
            )
            ax.scatter(
                clean["lon"],
                clean["lat"],
                s=36,
                facecolor="#ffcf33",
                edgecolor="#111111",
                linewidth=0.8,
                transform=transform,
                zorder=6,
                label=f"Line {line}",
            )
        else:
            ax.plot(
                clean["lon"],
                clean["lat"],
                color="#8a8a8a",
                linewidth=0.8,
                alpha=0.6,
                transform=transform,
                zorder=3,
            )
            ax.scatter(
                clean["lon"],
                clean["lat"],
                s=10,
                color="#666666",
                alpha=0.5,
                transform=transform,
                zorder=4,
            )


def _plot_pc_panel(
    ax: Any,
    pc_standardized: pd.Series,
    *,
    lag_months: int,
    threshold: float,
) -> None:
    event_dates = pc_standardized.loc[pc_standardized >= threshold].index
    shifted_dates = lagged_event_dates(
        pc_standardized,
        lag_months=lag_months,
        threshold=threshold,
    )
    ax.plot(pc_standardized.index, pc_standardized.to_numpy(), color="#222222", linewidth=1.0)
    ax.axhline(threshold, color="#b23b3b", linewidth=0.9, linestyle="--")
    ax.scatter(event_dates, pc_standardized.loc[event_dates], color="#b23b3b", s=16, zorder=3)
    shifted_y = np.full(len(shifted_dates), pc_standardized.min() - 0.25)
    ax.scatter(shifted_dates, shifted_y, color="#1f77b4", s=14, marker="|", zorder=3)
    ax.set_ylabel("PC z-score")
    ax.set_title(f"PC event dates and composite target dates{format_lag_for_title(lag_months)}")
    ax.grid(True, linewidth=0.4, alpha=0.3)


def _map_extent(metadata: pd.DataFrame) -> tuple[float, float, float, float]:
    stations = _station_locations(metadata)
    lon_range = stations["lon"].max() - stations["lon"].min()
    lat_range = stations["lat"].max() - stations["lat"].min()
    lon_margin = max(lon_range * 0.04, 0.05)
    lat_margin = max(lat_range * 0.04, 0.05)
    return (
        float(stations["lon"].min() - lon_margin),
        float(stations["lon"].max() + lon_margin),
        float(stations["lat"].min() - lat_margin),
        float(stations["lat"].max() + lat_margin),
    )


def _add_cartopy_features(ax: Any, cfeature: Any) -> None:
    try:
        ax.add_feature(cfeature.LAND, facecolor="#eeeeee", edgecolor="none", zorder=0)
        ax.coastlines(resolution="10m", linewidth=0.7, color="#333333", zorder=2)
    except Exception:
        try:
            ax.coastlines(resolution="110m", linewidth=0.7, color="#333333", zorder=2)
        except Exception:
            return


def plot_composite_map(
    *,
    composite: pd.Series,
    metadata: pd.DataFrame,
    pc_standardized: pd.Series,
    line: int,
    mode: int,
    depth: int,
    lag_months: int,
    threshold: float,
    output_path: Path,
    max_edge_km: float | None = None,
    extent: tuple[float, float, float, float] | None = None,
) -> Path:
    """Write one PC lead-lag composite map in lon-lat coordinates."""

    plt, mtri, ccrs, cfeature = _prepare_pyplot()
    projection = ccrs.PlateCarree()
    depth_values = _prepare_depth_values(composite, metadata, depth=depth)
    triangulation = _triangulate_lon_lat(mtri, depth_values, max_edge_km=max_edge_km)
    values = depth_values["value"].to_numpy(dtype=float)

    max_abs = float(np.nanmax(np.abs(values)))
    if not np.isfinite(max_abs) or max_abs == 0:
        max_abs = 1.0
    levels = np.linspace(-max_abs, max_abs, 21)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.6, 8.4), layout="constrained")
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 3.0])
    ax_pc = fig.add_subplot(gs[0, 0])
    ax_map = fig.add_subplot(gs[1, 0], projection=projection)
    _plot_pc_panel(ax_pc, pc_standardized, lag_months=lag_months, threshold=threshold)
    _add_cartopy_features(ax_map, cfeature)

    mesh = ax_map.tricontourf(
        triangulation,
        values,
        cmap="RdBu_r",
        levels=levels,
        vmin=-max_abs,
        vmax=max_abs,
        extend="both",
        transform=projection,
        zorder=1,
    )
    _plot_line_network(ax_map, metadata, line=line, transform=projection)
    ax_map.set_extent(extent or _map_extent(metadata), crs=projection)
    ax_map.set_title(
        f"Mode {mode} composite anomaly | depth {depth} m{format_lag_for_title(lag_months)}"
    )
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.legend(loc="best", fontsize=8, frameon=True)
    colorbar = fig.colorbar(mesh, ax=ax_map, orientation="vertical", shrink=0.62, pad=0.02)
    colorbar.set_label("Temperature anomaly composite (deg C)")
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def write_visualizations(
    *,
    table_dir: Path = OUTPUT_TABLE_DIR,
    output_dir: Path = OUTPUT_FIGURE_DIR,
    line: int = DEFAULT_LINE,
    modes: Iterable[int] | None = None,
    depths: Iterable[int] | None = None,
    lag_months: Iterable[int] = DEFAULT_LEAD_LAG_MONTHS,
    threshold: float = 1.0,
    max_edge_km: float | None = None,
    extent: tuple[float, float, float, float] | None = None,
) -> VisualizationOutputs:
    """Create PC lead-lag composite maps from analysis tables."""

    anomalies, metadata, pcs = read_analysis_tables(table_dir=table_dir, line=line)
    map_extent = extent or _map_extent(metadata)
    selected_modes = tuple(modes) if modes is not None else tuple(
        int(column.removeprefix("PC")) for column in pcs.columns if column.startswith("PC")
    )
    selected_depths = tuple(depths) if depths is not None else tuple(
        depth for depth in STANDARD_DEPTHS if depth in set(metadata["depth_m"])
    )

    paths: list[Path] = []
    skipped: list[str] = []
    for mode in selected_modes:
        pc_standardized = standardize_pc(pcs, mode=mode)
        for lag in lag_months:
            try:
                composite = composite_for_lag(
                    anomalies,
                    pc_standardized,
                    lag_months=lag,
                    threshold=threshold,
                )
            except ValueError as exc:
                skipped.append(f"mode {mode}, lag {lag:+d}: {exc}")
                continue

            for depth in selected_depths:
                lag_token = _format_lag_for_filename(int(lag))
                file_name = f"mode{mode}_lag_{lag_token}_depth_{int(depth)}m.png"
                output_path = output_dir / f"mode_{mode}" / f"lag_{lag_token}" / file_name
                try:
                    paths.append(
                        plot_composite_map(
                            composite=composite,
                            metadata=metadata,
                            pc_standardized=pc_standardized,
                            line=line,
                            mode=mode,
                            depth=int(depth),
                            lag_months=int(lag),
                            threshold=threshold,
                            output_path=output_path,
                            max_edge_km=max_edge_km,
                            extent=map_extent,
                        )
                    )
                except ValueError as exc:
                    skipped.append(
                        f"mode {mode}, lag {lag:+d}, depth {int(depth)} m: {exc}"
                    )
    return VisualizationOutputs(paths=paths, skipped=skipped)
