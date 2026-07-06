from __future__ import annotations

from pathlib import Path

import pandas as pd

from kodc.convert import convert_json_file, items_from_payload, read_json_payload

FIXTURES = Path(__file__).parent / "fixtures"


def test_items_from_payload_handles_normal_response() -> None:
    payload = read_json_payload(FIXTURES / "kodc_normal.json")

    items = items_from_payload(payload)

    assert len(items) == 1
    assert items[0]["sln_cde"] == "208"


def test_items_from_payload_handles_empty_year() -> None:
    payload = read_json_payload(FIXTURES / "kodc_empty.json")

    assert items_from_payload(payload) == []


def test_convert_json_file_writes_index_free_csv(tmp_path: Path) -> None:
    output_path = convert_json_file(FIXTURES / "kodc_normal.json", output_dir=tmp_path)

    df = pd.read_csv(output_path, encoding="utf-8-sig")

    assert output_path.name == "kodc_normal.csv"
    assert "Unnamed: 0" not in df.columns
    assert {"sln_cde", "sta_cde", "obs_dtm", "wtr_dep", "wtr_tmp"}.issubset(df.columns)
    assert int(df.loc[0, "sln_cde"]) == 208
