from fastapi import APIRouter

from app.api.v1 import admin, auth, meta, numerology, public, reports

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(numerology.router)
api_router.include_router(reports.router)
api_router.include_router(public.router)
api_router.include_router(admin.router)
