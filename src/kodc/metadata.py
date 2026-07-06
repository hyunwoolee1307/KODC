"""Station metadata helpers for the NIFS ``sooCode`` endpoint."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

from .config import (
    NIFS_API_URL,
    NIFS_REGION_CODES,
    NIFS_STATION_API_ID,
    RAW_DATA_DIR,
    STATION_CODE_CSV,
    STATION_COLUMN_ALIASES,
)
from .convert import items_from_payload

STATION_COLUMNS = (
    "gru_nam",
    "sln_cde",
    "sta_cde",
    "bld_dat",
    "end_dat",
    "lat",
    "lon",
    "zoo_dep",
    "bot_dep",
    "max_depth_m",
)


def fetch_station_code_payload(
    *,
    api_key: str,
    region_code: str,
    session: requests.Session | None = None,
    base_url: str = NIFS_API_URL,
    timeout: float = 60.0,
) -> dict:
    """Fetch station metadata for one NIFS region code."""

    client = session or requests.Session()
    response = client.get(
        base_url,
        params={"id": NIFS_STATION_API_ID, "key": api_key, "gru_nam": region_code},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def download_station_code_payloads(
    *,
    api_key: str,
    output_dir: Path = RAW_DATA_DIR,
    region_codes: tuple[str, ...] = NIFS_REGION_CODES,
    overwrite: bool = False,
    timeout: float = 60.0,
) -> list[Path]:
    """Download raw ``sooCode`` JSON payloads for the requested regions."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with requests.Session() as session:
        for region_code in region_codes:
            output_path = output_dir / f"soo_code_{region_code}.json"
            if output_path.exists() and not overwrite:
                paths.append(output_path)
                continue
            payload = fetch_station_code_payload(
                api_key=api_key,
                region_code=region_code,
                session=session,
                timeout=timeout,
            )
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            paths.append(output_path)
    return paths


def normalize_station_metadata(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize ``sooCode`` station metadata into stable analysis columns."""

    df = dataframe.copy().rename(columns=STATION_COLUMN_ALIASES)
    df = df.loc[:, [column for column in df.columns if not str(column).startswith("Unnamed")]]
    df = df.loc[:, ~df.columns.duplicated()]

    required = ("sln_cde", "sta_cde", "lat", "lon")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required station metadata columns: {', '.join(missing)}")

    for column in ("sln_cde", "sta_cde", "lat", "lon", "zoo_dep", "bot_dep", "max_depth_m"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    if "bot_dep" not in df.columns and "max_depth_m" in df.columns:
        df["bot_dep"] = df["max_depth_m"]
    elif "bot_dep" not in df.columns:
        df["bot_dep"] = pd.NA

    if "max_depth_m" not in df.columns:
        df["max_depth_m"] = pd.to_numeric(df["bot_dep"], errors="coerce")
    else:
        df["max_depth_m"] = df["max_depth_m"].fillna(pd.to_numeric(df["bot_dep"], errors="coerce"))

    for column in STATION_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    df = df.dropna(subset=["sln_cde", "sta_cde"])
    df["sln_cde"] = df["sln_cde"].astype(int)
    df["sta_cde"] = df["sta_cde"].astype(int)
    return df.loc[:, list(STATION_COLUMNS)].drop_duplicates(["sln_cde", "sta_cde"])


def station_metadata_from_payloads(paths: list[Path]) -> pd.DataFrame:
    """Create normalized station metadata from raw ``sooCode`` JSON payloads."""

    frames = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        frames.append(pd.DataFrame(items_from_payload(payload)))
    if not frames:
        raise ValueError("No station metadata payloads were provided.")
    return normalize_station_metadata(pd.concat(frames, ignore_index=True))


def write_station_metadata_csv(
    *,
    input_paths: list[Path],
    output_path: Path = STATION_CODE_CSV,
) -> Path:
    """Write normalized station metadata CSV from raw payload files."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    station_metadata_from_payloads(input_paths).to_csv(output_path, index=False)
    return output_path


def read_station_metadata(path: Path = STATION_CODE_CSV) -> pd.DataFrame:
    """Read normalized station metadata from CSV."""

    return normalize_station_metadata(pd.read_csv(path, encoding="utf-8-sig"))
