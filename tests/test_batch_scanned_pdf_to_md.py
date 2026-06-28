from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.batch_scanned_pdf_to_md import (  # noqa: E402
    assess_markdown_quality,
    convert_pdf_folder,
    stage_pdf_to_ascii,
)


def test_assess_markdown_quality_rejects_empty(tmp_path: Path):
    md = tmp_path / "empty.md"
    md.write_text("", encoding="utf-8")
    q = assess_markdown_quality(md)
    assert q["quality_ok"] is False


def test_assess_markdown_quality_rejects_image_only(tmp_path: Path):
    md = tmp_path / "image_only.md"
    md.write_text("![](page_1.png)\n![](page_2.png)\n", encoding="utf-8")
    q = assess_markdown_quality(md)
    assert q["quality_ok"] is False


def test_assess_markdown_quality_accepts_korean_text(tmp_path: Path):
    md = tmp_path / "ok.md"
    md.write_text("한글 본문입니다. " * 100, encoding="utf-8")
    q = assess_markdown_quality(md, min_compact_chars=100)
    assert q["quality_ok"] is True
    assert q["korean_chars"] > 0


def test_stage_pdf_to_ascii(tmp_path: Path):
    src = tmp_path / "한글 파일명.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF")
    staged = stage_pdf_to_ascii(src, tmp_path / "staging", 1)
    assert staged.name == "book_001.pdf"
    assert staged.exists()


def test_convert_pdf_folder_missing_input(tmp_path: Path):
    result = convert_pdf_folder(tmp_path / "does_not_exist", tmp_path / "out")
    assert result.ok is False
    assert result.failed == 1
    manifest = Path(result.manifest_path)
    assert manifest.exists()


def test_convert_pdf_folder_empty_dir_writes_manifest(tmp_path: Path):
    empty_in = tmp_path / "empty_in"
    empty_in.mkdir()
    out = tmp_path / "out"
    result = convert_pdf_folder(empty_in, out)
    assert result.total_files == 0
    manifest = Path(result.manifest_path)
    assert manifest.exists()
    # manifest must be valid UTF-8 JSON
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["input_dir"]
    assert "records" in data
