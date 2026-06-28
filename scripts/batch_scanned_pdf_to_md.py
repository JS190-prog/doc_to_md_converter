from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from src.backend import process_file  # noqa: E402

BatchStatus = Literal["queued", "running", "converted", "failed", "skipped"]


@dataclass
class PdfConvertRecord:
    source_pdf: str
    staged_pdf: str | None
    output_md: str | None
    status: BatchStatus
    message: str
    bytes_in: int | None = None
    bytes_out: int | None = None
    compact_chars: int = 0
    korean_chars: int = 0
    quality_ok: bool = False


@dataclass
class BatchConvertResult:
    ok: bool
    input_dir: str
    output_dir: str
    manifest_path: str
    total_files: int
    converted: int
    failed: int
    skipped: int
    records: list[PdfConvertRecord]


def _log(message: str) -> None:
    """Progress goes to stderr so --json stdout stays machine-readable."""
    print(message, file=sys.stderr, flush=True)


def compact_text(text: str) -> str:
    return "".join(text.split())


def count_korean(text: str) -> int:
    return sum(1 for ch in text if "가" <= ch <= "힣")


def write_manifest(path: Path, result: BatchConvertResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def assess_markdown_quality(md_path: Path, min_compact_chars: int = 500) -> dict[str, Any]:
    if not md_path.exists():
        return {
            "quality_ok": False,
            "bytes_out": 0,
            "compact_chars": 0,
            "korean_chars": 0,
            "reason": "output markdown not found",
        }
    text = md_path.read_text(encoding="utf-8", errors="replace")
    compact = compact_text(text)
    image_only = text.count("![](") > 0 and len(compact) < 200
    quality_ok = len(compact) >= min_compact_chars and not image_only
    return {
        "quality_ok": quality_ok,
        "bytes_out": md_path.stat().st_size,
        "compact_chars": len(compact),
        "korean_chars": count_korean(text),
        "reason": "ok" if quality_ok else "low text yield or image-only markdown",
    }


def stage_pdf_to_ascii(source: Path, staging_dir: Path, index: int) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged = staging_dir / f"book_{index:03d}.pdf"
    shutil.copy2(source, staged)
    return staged


def convert_one_pdf(
    source_pdf: Path,
    staging_dir: Path,
    markdown_dir: Path,
    index: int,
    overwrite: bool,
) -> PdfConvertRecord:
    record = PdfConvertRecord(
        str(source_pdf),
        None,
        None,
        "running",
        "started",
        bytes_in=source_pdf.stat().st_size if source_pdf.exists() else None,
    )
    try:
        staged = stage_pdf_to_ascii(source_pdf, staging_dir, index)
        record.staged_pdf = str(staged)
        generated_md = staged.with_suffix("").with_name(staged.stem + "_converted.md")
        final_md = markdown_dir / generated_md.name
        if final_md.exists() and not overwrite:
            q = assess_markdown_quality(final_md)
            record.output_md = str(final_md)
            record.status = "skipped"
            record.message = "already converted; use --overwrite to regenerate"
            record.bytes_out = q["bytes_out"]
            record.compact_chars = q["compact_chars"]
            record.korean_chars = q["korean_chars"]
            record.quality_ok = q["quality_ok"]
            return record
        success, message = process_file(str(staged))
        if not success:
            record.status = "failed"
            record.message = message
            return record
        if not generated_md.exists():
            record.status = "failed"
            record.message = (
                f"converter reported success but output not found: {generated_md}"
            )
            return record
        markdown_dir.mkdir(parents=True, exist_ok=True)
        if final_md.exists():
            final_md.unlink()
        shutil.move(str(generated_md), str(final_md))
        q = assess_markdown_quality(final_md)
        record.output_md = str(final_md)
        record.status = "converted" if q["quality_ok"] else "failed"
        record.message = "converted" if q["quality_ok"] else q["reason"]
        record.bytes_out = q["bytes_out"]
        record.compact_chars = q["compact_chars"]
        record.korean_chars = q["korean_chars"]
        record.quality_ok = q["quality_ok"]
        return record
    except Exception as exc:
        record.status = "failed"
        record.message = f"exception: {type(exc).__name__}: {exc}"
        return record


def convert_pdf_folder(
    input_dir: Path, output_dir: Path, overwrite: bool = False
) -> BatchConvertResult:
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    staging_dir = output_dir / "staging_pdf"
    markdown_dir = output_dir / "markdown"
    manifest_path = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_dir.glob("*.pdf")) if input_dir.exists() else []
    result = BatchConvertResult(
        False, str(input_dir), str(output_dir), str(manifest_path), len(pdfs), 0, 0, 0, []
    )
    write_manifest(manifest_path, result)
    if not input_dir.exists() or not pdfs:
        result.failed = 1
        result.records.append(
            PdfConvertRecord(
                str(input_dir), None, None, "failed", "input_dir missing or no pdf files"
            )
        )
        write_manifest(manifest_path, result)
        _log(f"[batch] input_dir missing or no PDFs: {input_dir}")
        return result

    _log(f"[batch] {len(pdfs)} PDF(s) found in {input_dir}")
    _log(f"[batch] manifest: {manifest_path}")
    for index, source_pdf in enumerate(pdfs, start=1):
        _log(f"[batch] ({index}/{len(pdfs)}) converting: {source_pdf.name}")
        record = convert_one_pdf(source_pdf, staging_dir, markdown_dir, index, overwrite)
        result.records.append(record)
        result.converted = sum(
            1 for r in result.records if r.status == "converted" and r.quality_ok
        )
        result.failed = sum(1 for r in result.records if r.status == "failed")
        result.skipped = sum(1 for r in result.records if r.status == "skipped")
        result.ok = (
            result.failed == 0
            and result.converted + result.skipped == result.total_files
        )
        write_manifest(manifest_path, result)
        _log(
            f"[batch] ({index}/{len(pdfs)}) {record.status}: {record.message} "
            f"(compact_chars={record.compact_chars}, korean_chars={record.korean_chars})"
        )
    _log(
        f"[batch] done. converted={result.converted}, "
        f"failed={result.failed}, skipped={result.skipped}"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch OCR scanned PDFs to Markdown.")
    parser.add_argument("input_dir")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else REPO_ROOT
        / "tmp"
        / "ocr_batch_runs"
        / datetime.now().strftime("books_%Y%m%d_%H%M%S")
    )
    result = convert_pdf_folder(
        Path(args.input_dir), output_dir, overwrite=args.overwrite
    )
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok: {result.ok}")
        print(f"manifest: {result.manifest_path}")
        print(
            f"converted: {result.converted}, failed: {result.failed}, "
            f"skipped: {result.skipped}"
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
