# Doc/PDF to Markdown Converter (문서 변환기)

이 프로그램은 Doc, Docx, PDF 파일을 Markdown(.md) 형식으로 변환해주는 도구입니다.

## 🚀 실행 방법 (How to Run)
폴더 내에 있는 **`run.bat`** 파일을 더블 클릭하여 실행하세요.

## 📋 기능 (Features)
- **Drag & Drop**: 파일을 프로그램 창에 드래그하여 놓으면 자동으로 변환됩니다.
- **지원 형식**:
  - `.docx`: 텍스트, 표, 헤더 등을 마크다운으로 깔끔하게 변환.
  - `.doc`: MS Word를 통해 자동으로 읽어서 변환 (Word 설치 필요).
  - `.pdf`: 텍스트 추출 및 OCR(이미지 문자 인식) 지원.

## ⚠️ 필수 요구 사항 (Prerequisites)
1. **Python 3.x**: 실행을 위해 파이썬이 설치되어 있어야 합니다.
2. **Microsoft Word**: `.doc` (구버전 워드 파일) 변환 시 필요합니다.
3. **Tesseract OCR (선택 사항)**:
   - 스캔된 PDF(이미지로 된 문서)를 변환하려면 Tesseract OCR 설치가 필요합니다.
   - [다운로드 링크](https://github.com/UB-Mannheim/tesseract/wiki)에서 Windows 버전을 설치하세요.

## 🛠 문제 해결 (Troubleshooting)
- **실행이 안 될 때**: `python-docx`, `pymupdf` 등의 라이브러리가 설치되었는지 확인하세요.
  ```bash
  pip install -r requirements.txt
  ```
- **OCR 오류**: Tesseract가 설치되지 않았거나 경로가 다르면 스캔된 PDF 변환이 실패할 수 있습니다.
