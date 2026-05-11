from fastapi import APIRouter

from app.api.endpoints import assessment, auth, health, recommendations

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(assessment.router)
api_router.include_router(recommendations.router)
