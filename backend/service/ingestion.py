import os
import pandas as pd
from fastapi import (
    UploadFile,
    HTTPException,
    status
) 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select
from datetime import datetime
from typing import Optional, Dict, List, Tuple


from database.model import Transaction, FraudRingSummary 
from graphs.engine import MainEngine
from graphs.build_graph import Graph
from core.config import vector_settings

from .embeddings.create_vector_db import CPUEmbeddings
from .embeddings.fiass_calculate import FAISSVectorStore


class DataIngestionService:

    """
    Handles data ingestion, fraud detection pipeline, and vector storage.
    Processes CSV files, runs detection, stores in database, and creates tenant-specific FAISS indices.
    """

    CHUNK_SIZE = 10_000

    def __init__(self, db: AsyncSession):
        self.db = db 
        self.embedder = CPUEmbeddings(training_mode=False)
        self.vector_store = FAISSVectorStore()


    def _create_transaction_documents(self, dataframe: pd.DataFrame, tenant_id: str) -> Tuple[List[str], List[Dict]]:
        """
        Creates semantic documents from raw transaction data for embedding.
        
        Args:
            dataframe: Raw transaction DataFrame
            tenant_id: User ID
            
        Returns:
            Tuple of (documents, metadata)
        """
        documents = []
        metadata = []
        
        # 1. Overall statistics document
        total_txns = len(dataframe)

        unique_senders = dataframe['sender'].nunique() if 'sender' in dataframe.columns else 0

        unique_receivers = dataframe['receiver'].nunique() if 'receiver' in dataframe.columns else 0

        total_amount = dataframe['amount'].sum() if 'amount' in dataframe.columns else 0

        avg_amount = dataframe['amount'].mean() if 'amount' in dataframe.columns else 0
        
        date_range = ""
        min_date = max_date = None

        if 'timestamp' in dataframe.columns:
            df_copy = dataframe.copy()
            df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')

            min_date = df_copy['timestamp'].min()
            max_date = df_copy['timestamp'].max()

            if pd.notna(min_date) and pd.notna(max_date):
                date_range = f"from {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        
        stats_doc = (
            f"Transaction dataset for tenant {tenant_id}: "
            f"{total_txns} total transactions involving {unique_senders} unique senders "
            f"and {unique_receivers} unique receivers {date_range}. "
            f"Total transaction volume: ${total_amount:,.2f}, "
            f"average transaction amount: ${avg_amount:,.2f}."
        )

        documents.append(stats_doc)
        metadata.append({
            "doc_id": "stats_summary",
            "category": "statistics",
            "total_transactions": total_txns,
            "date_range_start": min_date.isoformat() if pd.notna(min_date) else None,
            "date_range_end": max_date.isoformat() if pd.notna(max_date) else None
        })
        
        # 2. Country distribution
        if 'sender_country' in dataframe.columns:
            country_dist = dataframe['sender_country'].value_counts().head(10)

            countries_text = ", ".join([f"{country} ({count} txns)" for country, count in country_dist.items()])
            country_doc = f"Geographic distribution: Top sender countries are {countries_text}."

            documents.append(country_doc)
            metadata.append({
                "doc_id": "country_distribution",
                "category": "geographic",
                "top_countries": dict(country_dist.to_dict())
            })
        
        # 3. Transaction method distribution
        if 'txn_method' in dataframe.columns:
            method_dist = dataframe['txn_method'].value_counts().head(10)
            methods_text = ", ".join([f"{method} ({count} txns)" for method, count in method_dist.items()])

            method_doc = f"Payment methods used: {methods_text}."
            
            documents.append(method_doc)
            metadata.append({
                "doc_id": "payment_methods",
                "category": "payment_methods",
                "methods": dict(method_dist.to_dict())
            })
        
        # 4. KYC status distribution
        if 'sender_kyc' in dataframe.columns:
            kyc_dist = dataframe['sender_kyc'].value_counts()
            kyc_text = ", ".join([f"{status} ({count} txns)" for status, count in kyc_dist.items()])

            kyc_doc = f"KYC verification status: {kyc_text}."

            documents.append(kyc_doc)
            metadata.append({
                "doc_id": "kyc_distribution",
                "category": "compliance",
                "kyc_statuses": dict(kyc_dist.to_dict())
            })
        
        # 5. High-value transactions (top 10)
        if 'amount' in dataframe.columns and len(dataframe) > 0:
            high_value = dataframe.nlargest(min(10, len(dataframe)), 'amount')
            
            for idx, row in high_value.iterrows():
                sender = row.get('sender', 'Unknown')
                receiver = row.get('receiver', 'Unknown')
                amount = row.get('amount', 0)
                timestamp = row.get('timestamp', 'Unknown')
                country = row.get('sender_country', 'Unknown')
                method = row.get('txn_method', 'Unknown')
                
                doc = (
                    f"High-value transaction: {sender} sent ${amount:,.2f} to {receiver} "
                    f"on {timestamp} using {method} from {country}."
                )

                documents.append(doc)
                metadata.append({
                    "doc_id": f"high_value_txn_{idx}",
                    "category": "high_value_transaction",
                    "amount": float(amount),
                    "sender": sender,
                    "receiver": receiver,
                    "timestamp": str(timestamp)
                })
        
        # 6. Time-based patterns
        if 'timestamp' in dataframe.columns:
            df_copy = dataframe.copy()
            df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
            df_copy['hour'] = df_copy['timestamp'].dt.hour
            df_copy['day_of_week'] = df_copy['timestamp'].dt.day_name()
            
            hour_dist = df_copy['hour'].value_counts().head(5)
            hours_text = ", ".join([f"{hour}:00 ({count} txns)" for hour, count in hour_dist.items()])
            time_doc = f"Peak transaction hours: {hours_text}."
            
            documents.append(time_doc)
            metadata.append({
                "doc_id": "time_patterns",
                "category": "temporal",
                "peak_hours": dict(hour_dist.to_dict())
            })
        
        return documents, metadata


    def _create_fraud_ring_documents(
        self, 
        summary_df: pd.DataFrame, 
        report: Dict, 
        tenant_id: str
    ) -> Tuple[List[str], List[Dict]]:
        
        """
        Creates semantic documents from fraud detection results for embedding.
        
        Args:
            summary_df: Summary DataFrame from detection engine
            report: Full detection report
            tenant_id: User ID
            
        Returns:
            Tuple of (documents, metadata)
        """

        documents = []
        metadata = []
        
        # 1. Global detection summary
        summary = report.get('summary', {})
        pattern_detections = report.get('pattern_detections', {})
        
        summary_doc = (
            f"Fraud detection analysis for tenant {tenant_id}: "
            f"Analyzed {summary.get('total_accounts_analyzed', 0)} accounts, "
            f"flagged {summary.get('suspicious_accounts_flagged', 0)} as suspicious, "
            f"detected {summary.get('fraud_rings_detected', 0)} fraud rings. "
            f"Detection threshold: {summary.get('threshold_used', 0)}. "
            f"Processing time: {summary.get('processing_time_seconds', 0)} seconds."
        )

        documents.append(summary_doc)
        metadata.append({
            "doc_id": "detection_summary",
            "category": "summary",
            **summary
        })
        
        # 2. Pattern detection breakdown
        pattern_list = []
        for pattern, count in pattern_detections.items():
            if count > 0:
                pattern_list.append(f"{count} {pattern}")
        
        if pattern_list:
            pattern_doc = f"Detected fraud patterns: {', '.join(pattern_list)}."

            documents.append(pattern_doc)
            metadata.append({
                "doc_id": "pattern_breakdown",
                "category": "patterns",
                **pattern_detections
            })
        
        # 3. Individual fraud rings
        if not summary_df.empty:
            for idx, row in summary_df.iterrows():
                ring_id = row.get('Ring ID', 'Unknown')
                pattern_type = row.get('Pattern Type', 'Unknown')
                member_count = row.get('Member Count', 0)
                risk_score = row.get('Risk Score', 0)
                risk_category = row.get('Risk Category', 'Unknown')
                
                # Get member accounts (limit to first 10)
                members = row.get('Member Account IDs', '')
                if isinstance(members, str):
                    member_list = members.split(', ')
                    members_short = ', '.join(member_list[:10])

                    if len(member_list) > 10:
                        members_short += f" and {len(member_list) - 10} more"

                else:
                    members_short = str(members)
                    member_list = [str(members)]
                
                ring_doc = (
                    f"Fraud Ring {ring_id} detected with {risk_category} risk level. "
                    f"Pattern: {pattern_type}. Involves {member_count} accounts: {members_short}. "
                    f"Risk score: {risk_score}/100."
                )

                documents.append(ring_doc)
                metadata.append({
                    "doc_id": f"fraud_ring_{ring_id}",
                    "category": "fraud_ring",
                    "ring_id": ring_id,
                    "pattern_type": pattern_type,
                    "member_count": int(member_count),
                    "risk_score": float(risk_score),
                    "risk_category": risk_category,
                    "member_accounts": member_list
                })
        
        # 4. High-risk suspicious accounts
        suspicious_accounts = report.get('suspicious_accounts', [])
        high_risk_accounts = [acc for acc in suspicious_accounts if acc.get('risk_level') == 'HIGH']
        
        for acc in high_risk_accounts[:20]:  # Limit to top 20
            account_id = acc.get('account_id', 'Unknown')
            score = acc.get('suspicion_score', 0)
            patterns = ', '.join(acc.get('detected_patterns', []))
            ring_id = acc.get('ring_id')
            
            acc_doc = (
                f"High-risk account {account_id} flagged with suspicion score {score}/100. "
                f"Detected patterns: {patterns}."
            )

            if ring_id:
                acc_doc += f" Member of fraud ring {ring_id}."
            
            documents.append(acc_doc)
            metadata.append({
                "doc_id": f"suspicious_account_{account_id}",
                "category": "suspicious_account",
                "account_id": account_id,
                "suspicion_score": float(score),
                "risk_level": "HIGH",
                "patterns": acc.get('detected_patterns', []),
                "ring_id": ring_id
            })
        
        return documents, metadata
    

    async def _embed_and_store_documents(
        self, 
        documents: List[str],
        metadata: List[Dict],
        document_type: str,
        tenant_id: str,
        upload_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Embeds documents and stores them in tenant-specific FAISS index.
        
        Args:
            documents: List of text documents to embed
            metadata: List of metadata dictionaries (one per document)
            document_type: Type of documents ('transactions' or 'fraud_detection')
            tenant_id: User ID
            upload_metadata: Additional metadata about the upload
            
        Returns:
            Dictionary with embedding and storage statistics
        """
        if not documents:
            # print(f"[{tenant_id}] No documents to embed")
            return {"status": "skipped", "reason": "no_documents"}
        
        # print(f"\n[{tenant_id}] 🔄 Embedding {len(documents)} {document_type} documents...")
        
        # Embed documents
        embeddings = self.embedder.embed_documents(documents)
        
        # print(f"[{tenant_id}] ✅ Generated {len(embeddings)} embeddings")
        # print(f"[{tenant_id}] 📊 Embedding dimension: {len(embeddings[0]) if embeddings else 0}")
        
        # Add upload metadata to each document's metadata
        enhanced_metadata = []
        for meta in metadata:
            enhanced_meta = {
                **meta,
                **(upload_metadata or {})
            }
            enhanced_metadata.append(enhanced_meta)
        
        # Store in FAISS index
        # print(f"[{tenant_id}] 💾 Storing embeddings in FAISS index...")
        faiss_stats = self.vector_store.add_documents(
            tenant_id=tenant_id,
            embeddings=embeddings,
            documents=documents,
            metadata=enhanced_metadata,
            document_type=document_type
        )
        
        # Get index statistics
        index_stats = self.vector_store.get_index_stats(tenant_id)
        
        embedding_stats = {
            "status": "success",
            "document_type": document_type,
            "tenant_id": tenant_id,
            "documents_embedded": len(documents),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "cache_size": self.embedder.get_cache_size(),
            "faiss_stats": faiss_stats,
            "index_stats": index_stats
        }
        
        # print(f"[{tenant_id}] ✅ Stored in FAISS: {faiss_stats}")
        
        return embedding_stats


    async def _bulk_insert_transactions(
        self, 
        dataframe: pd.DataFrame, 
        tenant_id: str
    ) -> None:
        """
        Upserts transaction rows — skips rows whose transaction_id already exists
        for this tenant so re-uploading the same file does not create duplicates.

        Args:
            dataframe: Transaction data from CSV
            tenant_id: User ID from User table

        Raises:
            HTTPException: If database operation fails
        """
        from sqlalchemy import delete as sa_delete

        df = dataframe.copy()
        df['tenant_user_id'] = tenant_id

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        column_mapping = {
            'transaction_id': 'transaction_id',
            'sender': 'sender',
            'receiver': 'receiver',
            'amount': 'amount',
            'timestamp': 'timestamp',
            'sender_country': 'sender_country',
            'receiver_country': 'receiver_country',
            'sender_kyc': 'sender_kyc',
            'txn_method': 'txn_method',
            'device_id': 'device_id',
            'sender_acct_age': 'sender_acct_age',
            'velocity_mins': 'velocity_mins',
            'is_round_amount': 'is_round_amount',
            'tenant_user_id': 'tenant_user_id'
        }

        available_cols = [col for col in column_mapping.keys() if col in df.columns]
        df_to_insert = df[available_cols].copy()

        records = df_to_insert.replace({
            pd.NA: None,
            pd.NaT: None,
            float('nan'): None
        }).to_dict(orient="records")

        incoming_ids = [r['transaction_id'] for r in records if r.get('transaction_id')]

        try:
            if incoming_ids:
                # Delete existing rows for these exact transaction IDs under this tenant
                await self.db.execute(
                    sa_delete(Transaction).where(
                        Transaction.tenant_user_id == tenant_id,
                        Transaction.transaction_id.in_(incoming_ids)
                    )
                )

            for i in range(0, len(records), self.CHUNK_SIZE):
                chunk = records[i: i + self.CHUNK_SIZE]
                await self.db.execute(insert(Transaction).values(chunk))

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save transactions: {e}"
            )

    
    async def _bulk_insert_summary(
        self, 
        summary_df: pd.DataFrame, 
        tenant_id: str
    ):
        """
        Upserts fraud ring summaries into the database.
        Deletes any existing rings for this tenant first so that re-uploading
        a new file always reflects the latest detection results (no stale rings).
        Uses INSERT OR REPLACE semantics to handle the primary-key conflict that
        caused the 500 error when the same file was uploaded more than once.

        Args:
            summary_df: Summary DataFrame from MainEngine.summary_table()
            tenant_id: User ID from User table

        Raises:
            HTTPException: If database operation fails
        """
        from sqlalchemy import delete

        if summary_df.empty:
            return

        df = summary_df.copy()
        df['tenant_user_id'] = tenant_id
        df['created_at'] = datetime.utcnow()

        column_mapping = {
            "Ring ID": "ring_id",
            "Pattern Type": "pattern_type",
            "Member Count": "member_count",
            "Risk Score": "risk_score",
            "Risk Category": "risk_category",
            "Member Account IDs": "member_accounts"
        }
        df = df.rename(columns=column_mapping)

        db_columns = [
            'ring_id',
            'tenant_user_id',
            'pattern_type',
            'member_count',
            'risk_score',
            'risk_category',
            'member_accounts',
            'created_at'
        ]

        available_cols = [col for col in db_columns if col in df.columns]
        df = df[available_cols]

        records = df.replace({
            pd.NA: None,
            pd.NaT: None,
            float('nan'): None
        }).to_dict(orient="records")

        try:
            await self.db.execute(
                delete(FraudRingSummary).where(
                    FraudRingSummary.tenant_user_id == tenant_id
                )
            )

            stmt = insert(FraudRingSummary).values(records)
            await self.db.execute(stmt)
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save fraud ring summary: {e}"
            )
        

    async def _run_fraud_detection(
        self,
        dataframe: pd.DataFrame,
        tenant_id: str,
        cycle_length: int = 8, 
        ground_truth_labels: Optional[Dict] = None
    ) -> Dict:
        
        """
        Runs fraud detection pipeline on transaction data.
        
        Args:
            dataframe: Transaction data
            tenant_id: User ID
            cycle_length: Maximum cycle length to detect (3-8)
            ground_truth_labels: Optional ground truth for metrics
            
        Returns:
            Detection results including summary DataFrame and report
        """

        graph = Graph(raw_dataframe=dataframe)

        engine = MainEngine(
            graph=graph,
            cycle_length=cycle_length,
            ground_truth_labels=ground_truth_labels
        )

        report = engine.run_full_pipeline(compute_metrics=ground_truth_labels is not None)

        fraud_rings = report["fraud_rings"]
        account_scores = report["account_scores"]
        
        summary_df = engine.summary_table(
            fraud_rings=fraud_rings,
            account_scores=account_scores
        )

        return {
            "report": report,
            "summary_df": summary_df,
            "account_scores": account_scores
        }


    async def process_csv_pipeline(
        self,
        file_path: str,
        tenant_id: str,
        filename: str = None,
        cycle_length: int = 8,
        save_transactions: bool = True,
        save_summary: bool = True,
        embed_transactions: bool = True,
        embed_results: bool = True,
        ground_truth_labels: Optional[Dict] = None
    ) -> Dict:
        
        """
        Master pipeline: CSV processing, fraud detection, database storage, and FAISS indexing.
        Each upload appends to the tenant's existing FAISS index.
        """
        
        # print(f"[{tenant_id}] Starting Data Ingestion Pipeline...")

        upload_timestamp = datetime.utcnow().isoformat()

        try: 
            from database.model import User 

            result = await self.db.execute(
                select(User).where(User.user_id == tenant_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with ID {tenant_id} not found"
                )
            
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {file_path}"
                )
            
            df = pd.read_csv(file_path)

            transaction_embedding_stats = None
            if embed_transactions:

                transaction_docs, transaction_meta = self._create_transaction_documents(df, tenant_id)
                
                upload_meta = {
                    "source_file": filename or os.path.basename(file_path),
                    "upload_timestamp": upload_timestamp,
                    "total_transactions": len(df)
                }
                
                transaction_embedding_stats = await self._embed_and_store_documents(
                    documents=transaction_docs,
                    metadata=transaction_meta,
                    document_type="transactions",
                    tenant_id=tenant_id,
                    upload_metadata=upload_meta
                )

            if save_transactions:
                await self._bulk_insert_transactions(dataframe=df, tenant_id=tenant_id)

            detection_results = await self._run_fraud_detection(
                dataframe=df,
                tenant_id=tenant_id,
                cycle_length=cycle_length,
                ground_truth_labels=ground_truth_labels
            )

            detection_embedding_stats = None
            if embed_results:
                fraud_docs, fraud_meta = self._create_fraud_ring_documents(
                    summary_df=detection_results["summary_df"],
                    report=detection_results["report"],
                    tenant_id=tenant_id
                )
                
                upload_meta = {
                    "source_file": filename or os.path.basename(file_path),
                    "upload_timestamp": upload_timestamp,
                    "fraud_rings_detected": len(detection_results["report"]["fraud_rings"]),
                    "suspicious_accounts": len(detection_results["report"]["suspicious_accounts"])
                }
                
                detection_embedding_stats = await self._embed_and_store_documents(
                    documents=fraud_docs,
                    metadata=fraud_meta,
                    document_type="fraud_detection",
                    tenant_id=tenant_id,
                    upload_metadata=upload_meta
                )

            if save_summary:
                await self._bulk_insert_summary(
                    summary_df=detection_results["summary_df"],
                    tenant_id=tenant_id
                )

            if os.path.exists(file_path):
                os.remove(file_path)


            return {
                "status": "success",
                "tenant_id": tenant_id,
                "tenant_email": user.email_id,
                "tenant_organization": user.organization,
                "transactions_processed": len(df),
                "suspicious_accounts": len(detection_results["report"]["suspicious_accounts"]),
                "fraud_rings_detected": len(detection_results["report"]["fraud_rings"]),
                "summary": detection_results["report"]["summary"],
                "pattern_detections": detection_results["report"]["pattern_detections"],
                "embedding_stats": {
                    "transaction_embeddings": transaction_embedding_stats,
                    "detection_embeddings": detection_embedding_stats,
                    "total_cache_size": self.embedder.get_cache_size()
                }
            }


        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Pipeline failed: {str(e)}"
            )
        

    async def process_upload_file(
        self,
        file: UploadFile,
        tenant_id: str,
        temp_dir: str = "temp/",
        **kwargs
    ) -> Dict:
        """Processes an uploaded file through the complete pipeline with FAISS indexing."""

        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{file.filename} is not a CSV file"
            )
        
        os.makedirs(temp_dir, exist_ok=True)


        import time
        timestamp = int(time.time())
        temp_path = os.path.join(temp_dir, f"{tenant_id}_{timestamp}_{file.filename}")
        
        try:
            contents = await file.read()
            
            try:
                decoded = contents.decode("utf-8")
            except UnicodeDecodeError:
                decoded = contents.decode("latin-1")
            
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(decoded)
            
            result = await self.process_csv_pipeline(
                file_path=temp_path,
                tenant_id=tenant_id,
                filename=file.filename,
                **kwargs
            )
            
            return result
            
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
            
        finally:
            await file.close()

    
    async def get_tenant_index_stats(self, tenant_id: str) -> Optional[Dict]:
        """Get statistics about tenant's FAISS index."""
        return self.vector_store.get_index_stats(tenant_id)


    async def delete_tenant_index(self, tenant_id: str) -> bool:
        """Delete tenant's entire FAISS index."""
        return self.vector_store.delete_index(tenant_id)


    async def get_user_transactions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Retrieves transactions for a specific tenant.
        
        Args:
            tenant_id: User ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of transaction records
        """
        from sqlalchemy import desc

        stmt = (
            select(Transaction)
            .where(Transaction.tenant_user_id == tenant_id)
            .order_by(desc(Transaction.timestamp))
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()
        
        return [
            {
                "id": txn.id,
                "transaction_id": txn.transaction_id,
                "sender": txn.sender,
                "receiver": txn.receiver,
                "amount": float(txn.amount) if txn.amount else None,
                "timestamp": txn.timestamp.isoformat() if txn.timestamp else None,
                "sender_country": txn.sender_country,
                "receiver_country": txn.receiver_country,
                "sender_kyc": txn.sender_kyc,
                "txn_method": txn.txn_method,
                "device_id": txn.device_id
            }
            for txn in transactions
        ]


    async def get_user_fraud_rings(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Retrieves fraud rings for a specific tenant.
        
        Args:
            tenant_id: User ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of fraud ring records
        """
        from sqlalchemy import desc
        
        stmt = (
            select(FraudRingSummary)
            .where(FraudRingSummary.tenant_user_id == tenant_id)
            .order_by(desc(FraudRingSummary.risk_score))
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(stmt)
        rings = result.scalars().all()
        
        return [
            {
                "ring_id": ring.ring_id,
                "pattern_type": ring.pattern_type,
                "member_count": ring.member_count,
                "risk_score": float(ring.risk_score) if ring.risk_score else None,
                "risk_category": ring.risk_category,
                "member_accounts": ring.member_accounts,
                "created_at": ring.created_at.isoformat() if ring.created_at else None
            }
            for ring in rings
        ]
    