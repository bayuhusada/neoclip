from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import router as config_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.transcribe import router as transcribe_router
from app.api.ai_settings import router as ai_settings_router
from app.api.clips import router as clips_router
from app.api.framing import router as framing_router
from app.api.videos import router as videos_router
from app.core.config import settings
from app.services.worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_worker()
    try:
        yield
    finally:
        stop_worker(timeout=5.0)


app = FastAPI(
    title="NeoClip AI API",
    version="0.1.0",
    description="Local-first personal AI video clipper",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(videos_router, prefix="/api")
app.include_router(transcribe_router, prefix="/api")
app.include_router(ai_settings_router, prefix="/api")
app.include_router(clips_router, prefix="/api")
app.include_router(framing_router, prefix="/api")


@app.get("/")
def root():
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
