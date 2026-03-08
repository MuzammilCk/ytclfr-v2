"""Text normalization and deduplication utilities for OCR output."""

from dataclasses import dataclass
import re
import unicodedata

from rapidfuzz import fuzz

from ytclfr_core.errors.exceptions import OCRProcessingError

_RANKING_PREFIX_RE = re.compile(r"^\s*(?:#\s*)?(?:\d{1,4}|[ivxlcdm]{1,8})\s*[\.\):\-]+\s*", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?<!\w)#[\w-]+")
_DECORATIVE_SYMBOL_RE = re.compile(
    r"[★☆✪✯✰✦✧❖◆◇■□▪▫●○◎◉⬤⬥▶◀►◄➤➥➜➔➜✨🔥💥💫⭐❤❣♡♥️]+"
)
_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]")
_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_NON_ALNUM_FOR_MATCH_RE = re.compile(r"[^0-9a-z]+")


@dataclass(slots=True)
class DuplicateMatch:
    """Represents one dropped line and its fuzzy-matched original."""

    duplicate: str
    matched_with: str
    similarity: float


@dataclass(slots=True)
class TextCleaningResult:
    """Result payload for normalized and deduplicated text."""

    cleaned_text: str
    cleaned_lines: list[str]
    duplicate_matches: list[DuplicateMatch]
    dropped_line_count: int


class TextCleaner:
    """Normalize OCR text and remove fuzzy duplicates."""

    def __init__(
        self,
        *,
        fuzzy_similarity_threshold: float = 90.0,
        min_line_length: int = 2,
        watermark_patterns: list[str] | None = None,
    ) -> None:
        if fuzzy_similarity_threshold < 0.0 or fuzzy_similarity_threshold > 100.0:
            raise OCRProcessingError("fuzzy_similarity_threshold must be between 0 and 100.")
        if min_line_length < 1:
            raise OCRProcessingError("min_line_length must be at least 1.")
        patterns = watermark_patterns or [
            r"\bsubscribe\b",
            r"\bfollow\s+for\s+more\b",
            r"\blike\s+and\s+share\b",
            r"\b(?:instagram|tiktok|facebook|twitter|x\.com)\b",
            r"\bwatermark\b",
            r"(?<!\w)@[a-z0-9_.]{2,}",
        ]
        try:
            self._watermark_patterns = [re.compile(pat, re.IGNORECASE) for pat in patterns]
        except re.error as exc:
            raise OCRProcessingError("Invalid watermark regex pattern.") from exc
        self._fuzzy_similarity_threshold = float(fuzzy_similarity_threshold)
        self._min_line_length = int(min_line_length)

    def clean_text(self, text: str) -> TextCleaningResult:
        """Normalize text block, remove noisy lines, and deduplicate with fuzzy matching."""
        try:
            raw_lines = text.splitlines()
            cleaned_lines = self.clean_lines(raw_lines)
            unique_lines, duplicate_matches = self._deduplicate_lines(cleaned_lines)
            return TextCleaningResult(
                cleaned_text="\n".join(unique_lines),
                cleaned_lines=unique_lines,
                duplicate_matches=duplicate_matches,
                dropped_line_count=max(0, len(raw_lines) - len(unique_lines)),
            )
        except OCRProcessingError:
            raise
        except Exception as exc:
            raise OCRProcessingError("Text cleaning failed.") from exc

    def clean_lines(self, lines: list[str]) -> list[str]:
        """Clean each line and drop empty/noisy lines."""
        cleaned: list[str] = []
        for line in lines:
            normalized = self._clean_line(line)
            if normalized is None:
                continue
            cleaned.append(normalized)
        return cleaned

    def _clean_line(self, line: str) -> str | None:
        """Apply normalization and noise-removal rules to one line."""
        if not isinstance(line, str):
            return None
        text = unicodedata.normalize("NFKC", line).strip()
        if not text:
            return None

        text = _RANKING_PREFIX_RE.sub("", text)
        text = _HASHTAG_RE.sub(" ", text)
        text = _DECORATIVE_SYMBOL_RE.sub(" ", text)
        text = _EMOJI_RE.sub(" ", text)
        for pattern in self._watermark_patterns:
            text = pattern.sub(" ", text)

        text = _SPACE_RE.sub(" ", text).strip(" -_|:;,.")
        if not text:
            return None
        if _PUNCT_ONLY_RE.match(text):
            return None
        if len(text) < self._min_line_length:
            return None
        return text

    def _deduplicate_lines(self, lines: list[str]) -> tuple[list[str], list[DuplicateMatch]]:
        """Drop exact and fuzzy duplicates while preserving order."""
        unique_lines: list[str] = []
        unique_match_keys: list[str] = []
        duplicate_matches: list[DuplicateMatch] = []

        for candidate in lines:
            candidate_key = self._normalize_for_match(candidate)
            if not candidate_key:
                continue

            matched_index: int | None = None
            matched_score = 0.0
            for idx, existing_key in enumerate(unique_match_keys):
                if candidate_key == existing_key:
                    matched_index = idx
                    matched_score = 100.0
                    break
                score = float(fuzz.ratio(candidate_key, existing_key))
                if score >= self._fuzzy_similarity_threshold:
                    matched_index = idx
                    matched_score = score
                    break

            if matched_index is None:
                unique_lines.append(candidate)
                unique_match_keys.append(candidate_key)
                continue

            duplicate_matches.append(
                DuplicateMatch(
                    duplicate=candidate,
                    matched_with=unique_lines[matched_index],
                    similarity=matched_score,
                )
            )

        return unique_lines, duplicate_matches

    def _normalize_for_match(self, value: str) -> str:
        """Build a normalized key used by exact/fuzzy duplicate checks."""
        lowered = unicodedata.normalize("NFKC", value).lower()
        alnum_only = _NON_ALNUM_FOR_MATCH_RE.sub(" ", lowered)
        return _SPACE_RE.sub(" ", alnum_only).strip()

