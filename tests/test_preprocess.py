from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from kodc.preprocess import process_anomaly_with_filter

FIXTURES = Path(__file__).parent / "fixtures"


def _synthetic_dataframe() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "kodc_synthetic.csv")


def test_process_anomaly_with_filter_interpolates_and_filters() -> None:
    result = process_anomaly_with_filter(
        _synthetic_dataframe(),
        start_date="2000-01-01",
        end_date="2001-03-31",
        baseline_start="2000-01-01",
        baseline_end="2001-12-31",
        min_observations=4,
        standard_depths=(0, 10),
    )

    assert "Sln208_Sta1_0m" in result.anomalies.columns
    assert "Sln208_Sta2_10m" in result.anomalies.columns
    assert result.metadata.shape[0] == 4
    assert result.anomalies.loc[pd.Timestamp("2000-01-15"), "Sln208_Sta1_0m"] == pytest.approx(
        -1.0
    )
    assert result.anomalies.loc[pd.Timestamp("2001-01-15"), "Sln208_Sta1_0m"] == pytest.approx(
        1.0
    )


def test_process_anomaly_with_filter_caps_depths_with_station_metadata() -> None:
    station_metadata = pd.DataFrame(
        {
            "sln_cde": [208, 208],
            "sta_cde": [1, 2],
            "lat": [35.0, 35.5],
            "lon": [129.0, 130.0],
            "max_depth_m": [0, 10],
        }
    )

    result = process_anomaly_with_filter(
        _synthetic_dataframe(),
        start_date="2000-01-01",
        end_date="2001-03-31",
        baseline_start="2000-01-01",
        baseline_end="2001-12-31",
        min_observations=4,
        standard_depths=(0, 10),
        station_metadata=station_metadata,
    )

    assert "Sln208_Sta1_0m" in result.anomalies.columns
    assert "Sln208_Sta1_10m" not in result.anomalies.columns
    assert "max_depth_m" in result.metadata.columns
    station_1_depths = result.metadata.loc[
        result.metadata["sta_cde"] == 1,
        "max_depth_m",
    ].unique()
    assert station_1_depths.tolist() == [0.0]


def test_process_anomaly_with_filter_rejects_under_sampled_stations() -> None:
    with pytest.raises(ValueError, match="No stations satisfied"):
        process_anomaly_with_filter(
            _synthetic_dataframe(),
            start_date="2000-01-01",
            end_date="2001-03-31",
            baseline_start="2000-01-01",
            baseline_end="2001-12-31",
            min_observations=5,
            standard_depths=(0, 10),
        )
