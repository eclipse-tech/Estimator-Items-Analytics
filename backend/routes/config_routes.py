"""Configuration-related routes."""
from fastapi import APIRouter
from utils.constants import APP_ENVIRONMENT

router = APIRouter()


@router.get("/config")
def get_config():
    """
    Return app configuration including current environment (single source of truth).
    Used by frontend and scripts to read APP_ENVIRONMENT.
    """
    return {"environment": APP_ENVIRONMENT}
