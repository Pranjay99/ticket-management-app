import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from backend.config import settings
from backend.db.session import engine, Base, SessionLocal
from backend.db.seed import seed_if_empty
from backend.api.routes import tickets, insights, search, suggest
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables if they don't exist...")
    from backend.models import ticket, insight  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered customer support insight platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(tickets.router, prefix=API_PREFIX)
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(suggest.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["Health"])
def health_check():
    from sqlalchemy import text
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "database": db_status,
    }


# ── Serve React frontend ─────────────────────────────────────────────────────
# Must be defined after all API routes so /api/* is not intercepted
_DIST = os.path.join(os.path.dirname(__file__), "..", "react-frontend", "dist")

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str = ""):
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    index = os.path.join(_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"detail": "Frontend not built. Run: cd react-frontend && npm run build"}
