"""
Pydantic schemas for the chatbot API endpoints.
File: schema/chatbout.py  (keep original filename)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatQueryRequest(BaseModel):
    """Request body for POST /chatbot/query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question about the transaction data.",
        examples=["How many transactions are there?"],
    )
    batch_id: Optional[str] = Field(
        None,
        description=(
            "FileBatch UUID returned by GET /chatbot/batches. "
            "Scopes the chatbot to a specific uploaded file. "
            "Defaults to the most-recently uploaded file when omitted."
        ),
    )
    session_id: str = Field(
        "default",
        description="Session identifier for multi-turn conversation memory.",
    )
    include_followup: bool = Field(
        True,
        description="Whether to include follow-up question suggestions in the response.",
    )
    include_trace: bool = Field(
        False,
        description="Whether to include the internal reasoning trace in the response.",
    )


class ChatQueryResponse(BaseModel):
    """Response body for POST /chatbot/query."""

    answer: str = Field(..., description="Natural language answer.")
    table_data: Optional[List[Dict[str, Any]]] = Field(
        None, description="Tabular result data (up to 100 rows)."
    )
    answer_type: str = Field(..., description="Internal classification of the answer type.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0–1].")
    followup_suggestions: Optional[List[str]] = Field(
        None, description="Suggested follow-up queries."
    )
    is_fallback: bool = Field(
        False, description="True when a low-confidence fallback response was returned."
    )

    class Config:
        extra = "allow"   # forward-compatible — extra fields from chatbot are ignored


class SessionSummaryResponse(BaseModel):
    """Response body for GET /chatbot/session/{session_id}."""

    session_id: str
    interaction_count: int = 0
    interactions: List[Dict[str, Any]] = []


class DatasetInfoResponse(BaseModel):
    """Response body for GET /chatbot/dataset/info."""

    rows: int = 0
    columns: List[str] = []
    kyc_distribution: Dict[str, Any] = {}
    method_distribution: Dict[str, Any] = {}
    country_distribution: Dict[str, Any] = {}
    amount_stats: Dict[str, Any] = {}
    fraud_summary: Optional[Dict[str, Any]] = None
    date_range: Optional[Dict[str, str]] = None

    class Config:
        extra = "allow"


class BuildVectorDBRequest(BaseModel):
    """Request body for POST /chatbot/vector-db/build."""

    batch_id: Optional[str] = Field(
        None,
        description="FileBatch UUID to build the index for. Defaults to latest.",
    )
    force_rebuild: bool = Field(
        False,
        description="Force rebuild even if an index already exists.",
    )


class BuildVectorDBResponse(BaseModel):
    """Response body for POST /chatbot/vector-db/build."""

    status: str
    documents_added: Optional[int] = None
    total_documents: Optional[int] = None
    message: Optional[str] = None

    class Config:
        extra = "allow"
        