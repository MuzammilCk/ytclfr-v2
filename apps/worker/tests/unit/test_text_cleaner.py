"""Unit tests for OCR text normalization and deduplication."""

from ytclfr_infra.ocr.text_cleaner import TextCleaner


def test_clean_text_removes_ranking_watermarks_hashtags_and_symbols() -> None:
    """Cleaner should remove ranking prefixes, hashtags, symbols, and watermark lines."""
    cleaner = TextCleaner(fuzzy_similarity_threshold=95.0)
    input_text = "\n".join(
        [
            "1) Hello #world ✨✨",
            "2. SUBSCRIBE",
            "@my_channel",
            "3) Keep this line!!!",
            "★★★★★",
        ]
    )

    result = cleaner.clean_text(input_text)

    assert result.cleaned_lines == ["Hello", "Keep this line!!!"]
    assert result.cleaned_text == "Hello\nKeep this line!!!"
    assert result.dropped_line_count == 3


def test_clean_text_deduplicates_with_fuzzy_matching() -> None:
    """Cleaner should drop near-duplicate lines using RapidFuzz similarity."""
    cleaner = TextCleaner(fuzzy_similarity_threshold=90.0)
    input_text = "\n".join(
        [
            "1) GLOBETROTTER",
            "2) Globe Trotter",
            "3) Globe-Trotter",
            "4) Different line",
        ]
    )

    result = cleaner.clean_text(input_text)

    assert result.cleaned_lines == ["GLOBETROTTER", "Different line"]
    assert len(result.duplicate_matches) == 2
    assert all(match.similarity >= 90.0 for match in result.duplicate_matches)

