import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

MAX_HISTORY = 10


class ConversationMemoryManager:
    """
    Manages per-session conversation history and context.
    Enables follow-up question resolution using prior context.
    """

    def __init__(self, max_history: int = MAX_HISTORY):
        self.max_history = max_history
        self._sessions: Dict[str, Dict] = {}
        logger.info(f"ConversationMemoryManager initialized (max_history={max_history}).")


    def _get_session(self, session_id: str) -> Dict:
        """Get or create a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat(),
                "interactions": deque(maxlen=self.max_history),
                "context": {
                    "last_query_spec": None,
                    "last_result_count": None,
                    "last_filters": [],
                    "last_columns": [],
                    "last_operation": None,
                    "topic": None,
                },
                "data": {},
            }
            logger.info(f"New session created: {session_id}")
        return self._sessions[session_id]
    

    def add_interaction(
        self,
        session_id: str,
        user_query: str,
        bot_response: str,
        query_spec: Optional[Dict] = None,
        result_meta: Optional[Dict] = None,
    ) -> None:
        """
        Add a completed interaction to session history.

        Args:
            session_id: Session identifier
            user_query: User's raw query
            bot_response: Bot's text response
            query_spec: Analyzed query spec (optional)
            result_meta: Result metadata like row count, columns (optional)
        """
        session = self._get_session(session_id)

        interaction = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_query": user_query,
            "bot_response": bot_response[:500],  # Truncate for storage
            "query_spec": query_spec,
            "result_meta": result_meta or {},
        }

        session["interactions"].append(interaction)
        session["last_updated"] = datetime.utcnow().isoformat()

        # Update context
        if query_spec:
            ctx = session["context"]
            ctx["last_query_spec"] = query_spec
            ctx["last_operation"] = query_spec.get("operation_type")
            ctx["last_filters"] = query_spec.get("filters", [])
            ctx["last_columns"] = query_spec.get("referenced_columns", [])
            ctx["topic"] = query_spec.get("primary_domain")

        if result_meta:
            session["context"]["last_result_count"] = result_meta.get("count")

        logger.debug(f"Interaction added to session {session_id}. Total: {len(session['interactions'])}")


    def get_context(self, session_id: str) -> Dict:
        """
        Get current conversation context for a session.

        Args:
            session_id: Session identifier

        Returns:
            Context dictionary with recent state
        """
        session = self._get_session(session_id)
        return session["context"].copy()
    

    def get_history(self, session_id: str, last_n: int = 3) -> List[Dict]:
        """
        Get last N interactions for a session.

        Args:
            session_id: Session identifier
            last_n: Number of recent interactions to return

        Returns:
            List of interaction dicts
        """
        session = self._get_session(session_id)
        history = list(session["interactions"])
        return history[-last_n:] if len(history) >= last_n else history
    

    def update_session_data(self, session_id: str, key: str, value: Any) -> None:
        """
        Store arbitrary session data (e.g., last dataframe, user preferences).

        Args:
            session_id: Session identifier
            key: Data key
            value: Data value
        """
        session = self._get_session(session_id)
        session["data"][key] = value
        session["last_updated"] = datetime.utcnow().isoformat()
        logger.debug(f"Session data updated: {session_id}[{key}]")


    def get_session_data(self, session_id: str, key: str, default: Any = None) -> Any:
        """
        Retrieve stored session data.

        Args:
            session_id: Session identifier
            key: Data key
            default: Default value if key not found

        Returns:
            Stored value or default
        """
        session = self._get_session(session_id)
        return session["data"].get(key, default)


    def reset(self, session_id: str) -> None:
        """
        Reset session history and context.

        Args:
            session_id: Session identifier
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
        logger.info(f"Session reset: {session_id}")


    def resolve_followup(self, session_id: str, current_spec: Dict) -> Dict:
        """
        Enrich a follow-up query spec with context from prior interactions.
        Handles cases like "show me more", "filter those by country", etc.

        Args:
            session_id: Session identifier
            current_spec: Current query analysis result

        Returns:
            Enriched query spec
        """
        context = self.get_context(session_id)
        if not context["last_query_spec"]:
            return current_spec

        spec = current_spec.copy()
        raw = spec.get("raw_query", "").lower()

        # "those", "them", "that", "these" → inherit previous filters
        if any(ref in raw for ref in ["those", "them", "that", "these results", "the results"]):
            prev_filters = context.get("last_filters", [])
            if prev_filters and not spec["filters"]:
                spec["filters"] = prev_filters
                logger.debug(f"Inherited {len(prev_filters)} filters from previous interaction.")

        # "show more" → inherit operation + filters from previous
        if "more" in raw or "again" in raw:
            last_spec = context["last_query_spec"]
            if last_spec:
                if not spec["filters"]:
                    spec["filters"] = last_spec.get("filters", [])
                if not spec["target_column"]:
                    spec["target_column"] = last_spec.get("target_column")

        return spec


    def get_session_summary(self, session_id: str) -> Dict:
        """
        Get a summary of a session's activity.
        """
        session = self._get_session(session_id)
        history = list(session["interactions"])

        return {
            "session_id": session_id,
            "created_at": session["created_at"],
            "last_updated": session["last_updated"],
            "total_interactions": len(history),
            "current_topic": session["context"].get("topic"),
            "last_operation": session["context"].get("last_operation"),
        }
    

    def get_all_sessions(self) -> List[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())

