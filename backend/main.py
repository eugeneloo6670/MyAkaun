from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from migrations import run_migrations
from routers import entries, periods, reports, hermes
from auth import require_api_auth

# Create any tables that don't exist yet (no-op if they all exist).
Base.metadata.create_all(bind=engine)
# Then patch any existing tables that are missing columns added in later versions.
# This is a lightweight stand-in for proper migrations; see migrations.py.
run_migrations(engine)

app = FastAPI(
    title="Hermes Accounting API",
    description="Malaysia-specific accounting backend with Hermes agent integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_auth = [Depends(require_api_auth)]
app.include_router(entries.router, prefix="/api/entries", tags=["entries"], dependencies=api_auth)
app.include_router(periods.router, prefix="/api/periods", tags=["periods"], dependencies=api_auth)
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=api_auth)
app.include_router(hermes.router, prefix="/api/hermes", tags=["hermes"], dependencies=api_auth)

@app.get("/health")
def health():
    return {"status": "ok", "service": "hermes-accounting"}
