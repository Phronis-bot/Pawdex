from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.animals import router as animals_router
from app.db import get_session
from app.sightings import router as sightings_router

app = FastAPI(title="Pawdex API", version="0.2.0")
app.include_router(sightings_router)
app.include_router(animals_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
