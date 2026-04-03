from pydantic import BaseModel, Field

from typing import List, Dict, Optional, Any

class ChatQueryRequest(BaseModel):
    """Request model for chat query."""
    query: str = Field(..., min_length=1, description="Natural language query")
    session_id: str = Field(default="default", description="Session identifier")
    include_followup: bool = Field(default=True, description="Include follow-up suggestions")
    include_trace: bool = Field(default=False, description="Include reasoning trace")


class ChatQueryResponse(BaseModel):
    """Response model for chat query."""
    answer: str
    table_data: Optional[List[Dict]] = None
    answer_type: str
    followup_suggestions: List[str] = []
    confidence: Optional[float] = None
    trace: Optional[List[Dict]] = None
    sub_question_count: Optional[int] = None


class SessionSummaryResponse(BaseModel):
    """Response model for session summary."""
    session_id: str
    interaction_count: int
    interactions: List[Dict]


class DatasetInfoResponse(BaseModel):
    """Response model for dataset info."""
    transaction_count: int = Field(alias="rows")
    columns: List[str] = []
    kyc_distribution: Dict[str, int] = {}
    method_distribution: Dict[str, int] = {}
    country_distribution: Dict[str, int] = {}
    amount_stats: Dict[str, Optional[float]]


class BuildVectorDBRequest(BaseModel):
    """Request model for building vector DB."""
    force_rebuild: bool = Field(default=False, description="Force rebuild of index")


class BuildVectorDBResponse(BaseModel):
    """Response model for vector DB building."""
    status: str
    stats: Optional[Dict] = None
    reason: Optional[str] = None
    