from fastapi import APIRouter

from app.api.endpoints import assessment, auth, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(assessment.router)
