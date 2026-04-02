import os
import json
import pickle
import faiss
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from core.config import vector_settings

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    Manages tenant-specific FAISS indices for semantic search.
    Each tenant has their own FAISS index that persists across uploads.
    """

    def __init__(self, base_path: str = None):
        """
        Initialize FAISS vector store.
        
        Args:
            base_path: Base directory for storing FAISS indices
        """
        self.base_path = base_path or vector_settings.FAISS_PATH
        os.makedirs(self.base_path, exist_ok=True)
        
        # Cache for loaded indices (tenant_id -> {index, metadata})
        self._index_cache: Dict[str, Dict] = {}
        
        logger.info(f"FAISS Vector Store initialized at {self.base_path}")


    def _get_tenant_index_path(self, tenant_id: str) -> str:
        """Get the directory path for a tenant's FAISS index."""
        tenant_dir = os.path.join(self.base_path, tenant_id)
        os.makedirs(tenant_dir, exist_ok=True)
        return tenant_dir
    

    def _get_index_file_path(self, tenant_id: str) -> str:
        """Get the FAISS index file path."""
        return os.path.join(self._get_tenant_index_path(tenant_id), "index.faiss")
    

    def _get_metadata_file_path(self, tenant_id: str) -> str:
        """Get the metadata file path."""
        return os.path.join(self._get_tenant_index_path(tenant_id), "metadata.pkl")
    

    def _get_documents_file_path(self, tenant_id: str) -> str:
        """Get the documents file path."""
        return os.path.join(self._get_tenant_index_path(tenant_id), "documents.json")
    

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
    

    def _load_index(self, tenant_id: str) -> Optional[Dict]:
        """
        Load FAISS index and metadata from disk.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Dictionary with index, metadata, and documents, or None if not exists
        """
        index_path = self._get_index_file_path(tenant_id)
        metadata_path = self._get_metadata_file_path(tenant_id)
        documents_path = self._get_documents_file_path(tenant_id)
        
        if not os.path.exists(index_path):
            logger.info(f"No existing index found for tenant {tenant_id}")
            return None
        
        try:
            index = faiss.read_index(index_path)
            
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            
            with open(documents_path, 'r', encoding='utf-8') as f:
                documents = json.load(f)
            
            logger.info(
                f"Loaded index for tenant {tenant_id}: "
                f"{index.ntotal} vectors, {len(documents)} documents"
            )
            
            return {
                "index": index,
                "metadata": metadata,
                "documents": documents
            }
            
        except Exception as e:
            logger.error(f"Failed to load index for tenant {tenant_id}: {e}")
            return None
        
    
    # TODO: Update this function to save all index in postgress database
    def _save_index(
        self, 
        tenant_id: str, 
        index: faiss.Index, 
        metadata: Dict,
        documents: List[str]
    ) -> None:
        """
        Save FAISS index and metadata to disk.
        
        Args:
            tenant_id: User ID
            index: FAISS index
            metadata: Metadata dictionary
            documents: List of original documents
        """
        try:
            index_path = self._get_index_file_path(tenant_id)
            metadata_path = self._get_metadata_file_path(tenant_id)
            documents_path = self._get_documents_file_path(tenant_id)
            
            faiss.write_index(index, index_path)
            
            with open(metadata_path, 'wb') as f:
                pickle.dump(metadata, f)
            
            with open(documents_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)
            
            logger.info(
                f"Saved index for tenant {tenant_id}: "
                f"{index.ntotal} vectors, {len(documents)} documents"
            )
            
        except Exception as e:
            logger.error(f"Failed to save index for tenant {tenant_id}: {e}")
            raise


    def add_documents(
        self,
        tenant_id: str,
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict],
        document_type: str
    ) -> Dict:
        """
        Add documents to tenant's FAISS index. Creates new index or appends to existing.
        
        Args:
            tenant_id: User ID
            embeddings: List of embedding vectors
            documents: List of original text documents
            metadata: List of metadata dictionaries (one per document)
            document_type: Type of documents ('transactions' or 'fraud_detection')
            
        Returns:
            Statistics about the operation
        """

        if not embeddings or not documents:
            logger.warning(f"No documents to add for tenant {tenant_id}")
            return {"status": "skipped", "reason": "empty_input"}
        
        if len(embeddings) != len(documents) != len(metadata):
            raise ValueError("embeddings, documents, and metadata must have same length")
        
        embeddings_array = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_array.shape[1]
        
        faiss.normalize_L2(embeddings_array)
        
        if tenant_id in self._index_cache:
            index_data = self._index_cache[tenant_id]
        else:
            index_data = self._load_index(tenant_id)
        
        if index_data is None:
            index = self._create_index(dimension)

            index_data = {
                "index": index,
                "metadata": {
                    "tenant_id": tenant_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "dimension": dimension,
                    "total_uploads": 0,
                    "document_metadata": []
                },
                "documents": []
            }

            logger.info(f"Created new index for tenant {tenant_id}")

        else:
            logger.info(f"Appending to existing index for tenant {tenant_id}")
        
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
        
        self._index_cache[tenant_id] = index_data
        
        # Save to disk
        self._save_index(
            tenant_id=tenant_id,
            index=index_data["index"],
            metadata=index_data["metadata"],
            documents=index_data["documents"]
        )
        
        stats = {
            "status": "success",
            "tenant_id": tenant_id,
            "document_type": document_type,
            "documents_added": len(documents),
            "total_documents": index_data["index"].ntotal,
            "upload_number": index_data["metadata"]["total_uploads"],
            "dimension": dimension
        }
        
        logger.info(f"Added {len(documents)} documents to tenant {tenant_id}'s index")
        return stats
    

    def search(
        self,
        tenant_id: str,
        query_embedding: List[float],
        k: int = 10,
        filter_by: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar documents in tenant's index.
        
        Args:
            tenant_id: User ID
            query_embedding: Query embedding vector
            k: Number of results to return
            filter_by: Optional filters (e.g., {"document_type": "fraud_detection"})
            
        Returns:
            List of search results with documents and scores
        """

        if tenant_id not in self._index_cache:
            index_data = self._load_index(tenant_id)

            if index_data is None:
                logger.warning(f"No index found for tenant {tenant_id}")
                return []
            
            self._index_cache[tenant_id] = index_data

        else:
            index_data = self._index_cache[tenant_id]
        
        query_array = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_array)
        
        search_k = min(k * 3, index_data["index"].ntotal)
        distances, indices = index_data["index"].search(query_array, search_k)
        
        results = []
        for idx, score in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            
            doc_metadata = index_data["metadata"]["document_metadata"][idx]
            
            if filter_by:
                skip = False
                for key, value in filter_by.items():
                    if doc_metadata.get(key) != value:
                        skip = True
                        break
                if skip:
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
            f"Search for tenant {tenant_id}: "
            f"found {len(results)} results (requested {k})"
        )
        
        return results
    

    def get_index_stats(self, tenant_id: str) -> Optional[Dict]:
        """
        Get statistics about tenant's index.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Dictionary with index statistics
        """

        if tenant_id not in self._index_cache:
            index_data = self._load_index(tenant_id)

            if index_data is None:
                return None
            self._index_cache[tenant_id] = index_data

        else:
            index_data = self._index_cache[tenant_id]
        
        doc_types = {}
        for meta in index_data["metadata"]["document_metadata"]:
            doc_type = meta.get("document_type", "unknown")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        stats = {
            "tenant_id": tenant_id,
            "total_documents": index_data["index"].ntotal,
            "dimension": index_data["metadata"]["dimension"],
            "total_uploads": index_data["metadata"]["total_uploads"],
            "created_at": index_data["metadata"]["created_at"],
            "last_updated": index_data["metadata"].get("last_updated"),
            "documents_by_type": doc_types,
            "index_size_mb": self._get_index_size(tenant_id)
        }
        
        return stats
    

    def _get_index_size(self, tenant_id: str) -> float:
        """Get the size of tenant's index files in MB."""
        total_size = 0
        tenant_dir = self._get_tenant_index_path(tenant_id)
        
        if os.path.exists(tenant_dir):

            for filename in os.listdir(tenant_dir):
                file_path = os.path.join(tenant_dir, filename)

                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
        
        return round(total_size / (1024 * 1024), 2)
    

    def delete_index(self, tenant_id: str) -> bool:
        """
        Delete tenant's entire index.
        
        Args:
            tenant_id: User ID
            
        Returns:
            True if successful
        """
        import shutil
        
        if tenant_id in self._index_cache:
            del self._index_cache[tenant_id]
        
        tenant_dir = self._get_tenant_index_path(tenant_id)
        if os.path.exists(tenant_dir):

            try:
                shutil.rmtree(tenant_dir)
                logger.info(f"Deleted index for tenant {tenant_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete index for tenant {tenant_id}: {e}")
                return False
        
        return True
    
    
    def list_all_indices(self) -> List[Dict]:
        """
        List all tenant indices.
        
        Returns:
            List of dictionaries with tenant index information
        """
        indices = []
        
        if not os.path.exists(self.base_path):
            return indices
        
        for tenant_id in os.listdir(self.base_path):
            tenant_dir = os.path.join(self.base_path, tenant_id)
            if os.path.isdir(tenant_dir):
                stats = self.get_index_stats(tenant_id)
                if stats:
                    indices.append(stats)
        
        return indices
    
    