import re
import string
import logging
from typing import List, Tuple


logger = logging.getLogger(__name__)

# Minimal stop words — keep domain-relevant words like "not", "no", "from", "to"
STOP_WORDS = {
    "a", "an", "the", "is", "it", "this", "that", "these", "those",
    "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "shall", "should",
    "may", "might", "must", "can", "could",
    "i", "me", "my", "we", "our", "you", "your",
    "he", "she", "they", "them", "his", "her", "their",
    "what", "which", "who", "whom", "whose",
    "also", "just", "very", "really", "quite",
    "please", "kindly", "could you", "can you",
}

# Simple lemmatization rules (suffix → base)
LEMMA_RULES: List[Tuple[str, str]] = [
    ("transactions", "transaction"),
    ("payments", "payment"),
    ("transfers", "transfer"),
    ("senders", "sender"),
    ("receivers", "receiver"),
    ("countries", "country"),
    ("amounts", "amount"),
    ("accounts", "account"),
    ("devices", "device"),
    ("methods", "method"),
    ("flagged", "flag"),
    ("showing", "show"),
    ("shown", "show"),
    ("shows", "show"),
    ("listing", "list"),
    ("listed", "list"),
    ("lists", "list"),
    ("filtering", "filter"),
    ("filtered", "filter"),
    ("sorting", "sort"),
    ("sorted", "sort"),
    ("grouping", "group"),
    ("grouped", "group"),
    ("comparing", "compare"),
    ("compared", "compare"),
    ("detecting", "detect"),
    ("detected", "detect"),
    ("calculating", "calculate"),
    ("calculated", "calculate"),
    ("ranking", "rank"),
    ("ranked", "rank"),
]


class TextPreprocessor:
    """
    Cleans, tokenizes, and lemmatizes raw input text for query analysis.
    """

    def __init__(self):
        self._lemma_map = {old: new for old, new in LEMMA_RULES}
        logger.info("TextPreprocessor initialized.")


    def clean(self, text: str) -> str:
        """
        Clean raw input text.
        - Lowercase
        - Remove extra whitespace
        - Normalize punctuation
        - Remove special characters except those meaningful (e.g., $, %, >, <, =)

        Args:
            text: Raw user input

        Returns:
            Cleaned string
        """
        if not text or not isinstance(text, str):
            return ""

        text = text.lower().strip()

        # Normalize unicode quotes/dashes
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2013", "-").replace("\u2014", "-")

        # Normalize multiple spaces/newlines
        text = re.sub(r"\s+", " ", text)

        # Remove characters that are truly noise (keep: alphanumeric, space, _, -, $, %, <, >, =, ., ,, ?, !)
        text = re.sub(r"[^\w\s\-_$%<>=.,?!']", " ", text)

        # Collapse again
        text = re.sub(r"\s+", " ", text).strip()

        logger.debug(f"Cleaned text: '{text}'")
        return text
    

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize cleaned text into individual tokens.
        Preserves multi-word phrases like "account age", "sender country".

        Args:
            text: Cleaned input string

        Returns:
            List of tokens
        """
        if not text:
            return []

        # Split on whitespace (preserve underscores as part of tokens)
        tokens = text.split()

        # Strip punctuation from edges of tokens, preserving internal hyphens
        cleaned_tokens = []
        for token in tokens:
            token = token.strip(string.punctuation.replace("-", "").replace("_", ""))

            if token:
                cleaned_tokens.append(token)

        logger.debug(f"Tokenized into {len(cleaned_tokens)} tokens: {cleaned_tokens}")
        return cleaned_tokens
    

    def remove_stop_words(self, tokens: List[str]) -> List[str]:
        """
        Remove stop words from token list, preserving domain-relevant tokens.

        Args:
            tokens: List of tokens

        Returns:
            Filtered token list
        """
        filtered = [t for t in tokens if t not in STOP_WORDS]
        logger.debug(f"After stop word removal: {filtered}")
        return filtered
    

    def lemmatize(self, tokens: List[str]) -> List[str]:
        """
        Apply simple rule-based lemmatization to normalize verb/noun forms.

        Args:
            tokens: List of tokens

        Returns:
            Lemmatized token list
        """
        lemmatized = []
        for token in tokens:
            lemmatized.append(self._lemma_map.get(token, token))

        logger.debug(f"Lemmatized tokens: {lemmatized}")
        return lemmatized
    

    def preprocess(self, text: str, remove_stops: bool = True) -> dict:
        """
        Full preprocessing pipeline: clean → tokenize → (stop word removal) → lemmatize.

        Args:
            text: Raw user input
            remove_stops: Whether to remove stop words

        Returns:
            Dictionary with keys: original, cleaned, tokens, filtered_tokens, lemmatized_tokens
        """
        
        original = text
        cleaned = self.clean(text)
        tokens = self.tokenize(cleaned)
        filtered = self.remove_stop_words(tokens) if remove_stops else tokens
        lemmatized = self.lemmatize(filtered)

        result = {
            "original": original,
            "cleaned": cleaned,
            "tokens": tokens,
            "filtered_tokens": filtered,
            "lemmatized_tokens": lemmatized,
            "processed_text": " ".join(lemmatized),
        }

        logger.info(f"Preprocessed query: '{original}' → '{result['processed_text']}'")
        return result
