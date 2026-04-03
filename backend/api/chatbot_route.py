from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    status
)

from sqlalchemy.ext.asyncio import AsyncSession

import logging

from database.session import get_db
from database.model import User

from auth.deps import get_current_user

from schema.chatbout import (
    ChatQueryResponse,
    ChatQueryRequest,
    SessionSummaryResponse,
    DatasetInfoResponse,
    BuildVectorDBRequest,
    BuildVectorDBResponse
)

from chatbot import VECTOR_AVAILABLE

from service.chatbot_service import (
    _chatbot_cache,
    get_vector_store,
    get_or_create_chatbot,
    convert_table_data
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query chatbot with natural language",
    description="""
    Ask questions about your transaction data in natural language.
    
    Example queries:
    - "How many transactions are there?"
    - "What is the average transaction amount?"
    - "Show me high-risk transactions"
    - "Group transactions by country"
    - "Find suspicious patterns"
    """
)
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Answer a natural language query about fraud detection data."""
    try:
        # Get chatbot
        chatbot = await get_or_create_chatbot(current_user.user_id, db)
        
        # Process query
        response = chatbot.answer_query(
            user_query=request.query,
            session_id=request.session_id,
            include_followup=request.include_followup,
            include_trace=request.include_trace
        )
        
        # Convert table data
        response["table_data"] = convert_table_data(response.get("table_data"))
        
        return ChatQueryResponse(**response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session summary"
)
async def get_session_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation history and summary for a session."""
    try:
        chatbot = await get_or_create_chatbot(current_user.user_id, db)
        summary = chatbot.get_session_summary(session_id)
        
        return SessionSummaryResponse(
            session_id=session_id,
            interaction_count=summary.get("interaction_count", 0),
            interactions=summary.get("interactions", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session summary: {str(e)}"
        )


@router.post(
    "/session/{session_id}/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset session"
)
async def reset_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset conversation history for a session."""
    try:
        chatbot = await get_or_create_chatbot(current_user.user_id, db)
        chatbot.reset_session(session_id)
        
        return {
            "status": "success",
            "message": f"Session {session_id} reset successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting session: {str(e)}"
        )


@router.get(
    "/dataset/info",
    response_model=DatasetInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dataset information"
)
async def get_dataset_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get information about the loaded transaction dataset."""
    try:
        chatbot = await get_or_create_chatbot(current_user.user_id, db)
        info = chatbot.get_dataset_info()
        
        formatted_info = {
            "rows": info.get("transaction_count", 0),
            "columns": info.get("column_names", []),
            "kyc_distribution": info.get("kyc_dist", {}),
            "method_distribution": info.get("method_dist", {}),
            "country_distribution": info.get("country_dist", {}),
            "amount_stats": {
                "min": info.get("min_amount"),
                "max": info.get("max_amount"),
                "avg": info.get("avg_amount"),
                "total": info.get("total_amount")
            }
        }

        if info.get("fraud_summary"):
            formatted_info["fraud_summary"] = info["fraud_summary"]

        return DatasetInfoResponse(**formatted_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dataset info: {str(e)}"
        )


@router.post(
    "/vector-db/build",
    response_model=BuildVectorDBResponse,
    status_code=status.HTTP_200_OK,
    summary="Build vector database"
)
async def build_vector_db(
    request: BuildVectorDBRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Build or rebuild the vector database for semantic search."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vector search is not available. Check VectorRetriever installation."
        )
    
    try:
        chatbot = await get_or_create_chatbot(current_user.user_id, db)
        
        result = chatbot.build_vector_db(
            tenant_id=current_user.user_id,
            force_rebuild=request.force_rebuild
        )
        
        return BuildVectorDBResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building vector DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building vector DB: {str(e)}"
        )
    


@router.get(
    "/vector-index/stats",
    status_code=status.HTTP_200_OK,
    summary="Get vector index statistics",
    tags=["Vector Search"]
)
async def get_vector_index_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics about your FAISS vector index.
    Shows total documents, uploads, and breakdown by type.
    """
    try:
        vector_store = get_vector_store(db)
        
        stats = await vector_store.get_index_stats(current_user.user_id)
        
        if stats is None:
            return {
                "status": "success",
                "tenant_id": current_user.user_id,
                "message": "No vector index found. Upload data with embeddings enabled to create one.",
                "has_index": False
            }
        
        return {
            "status": "success",
            **stats,
            "has_index": True
        }
    
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Vector indexing not available. Enable embeddings during upload."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get index stats: {str(e)}"
        )


@router.delete(
    "/vector-index",
    status_code=status.HTTP_200_OK,
    summary="Delete vector index",
    tags=["Vector Search"]
)
async def delete_vector_index(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete your entire FAISS vector index.
    This will remove all embeddings but not the database records.
    """
    try:
        vector_store = get_vector_store(db)
        
        success = await vector_store.delete_index(current_user.user_id)
        
        if success:
            # Also clear chatbot cache since index is deleted
            global _chatbot_cache
            if current_user.user_id in _chatbot_cache:
                del _chatbot_cache[current_user.user_id]
            
            return {
                "status": "success",
                "tenant_id": current_user.user_id,
                "message": "Vector index deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete vector index"
            )
    
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Vector indexing not available."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}"
        )


@router.delete(
    "/cache",
    status_code=status.HTTP_200_OK,
    summary="Clear chatbot cache"
)
async def clear_chatbot_cache(
    current_user: User = Depends(get_current_user)
):
    """Clear cached chatbot instance for current user."""
    global _chatbot_cache
    
    if current_user.user_id in _chatbot_cache:
        del _chatbot_cache[current_user.user_id]
        logger.info(f"Cleared chatbot cache for tenant {current_user.user_id}")
        
        return {
            "status": "success",
            "message": "Chatbot cache cleared. Next query will reload data."
        }
    
    return {
        "status": "success",
        "message": "No cached chatbot found for user."
    }


# @router.get(
#     "/health",
#     status_code=status.HTTP_200_OK,
#     summary="Health check"
# )
# async def chatbot_health():
#     """Check chatbot service health and status."""
#     try:
#         embeddings = get_embeddings()
#         vector_store = get_vector_store()
        
#         return {
#             "status": "healthy",
#             "vector_available": VECTOR_AVAILABLE,
#             "embeddings_cache_size": embeddings.get_cache_size(),
#             "cached_chatbots": len(_chatbot_cache),
#             "embeddings_model": embeddings.model_name
#         }
#     except Exception as e:
#         logger.error(f"Health check failed: {e}", exc_info=True)
#         return {
#             "status": "unhealthy",
#             "error": str(e)
#         }

