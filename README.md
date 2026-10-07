# 문서 Markdown 변환기

Windows 환경에서 오피스 문서, 스프레드시트, 프레젠테이션, HWP/HWPX,
PDF 파일을 Markdown으로 변환하는 도구 모음입니다.

간단한 GUI 실행 진입점과 스크립트에서 호출할 수 있는 CLI를 함께 제공합니다.
PDF는 먼저 내장 텍스트 레이어를 사용하고, 스캔본처럼 텍스트가 없는 페이지는
OCR로 처리합니다.

## 지원 형식

- Word 문서: `.docx`, `.doc`
- PowerPoint: `.pptx`
- Excel: `.xlsx`, `.xls`
- 한글 문서: `.hwp`, `.hwpx`
- PDF: 디지털 텍스트 PDF, OCR이 필요한 스캔 PDF

## 빠른 시작

Python 의존성을 설치합니다.

```powershell
python -m pip install -r requirements.txt
```

GUI를 실행합니다.

```powershell
python -m src.main
```

Windows에서는 `run.bat`를 더블 클릭해도 됩니다. 특정 Python 인터프리터를
사용해야 한다면 먼저 `DOC_TO_MD_PYTHON` 환경변수를 지정하세요.

```powershell
$env:DOC_TO_MD_PYTHON = "C:\Path\To\python.exe"
.\run.bat
```

## CLI 사용법

PowerShell에서 하나 이상의 파일을 변환할 수 있습니다.

```powershell
python .\scripts\convert_to_md_cli.py --json .\sample\123.pdf
```

변환 결과는 입력 파일 옆에 `*_converted.md` 이름으로 저장됩니다.

브리지 연동에서는 다음 스크립트를 사용할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_doc_to_md_bridge.ps1 --json .\sample\123.pdf
```

conda 환경의 DLL 경로가 런타임에 필요하다면, 환경을 먼저 활성화하거나
`DOC_TO_MD_CONDA_PREFIX`를 지정하세요.

## OCR 참고 사항

PDF 처리는 페이지 검사와 렌더링에 PyMuPDF를 사용하고, 이미지 기반 페이지는
PaddleOCR로 인식합니다. 큰 스캔 PDF는 특히 CPU 환경에서 시간이 오래 걸릴 수
있습니다.

## 포함된 도구

`tools/hwp2md.exe` 바이너리는 HWP/HWPX 변환용 fallback 도구로 포함되어
있습니다. 해당 도구의 upstream 라이선스는 `tools/LICENSE`에 들어 있습니다.

## 라이선스

이 저장소는 MIT 라이선스로 배포됩니다. 자세한 내용은 `LICENSE`를 확인하세요.
포함된 third-party 도구는 각 도구의 라이선스를 함께 확인하세요.

## 개발

```bash
python -m pip install -r requirements-dev.txt   # Windows 전용 패키지(pywin32)는 자동 제외
python -m pytest -q
```

- 변환 결과는 `<원본이름>_converted.md`로 저장됩니다. 같은 폴더에 같은 이름의 다른 문서(예: `a.docx`와 `a.pdf`)가 있으면 `a_pdf_converted.md`처럼 확장자가 붙어 서로 덮어쓰지 않습니다.
- `DOC2MD_UTF8_BOM=0` 이면 BOM 없는 UTF-8로 저장합니다(RAG/파서 연동 시 권장).
- OCR 튜닝(환경 변수): `OCR_DET_LIMIT_SIDE_LEN`(기본 960, 작은 글씨는 1920 등으로 상향), `OCR_MIN_SCORE`(기본 0.5).
- 로그는 `logging`으로 출력되며 GUI 로그 창에도 표시됩니다.

## 번들 바이너리 (`tools/hwp2md.exe`)

- 출처: https://github.com/roboco-io/hwp2md (MIT, `tools/LICENSE`)
- SHA256: `6e552193ad0235a1cd4155a5f19ce18dbf78499a4be5fc5f58cfc3087cb14c6d`
- 교체 시 위 해시와 출처 릴리스 태그를 함께 갱신하세요. 변환기는 kordoc → hwp2md → 내장 파서 순으로 시도하므로 hwp2md는 보조 수단입니다.
