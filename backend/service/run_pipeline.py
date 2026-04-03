import os
import json
import shutil
import time

from fastapi import (
    HTTPException,
    status,
    UploadFile
)

from io import StringIO
from typing import List, Dict, Optional
import pandas as pd

from backend.graphs.engine import MainEngine
from backend.graphs.build_graph import Graph


class Detect: 

    """
    Handles fraud detection pipeline for uploaded CSV files.
    Processes files, runs detection algorithms, and generates tenant-specific reports.
    """

    def __init__(self, temp_dir: str = "temp/"):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    
    def _get_tenant_temp_path(self, tenant_id: str) -> str:
        """
        Get tenant-specific temp directory.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Path to tenant's output directory
        """
        tenant_path = os.path.join(self.temp_dir, tenant_id)
        os.makedirs(tenant_path, exist_ok=True)
        return tenant_path


    async def handle_files(self, files: List[UploadFile]) -> dict[str, Graph]:

        """
        Processes uploaded CSV files and converts them to Graph objects.
        
        Args:
            files: List of uploaded CSV files
            
        Returns:
            Dictionary mapping filename to Graph object
            
        Raises:
            HTTPException: If files are invalid or processing fails
        """

        output_dic: Dict[str, Graph] = {}

        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files uploaded"
            )

        for file in files:

            if not file.filename.lower().endswith(".csv"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{file.filename} is not a csv file"
                )

            try:
                contents = await file.read()

                try:
                    decoded = contents.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = contents.decode("latin-1")

                df = pd.read_csv(StringIO(decoded), sep=None, engine="python")

                graph = Graph(raw_dataframe=df)
                output_dic[file.filename] = graph

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid CSV file {file.filename}: {str(e)}"
                )

            finally:
                await file.close()

        return output_dic
    

    async def run_detction_pipeline(
        self,
        input_dict: Dict[str, Graph],
        tenant_id: str,
        cycle_length: int = 8,
        ground_truth_labels: Optional[Dict] = None,
        compute_metrics: bool = True
    ) -> dict:
        
        """
        Runs fraud detection pipeline on all graphs for a specific tenant.
        Saves results to database.
        
        Args:
            input_dict: Dictionary mapping filename to Graph object
            tenant_id: User ID (for tenant-specific storage)
            cycle_length: Maximum cycle length to detect (3-8)
            ground_truth_labels: Optional ground truth for metrics
            compute_metrics: Whether to compute performance metrics
            
        Returns:
            Dictionary containing results for each file
        """

        tenent_temp_path = self._get_tenant_temp_path(tenant_id=tenant_id)

        all_results: Dict = {}

        for filename, graph in input_dict.items():

            algo = MainEngine(
                graph=graph,
                cycle_length=cycle_length,
                ground_truth_labels=ground_truth_labels
            )
            report = algo.run_full_pipeline(compute_metrics=compute_metrics)

            fraud_rings = report["fraud_rings"]
            account_scores = report["account_scores"]
            suspicious_accounts = report["suspicious_accounts"]
            pattern_detections = report["pattern_detections"]
            summary_info = report["summary"]

            # Build summary DataFrame from the ring + score data
            summary_df = algo.summary_table(
                fraud_rings=fraud_rings,
                account_scores=account_scores
            )

            # Save JSON report (strip internal account_scores key)
            json_report = {
                "tenant_id": tenant_id,
                "source_file": filename,
                "suspicious_accounts": suspicious_accounts,
                "fraud_rings": fraud_rings,
                "pattern_detections": pattern_detections,
                "summary": summary_info
            }


            safe_name = filename.rsplit(".", 1)[0]
            json_name = f"{safe_name}_analysis.json"
            json_path = os.path.join(tenent_temp_path, json_name)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=4, default=str)


            csv_filename = f"{safe_name}_summary.csv"
            csv_path = os.path.join(tenent_temp_path, csv_filename)

            all_results[filename] = {
                "report": json_report,
                "summary_df": summary_df,
                "summary_records": summary_df.to_dict(orient="records") if not summary_df.empty else [],
                "account_scores": account_scores,  
                "json_path": json_path,
                "csv_path": csv_path if not summary_df.empty else None
            }

        return all_results
    

    def clean_expired_session(
        self,
        expire_minutes: int = 1440
    ) -> None: 
        """
        Sweeps the temp directory and deletes any tenant folders older than the expire time.
        1440 minutes = 24 hours.
        """

        if not os.path.exists(self.temp_dir):
            return 
        
        now = time.time()

        expire_seconds = expire_minutes * 60

        for tenant_folder in os.listdir(self.temp_dir):
            folder_path = os.path.join(self.temp_dir, tenant_folder)
            
            if os.path.isdir(folder_path):

                folder_mtime = os.path.getmtime(folder_path)
                
                # If the folder is older than 24 hours, delete it
                if (now - folder_mtime) > expire_seconds:
                    try:
                        shutil.rmtree(folder_path, ignore_errors=True)
                    except Exception as e:
                        print(f"Failed to delete expired temp folder {folder_path}: {e}")


    def cleanup_specific_tenant(self, tenant_id: str) -> None:
        """
        Immediately deletes a specific tenant's temp folder (useful for a logout endpoint).
        """
        folder_path = self._get_tenant_temp_path(tenant_id)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)

    