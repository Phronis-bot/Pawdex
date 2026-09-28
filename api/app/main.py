import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.animals import router as animals_router
from app.auth import current_user_id
from app.config import settings
from app.db import get_session
from app.map import router as map_router
from app.models import User
from app.reports import router as reports_router
from app.sightings import router as sightings_router
from app.warmup import main as warmup

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.preload_models:
        # In the background, so /health answers while the models load.
        threading.Thread(target=warmup, name="preload-models", daemon=True).start()
    yield


app = FastAPI(title="Pawdex API", version="0.5.0", lifespan=lifespan)
app.include_router(sightings_router)
app.include_router(reports_router)
app.include_router(animals_router)
app.include_router(map_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/me")
def me(user_id: uuid.UUID = Depends(current_user_id), session: Session = Depends(get_session)):
    """The anonymous player's generated nickname."""
    return {"id": str(user_id), "nickname": session.get(User, user_id).nickname}


@app.get("/health")
def health(session: Session = Depends(get_session)):
    try:
        rows = session.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector')")
        ).all()
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "error", "db": "unreachable"})

    extensions = {name: version for name, version in rows}
    ok = "postgis" in extensions and "vector" in extensions
    body = {
        "status": "ok" if ok else "degraded",
        "db": "ok",
        "postgis": extensions.get("postgis"),
        "pgvector": extensions.get("vector"),
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)
