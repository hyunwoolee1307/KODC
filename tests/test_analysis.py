from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pandas as pd

from kodc.analysis import compute_eof_tables, write_analysis_tables

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_eof_tables_shapes() -> None:
    anomaly_df = pd.DataFrame(
        {
            "Sln208_Sta1_0m": [-1.0, 1.0, -0.5, 0.5],
            "Sln208_Sta1_10m": [-0.8, 0.8, -0.3, 0.3],
            "Sln208_Sta2_0m": [1.0, -1.0, 0.5, -0.5],
        },
        index=pd.date_range("2000-01-15", periods=4, freq="2MS"),
    )

    result = compute_eof_tables(anomaly_df, n_modes=2)

    assert result.pcs.shape == (4, 2)
    assert result.variance["mode"].tolist() == [1, 2]


def test_write_analysis_tables_creates_expected_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "interim"
    output_dir = tmp_path / "tables"
    input_dir.mkdir()
    copyfile(FIXTURES / "kodc_synthetic.csv", input_dir / "kodc_synthetic.csv")

    outputs = write_analysis_tables(
        input_dir=input_dir,
        output_dir=output_dir,
        line=208,
        start_date="2000-01-01",
        end_date="2001-03-31",
        baseline_start="2000-01-01",
        baseline_end="2001-12-31",
        min_observations=4,
        n_modes=2,
        standard_depths=(0, 10),
    )

    expected = {
        "line208_anomalies.csv",
        "all_station_anomalies.csv",
        "station_metadata.csv",
        "line208_pcs.csv",
        "line208_variance.csv",
    }
    assert {path.name for path in outputs.paths.values()} == expected
    for path in outputs.paths.values():
        assert path.exists()
