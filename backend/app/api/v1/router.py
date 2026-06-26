from fastapi import APIRouter

from app.api.v1 import auth, conversations, cohorts, tracks, users
from app.api.v1.admin import playground as admin_playground

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tracks.router)
api_router.include_router(cohorts.router)
api_router.include_router(conversations.router)
api_router.include_router(admin_playground.router)
