from __future__ import annotations

import json
import os
import shutil
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = PROJECT_ROOT / "offline_assets" / "paddle_models"

REQUIRED_MODELS = (
    "PP-OCRv5_server_det",
    "korean_PP-OCRv5_mobile_rec",
)
REQUIRED_MODEL_FILES = (
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)


def _model_home_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_model_home = os.getenv("PADDLE_PDX_MODEL_HOME", "").strip()
    if env_model_home:
        candidates.append(Path(env_model_home))

    candidates.append(Path.home() / ".paddlex" / "official_models")
    return candidates


def _resolve_model_home() -> Path:
    for candidate in _model_home_candidates():
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Paddle model cache not found. Expected one of: "
        + ", ".join(str(p) for p in _model_home_candidates())
    )


def _is_valid_model_dir(path: Path) -> bool:
    return path.is_dir() and all((path / file_name).exists() for file_name in REQUIRED_MODEL_FILES)


def _copy_model(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(
        source_dir,
        target_dir,
        ignore=shutil.ignore_patterns(".cache", "*.md", ".gitattributes", "*.metadata"),
    )


def _ensure_models_downloaded() -> None:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    print("[1/3] Ensuring PaddleOCR models are available in local cache...")
    PaddleOCR(
        lang="korean",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_limit_side_len=960,
        text_det_limit_type="max",
    )


def _copy_required_models() -> None:
    print("[2/3] Copying required models into offline_assets...")
    model_home = _resolve_model_home()
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    for model_name in REQUIRED_MODELS:
        source_dir = model_home / model_name
        target_dir = TARGET_ROOT / model_name
        if not source_dir.exists():
            raise FileNotFoundError(f"Required model not found in cache: {source_dir}")
        _copy_model(source_dir, target_dir)
        if not _is_valid_model_dir(target_dir):
            raise RuntimeError(f"Copied model is incomplete: {target_dir}")
        print(f"  - {model_name}")


def _write_manifest() -> None:
    print("[3/3] Writing manifest...")
    manifest_path = TARGET_ROOT / "manifest.json"
    manifest = {
        "models": list(REQUIRED_MODELS),
        "required_files": list(REQUIRED_MODEL_FILES),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    try:
        _ensure_models_downloaded()
        _copy_required_models()
        _write_manifest()
        print(f"Done. Offline assets prepared at: {TARGET_ROOT}")
        return 0
    except Exception as exc:
        print(f"Failed to prepare offline assets: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

