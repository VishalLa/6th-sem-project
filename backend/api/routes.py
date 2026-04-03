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

        # Run detection pipeline with tenant isolation
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
        
        # Instantly delete this specific user's temporary folder
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
    - Fraud detection
    - Database storage
    - Embedding generation
    - FAISS indexing
    
    Each upload appends to the tenant's existing FAISS index.
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
        
        # Convert NumPy types to JSON-serializable types
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
    Returns JSON and CSV files grouped by analysis.
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
    Retrieve transactions for the current user from database.
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
    Retrieve fraud rings detected for the current user from database.
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
    "/index",
    status_code=status.HTTP_200_OK,
    tags=["Data Retrieval"]
)
async def delete_tenant_index(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete the FAISS index for the current user's tenant.
    """
    try:
        service = DataIngestionService(db)

        success = await service.delete_tenant_index(tenant_id=current_user.user_id)

        if success:
            return {"status": "success", "message": "FAISS index deleted."}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete FAISS index."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}"
        )



@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["System"]
)
async def health_check():
    """
    Check if the API is running.
    """
    return {
        "status": "healthy",
        "service": "Money Laundering Detection API",
        "version": "1.0.0"
    }

