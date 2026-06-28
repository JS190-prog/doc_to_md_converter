from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Dict

APP_DIR_NAME = "doc_to_md_converter"
BUNDLE_VERSION = "2026.02.12.1"
MODEL_NAMES = {
    "det": "PP-OCRv5_server_det",
    "rec": "korean_PP-OCRv5_mobile_rec",
}
REQUIRED_MODEL_FILES = (
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)


def _app_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _bundled_models_root() -> Path:
    override = os.getenv("DOC2MD_PADDLE_MODEL_BUNDLE", "").strip()
    if override:
        return Path(override)

    if getattr(sys, "frozen", False):
        return _app_root() / "runtime_assets" / "paddle_models"
    return _app_root() / "offline_assets" / "paddle_models"


def _runtime_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home())
    root = Path(local_app_data) / APP_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_models_root() -> Path:
    root = _runtime_root() / "paddle_models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_valid_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return all((path / file_name).exists() for file_name in REQUIRED_MODEL_FILES)


def _copy_model_dir(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(
        source_dir,
        target_dir,
        ignore=shutil.ignore_patterns(".cache", "*.md", ".gitattributes", "*.metadata"),
    )


def _marker_path(runtime_models_root: Path) -> Path:
    return runtime_models_root / ".bundle_version"


def _needs_refresh(runtime_models_root: Path) -> bool:
    marker = _marker_path(runtime_models_root)
    if not marker.exists():
        return True
    try:
        return marker.read_text(encoding="utf-8").strip() != BUNDLE_VERSION
    except Exception:
        return True


def _write_marker(runtime_models_root: Path) -> None:
    _marker_path(runtime_models_root).write_text(BUNDLE_VERSION, encoding="utf-8")


def _model_kwargs_from(models_root: Path) -> Dict[str, str]:
    """Return explicit PaddleOCR model kwargs if both models are valid under
    ``models_root``; otherwise an empty dict."""
    detection_model_dir = models_root / MODEL_NAMES["det"]
    recognition_model_dir = models_root / MODEL_NAMES["rec"]
    if not (_is_valid_model_dir(detection_model_dir) and _is_valid_model_dir(recognition_model_dir)):
        return {}
    return {
        "text_detection_model_name": MODEL_NAMES["det"],
        "text_detection_model_dir": str(detection_model_dir),
        "text_recognition_model_name": MODEL_NAMES["rec"],
        "text_recognition_model_dir": str(recognition_model_dir),
    }


def prepare_offline_ocr_assets() -> Dict[str, str]:
    """
    Copies bundled PaddleOCR models into a local writable directory on first run,
    and returns explicit model directories for PaddleOCR initialization.
    """
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    source_root = _bundled_models_root()
    runtime_models_root = _runtime_models_root()
    model_names = list(MODEL_NAMES.values())

    source_usable = source_root.exists() and all(
        _is_valid_model_dir(source_root / name) for name in model_names
    )

    # When the bundled source is unavailable, reuse models that were already
    # staged into the writable runtime dir on a previous run. Without this,
    # a missing source bundle returns {} and forces PaddleOCR to resolve its
    # models online — which hangs on offline / network-locked hosts even though
    # valid models are already present on disk.
    if not source_usable:
        runtime_kwargs = _model_kwargs_from(runtime_models_root)
        if runtime_kwargs:
            return runtime_kwargs
        if source_root.exists():
            missing = [name for name in model_names if not _is_valid_model_dir(source_root / name)]
            print(f"[OCR] Bundled model files are missing: {', '.join(missing)}")
        return {}

    refresh_needed = _needs_refresh(runtime_models_root)

    for model_name in model_names:
        source_model_dir = source_root / model_name
        target_model_dir = runtime_models_root / model_name
        if refresh_needed or not _is_valid_model_dir(target_model_dir):
            _copy_model_dir(source_model_dir, target_model_dir)

    _write_marker(runtime_models_root)

    return _model_kwargs_from(runtime_models_root)
