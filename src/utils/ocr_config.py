from __future__ import annotations

import os


TEXT_DET_LIMIT_ENV = "DOC_TO_MD_TEXT_DET_LIMIT_SIDE_LEN"
MIN_TEXT_DET_LIMIT_SIDE_LEN = 960
DEFAULT_TEXT_DET_LIMIT_SIDE_LEN = 2048
MAX_TEXT_DET_LIMIT_SIDE_LEN = 4096


def resolve_text_det_limit_side_len(value: str | None = None) -> int:
    """Resolve the bounded PaddleOCR detection size used by the converter.

    Dense 300-DPI pages lose too much text at PaddleOCR's 960-pixel limit.
    Keep an explicit environment override for constrained or unusually detailed
    documents, while making the measured 2048-pixel setting the safe default.
    """
    raw_value = value
    if raw_value is None:
        raw_value = os.getenv(
            TEXT_DET_LIMIT_ENV,
            str(DEFAULT_TEXT_DET_LIMIT_SIDE_LEN),
        )

    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{TEXT_DET_LIMIT_ENV} must be an integer, got {raw_value!r}"
        ) from exc

    return max(
        MIN_TEXT_DET_LIMIT_SIDE_LEN,
        min(MAX_TEXT_DET_LIMIT_SIDE_LEN, parsed),
    )
