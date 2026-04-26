import json
import io
import csv
from typing import Dict, Optional, List

from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from database.model import JSONStore, FileBatch


class DownLoad_JSON:
    
    """
    Handles listing, downloading, and deleting of generated JSON reports
    stored in the PostgreSQL database.

    All queries join through FileBatch to verify tenant ownership — JSONStore
    no longer carries a direct tenant_user_id column.
    """

    def __init__(self, db: AsyncSession):
        self.db = db


    async def _get_json_store_for_tenant(
        self,
        tenant_id: str,
        *,
        batch_id: Optional[str] = None,
        filename: Optional[str] = None,
        report_id: Optional[int] = None,
    ) -> JSONStore:
        """
        Load a JSONStore row and verify it belongs to tenant_id via the
        FileBatch join.  At least one of batch_id / filename / report_id
        must be supplied as a filter.

        Raises HTTP 404 if the record is not found or not owned by the tenant.
        """
        stmt = (
            select(JSONStore)
            .join(JSONStore.batch)
            .where(FileBatch.tenant_user_id == tenant_id)
        )

        if batch_id is not None:
            stmt = stmt.where(JSONStore.batch_id == batch_id)
        if filename is not None:
            stmt = stmt.where(JSONStore.filename == filename)
        if report_id is not None:
            stmt = stmt.where(JSONStore.id == report_id)

        result  = await self.db.execute(stmt)
        db_file = result.scalar_one_or_none()

        if not db_file:
            detail = (
                f"Report not found"
                + (f" (batch_id={batch_id})"   if batch_id  else "")
                + (f" (filename={filename})"    if filename  else "")
                + (f" (id={report_id})"         if report_id else "")
                + f" for tenant {tenant_id}."
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

        return db_file


    async def show_json_files(self, tenant_id: str) -> Dict:
        """
        List all JSON reports for a tenant, joined through FileBatch.

        Returns a dict suitable for the /my-reports endpoint, including
        batch_id so the frontend can build batch-scoped download URLs.
        """
        try:
            stmt = (
                select(JSONStore)
                .join(JSONStore.batch)
                .where(FileBatch.tenant_user_id == tenant_id)
                .order_by(JSONStore.uploaded_at.desc())
            )

            result  = await self.db.execute(stmt)
            reports = result.scalars().all()

            if not reports:
                return {
                    "tenant_id": tenant_id,
                    "files":     [],
                    "message":   f"No reports found for tenant {tenant_id}.",
                }

            files: List[Dict] = []
            for report in reports:
                base_name = (
                    report.filename
                    .replace("_analysis.json", "")
                    .replace(".json", "")
                )
                files.append({
                    "id":               report.id,
                    "batch_id":         report.batch_id,
                    "analysis_name":    base_name,
                    "filename":         report.filename,
                    "uploaded_at":      report.uploaded_at.isoformat() if report.uploaded_at else None,
                    # Batch-scoped download URLs (preferred)
                    "json_download_url": f"/batch/{report.batch_id}/download/json",
                    "csv_download_url":  f"/batch/{report.batch_id}/download/csv",
                })

            return {
                "tenant_id":       tenant_id,
                "total_analyses":  len(files),
                "files":           files,
            }

        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "files":     [],
                "error":     str(e),
            }


    async def download_json_by_batch(
        self, tenant_id: str, batch_id: str
    ) -> Response:
        """
        Download the JSON report for a specific batch.

        Args:
            tenant_id: Authenticated user's UUID.
            batch_id:  Target FileBatch UUID.

        Returns:
            Downloadable JSON Response.
        """
        db_file  = await self._get_json_store_for_tenant(tenant_id, batch_id=batch_id)
        json_str = json.dumps(db_file.json_data, indent=4)

        return Response(
            content=json_str,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{db_file.filename}"'
            },
        )


    async def download_csv_by_batch(
        self, tenant_id: str, batch_id: str
    ) -> StreamingResponse:
        """
        Dynamically generate and download a CSV summary for a specific batch.

        Args:
            tenant_id: Authenticated user's UUID.
            batch_id:  Target FileBatch UUID.

        Returns:
            StreamingResponse containing the generated CSV.
        """
        db_file = await self._get_json_store_for_tenant(tenant_id, batch_id=batch_id)

        output  = io.StringIO()
        writer  = csv.writer(output)
        data    = db_file.json_data

        self._write_csv(writer, data)
        output.seek(0)

        base_name = (
            db_file.filename
            .replace("_analysis.json", "")
            .replace(".json", "")
        )
        csv_filename = f"{base_name}_summary.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{csv_filename}"'},
        )


    async def download_json_file(self, tenant_id: str, file_name: str) -> Response:
        """
        Download a JSON report by filename.
        Ownership is verified via the FileBatch join.

        Args:
            tenant_id: Authenticated user's UUID.
            file_name: Filename with or without .json extension.
        """
        if not file_name.endswith(".json"):
            file_name = f"{file_name}.json"

        db_file  = await self._get_json_store_for_tenant(tenant_id, filename=file_name)
        json_str = json.dumps(db_file.json_data, indent=4)

        return Response(
            content=json_str,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"'
            },
        )


    async def download_csv_file(
        self, tenant_id: str, file_name: str
    ) -> StreamingResponse:
        """
        Dynamically generate and download a CSV summary by filename.
        Ownership is verified via the FileBatch join.

        Args:
            tenant_id: Authenticated user's UUID.
            file_name: Base name of the file (with or without extension).
        """
        json_filename = f"{file_name}.json"
        if file_name.endswith("_summary"):
            json_filename = file_name.replace("_summary", "_analysis.json")

        db_file = await self._get_json_store_for_tenant(
            tenant_id, filename=json_filename
        )

        output = io.StringIO()
        writer = csv.writer(output)
        self._write_csv(writer, db_file.json_data)
        output.seek(0)

        csv_filename = (
            f"{file_name}_summary.csv"
            if not file_name.endswith(".csv")
            else file_name
        )

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{csv_filename}"'},
        )
    

    async def delete_analysis(self, tenant_id: str, analysis_name: str) -> Dict:
        """
        Delete the JSON report (and its dynamically generated CSV) by analysis name.
        Ownership is verified via the FileBatch join before deletion.

        Args:
            tenant_id:     Authenticated user's UUID.
            analysis_name: Base name of the analysis (no extension).
        """
        json_filename = (
            f"{analysis_name}.json"
            if analysis_name.endswith("_analysis")
            else f"{analysis_name}_analysis.json"
        )

        # Verify ownership first — raises 404 if not found / not owned
        db_file = await self._get_json_store_for_tenant(
            tenant_id, filename=json_filename
        )

        try:
            await self.db.delete(db_file)
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete analysis '{analysis_name}': {e}",
            )

        return {
            "tenant_id":     tenant_id,
            "analysis_name": analysis_name,
            "deleted_files": [json_filename],
            "status":        "success",
        }


    async def delete_by_batch(self, tenant_id: str, batch_id: str) -> Dict:
        """
        Delete the JSON report for a specific batch.
        Ownership is verified via the FileBatch join before deletion.

        Args:
            tenant_id: Authenticated user's UUID.
            batch_id:  Target FileBatch UUID.
        """
        db_file = await self._get_json_store_for_tenant(tenant_id, batch_id=batch_id)
        filename = db_file.filename

        try:
            await self.db.delete(db_file)
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete report for batch {batch_id}: {e}",
            )

        return {
            "tenant_id":     tenant_id,
            "batch_id":      batch_id,
            "deleted_files": [filename],
            "status":        "success",
        }
    

    @staticmethod
    def _write_csv(writer: csv.writer, data) -> None:
        """
        Write JSON data to a csv.writer in the most sensible shape.

        Handles three common structures:
        - dict of scalars           → two rows: header + values
        - list of dicts             → header row + one row per item
        - dict of lists (columnar)  → header row + one row per index
        """
        if isinstance(data, dict):
            # Check if values are all lists of equal length (columnar layout)
            values = list(data.values())
            if values and all(isinstance(v, list) for v in values):
                length = len(values[0])
                if all(len(v) == length for v in values):
                    writer.writerow(data.keys())
                    for i in range(length):
                        writer.writerow(v[i] for v in values)
                    return

            # Plain scalar dict
            writer.writerow(data.keys())
            writer.writerow(data.values())

        elif isinstance(data, list) and data and isinstance(data[0], dict):
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())

        else:
            # Fallback: dump as single cell
            writer.writerow(["data"])
            writer.writerow([json.dumps(data)])
            