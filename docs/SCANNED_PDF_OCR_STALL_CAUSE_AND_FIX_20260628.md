# 스캔 PDF OCR 전처리 중단 원인 분석 및 수정 코드 지시서

작성일: 2026-06-28 17:31:40 KST
대상 프로젝트: `C:\scratch\doc_to_md_converter`

## 1. 현상 및 원인 분석
고유 확인 마커: SCANNED_PDF_OCR_STALL_FIX_20260628_KST

대상 작업은 C:\Users\USER\Downloads\도서 폴더의 스캔 PDF를 OCR로 Markdown 변환한 뒤 OpenCrab 에이전트툴 인제스트 입력으로 사용하는 것이다.

확인된 현상은 다음과 같다.

- PDF가 모두 스캔 PDF라 텍스트층이 없고 이미지 기반으로 인식된다.
- C:\scratch\doc_to_md_converter에는 PDF OCR 변환 코드가 존재한다.
- scripts/convert_to_md_cli.py는 src.backend.process_file()을 호출한다.
- src.backend.py는 PDF 입력 시 _convert_pdf_with_router()를 호출한다.
- src/converters/pdf_converter.py는 PyMuPDF로 페이지를 300dpi 이미지로 렌더링한 뒤 get_ocr_text(img, paragraph=True)를 호출한다.
- src/converters/ocr_engine.py는 PaddleOCR 기반이며 GPU 실패 시 CPU fallback 구조가 있다.
- local-code MCP의 현재 allowed_command_specs에는 convert_to_md_cli.py 또는 일괄 OCR 변환을 실행하는 전용 명령이 없다.
- 이전 진행 중 범용 Python snippet 경로가 local-code MCP 자체 Python/venv 시작 지연 또는 timeout에 걸려 작업용 staging 단계에서 멈춘 것처럼 보였다.

직접 원인: OCR 엔진 자체가 멈춘 것이 아니라, ChatGPT -> local-code MCP -> doc_to_md_converter CLI 실행으로 이어지는 실행 경로가 아직 등록되어 있지 않아 실제 변환 실행 전 단계에서 막혔다.

근본 원인: 장시간 OCR 작업을 안전하게 시작하고 상태를 조회하는 background job/manifest 구조가 없고, MCP allowlist에 doc_to_md_converter 실행 명령이 없다. 따라서 사용자가 보기에는 작업이 멈춘 것처럼 보인다.

확인 필요: run.bat 내용은 안전 검사 차단으로 직접 확인하지 못했다. 다음 작업에서 로컬에서 직접 열어 CLI 실행 경로를 재확인해야 한다.

## 2. 수정 대상 파일
| 구분 | 파일 | 수정 내용 | 우선순위 |
|---|---|---|---|
| 필수 | C:\scratch\doc_to_md_converter\scripts\batch_scanned_pdf_to_md.py | 스캔 PDF 폴더를 일괄 OCR -> Markdown 변환하는 CLI 추가 | 필수 |
| 필수 | local-code MCP 설정의 allowed_command_specs | doc_to_md_batch_convert 실행 명령 추가 | 필수 |
| 권장 | C:\scratch\doc_to_md_converter\src\backend.py | 변환 성공/실패 외 품질 메타데이터 반환 옵션 추가 | 권장 |
| 권장 | C:\scratch\doc_to_md_converter\src\converters\pdf_converter.py | 페이지별 진행률 callback 또는 manifest 기록 지원 | 권장 |
| 권장 | C:\scratch\doc_to_md_converter\src\utils\ocr_quality.py | OCR 결과 품질 평가 함수 추가 | 권장 |
| 테스트 | C:\scratch\doc_to_md_converter\tests\test_batch_scanned_pdf_to_md.py | batch CLI, manifest, 품질 게이트 테스트 | 테스트 |

## 3. 추가/수정할 도구명
| 도구명 | 유형 | 목적 | 위험도 | 등록 위치 |
|---|---|---|---|---|
| doc_to_md_batch_convert | 파일 생성형 실행 명령 | 입력 폴더의 PDF를 OCR 변환하고 MD/manifest 생성 | 중간 | local-code MCP allowed_command_specs |
| mcp_start_doc_to_md_batch_job | background 실행 도구 후보 | 장시간 OCR 변환 job 시작 | 중간 | local-code MCP 신규 도구 후보 |
| mcp_doc_to_md_batch_status | read-only | manifest 기준 진행률 조회 | 낮음 | local-code MCP 신규 도구 후보 |
| mcp_doc_to_md_quality_check | validation-only | 변환 MD 품질 게이트 | 낮음 | local-code MCP 신규 도구 후보 |

## 4. 함수 시그니처
```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BatchStatus = Literal['queued', 'running', 'converted', 'failed', 'skipped']

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

def stage_pdf_to_ascii(source: Path, staging_dir: Path, index: int) -> Path: ...
def assess_markdown_quality(md_path: Path, min_compact_chars: int = 500) -> dict[str, Any]: ...
def convert_one_pdf(source_pdf: Path, staging_dir: Path, output_dir: Path, index: int, overwrite: bool) -> PdfConvertRecord: ...
def convert_pdf_folder(input_dir: Path, output_dir: Path, overwrite: bool = False) -> BatchConvertResult: ...
```

## 5. 핵심 알고리즘
1. 입력 폴더 C:\Users\USER\Downloads\도서 존재 여부를 확인한다.
2. PDF 파일만 수집한다.
3. 출력 폴더 C:\scratch\doc_to_md_converter\tmp\ocr_batch_runs\books_YYYYMMDD_HHMMSS를 만든다.
4. 원본 PDF는 수정하지 않고 staging_pdf/book_001.pdf 형식의 ASCII 파일명으로 복사한다.
5. 각 staged PDF에 대해 기존 src.backend.process_file()을 호출한다.
6. 생성된 book_001_converted.md를 markdown 폴더로 이동한다.
7. Markdown 파일의 공백 제거 글자 수, 한글 글자 수, 이미지 링크만 있는지 여부를 검사한다.
8. 파일별 상태를 manifest.json에 즉시 기록한다.
9. failed 또는 quality_ok=false 파일이 있으면 OpenCrab 인제스트를 중단하고 보류 목록으로 분리한다.
10. 모든 파일이 quality_ok=true일 때만 OpenCrab 팩 인제스트 단계로 넘긴다.

## 6. 검증 방식
자동 검증:

- manifest.json 존재 여부 확인
- records 길이와 total_files 일치 확인
- 성공 파일의 output_md 존재 확인
- bytes_out > 0 확인
- compact_chars >= 500 확인
- 이미지 링크만 있는 Markdown이 아닌지 확인

수동 검증:

- 첫 번째 변환 MD와 가장 큰 변환 MD를 직접 열어 본문 텍스트가 추출됐는지 확인
- 한글 띄어쓰기, 목차, 표 구조 일부를 확인
- OpenCrab 인제스트 전 샘플 질의로 원문 근거 검색 가능 여부 확인

실패 시 중단 기준:

- 입력 폴더 없음: 즉시 실패
- PDF 0개: 즉시 실패
- PaddleOCR import 실패: 전체 실패
- 일부 PDF 실패: 실패 파일만 보류
- Markdown 품질 미달: 해당 파일은 인제스트 제외

## 7. 테스트 방향
단위 테스트:

- stage_pdf_to_ascii()가 한글 파일명을 ASCII 파일명으로 복사하는지 확인
- assess_markdown_quality()가 빈 파일, 이미지 링크만 있는 파일, 정상 한글 텍스트 파일을 구분하는지 확인
- manifest JSON이 UTF-8로 저장되는지 확인

통합 테스트:

- sample/123.pdf를 대상으로 batch 변환 실행
- tmp/ocr_batch_runs/.../manifest.json 생성 확인
- 성공한 Markdown 파일의 compact_chars가 기준 이상인지 확인

회귀 테스트:

- 기존 scripts/convert_to_md_cli.py sample/123.pdf --json 동작이 유지되는지 확인
- 디지털 PDF는 text layer 경로를 유지하는지 확인
- 스캔 PDF는 PaddleOCR 경로로 진입하는지 확인

## 8. 완성형 실제 코드 초안
아래 코드를 C:\scratch\doc_to_md_converter\scripts\batch_scanned_pdf_to_md.py로 저장한다.

```python
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

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from src.backend import process_file

BatchStatus = Literal['queued', 'running', 'converted', 'failed', 'skipped']

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

def compact_text(text: str) -> str:
    return ''.join(text.split())

def count_korean(text: str) -> int:
    return sum(1 for ch in text if '가' <= ch <= '힣')

def write_manifest(path: Path, result: BatchConvertResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding='utf-8')

def assess_markdown_quality(md_path: Path, min_compact_chars: int = 500) -> dict[str, Any]:
    if not md_path.exists():
        return {'quality_ok': False, 'bytes_out': 0, 'compact_chars': 0, 'korean_chars': 0, 'reason': 'output markdown not found'}
    text = md_path.read_text(encoding='utf-8', errors='replace')
    compact = compact_text(text)
    image_only = text.count('![](') > 0 and len(compact) < 200
    quality_ok = len(compact) >= min_compact_chars and not image_only
    return {
        'quality_ok': quality_ok,
        'bytes_out': md_path.stat().st_size,
        'compact_chars': len(compact),
        'korean_chars': count_korean(text),
        'reason': 'ok' if quality_ok else 'low text yield or image-only markdown',
    }

def stage_pdf_to_ascii(source: Path, staging_dir: Path, index: int) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged = staging_dir / f'book_{index:03d}.pdf'
    shutil.copy2(source, staged)
    return staged

def convert_one_pdf(source_pdf: Path, staging_dir: Path, markdown_dir: Path, index: int, overwrite: bool) -> PdfConvertRecord:
    record = PdfConvertRecord(str(source_pdf), None, None, 'running', 'started', bytes_in=source_pdf.stat().st_size if source_pdf.exists() else None)
    try:
        staged = stage_pdf_to_ascii(source_pdf, staging_dir, index)
        record.staged_pdf = str(staged)
        generated_md = staged.with_suffix('').with_name(staged.stem + '_converted.md')
        final_md = markdown_dir / generated_md.name
        if final_md.exists() and not overwrite:
            q = assess_markdown_quality(final_md)
            record.output_md = str(final_md)
            record.status = 'skipped'
            record.message = 'already converted; use --overwrite to regenerate'
            record.bytes_out = q['bytes_out']
            record.compact_chars = q['compact_chars']
            record.korean_chars = q['korean_chars']
            record.quality_ok = q['quality_ok']
            return record
        success, message = process_file(str(staged))
        if not success:
            record.status = 'failed'
            record.message = message
            return record
        if not generated_md.exists():
            record.status = 'failed'
            record.message = f'converter reported success but output not found: {generated_md}'
            return record
        markdown_dir.mkdir(parents=True, exist_ok=True)
        if final_md.exists():
            final_md.unlink()
        shutil.move(str(generated_md), str(final_md))
        q = assess_markdown_quality(final_md)
        record.output_md = str(final_md)
        record.status = 'converted' if q['quality_ok'] else 'failed'
        record.message = 'converted' if q['quality_ok'] else q['reason']
        record.bytes_out = q['bytes_out']
        record.compact_chars = q['compact_chars']
        record.korean_chars = q['korean_chars']
        record.quality_ok = q['quality_ok']
        return record
    except Exception as exc:
        record.status = 'failed'
        record.message = f'exception: {type(exc).__name__}: {exc}'
        return record

def convert_pdf_folder(input_dir: Path, output_dir: Path, overwrite: bool = False) -> BatchConvertResult:
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    staging_dir = output_dir / 'staging_pdf'
    markdown_dir = output_dir / 'markdown'
    manifest_path = output_dir / 'manifest.json'
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_dir.glob('*.pdf')) if input_dir.exists() else []
    result = BatchConvertResult(False, str(input_dir), str(output_dir), str(manifest_path), len(pdfs), 0, 0, 0, [])
    write_manifest(manifest_path, result)
    if not input_dir.exists() or not pdfs:
        result.failed = 1
        result.records.append(PdfConvertRecord(str(input_dir), None, None, 'failed', 'input_dir missing or no pdf files'))
        write_manifest(manifest_path, result)
        return result
    for index, source_pdf in enumerate(pdfs, start=1):
        record = convert_one_pdf(source_pdf, staging_dir, markdown_dir, index, overwrite)
        result.records.append(record)
        result.converted = sum(1 for r in result.records if r.status == 'converted' and r.quality_ok)
        result.failed = sum(1 for r in result.records if r.status == 'failed')
        result.skipped = sum(1 for r in result.records if r.status == 'skipped')
        result.ok = result.failed == 0 and result.converted + result.skipped == result.total_files
        write_manifest(manifest_path, result)
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description='Batch OCR scanned PDFs to Markdown.')
    parser.add_argument('input_dir')
    parser.add_argument('--output-dir', default=None)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / 'tmp' / 'ocr_batch_runs' / datetime.now().strftime('books_%Y%m%d_%H%M%S')
    result = convert_pdf_folder(Path(args.input_dir), output_dir, overwrite=args.overwrite)
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f'ok: {result.ok}')
        print(f'manifest: {result.manifest_path}')
        print(f'converted: {result.converted}, failed: {result.failed}, skipped: {result.skipped}')
    return 0 if result.ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
```

local-code MCP command spec 초안:

```json
{
  "name": "doc_to_md_batch_convert",
  "argv": [
    "C:/scratch/doc_to_md_converter/.venv/Scripts/python.exe",
    "C:/scratch/doc_to_md_converter/scripts/batch_scanned_pdf_to_md.py"
  ],
  "timeout_seconds": 86400
}
```

테스트 초안:

```python
from pathlib import Path
from scripts.batch_scanned_pdf_to_md import assess_markdown_quality, stage_pdf_to_ascii

def test_assess_markdown_quality_rejects_empty(tmp_path: Path):
    md = tmp_path / 'empty.md'
    md.write_text('', encoding='utf-8')
    q = assess_markdown_quality(md)
    assert q['quality_ok'] is False

def test_assess_markdown_quality_accepts_korean_text(tmp_path: Path):
    md = tmp_path / 'ok.md'
    md.write_text('한글 본문입니다. ' * 100, encoding='utf-8')
    q = assess_markdown_quality(md, min_compact_chars=100)
    assert q['quality_ok'] is True

def test_stage_pdf_to_ascii(tmp_path: Path):
    src = tmp_path / '한글 파일명.pdf'
    src.write_bytes(b'%PDF-1.4\n%%EOF')
    staged = stage_pdf_to_ascii(src, tmp_path / 'staging', 1)
    assert staged.name == 'book_001.pdf'
    assert staged.exists()
```

## 9. 사용자 가드 및 상태 알림
사용자가 멈춤으로 오해하지 않도록 다음 상태 메시지와 상태값을 추가한다.

```python
from dataclasses import dataclass
from typing import Any, Literal

@dataclass
class UserVisibleOperationState:
    operation_id: str
    phase: str
    status: Literal['started', 'in_progress', 'converted', 'verified', 'already_converted', 'failed']
    user_message: str
    evidence: dict[str, Any]
    next_action: str | None = None
```

사용자 표시 메시지 예시:

- 스캔 PDF OCR 변환을 시작했습니다. manifest에 파일별 진행 상태를 기록합니다.
- PaddleOCR 초기화 중입니다. GPU 실패 시 CPU로 자동 전환됩니다.
- book_003.pdf OCR 변환 중입니다. 전체 7개 중 3번째입니다.
- Markdown 텍스트량이 기준 미달이라 OpenCrab 인제스트에서 보류했습니다.
- OCR 변환 완료. manifest와 Markdown 산출물을 확인했습니다.
- 변환 CLI가 local-code MCP 허용 명령에 등록되어 있지 않아 실행하지 못했습니다.

동일 현상 재발 시 처리:

1. mcp_command_specs_status에서 doc_to_md_batch_convert가 등록되어 있는지 확인한다.
2. 등록되어 있지 않으면 OCR을 시작하지 않고 설정 누락으로 보고한다.
3. background job을 시작한 경우 job_id와 manifest_path를 즉시 사용자에게 표시한다.
4. manifest.json이 60초 이상 갱신되지 않으면 PaddleOCR 초기화, GPU fallback, 현재 파일/page 로그를 확인한다.
5. 실패 PDF는 재처리 목록으로 분리하고 성공 PDF만 OpenCrab 인제스트 후보로 넘긴다.

## 10. 완료 기준
- [x] 원인 분석 충분함
- [x] 수정 대상 파일 들어가 있음
- [x] 추가할 도구명 들어가 있음
- [x] 함수 시그니처 들어가 있음
- [x] 핵심 알고리즘 들어가 있음
- [x] 검증 방식 들어가 있음
- [x] 테스트 방향 들어가 있음
- [x] 완성형 실제 코드 초안 들어가 있음
- [x] 동일 현상 발생 시 사용자가 알 수 있는 가드 들어가 있음

다음 실행 순서:

1. scripts/batch_scanned_pdf_to_md.py를 실제 파일로 추가한다.
2. local-code MCP 설정에 doc_to_md_batch_convert command spec을 등록한다.
3. local-code MCP를 재시작한다.
4. C:\Users\USER\Downloads\도서 폴더를 입력으로 batch OCR을 실행한다.
5. manifest.json에서 모든 파일의 quality_ok=true를 확인한다.
6. 그 다음 OpenCrab 팩 인제스트를 진행한다.
