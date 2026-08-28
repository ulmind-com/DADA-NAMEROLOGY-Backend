from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("dada")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)

    from app.api.v1.admin import reload_rules
    from app.db.seed import seed

    with SessionLocal() as db:
        seed(db)
        reload_rules(db)

    log.info("%s API ready  (env=%s)", settings.PROJECT_NAME, settings.ENV)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME + " API",
    version="1.0.0",
    description=(
        "Chaldean numerology engine for Name, Mobile and Vehicle numbers, "
        "with email-OTP + Google authentication and an admin panel."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail, "status": exc.status_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Flatten pydantic errors into one human-readable message.

    `exc.errors()` carries the raw exception object under `ctx`, which is not
    JSON-serialisable, so only the safe fields are echoed back.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "input"
    msg = str(first.get("msg", "Invalid input")).replace("Value error, ", "")
    details = [
        {
            "field": ".".join(str(p) for p in e.get("loc", [])[1:]) or "input",
            "message": str(e.get("msg", "")).replace("Value error, ", ""),
            "type": e.get("type", ""),
        }
        for e in errors
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": True, "message": f"{field}: {msg}", "status": 422, "details": details},
    )


app.include_router(api_router, prefix=settings.API_V1)


@app.get("/", include_in_schema=False)
def root():
    return {
        "app": settings.PROJECT_NAME,
        "docs": "/docs",
        "api": settings.API_V1,
        "modules": ["name", "mobile", "vehicle"],
    }
