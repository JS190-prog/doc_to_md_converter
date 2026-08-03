from src.utils.ocr_corrections import apply_ocr_corrections


def test_book_profile_repairs_contextual_ai_ocr_confusions() -> None:
    source = "Gemini Al 기반 Al agent와 Vercel Al SDK, Al 답변"

    corrected = apply_ocr_corrections(source, profile="book")

    assert corrected == "Gemini AI 기반 AI agent와 Vercel AI SDK, AI 답변"


def test_book_profile_does_not_replace_ambiguous_al_globally() -> None:
    source = 'I "Accept Al" always. Expand Al.'

    assert apply_ocr_corrections(source, profile="book") == source
