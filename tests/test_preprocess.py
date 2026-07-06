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
