import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from core.config import settings
from database.base import Base

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router 
from api.auth import router as auth_router 
from api.user import router as user_router
from api.chatbot_route import router as chatbout_router


def init_db():
    """
    Create all database tables.
    This is for development only - use Alembic in production.
    """
    # Use sync engine for table creation
    engine = create_engine(
        settings.SQLALCHEMY_SYNC_DATABASE_URI,
        echo=True
    )
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

app = FastAPI(
    title="Money Laundering Detection API",
    description=(
        "Advanced fraud detection system using graph analysis, machine learning, "
        "and semantic search. Features include:\n"
        "- Multi-tenant isolation\n"
        "- Real-time fraud detection with 10 algorithms\n"
        "- Vector embeddings with FAISS\n"
        "- Semantic search over transaction data\n"
        "- Incremental learning per tenant"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=auth_router)
app.include_router(router=user_router)
app.include_router(router=api_router)
app.include_router(router=chatbout_router)

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint."""
    return {
        "message": "Money Laundering Detection API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    init_db()
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False
    )
