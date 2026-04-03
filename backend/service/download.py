import json
import io
import csv
from typing import Dict

from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from database.model import JSONStore 


# TODO: Updaate this entire code so it extracts all the saved stuff form postgress database


class DownLoad_JSON:
    
    """
    Handles listing, downloading, and deleting of generated JSON reports 
    stored directly in the PostgreSQL database.
    """

    def __init__(self, db: AsyncSession):
        self.db = db


    async def show_json_files(self, tenant_id: str) -> Dict:
        """
        Lists all JSON files for a specific tenant from the database.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Dictionary with list of tenant's files and download URLs
        """

        try:
            query = select(JSONStore.filename).where(JSONStore.tenant_user_id == tenant_id)

            result = await self.db.execute(query)
            filenames = result.scalars().all()

            if not filenames:
                return {
                    "tenant_id": tenant_id,
                    "files": [],
                    "message": f"No reports found for tenant {tenant_id}."
                }


            file_groups = {}
            for file_name in filenames:
                base_name = file_name.replace("_analysis.json", "").replace(".json", "")
                
                file_groups[base_name] = {
                    "analysis_name": base_name,
                    "json_file": file_name,
                    "json_download_url": f"/download/json/{tenant_id}/{base_name}",
                    "csv_download_url": f"/download/csv/{tenant_id}/{base_name}"
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


    async def download_json_file(self, tenant_id: str, file_name: str) -> Response:
        """
        Downloads a specific JSON file for a tenant from the database.
        
        Args:
            tenant_id: User ID
            file_name: Name of file (without .json extension)
            
        Returns:
            FastAPI Response configured to download as a JSON file
        """

        if not file_name.endswith(".json"):
            file_name = f"{file_name}.json"

        # Query the database for the specific file
        query = select(JSONStore).where(
            JSONStore.tenant_user_id == tenant_id,
            JSONStore.filename == file_name
        )

        result = await self.db.execute(query)
        db_file = result.scalar_one_or_none()

        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_name}' not found for tenant {tenant_id}"
            )

        # Convert the JSONB data back to a formatted string
        json_str = json.dumps(db_file.json_data, indent=4)

        # Return as a downloadable file
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
        )


    async def download_csv_file(self, tenant_id: str, file_name: str) -> StreamingResponse:
        """
        Dynamically generates and downloads a CSV summary from the stored JSON data.
        
        Args:
            tenant_id: User ID
            file_name: Base name of file (without extension)
            
        Returns:
            StreamingResponse containing the generated CSV
        """
        # Look for the source JSON file in the DB
        json_filename = f"{file_name}.json"
        if file_name.endswith("_summary"):
            json_filename = file_name.replace("_summary", "_analysis.json")

        query = select(JSONStore).where(
            JSONStore.tenant_user_id == tenant_id,
            JSONStore.filename == json_filename
        )

        result = await self.db.execute(query)
        db_file = result.scalar_one_or_none()

        if not db_file or not db_file.json_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source data for '{file_name}' not found"
            )

        # Generate CSV on the fly from the JSON data
        output = io.StringIO()
        writer = csv.writer(output)
        
        data = db_file.json_data
        
        # Handle dict vs list of dicts for CSV conversion
        if isinstance(data, dict):
            writer.writerow(data.keys())
            writer.writerow(data.values())

        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):

            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())

        output.seek(0)
        
        download_filename = f"{file_name}_summary.csv" if not file_name.endswith(".csv") else file_name

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
        )


    async def delete_analysis(self, tenant_id: str, analysis_name: str) -> Dict:
        """
        Deletes the JSON file (and therefore the dynamic CSV) for a specific analysis.
        
        Args:
            tenant_id: User ID
            analysis_name: Base name of the analysis
            
        Returns:
            Deletion status
        """
        json_filename = f"{analysis_name}_analysis.json"
        if not analysis_name.endswith("_analysis"):
            json_filename = f"{analysis_name}.json"

        # Execute a delete query
        query = delete(JSONStore).where(
            JSONStore.tenant_user_id == tenant_id,
            JSONStore.filename == json_filename
        )
        
        result = await self.db.execute(query)
        await self.db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis '{analysis_name}' not found for tenant {tenant_id}"
            )

        return {
            "tenant_id": tenant_id,
            "analysis_name": analysis_name,
            "deleted_files": [json_filename],
            "status": "success"
        }
    
