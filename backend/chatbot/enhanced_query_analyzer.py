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


    # ------------------------------------------------------------------
    # Priority rules applied BEFORE the intent-detector output.
    # Each entry: (trigger_phrases, operation_type, aggregation_or_None)
    # Checked top-to-bottom; first match wins.
    # ------------------------------------------------------------------
    _PRIORITY_RULES = [
        # COUNT
        (["how many", "number of", "total number", "count of", "how much", "total count"],
         "COUNT", "COUNT"),
        # AGGREGATE / AVG
        (["average", "avg", "mean", "what is the average", "what's the average"],
         "AGGREGATE", "AVG"),
        # AGGREGATE / MAX
        (["highest amount", "maximum amount", "largest amount", "max amount"],
         "AGGREGATE", "MAX"),
        # AGGREGATE / MIN
        (["lowest amount", "minimum amount", "smallest amount", "min amount"],
         "AGGREGATE", "MIN"),
        # AGGREGATE / SUM
        (["total amount", "sum of", "what is the total", "overall amount",
          "what's the total", "cumulative amount", "grand total"],
         "AGGREGATE", "SUM"),
        # GROUP_BY
        (["group by", "group transactions by", "breakdown by", "split by",
          "by sender country", "by receiver country", "by payment method",
          "by txn method", "by method", "by country", "by kyc", "by channel",
          "per country", "per method", "breakdown of", "categorize by",
          "organize by", "distribute by", "classify by"],
         "GROUP_BY", None),
        # FRAUD
        (["suspicious", "fraud", "anomal", "risky", "high-risk",
          "high risk", "flagged", "flag", "risk", "detect", "money laundering",
          "aml", "illicit", "at risk", "red flag", "suspicious activity"],
         "FRAUD_DETECT", None),
    ]

    def analyze(self, raw_query: str) -> Dict:
        """
        Full analysis of a raw user query.

        Args:
            raw_query: Raw user input

        Returns:
            QuerySpec dict with all analysis results
        """
        # Multi-question detection
        multi = self.multi_detector.detect_multiple(raw_query)
        primary_query = multi["questions"][0] if multi["questions"] else raw_query

        # Preprocessing
        pp = self.query_preprocessor.preprocess(primary_query)
        tokens = pp["lemmatized_tokens"]
        text = pp["corrected_text"]
        text_lower = text.lower()
        raw_lower = raw_query.lower()

        # Intent + domain (used for confidence scoring)
        intent_domain = self.intent_detector.analyze(tokens, text)

        # Keyword extraction
        keywords = self.keyword_extractor.extract_keywords(tokens, text)

        # NER
        entities = self.ner.extract(text)

        # Math spec
        math_spec = self.math_handler.build_math_spec(text, tokens)

        # ------------------------------------------------------------------
        # Operation routing: priority rules first, then intent detector
        # ------------------------------------------------------------------
        operation_type = None
        forced_aggregation = None
        priority_rule_matched = False

        for triggers, op, agg in self._PRIORITY_RULES:
            if any(t in text_lower or t in raw_lower for t in triggers):
                operation_type = op
                forced_aggregation = agg
                priority_rule_matched = True
                logger.debug(f"Priority rule matched: op={op}, agg={agg}")
                break

        if operation_type is None:
            primary_intent = intent_domain["primary_intent"]
            operation_type = INTENT_TO_OPERATION.get(primary_intent, "SELECT")
            # Math override only when no priority rule matched
            if math_spec["is_math_query"] and operation_type not in (
                "FRAUD_DETECT", "HELP", "NAVIGATE"
            ):
                operation_type = "CALCULATE"

        primary_intent = intent_domain["primary_intent"]

        # Detect target column
        target_column = self._detect_target_column(keywords["columns"], operation_type, entities, text)

        # Detect group column
        group_column = self._detect_group_column(text, tokens, keywords["columns"])

        # Detect sort direction
        sort_direction = self._detect_sort_direction(text)

        # Determine aggregation — priority rule value takes precedence
        aggregation = forced_aggregation if forced_aggregation is not None \
            else self._detect_aggregation(text, operation_type)

        # Calculate confidence
        confidence = self._calculate_confidence(
            intent_domain, keywords, entities, operation_type, text, raw_lower,
            priority_rule_matched=priority_rule_matched
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
        text: str,
        raw_lower: str = "",
        priority_rule_matched: bool = False,
    ) -> float:
        """
        Calculate overall confidence score for the analysis.
        REWRITTEN: Cumulative boosts, higher base floor, domain-signal bonus,
        multi-signal bonus, priority-rule bonus.  Always returns [0.0, 1.0].
        """
        text_lower = text.lower()
        combined = text_lower + " " + raw_lower

        # ----------------------------------------------------------------
        # 1. BASE FLOOR — any coherent domain query starts at 0.40
        # ----------------------------------------------------------------
        score = 0.40

        # ----------------------------------------------------------------
        # 2. INTENT CONFIDENCE  (already base-adjusted in query_analysis.py)
        #    Contribute a proportional bonus above the base.
        #    intent_conf is already in [0.35, 1.0] after our fix there.
        # ----------------------------------------------------------------
        intent_conf = intent_domain.get("confidence", 0.50)
        # Map [0.35, 1.0] → additional [0, 0.15]
        intent_bonus = (intent_conf - 0.35) / 0.65 * 0.15
        score += max(intent_bonus, 0.0)

        # ----------------------------------------------------------------
        # 3. COLUMN SIGNAL  (+0.08 per column, max +0.16)
        # ----------------------------------------------------------------
        col_count = len(keywords.get("columns", {}))
        score += min(col_count * 0.08, 0.16)

        # ----------------------------------------------------------------
        # 4. FILTER SIGNAL  (+0.07 per filter, max +0.14)
        # ----------------------------------------------------------------
        filter_count = len(keywords.get("filters", []))
        score += min(filter_count * 0.07, 0.14)

        # ----------------------------------------------------------------
        # 5. ENTITY SIGNAL  (+0.05 per entity, max +0.10)
        # ----------------------------------------------------------------
        entity_count = sum(
            len(v) if isinstance(v, list) else 1 for v in entities.values()
        )
        score += min(entity_count * 0.05, 0.10)

        # ----------------------------------------------------------------
        # 6. MULTI-SIGNAL BONUS — queries that have BOTH column + filter
        #    signals are very well understood; reward them.
        # ----------------------------------------------------------------
        if col_count >= 1 and filter_count >= 1:
            score += 0.08
        if col_count >= 1 and entity_count >= 1:
            score += 0.05

        # ----------------------------------------------------------------
        # 7. PRIORITY RULE BONUS — a priority-rule match means we identified
        #    the operation with near-certainty.
        # ----------------------------------------------------------------
        if priority_rule_matched:
            score += 0.12

        # ----------------------------------------------------------------
        # 8. PATTERN BOOSTS — ALL matching patterns add up (no break).
        #    Each pattern boost is smaller than before to avoid runaway scores.
        # ----------------------------------------------------------------
        pattern_boosts = [
            # COUNT patterns
            ("how many",              0.12),
            ("number of",             0.10),
            ("count of",              0.10),
            ("total count",           0.10),
            # AGGREGATE patterns
            ("what is the average",   0.12),
            ("what's the average",    0.12),
            ("average",               0.08),
            ("what is the total",     0.12),
            ("what's the total",      0.12),
            ("total amount",          0.10),
            ("sum of",                0.10),
            # SHOW/FILTER patterns
            ("show me",               0.08),
            ("list all",              0.08),
            ("find all",              0.08),
            # FRAUD patterns
            ("high-risk",             0.10),
            ("high risk",             0.10),
            ("suspicious",            0.10),
            ("fraud",                 0.10),
            ("flagged",               0.08),
            # GROUP patterns
            ("group by",              0.10),
            ("breakdown by",          0.10),
            ("by country",            0.08),
            ("by method",             0.08),
            ("by kyc",                0.08),
            # FILTER qualifiers
            ("above",                 0.06),
            ("below",                 0.06),
            ("greater than",          0.06),
            ("less than",             0.06),
            ("where",                 0.05),
            ("from",                  0.04),
            # SORT qualifiers
            ("top",                   0.06),
            ("bottom",                0.06),
            ("sorted by",             0.07),
            ("ordered by",            0.07),
        ]

        for pattern, boost in pattern_boosts:
            if pattern in combined:
                score += boost
                logger.debug(f"Confidence boost +{boost} for pattern '{pattern}'")

        # ----------------------------------------------------------------
        # 9. NUMERIC CONDITIONS BONUS
        # ----------------------------------------------------------------
        if keywords.get("numeric_conditions"):
            score += 0.08

        # ----------------------------------------------------------------
        # 10. DOMAIN SIGNAL BONUS — query contains recognisable domain terms
        # ----------------------------------------------------------------
        domain_terms = [
            "transaction", "transfer", "payment", "sender", "receiver",
            "amount", "kyc", "fraud", "risk", "country", "method", "channel",
            "crypto", "wire", "ach", "p2p", "velocity", "account", "device",
        ]
        domain_hit_count = sum(1 for t in domain_terms if t in combined)
        if domain_hit_count >= 3:
            score += 0.08
        elif domain_hit_count >= 1:
            score += 0.04

        return round(min(score, 1.0), 2)
    