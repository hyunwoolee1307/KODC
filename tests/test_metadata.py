from __future__ import annotations

from pathlib import Path

from kodc.metadata import station_metadata_from_payloads, write_station_metadata_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_station_metadata_from_payloads_uses_bot_dep_as_max_depth() -> None:
    metadata = station_metadata_from_payloads([FIXTURES / "soo_code_E.json"])

    assert {"sln_cde", "sta_cde", "bot_dep", "max_depth_m"}.issubset(metadata.columns)
    assert metadata.loc[metadata["sta_cde"] == 1, "max_depth_m"].iloc[0] == 0
    assert metadata.loc[metadata["sta_cde"] == 2, "max_depth_m"].iloc[0] == 10


def test_write_station_metadata_csv(tmp_path: Path) -> None:
    output_path = write_station_metadata_csv(
        input_paths=[FIXTURES / "soo_code_E.json"],
        output_path=tmp_path / "station_codes.csv",
    )

    assert output_path.exists()
