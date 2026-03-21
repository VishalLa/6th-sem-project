import logging
from typing import List, Dict, Optional, Any

from .text_processor import TextPreprocessor
from .spell_checker import SpellChecker
from .kerword_extractor import KeyWordExtractor, NERModule
from .query_analysis import IntentDomainDetector, MultiQuestionDetector, MathematicalQueryHandler
from .domain_vocabulary import (
    COLUMN_ALIASES, ALL_COLUMNS, NUMERIC_COLUMNS, CATEGORICAL_COLUMNS,
    VALID_FILTER_VALUES, INTENT_KEYWORDS
)


logger = logging.getLogger(__name__)

# Operation type mapping from intent
INTENT_TO_OPERATION = {
    "show": "SELECT",
    "count": "COUNT",
    "aggregate": "AGGREGATE",
    "filter": "FILTER",
    "sort": "SORT",
    "group": "GROUP_BY",
    "compare": "COMPARE",
    "fraud": "FRAUD_DETECT",
    "navigate": "NAVIGATE",
    "math": "CALCULATE",
    "help": "HELP",
}

# UI action mapping
UI_ACTIONS = {
    "SELECT": "display_table",
    "COUNT": "display_count",
    "AGGREGATE": "display_stat",
    "FILTER": "display_table",
    "SORT": "display_table",
    "GROUP_BY": "display_grouped",
    "COMPARE": "display_comparison",
    "FRAUD_DETECT": "display_alert",
    "NAVIGATE": "navigate_page",
    "CALCULATE": "display_calculation",
    "HELP": "display_help",
}


class QueryPreprocessor:
    """
    Wraps TextPreprocessor with spell checking for query-specific preprocessing.
    """

    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.spell_checker = SpellChecker()
        logger.info("QueryPreprocessor initialized.")

    
    def preprocess(self, raw_query: str) -> Dict:
        """
        Full query preprocessing: clean → spell check → tokenize → lemmatize.

        Args:
            raw_query: Raw user input string

        Returns:
            Dict with all preprocessing results
        """
        # Step 1: Basic preprocessing
        pp = self.preprocessor.preprocess(raw_query)

        # Step 2: Spell check on cleaned text
        spell_result = self.spell_checker.check_text(pp["cleaned"])

        # Step 3: If corrections applied, re-preprocess corrected text
        if spell_result["has_corrections"]:
            corrected_pp = self.preprocessor.preprocess(spell_result["corrected_text"])
            pp["corrected_text"] = spell_result["corrected_text"]
            pp["spelling_corrections"] = spell_result["corrections"]
            pp["tokens"] = corrected_pp["tokens"]
            pp["filtered_tokens"] = corrected_pp["filtered_tokens"]
            pp["lemmatized_tokens"] = corrected_pp["lemmatized_tokens"]
            pp["processed_text"] = corrected_pp["processed_text"]
        else:
            pp["corrected_text"] = pp["cleaned"]
            pp["spelling_corrections"] = {}

        logger.debug(f"QueryPreprocessor result: {pp}")
        return pp
    

class EnhancedQueryAnalyzer:
    """
    Full query analysis pipeline. Produces a structured QuerySpec
    that drives the DataExecutor and answer constructor.
    IMPROVED: Better confidence scoring and query understanding.
    """

    def __init__(self):
        self.query_preprocessor = QueryPreprocessor()
        self.keyword_extractor = KeyWordExtractor()
        self.ner = NERModule()
        self.intent_detector = IntentDomainDetector()
        self.multi_detector = MultiQuestionDetector()
        self.math_handler = MathematicalQueryHandler()
        logger.info("EnhancedQueryAnalyzer initialized.")


    def analyze(self, raw_query: str) -> Dict:
        """
        Full analysis of a raw user query.
        IMPROVED: Better handling of common queries.

        Args:
            raw_query: Raw user input

        Returns:
            QuerySpec dict with all analysis results
        """
        # Multi-question detection (analyze each sub-question if needed)
        multi = self.multi_detector.detect_multiple(raw_query)

        # Work with the first question for primary analysis
        primary_query = multi["questions"][0] if multi["questions"] else raw_query

        # Preprocessing
        pp = self.query_preprocessor.preprocess(primary_query)
        tokens = pp["lemmatized_tokens"]
        text = pp["corrected_text"]

        # Intent + domain
        intent_domain = self.intent_detector.analyze(tokens, text)

        # Keyword extraction
        keywords = self.keyword_extractor.extract_keywords(tokens, text)

        # NER
        entities = self.ner.extract(text)

        # Math spec
        math_spec = self.math_handler.build_math_spec(text, tokens)

        # Determine operation type
        primary_intent = intent_domain["primary_intent"]
        operation_type = INTENT_TO_OPERATION.get(primary_intent, "SELECT")

        # If math operation detected, override
        if math_spec["is_math_query"] and operation_type not in ("FRAUD_DETECT", "HELP", "NAVIGATE"):
            operation_type = "CALCULATE"

        # Detect target column
        target_column = self._detect_target_column(keywords["columns"], operation_type, entities, text)

        # Detect group column
        group_column = self._detect_group_column(text, tokens, keywords["columns"])

        # Detect sort direction
        sort_direction = self._detect_sort_direction(text)

        # Determine aggregation
        aggregation = self._detect_aggregation(text, operation_type)

        # IMPROVED: Calculate confidence with better logic
        confidence = self._calculate_confidence(
            intent_domain, keywords, entities, operation_type, text
        )

        # UI action
        ui_action = UI_ACTIONS.get(operation_type, "display_table")

        query_spec = {
            # Raw + processed
            "raw_query": raw_query,
            "processed_text": pp["processed_text"],
            "spelling_corrections": pp["spelling_corrections"],
            # Multi-question
            "is_multi_question": multi["is_multi"],
            "sub_questions": multi["questions"],
            # Intent + domain
            "operation_type": operation_type,
            "primary_intent": primary_intent,
            "primary_domain": intent_domain.get("primary_domain", "transaction_analysis"),
            # Column targeting
            "target_column": target_column,
            "group_column": group_column,
            "referenced_columns": list(keywords["columns"].keys()),
            # Filters
            "filters": keywords["filters"],
            "numeric_conditions": keywords["numeric_conditions"],
            # Aggregation + sorting
            "aggregation": aggregation,
            "sort_direction": sort_direction,
            # Math
            "math_operation": math_spec.get("operation"),
            "time_range": math_spec.get("time_range"),
            # Entities
            "entities": entities,
            # Meta
            "ui_action": ui_action,
            "confidence": confidence,
            "is_low_confidence": confidence < 0.35,  # IMPROVED: Lowered threshold
        }

        logger.info(
            f"QuerySpec: op={operation_type}, intent={primary_intent}, "
            f"target={target_column}, confidence={confidence:.2f}"
        )
        return query_spec
    

    def _detect_target_column(
        self, columns: Dict, operation_type: str, entities: Dict, text: str
    ) -> Optional[str]:
        """
        Determine the primary target column for the operation.
        IMPROVED: Better detection for common queries.
        """
        text_lower = text.lower()
        
        # IMPROVED: Explicit detection for specific queries
        if "risk score" in text_lower or "risk rating" in text_lower:
            return "risk_score"
        
        if not columns:
            # Default by operation
            if operation_type in ("COUNT", "FRAUD_DETECT", "SELECT"):
                return "transaction_id"
            return "amount"

        # Prioritize numeric columns for aggregate operations
        if operation_type in ("AGGREGATE", "CALCULATE"):
            for col in NUMERIC_COLUMNS:
                if col in columns:
                    return col
            return "amount"

        # Return first referenced column
        return next(iter(columns.keys()))
    

    def _detect_group_column(
        self, text: str, tokens: List[str], columns: Dict
    ) -> Optional[str]:
        """
        Detect grouping column from 'by X' or 'per X' patterns.
        IMPROVED: Better pattern matching.
        """
        text_lower = text.lower()
        group_phrases = ["group by", "per", "by country", "by method", "breakdown by", "split by", "each"]

        for phrase in group_phrases:
            if phrase in text_lower:

                # IMPROVED: Check for method/channel keywords
                if "method" in text_lower or "channel" in text_lower or "payment" in text_lower:
                    return "txn_method"
                
                # Check for country keywords
                if "country" in text_lower:
                    if "sender" in text_lower or "from" in text_lower:
                        return "sender_country"
                    elif "receiver" in text_lower or "to" in text_lower:
                        return "receiver_country"
                    else:
                        return "sender_country"  # Default to sender country
                
                # Check for KYC
                if "kyc" in text_lower or "verification" in text_lower:
                    return "sender_kyc"
                
                # Find what column follows
                for col in CATEGORICAL_COLUMNS:
                    col_label = col.replace("_", " ")
                    if col in text_lower or col_label in text_lower:
                        return col

        return None
    

    def _detect_sort_direction(self, text: str) -> str:
        """Detect sort direction from text."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["highest", "largest", "most", "descending", "desc", "top"]):
            return "DESC"
        
        if any(kw in text_lower for kw in ["lowest", "smallest", "least", "ascending", "asc", "bottom"]):
            return "ASC"
        
        return "DESC"  # Default
    

    def _detect_aggregation(self, text: str, operation_type: str) -> Optional[str]:
        """
        Detect aggregation function from text.
        IMPROVED: Better detection logic.
        """
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["average", "avg", "mean"]):
            return "AVG"
        
        if any(kw in text_lower for kw in ["sum", "total"]):
            return "SUM"
        
        if any(kw in text_lower for kw in ["max", "maximum", "highest", "largest"]):
            return "MAX"
        
        if any(kw in text_lower for kw in ["min", "minimum", "lowest", "smallest"]):
            return "MIN"
        
        if any(kw in text_lower for kw in ["count", "how many", "number"]):
            return "COUNT"
        
        if operation_type == "AGGREGATE":
            return "SUM"
        
        return None


    def _calculate_confidence(
        self,
        intent_domain: Dict,
        keywords: Dict,
        entities: Dict,
        operation_type: str,
        text: str
    ) -> float:
        """
        Calculate overall confidence score for the analysis.
        IMPROVED: Better scoring logic with query-specific boosts.
        """
        score = 0.0
        text_lower = text.lower()

        # Intent confidence (0–0.3)
        intent_conf = intent_domain.get("confidence", 0.3)
        score += intent_conf * 0.3

        # Column matches (0–0.25)
        col_count = len(keywords.get("columns", {}))
        score += min(col_count * 0.125, 0.25)

        # Filter matches (0–0.15)
        filter_count = len(keywords.get("filters", []))
        score += min(filter_count * 0.075, 0.15)

        # Entity matches (0–0.15)
        entity_count = sum(len(v) if isinstance(v, list) else 1 for v in entities.values())
        score += min(entity_count * 0.075, 0.15)
        
        # IMPROVED: Boost for simple, common queries
        simple_query_patterns = [
            ("how many", 0.3),
            ("what is the average", 0.3),
            ("show me", 0.2),
            ("total", 0.2),
            ("count", 0.2),
            ("high-risk", 0.25),
            ("high risk", 0.25),
            ("suspicious", 0.25),
            ("fraud", 0.25),
            ("group by", 0.2),
            ("by country", 0.2),
            ("by method", 0.2),
        ]
        
        for pattern, boost in simple_query_patterns:
            if pattern in text_lower:
                score += boost
                logger.debug(f"Applied boost {boost} for pattern '{pattern}'")
                break

        # IMPROVED: Boost for numeric conditions
        if keywords.get("numeric_conditions"):
            score += 0.15

        return round(min(score, 1.0), 2)
    