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
        fraud_summary_df: Optional[pd.DataFrame] = None, 
        vector_store=None, 
        embeddings=None, 
        default_tenant_id: str = "default"
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
        self.fraud_summary_df = fraud_summary_df
        self.default_tenant_id = default_tenant_id
        
        self.data_executor = DataExecutor(df)
        self.fraud_executor = FraudSummaryExecutor(fraud_summary_df)
        self.query_analyzer = EnhancedQueryAnalyzer()
        self.memory_manager = ConversationMemoryManager()
        self.answer_constructor = RuleBasedAnswerConstructor()
        self.followup_suggester = FollowUpSuggester()
        self.fallback_handler = LowConfidenceFallback()
        self.tracer = ReasoningTracer()
        
        self.vector_retriever = None
        if vector_store and embeddings:
            self.vector_retriever = VectorRetriever(vector_store, embeddings)
        
        logger.info(f"Chatbot: {len(df)} txns, {len(fraud_summary_df) if fraud_summary_df is not None else 0} fraud rings")


    def _is_fraud_pattern_query(self, query_spec: Dict) -> bool:
        raw = query_spec.get("raw_query", "").lower()
        keywords = [
            "fraud pattern", 
            "fraud ring", 
            "detected fraud", 
            "fraud summary", 
            "cycle detection", 
            "layered shell", 
            "kyc cluster", 
            "smurfing", 
            "what fraud", 
            "which fraud", 
            "ring "
        ]
        return any(kw in raw for kw in keywords)
    

    def _handle_fraud_pattern_query(self, query_spec: Dict) -> Dict:
        if not self.fraud_executor.has_data():
            return {
                "answer": "No fraud patterns detected. Run detection first via /upload/full-pipeline.", 
                "table_data": None, 
                "answer_type": "no_fraud_data", 
                "confidence": 0.9
            }
        
        raw = query_spec.get("raw_query", "").lower()
        
        # Summary
        if any(kw in raw for kw in ["what fraud", "fraud patterns", "fraud summary"]):
            s = self.fraud_executor.get_pattern_summary()

            answer = (f"**Fraud Summary:** {s['total_rings']} rings, {len(s['pattern_types'])} pattern types\n"
                     f"High: {s['high_risk_count']} | Medium: {s['medium_risk_count']} | Low: {s['low_risk_count']}\n"
                     f"Avg Risk: {s['avg_risk_score']:.2f} | Max: {s['max_risk_score']:.2f}")
            
            return {
                "answer": answer, 
                "table_data": self.fraud_executor.get_high_risk_rings(10), 
                "answer_type": "fraud_summary", 
                "confidence": 0.95    
            }
        
        # Specific pattern
        patterns = {
            "cycle": "cycle_length_3", 
            "layered": "layered_shell", 
            "shell": "layered_shell",
            "kyc": "unverified_kyc_cluster", 
            "smurfing": "smurfing"
        }
        
        for kw, pat in patterns.items():
            if kw in raw:
                rings = self.fraud_executor.get_rings_by_pattern(pat)

                if rings.empty:
                    return {
                        "answer": f"No {pat.replace('_', ' ').title()} patterns.", 
                        "table_data": None, 
                        "answer_type": "no_pattern", 
                        "confidence": 0.85
                    }
                
                return {
                    "answer": f"{pat.replace('_', ' ').title()}: {len(rings)} rings, avg risk {rings['risk_score'].mean():.2f}", 
                    "table_data": rings.head(10), 
                    "answer_type": "pattern_specific", 
                    "confidence": 0.9
                }
        
        # High risk
        if any(kw in raw for kw in ["high risk", "highest risk", "top risk"]):
            high = self.fraud_executor.get_high_risk_rings(10)
            
            return {
                "answer": f"Top {len(high)} highest risk rings (risk {high['risk_score'].min():.2f}-{high['risk_score'].max():.2f})", 
                "table_data": high, 
                "answer_type": "high_risk", 
                "confidence": 0.95
            }
        
        # Account search
        import re
        acc = re.search(r'acc[_\s]?\d{5}', raw, re.IGNORECASE)
        if acc:
            aid = acc.group(0).upper().replace(" ", "_")
            rings = self.fraud_executor.search_account_in_rings(aid)

            if rings.empty:
                return {
                    "answer": f"Account {aid} not in any fraud rings.", 
                    "table_data": None, 
                    "answer_type": "account_clean", 
                    "confidence": 0.85
                }
            
            return {
                "answer": f"⚠️ Account {aid} in {len(rings)} fraud ring(s).", 
                "table_data": rings, 
                "answer_type": "account_in_rings", 
                "confidence": 0.95
            }
        
        return {
            "answer": "Ask about: pattern types, high-risk rings, or specific accounts.", 
            "table_data": None, 
            "answer_type": "fraud_help", 
            "confidence": 0.7
        }
    


    def answer_query(
        self, 
        user_query: str, 
        session_id: str = "default", 
        include_followup: bool = True, 
        include_trace: bool = False
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
        logger.info(f"[{session_id}] Query: {user_query}")
        query_spec = self.query_analyzer.analyze(user_query)
        exec_result = None  # Always initialise so followup block never hits NameError

        # Route: Fraud pattern vs Transaction
        if self._is_fraud_pattern_query(query_spec):
            response = self._handle_fraud_pattern_query(query_spec)
        else:
            if query_spec.get("is_low_confidence", False):
                response = self.fallback_handler.build_fallback_response(query_spec)

            elif query_spec["operation_type"] == "HELP":
                response = self.answer_constructor.construct_help_answer()

            else:
                exec_result = self.data_executor.execute(query_spec)
                response = self.answer_constructor.construct(query_spec, exec_result)

        if include_followup and response.get("answer_type") not in ["error", "clarification"]:
            # Use actual exec_result if available, otherwise build a lightweight proxy from the response
            followup_exec = exec_result if exec_result is not None else {
                "operation": response.get("answer_type", "SELECT"),
                "data": response.get("table_data"),
            }
            response["followup_suggestions"] = self.followup_suggester.suggest(query_spec, followup_exec)


        self.memory_manager.add_interaction(
            session_id=session_id, 
            user_query=user_query, 
            bot_response=response["answer"], query_spec=query_spec, 
            result_meta={"confidence": response.get("confidence", 0)}
        )

        return response


    def build_vector_db(
        self, 
        tenant_id: Optional[str] = None, 
        force_rebuild: bool = False
    ) -> Dict:

        if not self.vector_retriever:
            return {
                "status": "error", 
                "message": "Vector retrieval not available"
            }
        
        tid = tenant_id or self.default_tenant_id
        if not force_rebuild and self.vector_retriever.is_indexed(tid):
            stats = self.vector_retriever.get_index_stats(tid)

            return {
                "status": "already_indexed", 
                "documents_added": None, 
                "total_documents": stats["total_documents"]
            }
        
        stats = self.vector_retriever.index_dataframe(tenant_id=tid, df=self.df, document_type="transactions")
        
        return {
            "status": "success", 
            "documents_added": stats.get("documents_added"), "total_documents": stats.get("total_documents")
        }
    

    def reset_session(self, session_id: str) -> None:
        self.memory_manager.reset(session_id)
    

    def get_session_summary(self, session_id: str) -> Dict:
        return self.memory_manager.get_session_summary(session_id)
    

    def get_dataset_info(self) -> Dict:
        info = {
            "transaction_count": len(self.df), 
            "columns": list(self.df.columns), 
            "date_range": None
        }

        if "timestamp" in self.df.columns:
            df_copy = self.df.copy()
            df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"], errors="coerce")

            min_date, max_date = df_copy["timestamp"].min(), df_copy["timestamp"].max()
            
            if pd.notna(min_date) and pd.notna(max_date):
                info["date_range"] = {
                    "start": min_date.isoformat(), 
                    "end": max_date.isoformat()
                }

        if self.fraud_executor.has_data():
            info["fraud_summary"] = self.fraud_executor.get_pattern_summary()

        return info
    

class FraudSummaryExecutor:
    """
    Executes queries against fraud summary DataFrame.
    Handles fraud ring pattern analysis.
    """
    
    def __init__(self, fraud_df: pd.DataFrame):
        """
        Args:
            fraud_df: DataFrame with fraud ring summaries
        """
        self.fraud_df = fraud_df.copy() if fraud_df is not None else pd.DataFrame()

        self._preprocess_dataframe()

        logger.info(f"FraudSummaryExecutor initialized with {len(self.fraud_df)} fraud rings.")


    def _preprocess_dataframe(self):
        """Preprocess fraud summary DataFrame."""
        if self.fraud_df.empty:
            return
        
        # Normalize column names (database uses snake_case, CSV uses Title Case)
        column_mapping = {
            'Ring ID': 'ring_id',
            'Pattern Type': 'pattern_type',
            'Member Count': 'member_count',
            'Risk Score': 'risk_score',
            'Member Account IDs': 'member_accounts',
            'Avg Member Score': 'avg_member_score',
            'Max Member Score': 'max_member_score',
            'Structural Complexity': 'structural_complexity',
            'Internal Edge Count': 'internal_edge_count',
            'Ring Density': 'ring_density',
            'Risk Category': 'risk_category'
        }
        
        # Rename if columns are in CSV format
        if 'Ring ID' in self.fraud_df.columns:
            self.fraud_df.rename(columns=column_mapping, inplace=True)
        
        # Ensure numeric columns
        numeric_cols = [
            'member_count', 
            'risk_score', 
            'avg_member_score', 
            'max_member_score', 
            'structural_complexity', 
            'internal_edge_count', 
            'ring_density'
        ]
        
        for col in numeric_cols:
            if col in self.fraud_df.columns:
                self.fraud_df[col] = pd.to_numeric(self.fraud_df[col], errors='coerce')


    def has_data(self) -> bool:
        """Check if fraud summary data exists."""
        return not self.fraud_df.empty
    
    
    def get_pattern_summary(self) -> Dict:
        """
        Get overall summary of detected patterns.
        
        Returns:
            Summary statistics
        """
        if self.fraud_df.empty:
            return {
                "total_rings": 0,
                "pattern_types": [],
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 0
            }
        
        risk_counts = self.fraud_df['risk_category'].value_counts().to_dict()
        
        return {
            "total_rings": len(self.fraud_df),
            "pattern_types": self.fraud_df['pattern_type'].unique().tolist(),
            "high_risk_count": risk_counts.get('High', 0),
            "medium_risk_count": risk_counts.get('Medium', 0),
            "low_risk_count": risk_counts.get('Low', 0),
            "avg_risk_score": float(self.fraud_df['risk_score'].mean()),
            "max_risk_score": float(self.fraud_df['risk_score'].max())
        }
    

    def get_rings_by_pattern(self, pattern_type: str) -> pd.DataFrame:
        """
        Get all rings of a specific pattern type.
        
        Args:
            pattern_type: Pattern name (e.g., 'cycle_length_3', 'layered_shell')
        
        Returns:
            Filtered DataFrame
        """
        if self.fraud_df.empty:
            return pd.DataFrame()
        
        # Normalize pattern name
        pattern_lower = pattern_type.lower().replace(" ", "_")
        
        return self.fraud_df[
            self.fraud_df['pattern_type'].str.lower().str.replace(" ", "_") == pattern_lower
        ].copy()
    

    def get_high_risk_rings(self, top_n: int = 10) -> pd.DataFrame:
        """
        Get highest risk fraud rings.
        
        Args:
            top_n: Number of rings to return
        
        Returns:
            Top risk rings DataFrame
        """
        if self.fraud_df.empty:
            return pd.DataFrame()
        
        return self.fraud_df.nlargest(top_n, 'risk_score')
    

    def get_rings_by_risk_category(self, category: str) -> pd.DataFrame:
        """
        Get rings by risk category.
        
        Args:
            category: 'High', 'Medium', or 'Low'
        
        Returns:
            Filtered DataFrame
        """
        if self.fraud_df.empty:
            return pd.DataFrame()
        
        return self.fraud_df[
            self.fraud_df['risk_category'].str.lower() == category.lower()
        ].copy()
    
    
    def search_account_in_rings(self, account_id: str) -> pd.DataFrame:
        """
        Find all rings containing a specific account.
        
        Args:
            account_id: Account ID to search for
        
        Returns:
            Rings containing the account
        """
        if self.fraud_df.empty:
            return pd.DataFrame()
        
        # Search in member_accounts column (comma-separated list)
        account_upper = account_id.upper()
        
        mask = self.fraud_df['member_accounts'].str.contains(
            account_upper, 
            case=False, 
            na=False
        )
        
        return self.fraud_df[mask].copy()
    