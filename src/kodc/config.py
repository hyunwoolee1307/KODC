"""Project defaults for the KODC reproducibility workflow."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
OUTPUT_TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"

NIFS_API_URL = "https://www.nifs.go.kr/OpenAPI_json"
NIFS_API_ID = "sooList"
NIFS_API_KEY_ENV = "NIFS_API_KEY"

DEFAULT_START_YEAR = 1961
DEFAULT_END_YEAR = 2025
DEFAULT_LINE = 208
DEFAULT_START_DATE = "1982-01-01"
DEFAULT_END_DATE = "2025-12-31"
DEFAULT_BASELINE_START = "1991-01-01"
DEFAULT_BASELINE_END = "2020-12-31"
DEFAULT_MIN_OBSERVATIONS = 240
DEFAULT_EOF_MODES = 4
DEFAULT_FREQ_MONTHS = 2
DEFAULT_SAMPLE_DAY = 15
DEFAULT_LEAD_LAG_MONTHS = (-2, -4, -6, -12, 0, 2, 4, 6, 12)

STANDARD_DEPTHS = (0, 10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500)

KODC_COLUMNS = (
    "gru_nam",
    "sln_cde",
    "sta_cde",
    "lat",
    "lon",
    "obs_dtm",
    "wtr_dep",
    "wtr_tmp",
    "qc_wtr",
    "sal",
    "qc_sal",
    "dox",
    "qc_dox",
    "nut_po4_p",
    "nut_no2_n",
    "nut_no3_n",
    "nut_sio2_si",
    "nut_ph",
    "wtr_trn",
    "atm",
    "res_vsl_nm",
)

COLUMN_ALIASES = {
    "Line": "sln_cde",
    "Station": "sta_cde",
    "Latitude": "lat",
    "Longitude": "lon",
    "Date(KST)": "obs_dtm",
    "Depth(m)": "wtr_dep",
    "Water Temp(°C)": "wtr_tmp",
}


def get_api_key(env: Mapping[str, str] | None = None) -> str:
    """Return the NIFS API key from the environment."""

    values = os.environ if env is None else env
    key = values.get(NIFS_API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"{NIFS_API_KEY_ENV} is not set. Export it before running the download task."
        )
    return key
