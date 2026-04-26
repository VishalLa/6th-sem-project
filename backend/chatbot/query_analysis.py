import re
import logging
from typing import List, Dict, Optional, Tuple

from .domain_vocabulary import INTENT_KEYWORDS, NUMERIC_COLUMNS

logger = logging.getLogger(__name__)


DOMAIN_SIGNALS = {
    "fraud_detection": [
        "fraud", "suspicious", "anomaly", "risk", "alert", "flagged",
        "detect", "unusual", "abnormal", "outlier", "high risk", "kyc none",
        "unverified", "pending kyc",
    ],
    "transaction_analysis": [
        "transaction", "transfer", "payment", "amount", "sender", "receiver",
        "method", "channel", "wire", "ach", "p2p", "crypto",
    ],
    "geographic": [
        "country", "countries", "cross-border", "international", "domestic",
        "sg", "in", "ae", "ng", "ca", "uk", "us",
    ],
    "temporal": [
        "date", "time", "timestamp", "recent", "latest", "oldest", "when",
        "last", "first", "today", "velocity",
    ],
    "account": [
        "account", "sender account", "receiver account", "acc", "kyc",
        "device", "tenure", "age",
    ],
    "statistical": [
        "average", "mean", "total", "count", "sum", "max", "min",
        "distribution", "breakdown", "percentage", "ratio",
    ],
    "navigation": [
        "dashboard", "chart", "graph", "visualize", "plot", "go to", "open",
        "show page", "navigate",
    ],
    "help": [
        "help", "what can you", "how do i", "capabilities", "explain",
        "what is", "describe",
    ],
}

INTENT_PRIORITY = [
    "fraud", "navigate", "help", "math",
    "count", "aggregate", "group", "compare",
    "filter", "sort", "show",
]


class IntentDomainDetector:
    """
    Detects the primary intent and domain from preprocessed query text.
    """

    def __init__(self):
        logger.info("IntentDomainDetector initialized.")


    def detect_intent(self, tokens: List[str], text: str) -> Dict:
        """
        Detect the primary intent from token list and text.

        Args:
            tokens: Preprocessed tokens
            text: Full cleaned text

        Returns:
            Dict with: primary_intent, all_intents, confidence
        """
        text_lower = text.lower()
        token_set = set(tokens)
        intent_scores: Dict[str, int] = {}

        for intent, keywords in INTENT_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    # Multi-word phrases get higher weight
                    score += 2 if " " in kw else 1
                elif kw in token_set:
                    score += 1
            if score > 0:
                intent_scores[intent] = score

        if not intent_scores:
            return {
                "primary_intent": "show",
                "all_intents": {},
                "confidence": 0.3,
            }

        # Sort by priority order
        sorted_intents = sorted(
            intent_scores.items(),
            key=lambda x: (INTENT_PRIORITY.index(x[0]) if x[0] in INTENT_PRIORITY else 99, -x[1]),
        )
        primary = sorted_intents[0][0]
        max_score = sorted_intents[0][1]
        total_score = sum(intent_scores.values())

        raw_ratio = max_score / max(total_score, 1)
        confidence = min(raw_ratio * 0.65 + 0.35, 1.0)

        return {
            "primary_intent": primary,
            "all_intents": intent_scores,
            "confidence": round(confidence, 2),
        }


    def detect_domain(self, tokens: List[str], text: str) -> Dict:
        """
        Detect the subject domain of the query.

        Args:
            tokens: Preprocessed tokens
            text: Full cleaned text

        Returns:
            Dict with: primary_domain, all_domains
        """
        text_lower = text.lower()
        domain_scores: Dict[str, int] = {}

        for domain, signals in DOMAIN_SIGNALS.items():
            score = sum(1 for s in signals if s in text_lower)
            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            return {"primary_domain": "transaction_analysis", "all_domains": {}}

        primary = max(domain_scores, key=domain_scores.get)
        return {
            "primary_domain": primary,
            "all_domains": domain_scores,
        }


    def analyze(self, tokens: List[str], text: str) -> Dict:
        """Combined intent + domain analysis."""
        intent = self.detect_intent(tokens, text)
        domain = self.detect_domain(tokens, text)
        return {**intent, **domain}
    


MULTI_Q_SEPARATORS = re.compile(
    r"\s*(?:and also|also|and then|additionally|furthermore|plus|,\s*and|;\s*and|[;]|\band\b)\s+(?=(?:show|list|find|count|get|what|how many|give|display|calculate|compare|which))",
    re.IGNORECASE,
)

QUESTION_STARTERS = re.compile(
    r"(?:show|list|find|count|get|what|how many|give|display|calculate|compare|which|tell me)",
    re.IGNORECASE,
)


class MultiQuestionDetector:
    """
    Detects if a user query contains multiple distinct questions
    and splits them for individual processing.
    """

    def __init__(self):
        logger.info("MultiQuestionDetector initialized.")

    def detect_multiple(self, text: str) -> Dict:
        """
        Detect and split multiple questions from a compound query.

        Args:
            text: Raw or cleaned query text

        Returns:
            Dict with: is_multi, questions (list of str), question_count
        """
        parts = MULTI_Q_SEPARATORS.split(text)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) > 1:
            logger.info(f"Multi-question detected: {len(parts)} questions")
            return {
                "is_multi": True,
                "questions": parts,
                "question_count": len(parts),
            }

        # Check for "?" separated questions
        if text.count("?") > 1:
            q_parts = [q.strip() for q in text.split("?") if q.strip()]
            if len(q_parts) > 1:
                return {
                    "is_multi": True,
                    "questions": [q + "?" for q in q_parts],
                    "question_count": len(q_parts),
                }

        return {
            "is_multi": False,
            "questions": [text],
            "question_count": 1,
        }


MATH_OPERATION_PATTERNS = {
    "growth_rate": re.compile(
        r"\b(growth rate|growth|increase|change|percent change|rate of change)\b",
        re.IGNORECASE,
    ),
    "average": re.compile(
        r"\b(average|avg|mean)\b",
        re.IGNORECASE,
    ),
    "percentage": re.compile(
        r"\b(percentage|percent|proportion|share|ratio)\b",
        re.IGNORECASE,
    ),
    "sum": re.compile(
        r"\b(sum|total|add up|cumulative)\b",
        re.IGNORECASE,
    ),
    "count": re.compile(
        r"\b(count|how many|number of|tally)\b",
        re.IGNORECASE,
    ),
    "max": re.compile(r"\b(max|maximum|highest|largest|biggest)\b", re.IGNORECASE),
    "min": re.compile(r"\b(min|minimum|lowest|smallest|least)\b", re.IGNORECASE),
    "ranking": re.compile(r"\b(rank|top|bottom|leaderboard)\b", re.IGNORECASE),
}


TIME_RANGE_PATTERNS = {
    "last_n_hours": re.compile(r"last\s+(\d+)\s+hours?", re.IGNORECASE),
    "last_n_days": re.compile(r"last\s+(\d+)\s+days?", re.IGNORECASE),
    "last_n_minutes": re.compile(r"last\s+(\d+)\s+min(?:utes?)?", re.IGNORECASE),
    "between_dates": re.compile(
        r"between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ),
}



class MathematicalQueryHandler:
    """
    Handles mathematical/statistical query components:
    detects math operations, time ranges, and prepares calculation specs.
    """

    def __init__(self):
        logger.info("MathematicalQueryHandler initialized.")


    def detect_math_operation(self, text: str) -> Optional[str]:
        """
        Detect primary math operation from query text.

        Args:
            text: Cleaned query text

        Returns:
            Operation name string or None
        """
        for op_name, pattern in MATH_OPERATION_PATTERNS.items():
            if pattern.search(text):
                logger.debug(f"Math operation detected: {op_name}")
                return op_name
        return None


    def detect_time_range(self, text: str) -> Optional[Dict]:
        """
        Detect time range filters in query.

        Args:
            text: Cleaned query text

        Returns:
            Dict with time range info or None
        """
        for range_type, pattern in TIME_RANGE_PATTERNS.items():
            match = pattern.search(text)
            if match:
                if range_type in ("last_n_hours", "last_n_days", "last_n_minutes"):
                    return {"type": range_type, "value": int(match.group(1))}
                elif range_type == "between_dates":
                    return {
                        "type": "between_dates",
                        "start": match.group(1),
                        "end": match.group(2),
                    }
        return None


    def calculate_growth_rate(self, old_val: float, new_val: float) -> float:
        """
        Calculate percentage growth rate.

        Args:
            old_val: Previous value
            new_val: Current value

        Returns:
            Growth rate as a percentage
        """
        if old_val == 0:
            return 0.0
        return round(((new_val - old_val) / abs(old_val)) * 100, 2)
    

    def calculate_average(self, values: List[float]) -> float:
        """Calculate mean of values."""
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)


    def build_math_spec(self, text: str, tokens: List[str]) -> Dict:
        """
        Build a math specification from query.

        Args:
            text: Cleaned query text
            tokens: Preprocessed tokens

        Returns:
            Dict with operation, column, time_range
        """
        operation = self.detect_math_operation(text)
        time_range = self.detect_time_range(text)

        # Detect target column
        target_column = "amount"  # Default
        for col in NUMERIC_COLUMNS:
            if col in text.lower() or col.replace("_", " ") in text.lower():
                target_column = col
                break

        return {
            "operation": operation,
            "column": target_column,
            "time_range": time_range,
            "is_math_query": operation is not None,
        }
