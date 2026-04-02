import os

from fastapi import (
    HTTPException,
    status,
)
from fastapi.responses import FileResponse
from typing import Dict


# TODO: Updaate this entire code so it extracts all the saved stuff form postgress database


class DownLoad_JSON:

    """
    Handles listing and downloading of generated JSON reports.
    """

    def __init__(self, output_dir_path: str = "output/"):
        """
        Initialize with base output directory.
        
        Args:
            output_base_path: Base directory containing tenant folders
        """
        self.output_dir_path = output_dir_path


    def _get_tenant_output_path(self, tenant_id: str) -> str:
        """Get tenant-specific output directory."""
        return os.path.join(self.output_dir_path, tenant_id)
    

    async def show_json_files(self, tenant_id: str):

        """
        Lists all JSON files for a specific tenant only.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Dictionary with list of tenant's files
        """

        try:
            tenant_path = self._get_tenant_output_path(tenant_id)
            
            if not os.path.exists(tenant_path):
                return {
                    "tenant_id": tenant_id,
                    "files": [],
                    "message": f"No reports found for tenant {tenant_id}."
                }
            json_files = [f for f in os.listdir(tenant_path) if f.endswith(".json")]
            csv_files = [f for f in os.listdir(tenant_path) if f.endswith(".csv")]

            file_groups = {}
            for json_file in json_files:
                base_name = json_file.replace("_analysis.json", "")
                csv_file = f"{base_name}_summary.csv"
                
                file_groups[base_name] = {
                    "analysis_name": base_name,
                    "json_file": json_file,
                    "json_download_url": f"/download/json/{tenant_id}/{json_file.rsplit('.', 1)[0]}",
                    "csv_file": csv_file if csv_file in csv_files else None,
                    "csv_download_url": f"/download/csv/{tenant_id}/{base_name}" if csv_file in csv_files else None
                }

                return {
                "tenant_id": tenant_id,
                "total_analyses": len(file_groups),
                "files": list(file_groups.values())
            }

        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "files": [], 
                "error": str(e)
            }


    async def download_json_file(self, tenant_id: str, file_name: str) -> FileResponse:
        """
        Downloads a specific JSON file for a tenant.
        
        Args:
            tenant_id: User ID
            file_name: Name of file (without .json extension)
            
        Returns:
            FileResponse with the JSON file
            
        Raises:
            HTTPException: If file not found or unauthorized
        """

        if not file_name.endswith(".json"):
            file_name = f"{file_name}.json"

        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )

        tenant_path = self._get_tenant_output_path(tenant_id)
        file_path = os.path.join(tenant_path, file_name)

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_name}' not found"
            )

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/json"
        )
    

    async def download_csv_file(self, tenant_id: str, file_name: str) -> FileResponse:
        """
        Downloads a specific CSV summary file for a tenant.
        
        Args:
            tenant_id: User ID
            file_name: Base name of file (without extension)
            
        Returns:
            FileResponse with the CSV file
            
        Raises:
            HTTPException: If file not found or unauthorized
        """

        if not file_name.endswith(".csv"):
            file_name = f"{file_name}_summary.csv"


        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )

        tenant_path = self._get_tenant_output_path(tenant_id)
        file_path = os.path.join(tenant_path, file_name)


        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_name}' not found for tenant {tenant_id}"
            )

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="text/csv"
        )
    

    async def delete_analysis(self, tenant_id: str, analysis_name: str) -> Dict:
        """
        Deletes both JSON and CSV files for a specific analysis.
        
        Args:
            tenant_id: User ID
            analysis_name: Base name of the analysis
            
        Returns:
            Deletion status
        """
        tenant_path = self._get_tenant_output_path(tenant_id)
        
        json_file = f"{analysis_name}_analysis.json"
        csv_file = f"{analysis_name}_summary.csv"
        
        deleted_files = []
        
        # Delete JSON
        json_path = os.path.join(tenant_path, json_file)
        if os.path.exists(json_path):
            os.remove(json_path)
            deleted_files.append(json_file)
        
        # Delete CSV
        csv_path = os.path.join(tenant_path, csv_file)
        if os.path.exists(csv_path):
            os.remove(csv_path)
            deleted_files.append(csv_file)
        
        if not deleted_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis '{analysis_name}' not found for tenant {tenant_id}"
            )
        
        return {
            "tenant_id": tenant_id,
            "analysis_name": analysis_name,
            "deleted_files": deleted_files,
            "status": "success"
        }

    