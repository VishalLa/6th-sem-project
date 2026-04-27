from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

import logging
from typing import Optional

from database.session import get_db
from database.model import User

from auth.deps import get_current_user

from schema.chatbout import (
    ChatQueryResponse,
    ChatQueryRequest,
    SessionSummaryResponse,
    DatasetInfoResponse,
    BuildVectorDBRequest,
    BuildVectorDBResponse,
)

from chatbot import VECTOR_AVAILABLE

from service.chatbot_service import (
    _chatbot_cache,
    get_vector_store,
    get_or_create_chatbot,
    get_all_batch_ids,
    get_latest_batch_id,
    invalidate_chatbot_cache,
    convert_table_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# ------------------------------------------------------------------
# Batch picker — lets the frontend show a file-selection dropdown
# ------------------------------------------------------------------

@router.get(
    "/batches",
    status_code=status.HTTP_200_OK,
    summary="List uploaded file batches",
    description="""
    Returns all uploaded file batches for the current user, newest first.
    Use the returned batch_id values to scope chatbot queries to a specific file.
    """,
)
async def list_chatbot_batches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enumerate available batches so the UI can render a file-picker.
    Each entry contains batch_id, uploaded_at, and the original filename.
    """
    try:
        batches = await get_all_batch_ids(current_user.user_id, db)

        if not batches:
            return {
                "status":  "success",
                "message": "No uploaded files found. Upload data via /upload/full-pipeline.",
                "batches": [],
            }

        return {
            "status":       "success",
            "tenant_id":    current_user.user_id,
            "total":        len(batches),
            "batches":      batches,
        }

    except Exception as e:
        logger.error(f"Error listing batches: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing batches: {str(e)}",
        )


# ------------------------------------------------------------------
# Main chat endpoint — accepts optional batch_id query param
# ------------------------------------------------------------------

@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query chatbot with natural language",
    description="""
    Ask questions about your transaction data in natural language.

    Pass **batch_id** (from GET /chatbot/batches) to query a specific uploaded file.
    When batch_id is omitted the most-recently uploaded file is used.

    Example queries:
    - "How many transactions are there?"
    - "What is the average transaction amount?"
    - "Show me high-risk transactions"
    - "Group transactions by country"
    - "Find suspicious patterns"
    """,
)
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer a natural language query scoped to a specific uploaded file."""
    try:
        chatbot = await get_or_create_chatbot(
            tenant_id=current_user.user_id,
            db=db,
            batch_id=request.batch_id,   # ← user-selected file
        )

        response = chatbot.answer_query(
            user_query=request.query,
            session_id=request.session_id,
            include_followup=request.include_followup,
            include_trace=request.include_trace,
        )

        response["table_data"] = convert_table_data(response.get("table_data"))
        return ChatQueryResponse(**response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}",
        )


# ------------------------------------------------------------------
# Session management
# ------------------------------------------------------------------

@router.get(
    "/session/{session_id}",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session summary",
)
async def get_session_summary(
    session_id: str,
    batch_id: Optional[str] = Query(None, description="Batch to scope the chatbot to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation history and summary for a session."""
    try:
        chatbot = await get_or_create_chatbot(
            current_user.user_id, db, batch_id=batch_id
        )
        summary = chatbot.get_session_summary(session_id)

        return SessionSummaryResponse(
            session_id=session_id,
            interaction_count=summary.get("total_interactions", 0),
            interactions=summary.get("interactions", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session summary: {str(e)}",
        )


@router.post(
    "/session/{session_id}/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset session",
)
async def reset_session(
    session_id: str,
    batch_id: Optional[str] = Query(None, description="Batch to scope the chatbot to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset conversation history for a session."""
    try:
        chatbot = await get_or_create_chatbot(
            current_user.user_id, db, batch_id=batch_id
        )
        chatbot.reset_session(session_id)

        return {
            "status":  "success",
            "message": f"Session {session_id} reset successfully.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting session: {str(e)}",
        )


# ------------------------------------------------------------------
# Dataset info
# ------------------------------------------------------------------

@router.get(
    "/dataset/info",
    response_model=DatasetInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dataset information",
)
async def get_dataset_info(
    batch_id: Optional[str] = Query(None, description="Batch to inspect"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get information about a specific uploaded dataset (defaults to latest)."""
    try:
        chatbot = await get_or_create_chatbot(
            current_user.user_id, db, batch_id=batch_id
        )
        info = chatbot.get_dataset_info()

        formatted_info = {
            "rows":                info.get("transaction_count", 0),
            "columns":             info.get("columns", []),
            "kyc_distribution":    info.get("kyc_dist", {}),
            "method_distribution": info.get("method_dist", {}),
            "country_distribution": info.get("country_dist", {}),
            "amount_stats": {
                "min":   info.get("min_amount"),
                "max":   info.get("max_amount"),
                "avg":   info.get("avg_amount"),
                "total": info.get("total_amount"),
            },
        }
        if info.get("fraud_summary"):
            formatted_info["fraud_summary"] = info["fraud_summary"]
        if info.get("date_range"):
            formatted_info["date_range"] = info["date_range"]

        return DatasetInfoResponse(**formatted_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dataset info: {str(e)}",
        )


# ------------------------------------------------------------------
# Vector DB
# ------------------------------------------------------------------

@router.post(
    "/vector-db/build",
    response_model=BuildVectorDBResponse,
    status_code=status.HTTP_200_OK,
    summary="Build vector database for a batch",
)
async def build_vector_db(
    request: BuildVectorDBRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build or rebuild the FAISS vector index for a specific batch."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vector search is not available.",
        )
    try:
        chatbot = await get_or_create_chatbot(
            tenant_id=current_user.user_id,
            db=db,
            batch_id=request.batch_id,
        )

        result = chatbot.build_vector_db(
            tenant_id=current_user.user_id,
            batch_id=request.batch_id,
            force_rebuild=request.force_rebuild,
        )

        return BuildVectorDBResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building vector DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building vector DB: {str(e)}",
        )


@router.get(
    "/vector-index/stats",
    status_code=status.HTTP_200_OK,
    summary="Get FAISS index statistics for a batch",
    tags=["Vector Search"],
)
async def get_vector_index_stats(
    batch_id: Optional[str] = Query(None, description="Batch to inspect (defaults to latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show FAISS index statistics for a specific batch."""
    try:
        from service.chatbot_service import _resolve_batch_id
        resolved = await _resolve_batch_id(current_user.user_id, db, batch_id)

        vector_store = get_vector_store(db)
        stats = await vector_store.get_index_stats(current_user.user_id, resolved)

        if stats is None:
            return {
                "status":    "success",
                "tenant_id": current_user.user_id,
                "batch_id":  resolved,
                "message":   "No vector index found for this batch.",
                "has_index": False,
            }

        return {"status": "success", **stats, "has_index": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get index stats: {str(e)}",
        )


@router.delete(
    "/vector-index",
    status_code=status.HTTP_200_OK,
    summary="Delete FAISS index for a batch",
    tags=["Vector Search"],
)
async def delete_vector_index(
    batch_id: Optional[str] = Query(None, description="Batch whose index to delete (defaults to latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the FAISS vector index for a specific batch."""
    try:
        from service.chatbot_service import _resolve_batch_id
        resolved = await _resolve_batch_id(current_user.user_id, db, batch_id)

        vector_store = get_vector_store(db)
        success = await vector_store.delete_index(current_user.user_id, resolved)

        if success:
            # Evict the chatbot for this batch from cache
            removed = invalidate_chatbot_cache(current_user.user_id, resolved)
            return {
                "status":    "success",
                "tenant_id": current_user.user_id,
                "batch_id":  resolved,
                "message":   "Vector index deleted successfully.",
                "cache_entries_removed": removed,
            }

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vector index found for batch {resolved}.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}",
        )


# ------------------------------------------------------------------
# Cache management
# ------------------------------------------------------------------

@router.delete(
    "/cache",
    status_code=status.HTTP_200_OK,
    summary="Clear chatbot cache for current user",
)
async def clear_chatbot_cache(
    batch_id: Optional[str] = Query(
        None,
        description="Clear only this batch's chatbot. Omit to clear all batches.",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Clear cached chatbot instance(s) for the current user.
    Omit batch_id to evict ALL batches; supply batch_id to evict just one.
    """
    removed = invalidate_chatbot_cache(current_user.user_id, batch_id)

    scope = f"batch {batch_id}" if batch_id else "all batches"
    return {
        "status":               "success",
        "message":              f"Cleared chatbot cache for {scope}.",
        "cache_entries_removed": removed,
    }
