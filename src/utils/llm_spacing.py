"""
LLM-based Korean spacing corrector using local Ollama.

Sends OCR text to a local LLM with strict instructions to ONLY fix spacing,
preserving all original content exactly as-is.
"""

import requests
import re
import time

_OLLAMA_URL = "http://localhost:11434/api/generate"
_MODEL = "qwen3:8b-fast"
_TIMEOUT = 120  # seconds per request

_SYSTEM_PROMPT = """당신은 한국어 띄어쓰기 교정 전문가입니다.

## 규칙 (반드시 지켜야 함)
1. 입력된 텍스트의 **띄어쓰기만** 교정하세요.
2. 글자를 추가, 삭제, 변경하지 마세요. 오타도 그대로 두세요.
3. 문장 부호(마침표, 쉼표 등)도 그대로 유지하세요.
4. 줄바꿈(\\n)은 그대로 유지하세요.
5. 영어, 숫자, 특수문자는 그대로 유지하세요.
6. 설명이나 부연 없이 교정된 텍스트만 출력하세요.

## 예시
입력: 트렌드의시작과끝은사람이다.사람들의새로운취향이
출력: 트렌드의 시작과 끝은 사람이다. 사람들의 새로운 취향이"""


def _check_ollama_available():
    """Check if Ollama server is running."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _call_ollama(text, model=_MODEL):
    """Call Ollama API with the given text."""
    prompt = f"/no_think\n다음 텍스트의 띄어쓰기만 교정하세요. 글자는 절대 변경하지 마세요.\n\n{text}"

    payload = {
        "model": model,
        "prompt": prompt,
        "system": _SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": max(512, len(text) * 2),
        },
    }

    try:
        resp = requests.post(_OLLAMA_URL, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("response", "").strip()

        # Remove thinking tags if model outputs them
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()

        return result
    except Exception as e:
        print(f"  [LLM] Ollama error: {e}")
        return None


def _validate_llm_output(original, corrected):
    """
    Validate that LLM only changed spacing and didn't alter content.
    Returns corrected text if valid, original if not.
    """
    if not corrected:
        return original

    # Strip all whitespace from both and compare characters
    orig_chars = re.sub(r'\s+', '', original)
    corr_chars = re.sub(r'\s+', '', corrected)

    # Allow small deviation (LLM might fix a tiny OCR artifact)
    # but if more than 5% of characters changed, reject
    if len(corr_chars) == 0:
        return original

    # Check character-level similarity
    if orig_chars == corr_chars:
        return corrected  # Perfect: only spacing changed

    # If lengths differ significantly, reject
    len_ratio = len(corr_chars) / len(orig_chars) if orig_chars else 0
    if len_ratio < 0.9 or len_ratio > 1.1:
        print(f"  [LLM] Rejected: length ratio {len_ratio:.2f}")
        return original

    # Count character differences
    min_len = min(len(orig_chars), len(corr_chars))
    diffs = sum(1 for a, b in zip(orig_chars[:min_len], corr_chars[:min_len]) if a != b)
    diffs += abs(len(orig_chars) - len(corr_chars))
    diff_ratio = diffs / len(orig_chars)

    if diff_ratio > 0.05:
        print(f"  [LLM] Rejected: {diffs} char diffs ({diff_ratio:.1%})")
        return original

    return corrected


def fix_spacing_with_llm(text, model=_MODEL):
    """
    Fix Korean spacing using local Ollama LLM.

    Processes text paragraph by paragraph to keep requests manageable.
    Falls back to original text if LLM is unavailable or output is invalid.

    Returns: (corrected_text, was_llm_used)
    """
    if not text or not text.strip():
        return text, False

    if not _check_ollama_available():
        print("  [LLM] Ollama not available, skipping LLM spacing correction")
        return text, False

    # Split into paragraphs (preserve double newlines)
    paragraphs = text.split('\n\n')
    corrected_paragraphs = []
    llm_used = False

    for idx, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            corrected_paragraphs.append('')
            continue

        # Skip very short paragraphs (page numbers, headers)
        if len(para) < 10:
            corrected_paragraphs.append(para)
            continue

        # For long paragraphs, split into chunks of ~500 chars
        if len(para) > 800:
            # Split at sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', para)
            chunks = []
            current_chunk = ''
            for sent in sentences:
                if len(current_chunk) + len(sent) > 600 and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sent
                else:
                    current_chunk += (' ' if current_chunk else '') + sent
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            chunks = [para]

        corrected_chunks = []
        for chunk in chunks:
            result = _call_ollama(chunk, model)
            validated = _validate_llm_output(chunk, result)
            if validated != chunk:
                llm_used = True
            corrected_chunks.append(validated)

        corrected_paragraphs.append(' '.join(corrected_chunks))

    return '\n\n'.join(corrected_paragraphs), llm_used
