import logging
import pandas as pd
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    Retrieves semantically relevant documents from the FAISS vector store.
    Augments query results with vector-based semantic search.
    """

    def __init__(self, vector_store, embeddings):
        """
        Args:
            vector_store: FAISSVectorStore instance
            embeddings: CPUEmbeddings instance
        """
        self.vector_store = vector_store
        self.embeddings = embeddings
        logger.info("VectorRetriever initialized.")


    def retrieve(
        self,
        tenant_id: str,
        query: str,
        k: int = 5,
        filter_by: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Retrieve semantically similar documents for a query.

        Args:
            tenant_id: Tenant/user identifier
            query: Natural language query text
            k: Number of results to return
            filter_by: Optional metadata filter (e.g., {"document_type": "fraud_detection"})

        Returns:
            List of result dicts with document, score, and metadata
        """

        logger.info(f"Vector retrieval for tenant={tenant_id}, query='{query[:60]}...', k={k}")

        try:
            query_embedding = self.embeddings.embed_query(query)
            results = self.vector_store.search(
                tenant_id=tenant_id,
                query_embedding=query_embedding,
                k=k,
                filter_by=filter_by,
            )

            logger.info(f"Retrieved {len(results)} vector results.")
            return results

        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}", exc_info=True)
            return []
        

    def retrieve_fraud_patterns(
        self,
        tenant_id: str,
        query: str,
        k: int = 3,
    ) -> List[Dict]:
        """
        Retrieve fraud-related documents specifically.

        Args:
            tenant_id: Tenant identifier
            query: Query text
            k: Number of results

        Returns:
            List of fraud pattern results
        """
        return self.retrieve(
            tenant_id=tenant_id,
            query=query,
            k=k,
            filter_by={"document_type": "fraud_detection"},
        )
    

    def index_dataframe(
        self,
        tenant_id: str,
        df: pd.DataFrame,
        document_type: str = "transactions",
        text_columns: Optional[List[str]] = None,
        batch_size: int = 32,
    ) -> Dict:
        """
        Index a pandas DataFrame into the vector store.
        Converts rows to text documents for embedding.

        Args:
            tenant_id: Tenant identifier
            df: DataFrame to index
            document_type: Type tag for stored documents
            text_columns: Columns to include in text representation
            batch_size: Embedding batch size

        Returns:
            Indexing statistics
        """
        if text_columns is None:
            text_columns = list(df.columns)

        logger.info(f"Indexing {len(df)} rows for tenant={tenant_id}, type={document_type}")

        # Convert each row to a text document
        documents = []
        metadata_list = []

        for _, row in df.iterrows():
            parts = []

            for col in text_columns:
                if col in row and pd.notna(row[col]):
                    parts.append(f"{col}: {row[col]}")

            doc_text = " | ".join(parts)
            documents.append(doc_text)

            # Build metadata
            meta = {}
            for col in df.columns:
                val = row.get(col)

                if pd.notna(val) if not isinstance(val, str) else val:
                    meta[col] = str(val)

            metadata_list.append(meta)

        # Batch embed
        all_embeddings = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_embeddings = self.embeddings.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)

        # Add to vector store
        stats = self.vector_store.add_documents(
            tenant_id=tenant_id,
            embeddings=all_embeddings,
            documents=documents,
            metadata=metadata_list,
            document_type=document_type,
        )

        logger.info(f"Indexed {len(documents)} documents. Stats: {stats}")
        return stats
    

    def get_index_stats(self, tenant_id: str) -> Optional[Dict]:
        """Get index statistics for a tenant."""
        return self.vector_store.get_index_stats(tenant_id)


    def is_indexed(self, tenant_id: str) -> bool:
        """Check if a tenant has an existing index."""
        stats = self.get_index_stats(tenant_id)
        return stats is not None and stats.get("total_documents", 0) > 0