from __future__ import annotations

from pathlib import Path

import pytest

from kodc.config import get_api_key


def test_get_api_key_prefers_environment() -> None:
    assert get_api_key({"NIFS_API_KEY": "from-env"}, key_file=Path("missing")) == "from-env"


def test_get_api_key_reads_local_file(tmp_path: Path) -> None:
    key_file = tmp_path / "NIFS_API_KEY"
    key_file.write_text("from-file\n", encoding="utf-8")

    assert get_api_key({}, key_file=key_file) == "from-file"


def test_get_api_key_rejects_missing_or_placeholder_file(tmp_path: Path) -> None:
    key_file = tmp_path / "NIFS_API_KEY"
    key_file.write_text("replace-with-your-nifs-openapi-key\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no usable API key"):
        get_api_key({}, key_file=key_file)
