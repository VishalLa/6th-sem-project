from fastapi import (
    APIRouter,
    Depends,
    status,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks
)
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db 
from database.model import User 

from service.download import DownLoad_JSON 
from service.ingestion import DataIngestionService 
from service.run_pipeline import Detect

from auth.deps import get_current_user 
from core.helper import convert_numpy_types


router = APIRouter()


@router.post(
    "/upload/detect",
    status_code=status.HTTP_200_OK,
    tags=["Fraud Detection"]
)
async def upload_and_detect(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    cycle_length: int = 8,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload CSV files and run fraud detection.
    Files are stored in tenant-specific directories.
    """

    try:
        detector = Detect(temp_dir="temp/")

        background_tasks.add_task(detector.clean_expired_session, expire_minutes=1440)

        graphs_dict = await detector.handle_files(files=files)

        results = await detector.run_detction_pipeline(
            input_dict=graphs_dict,
            tenant_id=current_user.user_id,
            cycle_length=cycle_length
        )

        results = convert_numpy_types(results)

        return {
            "status": "success",
            "message": "Fraud detection completed successfully",
            "tenant_id": current_user.user_id,
            "files_processed": len(results),
            "results": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fraud detection failed: {str(e)}"
        )
    

@router.post(
    "/session/cleanup",
    status_code=status.HTTP_200_OK,
    tags=["Session Management"]
)
async def cleanup_user_session(
    current_user: User = Depends(get_current_user)
):
    """
    Deletes the temporary files for the current user.
    Call this from the frontend when the user logs out or their token expires.
    """
    try:
        detector = Detect(temp_dir="output/")
        detector.cleanup_specific_tenant(tenant_id=current_user.user_id)
        
        return {
            "status": "success",
            "message": "User session files cleaned up successfully."
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean up session files: {str(e)}"
        )
    

@router.post(
    "/upload/full-pipeline",
    status_code=status.HTTP_200_OK,
    tags=["Fraud Detection"]
)
async def upload_full_pipeline(
    file: UploadFile = File(...),
    cycle_length: int = 8,
    save_transactions: bool = True,
    save_summary: bool = True,
    embed_transactions: bool = True,
    embed_results: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload CSV file and run complete pipeline:
    - Creates a new FileBatch
    - Fraud detection
    - Database storage (transactions, fraud rings, JSON report)
    - Embedding generation & FAISS indexing

    Returns batch_id so the client can reference this upload later.
    """

    try:
        service = DataIngestionService(db)
        
        result = await service.process_upload_file(
            file=file,
            tenant_id=current_user.user_id,
            cycle_length=cycle_length,
            save_transactions=save_transactions,
            save_summary=save_summary,
            embed_transactions=embed_transactions,
            embed_results=embed_results
        )
        
        result = convert_numpy_types(result)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {str(e)}"
        )


@router.get(
    "/my-reports",
    status_code=status.HTTP_200_OK,
    tags=["File Management"]
)
async def list_my_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    """
    List all analysis reports for the current user.
    """
    try:
        downloader = DownLoad_JSON(db=db)
        files = await downloader.show_json_files(tenant_id=current_user.user_id)

        if files is None:
            files = []

        return files
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reports: {str(e)}"
        )


@router.get(
    "/download/json/{file_name}",
    status_code=status.HTTP_200_OK,
    tags=["File Management"]
)
async def download_json_report(
    file_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a specific JSON analysis report.
    Users can only download their own files.
    """
    downloader = DownLoad_JSON(db=db)
    
    return await downloader.download_json_file(
        tenant_id=current_user.user_id,
        file_name=file_name
    )


@router.get(
    "/download/csv/{file_name}",
    status_code=status.HTTP_200_OK,
    tags=["File Management"]
)
async def download_csv_summary(
    file_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a specific CSV summary file.
    Users can only download their own files.
    """
    downloader = DownLoad_JSON(db=db)
    
    return await downloader.download_csv_file(
        tenant_id=current_user.user_id,
        file_name=file_name
    )


@router.delete(
    "/reports/{analysis_name}",
    status_code=status.HTTP_200_OK,
    tags=["File Management"]
)
async def delete_report(
    analysis_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete both JSON and CSV files for a specific analysis.
    """
    try:
        downloader = DownLoad_JSON(db=db)
        
        return await downloader.delete_analysis(
            tenant_id=current_user.user_id,
            analysis_name=analysis_name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete report: {str(e)}"
        )


@router.get(
    "/my-transactions",
    status_code=status.HTTP_200_OK,
    tags=["Data Retrieval"]
)
async def get_my_transactions(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve transactions for the current user from database (all batches).
    """
    try:
        service = DataIngestionService(db)
        
        transactions = await service.get_user_transactions(
            tenant_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "status": "success",
            "tenant_id": current_user.user_id,
            "total_returned": len(transactions),
            "limit": limit,
            "offset": offset,
            "transactions": transactions
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transactions: {str(e)}"
        )


@router.get(
    "/my-fraud-rings",
    status_code=status.HTTP_200_OK,
    tags=["Data Retrieval"]
)
async def get_my_fraud_rings(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve fraud rings for the current user from database (all batches).
    Sorted by risk score (highest first).
    """
    try:
        service = DataIngestionService(db)
        
        fraud_rings = await service.get_user_fraud_rings(
            tenant_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "status": "success",
            "tenant_id": current_user.user_id,
            "total_returned": len(fraud_rings),
            "limit": limit,
            "offset": offset,
            "fraud_rings": fraud_rings
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve fraud rings: {str(e)}"
        )


@router.delete(
    "/index/{batch_id}",
    status_code=status.HTTP_200_OK,
    tags=["Data Retrieval"]
)
async def delete_tenant_index(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete the FAISS index for a specific batch belonging to the current user.
    The batch_id is returned by /upload/full-pipeline.
    """
    try:
        service = DataIngestionService(db)

        success = await service.delete_tenant_index(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
        )

        if success:
            return {
                "status": "success",
                "message": f"FAISS index for batch {batch_id} deleted.",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No FAISS index found for batch {batch_id}.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}"
        )


@router.get(
    "/my-batches",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def list_my_batches(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all uploaded file batches for the current user, newest first.
    Each entry includes the original filename, transaction count, and fraud
    ring count — enough information to let the user pick a batch in a UI
    dropdown without fetching the heavy data first.

    Returns batch_id values that can be passed to the /batch/{batch_id}/*
    endpoints below.
    """
    try:
        service = DataIngestionService(db)

        batches = await service.get_user_batches(
            tenant_id=current_user.user_id,
            limit=limit,
            offset=offset,
        )

        return {
            "status":         "success",
            "tenant_id":      current_user.user_id,
            "total_returned": len(batches),
            "limit":          limit,
            "offset":         offset,
            "batches":        batches,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list batches: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}/download/json",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def download_batch_json(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download the JSON fraud detection report for a specific batch.
    Returns 404 if the batch doesn't exist, belongs to another user,
    or was uploaded with save_json_report=False.
    """
    try:
        downloader = DownLoad_JSON(db=db)
        return await downloader.download_json_by_batch(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download JSON for batch {batch_id}: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}/download/csv",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def download_batch_csv(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a CSV summary dynamically generated from the JSON report
    for a specific batch.
    Returns 404 if the batch or its report doesn't exist.
    """
    try:
        downloader = DownLoad_JSON(db=db)
        return await downloader.download_csv_by_batch(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download CSV for batch {batch_id}: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}/transactions",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def get_batch_transactions(
    batch_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve transactions for a specific uploaded file batch.
    Returns 404 if the batch doesn't exist or belongs to another user.
    """
    try:
        service = DataIngestionService(db)

        transactions = await service.get_batch_transactions(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
            limit=limit,
            offset=offset,
        )

        return {
            "status":         "success",
            "tenant_id":      current_user.user_id,
            "batch_id":       batch_id,
            "total_returned": len(transactions),
            "limit":          limit,
            "offset":         offset,
            "transactions":   transactions,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transactions for batch {batch_id}: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}/fraud-rings",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def get_batch_fraud_rings(
    batch_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve fraud rings detected in a specific uploaded file batch,
    sorted by risk score (highest first).
    Returns 404 if the batch doesn't exist or belongs to another user.
    """
    try:
        service = DataIngestionService(db)

        fraud_rings = await service.get_batch_fraud_rings(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
            limit=limit,
            offset=offset,
        )

        return {
            "status":         "success",
            "tenant_id":      current_user.user_id,
            "batch_id":       batch_id,
            "total_returned": len(fraud_rings),
            "limit":          limit,
            "offset":         offset,
            "fraud_rings":    fraud_rings,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve fraud rings for batch {batch_id}: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}/report",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def get_batch_report(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the full JSON fraud detection report for a specific batch.
    Returns 404 if the batch doesn't exist, belongs to another user, or
    has no report (e.g. save_json_report=False was passed on upload).
    """
    try:
        service = DataIngestionService(db)

        report = await service.get_batch_json_report(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
        )

        return {
            "status":    "success",
            "tenant_id": current_user.user_id,
            "batch_id":  batch_id,
            "report":    report,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve report for batch {batch_id}: {str(e)}"
        )


@router.delete(
    "/batch/{batch_id}",
    status_code=status.HTTP_200_OK,
    tags=["Batch Management"]
)
async def delete_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a specific upload batch and ALL its associated data:
    transactions, fraud rings, JSON report, and FAISS index.
    This is irreversible. Returns 404 if the batch doesn't exist or
    belongs to another user.
    """
    try:
        service = DataIngestionService(db)

        result = await service.delete_batch(
            tenant_id=current_user.user_id,
            batch_id=batch_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete batch {batch_id}: {str(e)}"
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["System"]
)
async def health_check():
    """Check if the API is running."""
    return {
        "status": "healthy",
        "service": "Money Laundering Detection API",
        "version": "1.0.0"
    }
