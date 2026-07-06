"""Download KODC yearly JSON payloads from the NIFS OpenAPI."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import NIFS_API_ID, NIFS_API_URL, RAW_DATA_DIR


@dataclass(frozen=True)
class DownloadResult:
    year: int
    path: Path
    skipped: bool


def fetch_year_payload(
    *,
    api_key: str,
    year: int,
    session: requests.Session | None = None,
    base_url: str = NIFS_API_URL,
    timeout: float = 60.0,
) -> dict:
    """Fetch one year of KODC observations as a decoded JSON payload."""

    client = session or requests.Session()
    params = {
        "id": NIFS_API_ID,
        "key": api_key,
        "sdate": f"{year}0101",
        "edate": f"{year}1231",
    }
    response = client.get(base_url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def download_year(
    *,
    api_key: str,
    year: int,
    output_dir: Path = RAW_DATA_DIR,
    overwrite: bool = False,
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> DownloadResult:
    """Download a single year to ``output_dir/kodcYYYY.json``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"kodc{year}.json"
    if output_path.exists() and not overwrite:
        return DownloadResult(year=year, path=output_path, skipped=True)

    payload = fetch_year_payload(
        api_key=api_key,
        year=year,
        session=session,
        timeout=timeout,
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return DownloadResult(year=year, path=output_path, skipped=False)


def download_years(
    *,
    api_key: str,
    years: Iterable[int],
    output_dir: Path = RAW_DATA_DIR,
    overwrite: bool = False,
    timeout: float = 60.0,
) -> list[DownloadResult]:
    """Download multiple years with a shared HTTP session."""

    with requests.Session() as session:
        return [
            download_year(
                api_key=api_key,
                year=year,
                output_dir=output_dir,
                overwrite=overwrite,
                session=session,
                timeout=timeout,
            )
            for year in years
        ]
