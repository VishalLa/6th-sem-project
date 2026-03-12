import os
import json

from fastapi import (
    HTTPException,
    status,
    UploadFile
)
from fastapi.responses import FileResponse
from io import StringIO
from typing import List
import pandas as pd

from graphs.engine import MainEngine
from graphs.build_graph import Graph


class Detect:

    async def handle_files(self, files: List[UploadFile]) -> dict[str, Graph]:

        output_dic: dict[str, Graph] = {}

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
        input_dict: dict[str, Graph],
        output_path: str = "output/"
    ) -> dict:

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        all_results: dict = {}

        for filename, graph in input_dict.items():

            algo   = MainEngine(graph=graph)
            report = algo.run_full_pipeline()

            fraud_rings    = report["fraud_rings"]
            account_scores = report["account_scores"]

            # Build summary DataFrame from the ring + score data
            summary_df = algo.summary_table(
                fraud_rings=fraud_rings,
                account_scores=account_scores
            )

            # Save JSON report (strip internal account_scores key)
            json_report = {k: v for k, v in report.items() if k != "account_scores"}

            safe_name = filename.split(".")[0]
            file_name = f"{safe_name}_analysis.json"
            full_path = os.path.join(output_path, file_name)

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=4, default=str)

            print(f"[✓] Saved analysis for '{filename}' → {full_path}")

            all_results[filename] = {
                "report":    json_report,
                "summary":   summary_df.to_dict(orient="records"),
                "saved_to":  full_path
            }

        return all_results


class DownLoad_JSON:
    def __init__(self):
        self.output_dir_path = "output/"

    async def show_json_files(self):
        try:
            if not os.path.exists(self.output_dir_path):
                return {
                    "files": [],
                    "message": f"Directory '{self.output_dir_path}' not found."
                }
            files = [f for f in os.listdir(self.output_dir_path) if f.endswith(".json")]
            return {
                "files": [
                    {
                        "name": f,
                        "download_url": f"/download/{f}"
                    }
                    for f in files
                ]
            }
        except Exception as e:
            return {"files": [], "error": str(e)}

    async def download_file(self, file_name: str):

        file_name = f"{file_name}.json"

        if ".." in file_name or "/" in file_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )

        file_path = os.path.join(self.output_dir_path, file_name)

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
    