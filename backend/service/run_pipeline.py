import os
import json

from fastapi import (
    HTTPException,
    status,
    UploadFile
)
from fastapi.responses import FileResponse
from io import StringIO
from typing import List, Dict, Optional
import pandas as pd

from graphs.engine import MainEngine
from graphs.build_graph import Graph


class Detect:
    """
    Handles fraud detection pipeline for uploaded CSV files.
    Processes files, runs detection algorithms, and generates tenant-specific reports.
    """

    def __init__(self, output_base_path: str = "output/"):
        """
        Initialize Detect with base output path.
        
        Args:
            output_base_path: Base directory for all outputs
        """
        self.output_base_path = output_base_path


    def _get_tenant_output_path(self, tenant_id: str) -> str:
        """
        Get tenant-specific output directory.
        
        Args:
            tenant_id: User ID
            
        Returns:
            Path to tenant's output directory
        """
        tenant_path = os.path.join(self.output_base_path, tenant_id)
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
        Saves results to tenant-specific directory.
        
        Args:
            input_dict: Dictionary mapping filename to Graph object
            tenant_id: User ID (for tenant-specific storage)
            cycle_length: Maximum cycle length to detect (3-8)
            ground_truth_labels: Optional ground truth for metrics
            compute_metrics: Whether to compute performance metrics
            
        Returns:
            Dictionary containing results for each file
        """

        output_path = self._get_tenant_output_path(tenant_id)

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
            json_path = os.path.join(output_path, json_name)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=4, default=str)

            # print(f"[✓] Saved analysis for '{filename}' → {json_path}")

            csv_filename = f"{safe_name}_summary.csv"
            csv_path = os.path.join(output_path, csv_filename)

            if not summary_df.empty:
                summary_df.to_csv(csv_path, index=False)
                # print(f"\n💾 Saved summary CSV: {csv_path}")

            all_results[filename] = {
                "report": json_report,
                "summary_df": summary_df,
                "summary_records": summary_df.to_dict(orient="records") if not summary_df.empty else [],
                "account_scores": account_scores,  
                "json_path": json_path,
                "csv_path": csv_path if not summary_df.empty else None
            }

        return all_results
