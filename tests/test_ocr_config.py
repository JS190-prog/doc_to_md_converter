from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.ocr_config import (  # noqa: E402
    DEFAULT_TEXT_DET_LIMIT_SIDE_LEN,
    TEXT_DET_LIMIT_ENV,
    resolve_text_det_limit_side_len,
)


def test_text_detection_limit_defaults_to_measured_dense_page_value(monkeypatch):
    monkeypatch.delenv(TEXT_DET_LIMIT_ENV, raising=False)

    assert DEFAULT_TEXT_DET_LIMIT_SIDE_LEN == 2048
    assert resolve_text_det_limit_side_len() == 2048


@pytest.mark.parametrize(
    ("configured", "expected"),
    [("1024", 1024), ("2048", 2048), ("512", 960), ("8192", 4096)],
)
def test_text_detection_limit_honors_bounded_override(configured, expected):
    assert resolve_text_det_limit_side_len(configured) == expected


def test_text_detection_limit_rejects_non_integer_override():
    with pytest.raises(ValueError, match=TEXT_DET_LIMIT_ENV):
        resolve_text_det_limit_side_len("auto")
