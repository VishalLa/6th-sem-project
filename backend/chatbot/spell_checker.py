import logging
from typing import List, Dict, Optional, Tuple

from .domain_vocabulary import (
    COLUMN_ALIASES,
    SYNONYM_DICTIONARY,
    VALID_FILTER_VALUES,
    NUMERIC_COLUMNS,
    ALL_COLUMNS,
    HIGH_RISK_COUNTRY_PAIRS,
    DOMAIN_TERMS
)

logger = logging.getLogger(__name__)

# Master vocabulary: all known correct terms
KNOWN_VOCABULARY: List[str] = sorted(set(
    list(DOMAIN_TERMS)
    + list(COLUMN_ALIASES.keys())
    + [v for vals in SYNONYM_DICTIONARY.values() for v in vals]
    + [v for vals in VALID_FILTER_VALUES.values() for v in vals]
    + ALL_COLUMNS
))


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Compute Levenshtein edit distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Integer edit distance
    """

    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]

        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1

            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))

        prev_row = curr_row

    return prev_row[-1]


class SpellChecker:
    """
    Detects misspelled domain terms and suggests nearest correct alternatives.
    Operates on individual tokens and multi-word phrases.
    """

    _PROTECTED_WORDS: set = {
        "show", "find", "list", "get", "give", "tell", "what", "when", "where",
        "which", "with", "from", "into", "onto", "over", "under", "above",
        "below", "all", "any", "are", "and", "for", "the", "how", "many",
        "more", "less", "most", "last", "first", "next", "only", "also",
        "been", "have", "has", "was", "were", "did", "does", "not", "no",
        "yes", "top", "per", "by", "in", "on", "at", "to", "of",
        "high", "low", "new", "old", "big", "group", "sort", "compare",
        "count", "sum", "avg", "max", "min", "between", "total", "mean",
    }

    def __init__(self, max_edit_distance: int = 2, min_token_length: int = 5):
        """
        Args:
            max_edit_distance: Maximum edit distance to consider a correction
            min_token_length: Minimum token length to attempt correction (skip short tokens).
                              Raised to 5 (from 4) to avoid false corrections on 4-letter
                              common words like "show", "find", "list", etc.
        """
        self.vocabulary = KNOWN_VOCABULARY
        self.vocab_set = set(v.lower() for v in self.vocabulary)

        self.max_edit_distance = max_edit_distance
        self.min_token_length = min_token_length

        logger.info(f"SpellChecker initialized with {len(self.vocabulary)} vocabulary terms.")


    def is_known_word(self, word: str) -> bool:
        """
        Check if a word exists in the known vocabulary.

        Args:
            word: Token to check

        Returns:
            True if word is recognized
        """
        return word.lower() in self.vocab_set
    

    def find_nearest(self, word: str) -> Optional[Tuple[str, int]]:

        """
        Find the nearest known word by edit distance.

        Args:
            word: Potentially misspelled word

        Returns:
            Tuple of (best_match, distance) or None if no match within threshold
        """

        word_lower = word.lower()
        best_match = None
        best_dist = self.max_edit_distance + 1

        for candidate in self.vocabulary:
            dist = levenshtein_distance(word_lower, candidate.lower())

            if dist < best_dist:
                best_dist = dist
                best_match = candidate

        if best_dist <= self.max_edit_distance:
            return (best_match, best_dist)
        
        return None
    

    def _looks_like_id(self, token: str) -> bool:
        """
        Check if a token looks like a system ID (e.g., ACC00023, DEV-7700).
        """
        return bool(
            token.startswith(("acc", "dev", "txn"))
            or (len(token) > 5 and any(c.isdigit() for c in token) and any(c.isalpha() for c in token))
        )


    def check_tokens(self, tokens: List[str]) -> Dict:
        """
        Check a list of tokens for spelling errors and suggest corrections.

        Args:
            tokens: List of string tokens

        Returns:
            Dictionary with:
              - corrections: {original_token: suggested_correction}
              - corrected_tokens: list of tokens with corrections applied
              - has_corrections: bool
        """
        corrections = {}
        corrected_tokens = []

        for token in tokens:
            # Skip short tokens, numbers, IDs, and protected common words
            if (
                len(token) < self.min_token_length
                or token.lower() in self._PROTECTED_WORDS
                or token.startswith("acc")
                or token.startswith("txn")
                or token.startswith("dev")
                or token.isdigit()
                or self._looks_like_id(token)
            ):
                corrected_tokens.append(token)
                continue

            if self.is_known_word(token):
                corrected_tokens.append(token)

            else:
                match = self.find_nearest(token)

                if match:
                    suggested, dist = match
                    corrections[token] = suggested
                    corrected_tokens.append(suggested)
                    logger.debug(f"SpellCheck: '{token}' → '{suggested}' (dist={dist})")

                else:
                    corrected_tokens.append(token)

        return {
            "corrections": corrections,
            "corrected_tokens": corrected_tokens,
            "has_corrections": len(corrections) > 0,
        }
    

    def check_text(self, text: str) -> Dict:
        """
        Check raw text for spelling issues by tokenizing and checking tokens.

        Args:
            text: Raw or cleaned input text

        Returns:
            Dictionary with corrections and corrected text
        """
        tokens = text.lower().split()
        result = self.check_tokens(tokens)

        result["original_text"] = text
        result["corrected_text"] = " ".join(result["corrected_tokens"])

        if result["has_corrections"]:
            logger.info(
                f"Spelling corrections applied: {result['corrections']}"
            )
        return result
    

    def get_vocabulary_size(self) -> int:
        """Return total number of known vocabulary terms."""
        return len(self.vocabulary)