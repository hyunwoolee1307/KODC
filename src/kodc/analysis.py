"""High-level EOF analysis workflow for generated KODC CSV files."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import (
    DEFAULT_BASELINE_END,
    DEFAULT_BASELINE_START,
    DEFAULT_END_DATE,
    DEFAULT_EOF_MODES,
    DEFAULT_FREQ_MONTHS,
    DEFAULT_LINE,
    DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_SAMPLE_DAY,
    DEFAULT_START_DATE,
    INTERIM_DATA_DIR,
    OUTPUT_TABLE_DIR,
    STANDARD_DEPTHS,
    STATION_CODE_CSV,
)
from .metadata import read_station_metadata
from .preprocess import normalize_columns, process_anomaly_with_filter, read_kodc_csvs


@dataclass(frozen=True)
class EofTables:
    pcs: pd.DataFrame
    variance: pd.DataFrame


@dataclass(frozen=True)
class AnalysisOutputs:
    paths: dict[str, Path]


def compute_eof_tables(anomaly_df: pd.DataFrame, *, n_modes: int = DEFAULT_EOF_MODES) -> EofTables:
    """Compute EOF principal components and explained variance tables."""

    from eofs.standard import Eof

    matrix = anomaly_df.fillna(0.0).to_numpy(dtype=float)
    if matrix.size == 0:
        raise ValueError("EOF input matrix is empty.")

    max_modes = min(n_modes, matrix.shape[0], matrix.shape[1])
    if max_modes < 1:
        raise ValueError("EOF input matrix must have at least one time and one feature.")

    solver = Eof(matrix)
    pcs = solver.pcs(npcs=max_modes)
    variance_fraction = solver.varianceFraction()[:max_modes]

    pc_columns = [f"PC{mode}" for mode in range(1, max_modes + 1)]
    pcs_df = pd.DataFrame(pcs, index=anomaly_df.index, columns=pc_columns)
    variance_df = pd.DataFrame(
        {
            "mode": list(range(1, max_modes + 1)),
            "variance_fraction": variance_fraction,
            "variance_percent": variance_fraction * 100.0,
        }
    )
    return EofTables(pcs=pcs_df, variance=variance_df)


def write_analysis_tables(
    *,
    input_dir: Path = INTERIM_DATA_DIR,
    output_dir: Path = OUTPUT_TABLE_DIR,
    line: int = DEFAULT_LINE,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    baseline_start: str = DEFAULT_BASELINE_START,
    baseline_end: str = DEFAULT_BASELINE_END,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    n_modes: int = DEFAULT_EOF_MODES,
    standard_depths: Iterable[int] = STANDARD_DEPTHS,
    station_metadata_path: Path | None = STATION_CODE_CSV,
    freq_months: int = DEFAULT_FREQ_MONTHS,
    sample_day: int = DEFAULT_SAMPLE_DAY,
) -> AnalysisOutputs:
    """Run the official table-generating analysis workflow."""

    dataframe = normalize_columns(read_kodc_csvs(input_dir))
    line_data = dataframe.loc[dataframe["sln_cde"] == line]
    if line_data.empty:
        raise ValueError(f"No observations found for line {line}.")
    station_metadata = None
    if station_metadata_path is not None and station_metadata_path.exists():
        station_metadata = read_station_metadata(station_metadata_path)

    all_result = process_anomaly_with_filter(
        dataframe,
        start_date=start_date,
        end_date=end_date,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        min_observations=min_observations,
        standard_depths=standard_depths,
        station_metadata=station_metadata,
        freq_months=freq_months,
        sample_day=sample_day,
    )
    line_result = process_anomaly_with_filter(
        line_data,
        start_date=start_date,
        end_date=end_date,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        min_observations=min_observations,
        standard_depths=standard_depths,
        station_metadata=station_metadata,
        freq_months=freq_months,
        sample_day=sample_day,
    )
    eof_tables = compute_eof_tables(line_result.anomalies, n_modes=n_modes)

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"line{line}"
    paths = {
        "line_anomalies": output_dir / f"{prefix}_anomalies.csv",
        "all_station_anomalies": output_dir / "all_station_anomalies.csv",
        "station_metadata": output_dir / "station_metadata.csv",
        "line_pcs": output_dir / f"{prefix}_pcs.csv",
        "line_variance": output_dir / f"{prefix}_variance.csv",
    }

    line_result.anomalies.to_csv(paths["line_anomalies"], index_label="obs_dtm")
    all_result.anomalies.to_csv(paths["all_station_anomalies"], index_label="obs_dtm")
    all_result.metadata.to_csv(paths["station_metadata"], index=False)
    eof_tables.pcs.to_csv(paths["line_pcs"], index_label="obs_dtm")
    eof_tables.variance.to_csv(paths["line_variance"], index=False)
    return AnalysisOutputs(paths=paths)
