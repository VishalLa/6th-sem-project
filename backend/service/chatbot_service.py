from fastapi import (
    HTTPException, 
    status
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from typing import Dict, Optional, List, Any
import pandas as pd
import logging

from database.model import Transaction, FraudRingSummary, FileBatch

from service.embeddings.create_vector_db import CPUEmbeddings
from service.embeddings.fiass_calculate import FAISSVectorStore


from chatbot import FraudDetectionChatbot, VECTOR_AVAILABLE


logger = logging.getLogger(__name__)

_embeddings_instance: Optional[CPUEmbeddings] = None
_chatbot_cache: Dict[str, FraudDetectionChatbot] = {}


def get_embeddings() -> CPUEmbeddings:
    """Get or create singleton embeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info("Initializing CPUEmbeddings for chatbot")
        _embeddings_instance = CPUEmbeddings(training_mode=False)
    return _embeddings_instance


def get_vector_store(db: AsyncSession) -> FAISSVectorStore:
    """
    Get vector store instance with database session.
    NOTE: Not cached because it needs db session.
    """
    logger.debug("Creating FAISSVectorStore instance with db session")
    return FAISSVectorStore(db)


async def get_latest_batch_id(tenant_id: str, db: AsyncSession) -> Optional[str]:
    """
    Return the most recent batch_id for the given tenant, or None if none exist.

    Args:
        tenant_id: User UUID
        db: Database session

    Returns:
        Latest batch_id string or None
    """
    result = await db.execute(
        select(FileBatch.batch_id)
        .where(FileBatch.tenant_user_id == tenant_id)
        .order_by(desc(FileBatch.uploaded_at))
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def get_all_batch_ids(tenant_id: str, db: AsyncSession) -> List[Dict]:
    """
    Return all batches for a tenant with basic metadata, newest first.
    Used by the frontend to populate the file-picker dropdown.

    Returns:
        List of dicts: {batch_id, uploaded_at, filename}
    """
    from database.model import JSONStore

    result = await db.execute(
        select(FileBatch.batch_id, FileBatch.uploaded_at, JSONStore.filename)
        .outerjoin(JSONStore, JSONStore.batch_id == FileBatch.batch_id)
        .where(FileBatch.tenant_user_id == tenant_id)
        .order_by(desc(FileBatch.uploaded_at))
    )
    rows = result.all()

    return [
        {
            "batch_id":    row.batch_id,
            "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
            "filename":    row.filename,
        }
        for row in rows
    ]


async def _resolve_batch_id(
    tenant_id: str,
    db: AsyncSession,
    batch_id: Optional[str] = None,
) -> str:
    """
    Return the requested batch_id (after ownership check), or fall back to
    the latest one.  Raises HTTP 404 if no batches exist at all.
    """
    if batch_id:
        # Verify ownership
        result = await db.execute(
            select(FileBatch.batch_id).where(
                FileBatch.batch_id == batch_id,
                FileBatch.tenant_user_id == tenant_id,
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch {batch_id} not found or does not belong to this user.",
            )
        return batch_id

    latest = await get_latest_batch_id(tenant_id, db)
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploaded files found. Please upload data first via /upload/full-pipeline.",
        )
    return latest


async def load_user_transactions(
    tenant_id: str,
    db: AsyncSession,
    batch_id: str,
) -> pd.DataFrame:
    """
    Load transactions for one specific batch, verified against tenant_id.
    Raises HTTP 404 if the batch is empty.
    """
    result = await db.execute(
        select(Transaction)
        .join(Transaction.batch)
        .where(
            FileBatch.tenant_user_id == tenant_id,
            Transaction.batch_id == batch_id,
        )
    )
    transactions = result.scalars().all()

    if not transactions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No transactions found for batch {batch_id}. "
                "Please upload data first via /upload/full-pipeline."
            ),
        )

    df = pd.DataFrame([
        {
            "transaction_id":  t.transaction_id,
            "sender":          t.sender,
            "receiver":        t.receiver,
            "amount":          float(t.amount) if t.amount else 0.0,
            "timestamp":       t.timestamp,
            "sender_country":  t.sender_country,
            "receiver_country": t.receiver_country,
            "sender_kyc":      t.sender_kyc,
            "txn_method":      t.txn_method,
            "device_id":       t.device_id,
            "sender_acct_age": int(t.sender_acct_age) if t.sender_acct_age is not None else 0,
            "velocity_mins":   float(t.velocity_mins) if t.velocity_mins is not None else 0.0,
            "is_round_amount": bool(t.is_round_amount) if t.is_round_amount is not None else False,
        }
        for t in transactions
    ])

    logger.info(
        f"Loaded {len(df)} transactions for tenant={tenant_id} batch={batch_id}"
    )
    return df


async def load_fraud_summaries(
    tenant_id: str,
    db: AsyncSession,
    batch_id: str,
) -> Optional[pd.DataFrame]:
    """
    Load fraud ring summaries for one specific batch, verified against tenant_id.
    Returns None (not an error) when detection hasn't run yet.
    """
    result = await db.execute(
        select(FraudRingSummary)
        .join(FraudRingSummary.batch)
        .where(
            FileBatch.tenant_user_id == tenant_id,
            FraudRingSummary.batch_id == batch_id,
        )
    )
    summaries = result.scalars().all()

    if not summaries:
        logger.info(
            f"No fraud summaries for tenant={tenant_id} batch={batch_id}"
        )
        return None

    df = pd.DataFrame([
        {
            "ring_id":         s.ring_id,
            "pattern_type":    s.pattern_type,
            "member_count":    int(s.member_count) if s.member_count else 0,
            "risk_score":      float(s.risk_score) if s.risk_score else 0.0,
            "risk_category":   s.risk_category,
            "member_accounts": s.member_accounts,
            "created_at":      s.created_at,
        }
        for s in summaries
    ])

    logger.info(
        f"Loaded {len(df)} fraud summaries for tenant={tenant_id} batch={batch_id}"
    )
    return df


async def index_fraud_summaries(
    tenant_id: str,
    batch_id: str,
    db: AsyncSession,
    vector_store: FAISSVectorStore,
    embeddings: CPUEmbeddings,
) -> Dict:
    """
    Index fraud summaries for a specific batch into its FAISS index.
    Skipped silently when there is no fraud data yet.
    """
    fraud_df = await load_fraud_summaries(
        tenant_id=tenant_id,
        db=db,
        batch_id=batch_id,
    )

    if fraud_df is None or fraud_df.empty:
        return {"status": "skipped", "reason": "no_fraud_data"}

    documents     = []
    metadata_list = []

    for _, row in fraud_df.iterrows():
        doc_text = (
            f"Fraud Pattern: {row['pattern_type']} | "
            f"Ring ID: {row['ring_id']} | "
            f"Accounts Involved: {row['member_count']} | "
            f"Risk Score: {row['risk_score']} | "
            f"Risk Category: {row['risk_category']} | "
            f"Members: {row['member_accounts']}"
        )
        documents.append(doc_text)
        metadata_list.append({
            "ring_id":       str(row["ring_id"]),
            "pattern_type":  str(row["pattern_type"]),
            "risk_score":    str(row["risk_score"]),
            "risk_category": str(row["risk_category"]),
            "document_type": "fraud_summary",
        })

    all_embeddings = embeddings.embed_documents(documents)

    stats = await vector_store.add_documents(
        tenant_id=tenant_id,
        batch_id=batch_id,
        embeddings=all_embeddings,
        documents=documents,
        metadata=metadata_list,
        document_type="fraud_summary",
    )

    logger.info(
        f"Indexed {len(documents)} fraud summaries "
        f"tenant={tenant_id} batch={batch_id}"
    )
    return stats


async def get_or_create_chatbot(
    tenant_id: str,
    db: AsyncSession,
    batch_id: Optional[str] = None,
) -> FraudDetectionChatbot:
    """
    Return a cached chatbot for (tenant_id, batch_id), or build a new one.

    Each (tenant, batch) pair gets its own chatbot instance so that data
    from different uploads never mix.  batch_id defaults to the user's
    most-recent upload when not supplied.

    Args:
        tenant_id: Authenticated user's UUID.
        db:        Async database session.
        batch_id:  Optional FileBatch UUID chosen by the user in the UI.

    Returns:
        FraudDetectionChatbot scoped to the requested batch.
    """
    # Resolve / validate batch_id
    resolved_batch_id = await _resolve_batch_id(tenant_id, db, batch_id)
    cache_key = f"{tenant_id}_{resolved_batch_id}"

    if cache_key in _chatbot_cache:
        logger.debug(f"Cache hit for {cache_key}")
        return _chatbot_cache[cache_key]

    logger.info(
        f"Building chatbot for tenant={tenant_id} batch={resolved_batch_id}"
    )

    # Load data scoped to this exact batch
    df       = await load_user_transactions(tenant_id, db, resolved_batch_id)
    fraud_df = await load_fraud_summaries(tenant_id, db, resolved_batch_id)

    # Embeddings + vector store
    embeddings   = get_embeddings()
    vector_store = get_vector_store(db)

    chatbot = FraudDetectionChatbot(
        df=df,
        fraud_summary_df=fraud_df,
        vector_store=vector_store if VECTOR_AVAILABLE else None,
        embeddings=embeddings   if VECTOR_AVAILABLE else None,
        default_tenant_id=tenant_id,
        default_batch_id=resolved_batch_id,
    )

    # Index fraud summaries into this batch's FAISS index
    if VECTOR_AVAILABLE and fraud_df is not None:
        try:
            stats = await index_fraud_summaries(
                tenant_id=tenant_id,
                batch_id=resolved_batch_id,
                db=db,
                vector_store=vector_store,
                embeddings=embeddings,
            )
            logger.info(f"Fraud summary indexing: {stats}")
        except Exception as e:
            logger.warning(f"Could not index fraud summaries: {e}")

    # Cache under the (tenant, batch) key
    _chatbot_cache[cache_key] = chatbot
    logger.info(f"Chatbot cached at key={cache_key}")
    return chatbot


def invalidate_chatbot_cache(tenant_id: str, batch_id: Optional[str] = None) -> int:
    """
    Remove cached chatbot(s) for a tenant.

    Args:
        tenant_id: Owner UUID.
        batch_id:  If supplied, only that specific (tenant, batch) entry is
                   removed.  If None, ALL entries for the tenant are removed.

    Returns:
        Number of cache entries removed.
    """
    if batch_id:
        key = f"{tenant_id}_{batch_id}"
        if key in _chatbot_cache:
            del _chatbot_cache[key]
            return 1
        return 0

    keys_to_remove = [k for k in _chatbot_cache if k.startswith(f"{tenant_id}_")]
    for k in keys_to_remove:
        del _chatbot_cache[k]
    return len(keys_to_remove)


def convert_table_data(table_data: Any) -> Optional[List[Dict]]:
    """Convert DataFrame or list to JSON-serialisable list of dicts."""
    if table_data is None:
        return None
    
    if isinstance(table_data, pd.DataFrame):
        return table_data.head(100).to_dict("records")
    if isinstance(table_data, list):
        return table_data[:100]
    
    return None
