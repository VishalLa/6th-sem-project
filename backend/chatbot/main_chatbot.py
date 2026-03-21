import os
import logging
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple

from .enhanced_query_analyzer import EnhancedQueryAnalyzer
from .data_executor import DataExecutor
from .conversation_memory_manager import ConversationMemoryManager
from .answer_construction import (
    RuleBasedAnswerConstructor,
    FollowUpSuggester,
    ReasoningTracer,
)
from .fallback import LowConfidenceFallback

logger = logging.getLogger(__name__)


_VECTOR_AVAILABLE = False
try:
    from .vector_retriever import VectorRetriever
    _VECTOR_AVAILABLE = True
except ImportError:
    pass



class FraudDetectionChatbot:
    """
    Main chatbot class for fraud detection and transaction analysis.

    Capabilities:
    - Natural language querying of transaction data
    - Fraud detection and risk flagging
    - Statistical analysis and calculations
    - Multi-turn conversation with memory
    - Vector-based semantic search (optional)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        vector_store=None,
        embeddings=None,
        default_tenant_id: str = "default",
    ):
        """
        Initialize the chatbot.

        Args:
            df: Loaded transactions DataFrame
            vector_store: Optional FAISSVectorStore instance
            embeddings: Optional CPUEmbeddings instance
            default_tenant_id: Default tenant ID for vector operations
        """
        self.df = df
        self.default_tenant_id = default_tenant_id

        # Core components
        self.query_analyzer = EnhancedQueryAnalyzer()
        self.data_executor = DataExecutor(df)
        self.memory = ConversationMemoryManager()
        self.answer_constructor = RuleBasedAnswerConstructor()
        self.followup_suggester = FollowUpSuggester()
        self.fallback_handler = LowConfidenceFallback()
        self.tracer = ReasoningTracer()

        # Vector components (optional)
        self.vector_retriever: Optional["VectorRetriever"] = None
        if vector_store and embeddings and _VECTOR_AVAILABLE:
            self.vector_retriever = VectorRetriever(vector_store, embeddings)
            logger.info("Vector retriever enabled.")
        else:
            logger.info("Running without vector store (keyword+rule mode only).")

        logger.info(f"FraudDetectionChatbot initialized. Dataset: {len(df)} rows × {len(df.columns)} cols.")



    def answer_query(
        self,
        user_query: str,
        session_id: str = "default",
        include_followup: bool = True,
        include_trace: bool = False,
    ) -> Dict:
        """
        Primary entry point. Answer a user's natural language query.

        Args:
            user_query: Raw user input text
            session_id: Session identifier for memory
            include_followup: Whether to include follow-up suggestions
            include_trace: Whether to include reasoning trace in response

        Returns:
            Response dict with: answer, table_data, followup_suggestions,
                               answer_type, confidence, trace (optional)
        """
        self.tracer.reset()
        self.tracer.add_step("input", f"Received query: '{user_query}'")

        # Normalize
        user_query = user_query.strip()
        if not user_query:
            return self._empty_response()

        # ── Special commands ──
        if user_query.lower() in ("help", "?", "what can you do"):
            response = self.answer_constructor.construct_help_answer()
            self._finalize_response(response, session_id, user_query, None, None)
            return response

        if user_query.lower() in ("reset", "clear", "start over"):
            self.reset_session(session_id)
            response = {
                "answer": "Session cleared. How can I help you?",
                "table_data": None,
                "answer_type": "system",
            }
            return response

        # ── Analyze query ──
        self.tracer.add_step("analysis", "Running enhanced query analysis")
        query_spec = self.query_analyzer.analyze(user_query)

        # ── Follow-up context enrichment ──
        query_spec = self.memory.resolve_followup(session_id, query_spec)

        self.tracer.add_step(
            "spec",
            f"op={query_spec['operation_type']}, intent={query_spec['primary_intent']}, "
            f"confidence={query_spec['confidence']:.2f}",
        )

        # ── Multi-question handling ──
        if query_spec.get("is_multi_question") and len(query_spec.get("sub_questions", [])) > 1:
            return self.handle_multi_query(
                query_spec["sub_questions"],
                session_id=session_id,
                include_followup=include_followup,
            )

        # ── Route to handler ──
        operation = query_spec.get("operation_type", "SELECT")
        response = self._route(query_spec, session_id)

        # ── Follow-up suggestions ──
        if include_followup and not response.get("is_fallback"):
            execution_result = response.get("_execution_result", {})
            suggestions = self.followup_suggester.suggest(query_spec, execution_result)
            response["followup_suggestions"] = suggestions
        else:
            response["followup_suggestions"] = []

        # ── Reasoning trace ──
        if include_trace:
            response["trace"] = self.tracer.get_trace()

        # ── Save to memory ──
        self._finalize_response(
            response, session_id, user_query,
            query_spec,
            response.get("_execution_result"),
        )

        # Clean internal key
        response.pop("_execution_result", None)

        return response
    

    def _route(self, query_spec: Dict, session_id: str) -> Dict:
        """Route query_spec to the appropriate handler."""
        operation = query_spec.get("operation_type", "SELECT")

        if query_spec.get("is_low_confidence") and operation not in ("HELP", "NAVIGATE"):
            return self.fallback_handler.build_fallback_response(query_spec)

        if operation == "HELP":
            return self.answer_constructor.construct_help_answer()

        elif operation == "NAVIGATE":
            return self.handle_navigation(query_spec)

        elif operation == "CALCULATE":
            return self.handle_calculation(query_spec)

        elif operation == "COMPARE":
            return self.handle_comparison(query_spec)

        else:
            return self.handle_data_query(query_spec)
        

    def handle_data_query(self, query_spec: Dict) -> Dict:
        """
        Handle standard data queries (SELECT, FILTER, COUNT, GROUP_BY,
        AGGREGATE, FRAUD_DETECT).
        """
        self.tracer.add_step("execute", f"Executing {query_spec['operation_type']}")

        # Vector augmentation (if available and relevant)
        vector_context = []
        if self.vector_retriever and query_spec.get("primary_domain") == "fraud_detection":
            vector_context = self.vector_retriever.retrieve_fraud_patterns(
                tenant_id=self.default_tenant_id,
                query=query_spec.get("processed_text", query_spec.get("raw_query", "")),
                k=3,
            )
            self.tracer.add_step("vector", f"Retrieved {len(vector_context)} vector results")

        # Execute
        execution_result = self.data_executor.execute(query_spec)

        # Check for empty result
        data = execution_result.get("data")
        if isinstance(data, pd.DataFrame) and len(data) == 0:
            response = self.fallback_handler.handle_empty_result(query_spec)
            response["_execution_result"] = execution_result
            return response

        # Construct answer
        response = self.answer_constructor.construct(query_spec, execution_result, self.tracer)

        # Attach vector context if available
        if vector_context:
            response["vector_context"] = [r["document"][:200] for r in vector_context[:2]]

        response["_execution_result"] = execution_result
        response["confidence"] = query_spec.get("confidence", 0)

        return response
    

    def handle_calculation(self, query_spec: Dict) -> Dict:
        """Handle mathematical/calculation queries."""
        self.tracer.add_step("calculate", "Handling mathematical query")

        math_op = query_spec.get("math_operation")
        if math_op == "growth_rate":
            return self._handle_growth_rate(query_spec)

        # Default: run as aggregation
        query_spec["operation_type"] = "AGGREGATE"
        if not query_spec.get("aggregation"):
            query_spec["aggregation"] = "AVG"

        return self.handle_data_query(query_spec)
    

    def handle_comparison(self, query_spec: Dict) -> Dict:
        """Handle comparison queries (A vs B)."""
        self.tracer.add_step("compare", "Handling comparison query")

        # Run as group_by if we have a group column
        if query_spec.get("group_column"):
            query_spec["operation_type"] = "GROUP_BY"
            return self.handle_data_query(query_spec)

        # Otherwise run as select
        query_spec["operation_type"] = "SELECT"
        return self.handle_data_query(query_spec)
    

    def handle_navigation(self, query_spec: Dict) -> Dict:
        """Handle navigation requests."""
        text = query_spec.get("raw_query", "").lower()

        nav_map = {
            "dashboard": "main dashboard",
            "chart": "charts view",
            "fraud": "fraud detection panel",
            "report": "reports section",
        }

        destination = next(
            (label for keyword, label in nav_map.items() if keyword in text),
            "the requested page",
        )

        return {
            "answer": f"Navigating to **{destination}**.",
            "table_data": None,
            "answer_type": "navigation",
            "navigate_to": destination,
        }
    

    def handle_multi_query(
        self,
        sub_questions: List[str],
        session_id: str = "default",
        include_followup: bool = False,
    ) -> Dict:
        """Handle multiple questions in a single input."""
        self.tracer.add_step("multi_query", f"Processing {len(sub_questions)} sub-questions")

        answers = []
        for i, question in enumerate(sub_questions, 1):
            sub_response = self.answer_query(
                question,
                session_id=session_id,
                include_followup=False,
            )
            answers.append(f"**Question {i}:** {question}\n{sub_response['answer']}")

        combined_answer = "\n\n---\n\n".join(answers)
        return {
            "answer": combined_answer,
            "table_data": None,
            "answer_type": "multi_answer",
            "sub_question_count": len(sub_questions),
            "followup_suggestions": [],
        }
    

    def _handle_growth_rate(self, query_spec: Dict) -> Dict:
        """Handle growth rate calculation."""
        from .query_analysis import MathematicalQueryHandler
        math_handler = MathematicalQueryHandler()

        # Get filtered data
        execution_result = self.data_executor.execute_ranking(query_spec)
        df = execution_result.get("data")

        if df is None or len(df) < 2:
            return {
                "answer": "Not enough data to calculate a growth rate. Need at least 2 data points.",
                "table_data": None,
                "answer_type": "calculation",
            }

        col = query_spec.get("target_column", "amount")
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna().tolist()
            if len(values) >= 2:
                rate = math_handler.calculate_growth_rate(values[0], values[-1])
                direction = "increase" if rate >= 0 else "decrease"
                answer = (
                    f"The **growth rate** of {col.replace('_', ' ')} "
                    f"from first ({values[0]:,.2f}) to last ({values[-1]:,.2f}) "
                    f"is **{abs(rate):.2f}%** {direction}."
                )
                return {"answer": answer, "table_data": None, "answer_type": "calculation"}

        return {
            "answer": "Could not calculate growth rate for the specified data.",
            "table_data": None,
            "answer_type": "calculation",
        }
    

    def build_vector_db(
        self,
        tenant_id: Optional[str] = None,
        force_rebuild: bool = False,
    ) -> Dict:
        """
        Build (or rebuild) the vector database from the loaded DataFrame.

        Args:
            tenant_id: Tenant ID (defaults to default_tenant_id)
            force_rebuild: If True, delete existing index and rebuild

        Returns:
            Indexing statistics
        """
        if not self.vector_retriever:
            return {"status": "skipped", "reason": "no_vector_store"}

        tenant_id = tenant_id or self.default_tenant_id

        if not force_rebuild and self.vector_retriever.is_indexed(tenant_id):
            stats = self.vector_retriever.get_index_stats(tenant_id)
            logger.info(f"Index already exists for tenant={tenant_id}. Skipping rebuild.")
            return {"status": "already_indexed", "stats": stats}

        logger.info(f"Building vector DB for tenant={tenant_id}...")
        stats = self.vector_retriever.index_dataframe(
            tenant_id=tenant_id,
            df=self.df,
            document_type="transactions",
        )
        return stats
    

    def reset_session(self, session_id: str) -> None:
        """Reset a session's conversation history."""
        self.memory.reset(session_id)
        logger.info(f"Session {session_id} reset.")


    def get_session_summary(self, session_id: str) -> Dict:
        """Get a summary of a session."""
        return self.memory.get_session_summary(session_id)
    

    def _finalize_response(
        self,
        response: Dict,
        session_id: str,
        user_query: str,
        query_spec: Optional[Dict],
        execution_result: Optional[Dict],
    ) -> None:
        """Save interaction to memory."""
        result_meta = {}
        if execution_result:
            meta = execution_result.get("metadata", {})
            result_meta = {"count": meta.get("count"), "operation": execution_result.get("operation")}

        self.memory.add_interaction(
            session_id=session_id,
            user_query=user_query,
            bot_response=response.get("answer", ""),
            query_spec=query_spec,
            result_meta=result_meta,
        )


    def _empty_response(self) -> Dict:
        """Response for empty input."""
        return {
            "answer": "Please enter a question about the transaction data. Type **help** for examples.",
            "table_data": None,
            "answer_type": "empty_input",
            "followup_suggestions": [],
        }
    

    def get_dataset_info(self) -> Dict:
        """Return info about the loaded dataset."""
        return {
            "rows": len(self.df),
            "columns": list(self.df.columns),
            "kyc_distribution": self.df["sender_kyc"].value_counts().to_dict() if "sender_kyc" in self.df.columns else {},
            "method_distribution": self.df["txn_method"].value_counts().to_dict() if "txn_method" in self.df.columns else {},
            "country_distribution": self.df["sender_country"].value_counts().to_dict() if "sender_country" in self.df.columns else {},
            "amount_stats": {
                "mean": round(self.df["amount"].mean(), 2) if "amount" in self.df.columns else None,
                "max": round(self.df["amount"].max(), 2) if "amount" in self.df.columns else None,
                "min": round(self.df["amount"].min(), 2) if "amount" in self.df.columns else None,
            },
        }

