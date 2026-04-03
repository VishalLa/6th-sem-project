from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any


class JSONStoreCreate(BaseModel):
    filename: str 
    json_data: Dict[str, Any]


class JSONStoreResponse(BaseModel):
    id: int 
    tenant_user_id: str
    filename: str
    json_data: Dict[str, Any]
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaissIndexStoreCreate(BaseModel):
    documents: Optional[Dict[str, Any]] = None
    faiss_index: bytes
    metadata_pkl: bytes


class FaissIndexStoreResponse(BaseModel):
    id: int
    tenant_user_id: str
    documents: Optional[Dict[str, Any]] = None
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)
