import pickle
import faiss
import numpy as np

from fastapi import (
    HTTPException, 
    status
)

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

from database.model import FaissIndexStore, FileBatch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import logging

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    Manages tenant-specific FAISS indices for semantic search.
    Each tenant has their own FAISS index that persists across uploads.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize FAISS vector store.
        
        Args:
            base_path: Base directory for storing FAISS indices
        """
        self.db = db
        
        # Cache for loaded indices (tenant_id -> {index, metadata})
        self._index_cache: Dict[str, Dict] = {}
        
        logger.info(f"FAISS Vector Store initialized")



    def _create_index(self, dimension: int) -> faiss.Index:
        """
        Create a new FAISS index with cosine similarity.
        
        Args:
            dimension: Embedding dimension
            
        Returns:
            FAISS index
        """
        index = faiss.IndexFlatIP(dimension)
        
        logger.info(f"Created new FAISS index with dimension {dimension}")
        return index
    

    async def _load_index(self, tenant_id: str, batch_id: str) -> Optional[Dict]:
        """
        Load FAISS index and metadata from database.
        
        Args:
            batch_id: The ID of the specific file upload/batch
            tenant_id: User ID (used to verify ownership of the batch)
            
        Returns:
            Dictionary with index, metadata, and documents, or None if not exists
        """

        query = (
            select(FaissIndexStore)
            .join(FaissIndexStore.batch)
            .where(
                FaissIndexStore.batch_id == batch_id,
                FileBatch.tenant_user_id == tenant_id
            )
        )

        result = await self.db.execute(query)

        db_store: FaissIndexStore = result.scalar_one_or_none()

        if not db_store:
            return None

        index_bytes = np.frombuffer(db_store.faiss_index, dtype=np.uint8)
        index = faiss.deserialize_index(index_bytes)

        metadata = pickle.loads(db_store.metadata_pkl)


        return {
            "index": index,
            "metadata": metadata,
            "documents": db_store.documents
        }
    


    async def _save_index(
        self, 
        tenant_id: str, 
        batch_id: str,
        index: faiss.Index, 
        metadata: Dict[str, Any],
        documents: List[str]
    ) -> None:
        """
        Save FAISS index and metadata to database.
        
        Args:
            batch_id: The ID of the specific file upload/batch
            tenant_id: User ID (used to verify ownership of the batch)
            index: FAISS index
            metadata: Metadata dictionary
            documents: List of original documents
        """
        try: 

            index_bytes = faiss.serialize_index(index).tobytes()
            metadata_bytes = pickle.dumps(metadata)

            # Check if an index for this specific batch already exists
            query = select(FaissIndexStore).where(FaissIndexStore.batch_id == batch_id)

            result = await self.db.execute(query)
            existing_store = result.scalar_one_or_none()

            if existing_store:
                existing_store.documents = documents
                existing_store.faiss_index = index_bytes
                existing_store.metadata_pkl = metadata_bytes

            else:
                new_store = FaissIndexStore(
                    batch_id=batch_id,
                    documents=documents,
                    faiss_index=index_bytes,
                    metadata_pkl=metadata_bytes
                )

                self.db.add(new_store) 

            await self.db.commit()


        except Exception as e:

            await self.db.rollback()

            logger.error(f"Failed to save index for tenant {batch_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"error while saving FAISS indexes: {e}"
            )


    async def add_documents(
        self,
        tenant_id: str,
        batch_id: str, 
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict],
        document_type: str
    ) -> Dict:
        """
        Add documents to tenant's FAISS index. Creates new index or appends to existing.
        
        Args:
            Args:
            tenant_id:     Owner – used to verify ownership on load.
            batch_id:      Target FileBatch UUID.
            embeddings:    List of float vectors (one per document).
            documents:     List of original text documents.
            metadata:      List of metadata dicts (one per document).
            document_type: 'transactions' or 'fraud_detection'.
            
        Returns:
            Statistics about the operation
        """

        if not embeddings or not documents:
            logger.warning(f"No documents to add for tenant {tenant_id}")
            return {
                "status": "skipped", 
                "reason": "empty_input"
            }
        
        if len(embeddings) != len(documents) != len(metadata):
            raise ValueError("embeddings, documents, and metadata must have same length")
        
        embeddings_array = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_array.shape[1]
        
        faiss.normalize_L2(embeddings_array)
        
        if tenant_id in self._index_cache:
            index_data = self._index_cache[batch_id]
        else:
            index_data = await self._load_index(tenant_id, batch_id)

            if index_data is not None:
                logger.info(f"Loaded index from DB for batch {batch_id}")

            else:
                index_data = {
                    "index": self._create_index(dimension),
                    "metadata": {
                        "tenant_id":        tenant_id,
                        "batch_id":         batch_id,
                        "created_at":       datetime.utcnow().isoformat(),
                        "dimension":        dimension,
                        "total_uploads":    0,
                        "document_metadata": [],
                    },
                    "documents": [],
                }
                logger.info(f"Created new index for batch {batch_id}")
        

        start_idx = index_data["index"].ntotal
        index_data["index"].add(embeddings_array)
        index_data["documents"].extend(documents)


        for i, meta in enumerate(metadata):
            doc_meta = {
                "index": start_idx + i,
                "document_type": document_type,
                "added_at": datetime.utcnow().isoformat(),
                **meta
            }
            index_data["metadata"]["document_metadata"].append(doc_meta)
        
        index_data["metadata"]["total_uploads"] += 1
        index_data["metadata"]["last_updated"] = datetime.utcnow().isoformat()
        index_data["metadata"]["total_documents"] = index_data["index"].ntotal
        
        self._index_cache[batch_id] = index_data

        await self._save_index(
            tenant_id=tenant_id,
            batch_id=batch_id,
            index=index_data["index"],
            metadata=index_data["metadata"],
            documents=index_data["documents"]
        )

        stats = {
            "status": "success",
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "document_type": document_type,
            "documents_added": len(documents),
            "total_documents": index_data["index"].ntotal,
            "upload_number": index_data["metadata"]["total_uploads"],
            "dimension": dimension
        }
        
        logger.info(f"Added {len(documents)} documents to tenant {tenant_id}'s index")

        return stats


    async def search(
        self,
        tenant_id: str,
        batch_id: str,
        query_embedding: List[float],
        k: int = 10,
        filter_by: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar documents in a batch's FAISS index.

        Args:
            tenant_id:       Owner – used to verify ownership on load.
            batch_id:        Target FileBatch UUID.
            query_embedding: Query vector.
            k:               Number of results to return.
            filter_by:       Optional metadata filters.

        Returns:
            List of result dicts with 'document', 'score', and 'metadata'.
        """

        if batch_id not in self._index_cache:
            index_data = await self._load_index(tenant_id, batch_id)

            if index_data is None:
                logger.warning(f"No index found for batch {batch_id}")
                return []
            
            self._index_cache[batch_id] = index_data

        else:
            index_data = self._index_cache[batch_id]
        
        query_array = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_array)
        
        search_k = min(k * 3, index_data["index"].ntotal)
        if search_k == 0:
            return []
        
        distances, indices = index_data["index"].search(query_array, search_k)
        
        results = []
        for idx, score in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            
            doc_metadata = index_data["metadata"]["document_metadata"][idx]
            
            if filter_by:
                if any(doc_metadata.get(key) != val for key, val in filter_by.items()):
                    continue
            
            result = {
                "document": index_data["documents"][idx],
                "score": float(score),
                "metadata": doc_metadata
            }
            results.append(result)
            
            if len(results) >= k:
                break
        
        logger.info(
            f"Search for batch {batch_id}: "
            f"found {len(results)} results (requested {k})"
        )
        
        return results
    

    async def get_index_stats(self, tenant_id: str, batch_id: str) -> Optional[Dict]:
        """
        Return statistics for a specific batch's FAISS index.

        Args:
            tenant_id: Owner – used to verify ownership on load.
            batch_id:  Target FileBatch UUID.
        """

        if batch_id not in self._index_cache:
            index_data = await self._load_index(tenant_id, batch_id)

            if index_data is None:
                return None
            self._index_cache[batch_id] = index_data

        else:
            index_data = self._index_cache[batch_id]
        
        doc_types = {}
        for meta in index_data["metadata"]["document_metadata"]:
            doc_type = meta.get("document_type", "unknown")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        stats = {
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "total_documents": index_data["index"].ntotal,
            "dimension": index_data["metadata"]["dimension"],
            "total_uploads": index_data["metadata"]["total_uploads"],
            "created_at": index_data["metadata"]["created_at"],
            "last_updated": index_data["metadata"].get("last_updated"),
            "documents_by_type": doc_types
        }
        
        return stats
    

    async def delete_index(self, tenant_id: str, batch_id: str) -> bool:
        """
        Delete a batch's FAISS index from cache and database.

        Args:
            tenant_id: Owner – used to verify ownership via the join.
            batch_id:  Target FileBatch UUID.

        Returns:
            True if deleted, False if not found.
        """
        
        self._index_cache.pop(batch_id, None)

        query = (
            select(FaissIndexStore)
            .join(FaissIndexStore.batch)
            .where(
                FaissIndexStore.batch_id == batch_id,
                FileBatch.tenant_user_id == tenant_id
            )
        )
        
        result = await self.db.execute(query)
        db_store = result.scalar_one_or_none()

        if not db_store:
            return False 

        try: 
            self.db.delete(db_store)
            await self.db.commit()
            return True
        
        except Exception as e:
            
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"something went wrong while deleting indexes: {e}"
            )
