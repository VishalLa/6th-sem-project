import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReasoningTracer:
    """
    Tracks the reasoning steps taken to answer a query.
    Provides transparency into how the answer was derived.
    """

    def __init__(self):
        self._steps: List[Dict] = []
        self._session_traces: Dict[str, List] = {}

    
    def add_step(self, step_name: str, description: str, data: Any = None) -> None:
        """
        Add a reasoning step.

        Args:
            step_name: Short identifier (e.g., "intent_detection")
            description: Human-readable description of what happened
            data: Optional supporting data
        """
        step = {
            "step": step_name,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        self._steps.append(step)
        logger.debug(f"[TRACE] {step_name}: {description}")


    def get_trace(self) -> List[Dict]:
        """Return all reasoning steps."""
        return self._steps.copy()


    def get_trace_summary(self) -> str:
        """Return a formatted string summary of reasoning steps."""
        if not self._steps:
            return "No reasoning steps recorded."
        
        lines = []
        for i, step in enumerate(self._steps, 1):
            lines.append(f"{i}. [{step['step']}] {step['description']}")
        return "\n".join(lines)


    def reset(self) -> None:
        """Clear all reasoning steps."""
        self._steps = []


    def save_trace(self, trace_id: str) -> None:
        """Save current trace under an ID for later retrieval."""
        self._session_traces[trace_id] = self._steps.copy()
        self.reset()

    def get_saved_trace(self, trace_id: str) -> List[Dict]:
        """Retrieve a saved trace."""
        return self._session_traces.get(trace_id, [])
    


class RuleBasedAnswerConstructor:
    """
    Constructs natural language answers from execution results.
    Uses templates and rules — no LLM required.
    IMPROVED: Better error handling and answer formatting.
    """

    def __init__(self):
        logger.info("RuleBasedAnswerConstructor initialized.")


    def construct(self, query_spec: Dict, execution_result: Dict, tracer: Optional[ReasoningTracer] = None) -> Dict:
        """
        Main entry: construct answer from query spec + execution result.
        IMPROVED: Better error handling.

        Args:
            query_spec: Analyzed query specification
            execution_result: Result from DataExecutor
            tracer: Optional ReasoningTracer for transparency

        Returns:
            Dict with: answer (str), table_data (optional), answer_type
        """
        if tracer:
            tracer.add_step("answer_construction", f"Building answer for op={query_spec.get('operation_type')}")

        if not execution_result.get("success", False):
            error = execution_result.get("metadata", {}).get("error", "Unknown error")
            return {
                "answer": f"I encountered an error processing your request: {error}",
                "table_data": None,
                "answer_type": "error",
            }

        operation = execution_result.get("operation", "SELECT")

        if operation == "COUNT":
            return self._construct_count_answer(query_spec, execution_result)
        
        elif operation == "AGGREGATE":
            return self._construct_aggregate_answer(query_spec, execution_result)
        
        elif operation == "GROUP_BY":
            return self._construct_group_by_answer(query_spec, execution_result)
        
        elif operation == "FRAUD_DETECT":
            return self._construct_fraud_answer(query_spec, execution_result)
        
        else:
            return self._construct_from_result(query_spec, execution_result)


    def _construct_count_answer(self, spec: Dict, result: Dict) -> Dict:
        """Construct answer for COUNT operations."""
        count = result["data"].get("count", 0)
        filters = spec.get("filters", [])

        filter_desc = self._describe_filters(filters)
        qualifier = f" {filter_desc}" if filter_desc else ""

        answer = f"There are **{count:,}** transactions{qualifier} in the dataset."

        return {"answer": answer, "table_data": None, "answer_type": "count"}


    def _construct_aggregate_answer(self, spec: Dict, result: Dict) -> Dict:
        """
        Construct answer for AGGREGATE/CALCULATE operations.
        IMPROVED: Better null handling.
        """
        data = result["data"]
        label = data.get("label", "value")
        column = data.get("column", "amount")
        value = data.get("value", 0)

        # IMPROVED: Handle None/NaN values
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return {
                "answer": f"No data available for {column.replace('_', ' ')}.",
                "table_data": None,
                "answer_type": "aggregate",
            }

        filters = spec.get("filters", [])
        filter_desc = self._describe_filters(filters)
        qualifier = f" for {filter_desc} transactions" if filter_desc else ""

        col_label = column.replace("_", " ")

        if column == "amount":
            formatted_value = f"${value:,.2f}"
        elif column == "sender_acct_age":
            formatted_value = f"{value:,.1f} days"
        elif column == "risk_score":
            formatted_value = f"{value:,.2f}"
        else:
            formatted_value = f"{value:,.4f}"

        answer = f"The **{label}** {col_label}{qualifier} is **{formatted_value}**."

        return {"answer": answer, "table_data": None, "answer_type": "aggregate"}


    def _construct_group_by_answer(self, spec: Dict, result: Dict) -> Dict:
        """Construct answer for GROUP_BY operations."""
        df = result["data"]
        meta = result["metadata"]
        group_col = meta.get("group_column", "group")
        aggregation = meta.get("aggregation", "COUNT")

        filters = spec.get("filters", [])
        filter_desc = self._describe_filters(filters)

        group_label = group_col.replace("_", " ").title()
        qualifier = f" for {filter_desc} transactions" if filter_desc else ""

        answer = f"Here is the breakdown by **{group_label}**{qualifier}:\n\n"

        # Top 5 summary in text
        for _, row in df.head(5).iterrows():
            cols = list(df.columns)
            key_col = cols[0]
            val_col = cols[1]
            key = row[key_col]
            val = row[val_col]

            if isinstance(val, float):
                val_str = f"${val:,.2f}" if "amount" in val_col else f"{val:,.2f}"
            else:
                val_str = f"{val:,}"
            answer += f"- **{key}**: {val_str}\n"

        if len(df) > 5:
            answer += f"\n_...and {len(df) - 5} more groups._"

        return {
            "answer": answer,
            "table_data": df,
            "answer_type": "group_by",
        }


    def _construct_fraud_answer(self, spec: Dict, result: Dict) -> Dict:
        """Construct answer for FRAUD_DETECT operations."""
        df = result["data"]
        meta = result["metadata"]
        total_checked = meta.get("total_checked", len(df))
        flagged_count = len(df)

        if flagged_count == 0:
            answer = f"✅ No suspicious transactions were detected among the {total_checked:,} transactions analyzed."
            return {"answer": answer, "table_data": None, "answer_type": "fraud_clean"}

        pct = (flagged_count / total_checked * 100) if total_checked > 0 else 0

        answer = (
            f"⚠️ **{flagged_count:,}** potentially suspicious transactions detected "
            f"out of **{total_checked:,}** checked ({pct:.1f}%).\n\n"
        )

        # Summarize top risk flags
        if "risk_flags" in df.columns:
            all_flags = []
            for flags_str in df["risk_flags"].head(20):
                all_flags.extend([f.strip() for f in str(flags_str).split("|") if f.strip()])

            from collections import Counter
            flag_counts = Counter(all_flags).most_common(5)
            if flag_counts:
                answer += "**Most common risk signals:**\n"
                for flag, cnt in flag_counts:
                    answer += f"- {flag}: {cnt} transactions\n"

        answer += f"\n_Showing top {min(flagged_count, 10)} highest-risk transactions below._"

        # Top 10 by risk score
        display_df = df.head(10)[
            [c for c in ["transaction_id", "sender", "receiver", "amount", "txn_method",
                         "sender_country", "receiver_country", "sender_kyc", "risk_score", "risk_flags"]
             if c in df.columns]
        ]

        return {
            "answer": answer,
            "table_data": display_df,
            "answer_type": "fraud_alert",
        }


    def _construct_from_result(self, spec: Dict, result: Dict) -> Dict:
        """
        Construct answer for SELECT/SORT/FILTER operations.
        IMPROVED: Better handling of limited results.
        """
        df = result["data"]

        if df is None or len(df) == 0:
            filters = spec.get("filters", [])
            filter_desc = self._describe_filters(filters)
            qualifier = f" matching {filter_desc}" if filter_desc else ""
            return {
                "answer": f"No transactions found{qualifier}. Try adjusting your filters.",
                "table_data": None,
                "answer_type": "empty",
            }

        filters = spec.get("filters", [])
        filter_desc = self._describe_filters(filters)
        count = len(df)
        qualifier = f" matching {filter_desc}" if filter_desc else ""

        # Describe sort
        sort_col = spec.get("target_column", "")
        sort_dir = spec.get("sort_direction", "DESC")
        sort_desc = ""
        if sort_col and sort_col != "transaction_id":
            direction_word = "highest" if sort_dir == "DESC" else "lowest"
            sort_desc = f", sorted by {direction_word} {sort_col.replace('_', ' ')}"

        # IMPROVED: Check if results were limited
        was_limited = result.get("metadata", {}).get("limited", False)
        limit_note = " (showing sample)" if was_limited else ""

        answer = f"Found **{count:,}** transaction(s){qualifier}{sort_desc}{limit_note}."

        # Quick stats if amount is present
        if "amount" in df.columns:
            avg_amt = pd.to_numeric(df["amount"], errors="coerce").mean()
            if not pd.isna(avg_amt):
                answer += f" Average amount: **${avg_amt:,.2f}**."

        return {
            "answer": answer,
            "table_data": df,
            "answer_type": "table",
        }


    def _describe_filters(self, filters: List[Dict]) -> str:
        """Convert filter list to a readable description."""
        if not filters:
            return ""
        parts = []
        for f in filters:
            col = f.get("column", "").replace("_", " ")
            val = f.get("value", "")
            parts.append(f"{col}={val}")
        return ", ".join(parts)


    def construct_help_answer(self) -> Dict:
        """Construct a help response."""
        answer = (
            "Here's what I can help you with:\n\n"
            "📊 **Data Queries**\n"
            "- Show/list transactions with filters (e.g., 'show crypto transactions from NG')\n"
            "- Count transactions (e.g., 'how many wire transfers are there?')\n"
            "- Find top transactions by amount, velocity, etc.\n\n"
            "📈 **Statistics**\n"
            "- Average, sum, max, min of numeric fields\n"
            "- Group by country, method, KYC status\n\n"
            "🚨 **Fraud Detection**\n"
            "- 'Show suspicious transactions'\n"
            "- 'Detect fraud'\n"
            "- 'Flag high-risk transactions'\n\n"
            "🔢 **Calculations**\n"
            "- 'What is the average transaction amount?'\n"
            "- 'Total amount sent from SG'\n\n"
            "**Example queries:**\n"
            "- _Show transactions where KYC is None_\n"
            "- _How many transactions are there?_\n"
            "- _Average amount by payment method_\n"
            "- _Find suspicious transactions_\n"
        )
        return {"answer": answer, "table_data": None, "answer_type": "help"}



FOLLOWUP_TEMPLATES = {
    "SELECT": [
        "Would you like to filter these by a specific country?",
        "Want to see only transactions with unverified KYC?",
        "Should I sort these by amount instead?",
    ],
    "FRAUD_DETECT": [
        "Want me to break down the fraud risk by payment method?",
        "Should I show only transactions with no KYC?",
        "Want to see the full details for the top-risk transaction?",
    ],
    "GROUP_BY": [
        "Want to see the same breakdown for a different column?",
        "Should I filter this to a specific country?",
        "Want to sort by a different metric?",
    ],
    "AGGREGATE": [
        "Want to compare this across different payment methods?",
        "Should I show the individual transactions behind this number?",
        "Want to see the distribution instead?",
    ],
    "COUNT": [
        "Want to see the actual transactions in this count?",
        "Should I break this count down by country?",
        "Want to add more filters to narrow down?",
    ],
}


class FollowUpSuggester:
    """
    Generates contextually relevant follow-up questions based on the current result.
    """

    def __init__(self):
        logger.info("FollowUpSuggester initialized.")


    def suggest(
        self,
        query_spec: Dict,
        execution_result: Dict,
        max_suggestions: int = 3,
    ) -> List[str]:
        """
        Generate follow-up question suggestions.

        Args:
            query_spec: Current query specification
            execution_result: Current execution result
            max_suggestions: Max number of suggestions to return

        Returns:
            List of follow-up question strings
        """
        operation = execution_result.get("operation", "SELECT")
        suggestions = []

        # Base templates
        templates = FOLLOWUP_TEMPLATES.get(operation, FOLLOWUP_TEMPLATES["SELECT"])
        suggestions.extend(templates[:max_suggestions])

        # Dynamic suggestions based on result
        data = execution_result.get("data")
        if isinstance(data, pd.DataFrame) and len(data) > 0:
            # Suggest drilling into specific column values
            if "sender_country" in data.columns:
                countries = data["sender_country"].value_counts().index[:2].tolist()
                if countries:
                    suggestions.append(f"Want to filter to just {countries[0]} transactions?")

            if "txn_method" in data.columns:
                methods = data["txn_method"].value_counts().index[:1].tolist()
                if methods:
                    suggestions.append(f"Should I show only {methods[0]} transactions?")

        # Deduplicate and trim
        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        return unique[:max_suggestions]
    