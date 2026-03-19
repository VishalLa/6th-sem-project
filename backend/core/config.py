import os 
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path 
from dataclasses import dataclass, asdict 
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# database folder
DB_DIR = BASE_DIR / "db"
DB_FILE = DB_DIR / "app.db"

DB_DIR.mkdir(parents=True, exist_ok=True)

if not DB_FILE.exists():
    DB_FILE.touch()

FAISS_DIR = BASE_DIR / "faiss_store"
CACHE_DIR = BASE_DIR / "cache"
MODEL_DIR = BASE_DIR / "models" / "e5_small_v2"

FAISS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):

    DEBUG: bool = False
    
    DATABASE_URI: str = f"sqlite:///{DB_FILE.as_posix()}"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    SQLALCHEMY_SYNC_DATABASE_URI: Optional[str] = None
    SQLALCHEMY_ASYNC_DATABASE_URI: Optional[str] = None
    

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    LOG_FILE: str = "debug.log"
    LOG_FORMAT: str = "%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s"

    def model_post_init(self, __context):
        if self.DATABASE_URI.startswith("sqlite"):
            self.SQLALCHEMY_SYNC_DATABASE_URI = self.DATABASE_URI
            self.SQLALCHEMY_ASYNC_DATABASE_URI = self.DATABASE_URI.replace(
                "sqlite:///", "sqlite+aiosqlite:///"
            )
        else:
            self.SQLALCHEMY_SYNC_DATABASE_URI = self.DATABASE_URI
            self.SQLALCHEMY_ASYNC_DATABASE_URI = self.DATABASE_URI 

settings = Settings()



"""
Config for local Vector DB (FAISS)
"""
@dataclass
class VectorDBConfig: 

    MODEL_NAME: str = "intfloat/e5-small-v2"

    MODEL_PATH: str = MODEL_DIR.as_posix()
    FAISS_PATH: str = FAISS_DIR.as_posix()
    CACHE_PATH: str = CACHE_DIR.as_posix()

    ROWS_PER_CHUNK: int = 10
    TOP_K_RETRIEVAL: int = 10
    CONFIDENCE_THRESHOLD: float = 0.6
    MAX_CONVERSATION_HISTORY: int = 10
    
vector_settings = VectorDBConfig()
