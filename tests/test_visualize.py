from __future__ import annotations

from pathlib import Path

import pandas as pd

from kodc.config import DEFAULT_LEAD_LAG_MONTHS
from kodc.visualize import (
    composite_for_lag,
    format_lag_for_title,
    standardize_pc,
    write_visualizations,
)


def _metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "column": [
                "Sln207_Sta1_0m",
                "Sln207_Sta2_0m",
                "Sln208_Sta1_0m",
                "Sln208_Sta2_0m",
            ],
            "sln_cde": [207, 207, 208, 208],
            "sta_cde": [1, 2, 1, 2],
            "lat": [35.0, 35.0, 36.0, 36.0],
            "lon": [129.0, 130.0, 129.0, 130.0],
            "depth_m": [0, 0, 0, 0],
        }
    )


def test_default_lags_include_zero() -> None:
    assert 0 in DEFAULT_LEAD_LAG_MONTHS


def test_lag_zero_is_not_rendered_in_titles() -> None:
    assert format_lag_for_title(0) == ""
    assert format_lag_for_title(2) == " | lag +2 months"


def test_composite_for_lag_uses_pc_shifted_dates() -> None:
    index = pd.to_datetime(["2000-01-15", "2000-03-15", "2000-05-15", "2000-07-15"])
    anomalies = pd.DataFrame({"Sln208_Sta1_0m": [1.0, 2.0, 3.0, 4.0]}, index=index)
    pcs = pd.DataFrame({"PC1": [-1.0, 2.0, -1.0, -1.0]}, index=index)
    pc_standardized = standardize_pc(pcs, mode=1)

    composite = composite_for_lag(
        anomalies,
        pc_standardized,
        lag_months=2,
        threshold=1.0,
    )

    assert composite["Sln208_Sta1_0m"] == 3.0


def test_write_visualizations_creates_png(tmp_path: Path) -> None:
    table_dir = tmp_path / "tables"
    output_dir = tmp_path / "figures"
    table_dir.mkdir()

    index = pd.to_datetime(["2000-01-15", "2000-03-15", "2000-05-15", "2000-07-15"])
    anomalies = pd.DataFrame(
        {
            "obs_dtm": index,
            "Sln207_Sta1_0m": [1.0, 2.0, 3.0, 4.0],
            "Sln207_Sta2_0m": [1.5, 2.5, 3.5, 4.5],
            "Sln208_Sta1_0m": [2.0, 3.0, 4.0, 5.0],
            "Sln208_Sta2_0m": [2.5, 3.5, 4.5, 5.5],
        }
    )
    pcs = pd.DataFrame({"obs_dtm": index, "PC1": [-1.0, 2.0, -1.0, -1.0]})
    anomalies.to_csv(table_dir / "all_station_anomalies.csv", index=False)
    _metadata().to_csv(table_dir / "station_metadata.csv", index=False)
    pcs.to_csv(table_dir / "line208_pcs.csv", index=False)

    outputs = write_visualizations(
        table_dir=table_dir,
        output_dir=output_dir,
        line=208,
        modes=(1,),
        depths=(0,),
        lag_months=(2,),
        threshold=1.0,
        max_edge_km=200.0,
    )

    assert len(outputs.paths) == 1
    assert outputs.paths[0].exists()
    assert outputs.paths[0].suffix == ".png"
