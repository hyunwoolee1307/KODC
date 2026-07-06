"""Convert NIFS KODC JSON payloads into clean CSV files."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import INTERIM_DATA_DIR, KODC_COLUMNS, RAW_DATA_DIR


def items_from_payload(payload: dict) -> list[dict]:
    """Extract observation items from one NIFS JSON payload."""

    body = payload.get("body") or {}
    items = body.get("item", [])
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return items
    raise TypeError("Expected payload['body']['item'] to be a list, dict, or null.")


def dataframe_from_items(items: list[dict]) -> pd.DataFrame:
    """Create a CSV-ready DataFrame with stable KODC column order."""

    if not items:
        return pd.DataFrame(columns=KODC_COLUMNS)

    df = pd.DataFrame(items)
    df = df.loc[:, [column for column in df.columns if not str(column).startswith("Unnamed")]]

    for column in KODC_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    ordered = [column for column in KODC_COLUMNS if column in df.columns]
    extras = [column for column in df.columns if column not in ordered]
    return df.loc[:, ordered + extras]


def read_json_payload(path: Path) -> dict:
    """Read one JSON payload from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def convert_json_file(json_path: Path, output_dir: Path = INTERIM_DATA_DIR) -> Path:
    """Convert one ``kodcYYYY.json`` file to ``kodcYYYY.csv``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = read_json_payload(json_path)
    df = dataframe_from_items(items_from_payload(payload))
    output_path = output_dir / f"{json_path.stem}.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def convert_json_directory(
    input_dir: Path = RAW_DATA_DIR,
    output_dir: Path = INTERIM_DATA_DIR,
) -> list[Path]:
    """Convert all yearly JSON files in a directory."""

    json_files = sorted(input_dir.glob("kodc*.json"))
    if not json_files:
        raise FileNotFoundError(f"No kodc*.json files found in {input_dir}.")
    return [convert_json_file(path, output_dir=output_dir) for path in json_files]
