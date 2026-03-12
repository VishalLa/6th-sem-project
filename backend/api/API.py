from fastapi import (
    APIRouter,
    status,
    UploadFile
)
from typing import List
from .main_engine import Detect, DownLoad_JSON

route = APIRouter(tags=["input"])

@route.post(
    "/input/files",
    status_code=status.HTTP_200_OK
)
async def get_files(files: List[UploadFile]):
    detect = Detect()

    out_dict = await detect.handle_files(files=files)

    report = await detect.run_detction_pipeline(input_dict=out_dict)
    return report

@route.get(
    "/show/output/files",
    status_code=status.HTTP_200_OK
)
async def show_file():
    json_out_handler = DownLoad_JSON()

    output = await json_out_handler.show_json_files()

    return output

@route.get(
    "/download/{file_name}",
    status_code=status.HTTP_200_OK
)
async def download_file(file_name: str):
    json_out_handler = DownLoad_JSON()

    return await json_out_handler.download_file(file_name=file_name)

