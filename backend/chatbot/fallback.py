import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.4


CLARIFICATION_TEMPLATES = {
    "unclear_column": (
        "I'm not sure which field you're referring to. "
        "Could you clarify? For example, are you asking about the **{suggestions}**?"
    ),
    "unclear_operation": (
        "I understood your question but I'm not sure what you'd like me to do. "
        "Do you want me to: **list** the transactions, **count** them, or **calculate** a statistic?"
    ),
    "no_results": (
        "I couldn't find any transactions matching your criteria. "
        "You could try: removing some filters, checking the spelling of country/method names, "
        "or broadening your search."
    ),
    "ambiguous_filter": (
        "I found multiple possible interpretations for your filter. "
        "Did you mean: **{option_a}** or **{option_b}**?"
    ),
    "general": (
        "I'm not fully confident I understood your question. "
        "Could you rephrase it or be more specific? "
        "You can ask things like: _'Show crypto transactions from Nigeria'_ or "
        "_'What is the average amount for verified senders?'_"
    ),
}

EXAMPLE_QUERIES = [
    "Show all transactions from Nigeria",
    "Count crypto transactions",
    "What is the average transaction amount?",
    "Find suspicious transactions",
    "Show top 10 highest amount transfers",
    "Group transactions by payment method",
    "How many transactions have no KYC?",
    "Average amount by sender country",
]



class LowConfidenceFallback:
    """
    The Safety Net: handles uncertain interpretations gracefully.
    Returns helpful clarification messages rather than wrong answers.
    """

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold
        logger.info(f"LowConfidenceFallback initialized (threshold={confidence_threshold}).")


    def is_low_confidence(self, query_spec: Dict) -> bool:
        """
        Check if a query spec has low confidence.

        Args:
            query_spec: Analyzed query specification

        Returns:
            True if confidence is below threshold
        """
        return query_spec.get("confidence", 0) < self.confidence_threshold


    def build_fallback_response(self, query_spec: Dict) -> Dict:
        """
        Build a fallback response for a low-confidence query.

        Args:
            query_spec: Analyzed query specification

        Returns:
            Response dict with clarification message and suggestions
        """
        confidence = query_spec.get("confidence", 0)
        raw_query = query_spec.get("raw_query", "")
        operation = query_spec.get("operation_type", "")
        columns = query_spec.get("referenced_columns", [])
        corrections = query_spec.get("spelling_corrections", {})

        # Choose appropriate message
        if not columns and operation not in ("HELP", "NAVIGATE"):
            template = CLARIFICATION_TEMPLATES["unclear_column"]
            suggestions = "**amount**, **sender_country**, **txn_method**, or **sender_kyc**"
            message = template.format(suggestions=suggestions)

        elif operation == "SELECT" and confidence < 0.3:
            message = CLARIFICATION_TEMPLATES["unclear_operation"]

        else:
            message = CLARIFICATION_TEMPLATES["general"]

        # Add spelling correction note
        if corrections:
            correction_str = ", ".join(
                f"'{orig}' → '{corr}'" for orig, corr in corrections.items()
            )
            message += f"\n\n_Note: I auto-corrected some terms: {correction_str}_"

        # Add example suggestions
        import random
        examples = random.sample(EXAMPLE_QUERIES, min(3, len(EXAMPLE_QUERIES)))
        examples_str = "\n".join(f"- _{q}_" for q in examples)

        full_message = (
            f"{message}\n\n"
            f"**Some examples of what you can ask:**\n{examples_str}"
        )

        logger.info(f"Low-confidence fallback triggered for query: '{raw_query}' (conf={confidence:.2f})")

        return {
            "answer": full_message,
            "table_data": None,
            "answer_type": "clarification",
            "confidence": confidence,
            "is_fallback": True,
        }


    def handle_empty_result(self, query_spec: Dict) -> Dict:
        """
        Handle the case where a query returned no results.

        Args:
            query_spec: The query specification that yielded no results

        Returns:
            Helpful response dict
        """
        filters = query_spec.get("filters", [])
        filter_desc = ", ".join(
            f"{f.get('column', '?')}={f.get('value', '?')}" for f in filters
        )

        message = CLARIFICATION_TEMPLATES["no_results"]
        if filter_desc:
            message = (
                f"No transactions found with filters: **{filter_desc}**.\n\n"
                "You could try:\n"
                "- Removing some filters\n"
                "- Checking spelling (e.g., 'Verified' not 'verified')\n"
                "- Using broader criteria\n"
            )

        return {
            "answer": message,
            "table_data": None,
            "answer_type": "empty",
            "is_fallback": True,
        }
    

    def handle_unknown_query(self) -> Dict:
        """Handle a completely unrecognized query."""
        message = (
            "I'm sorry, I couldn't understand your question. "
            "I'm specialized in answering questions about **financial transaction data**.\n\n"
            "Try asking about:\n"
            "- Transactions (show, filter, count)\n"
            "- Amounts (average, total, max)\n"
            "- Fraud detection (suspicious transactions, risk flags)\n"
            "- Geographic patterns (by country)\n"
            "- Payment methods (crypto, wire, ACH, P2P)\n\n"
            "Type **help** to see more examples."
        )
        return {
            "answer": message,
            "table_data": None,
            "answer_type": "unknown",
            "is_fallback": True,
        }

