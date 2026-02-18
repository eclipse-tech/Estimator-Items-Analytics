"""Authentication-related routes."""
from fastapi import APIRouter
from services.authService import get_auth_token as auth_get_auth_token
from utils.constants import APP_ENVIRONMENT

router = APIRouter()


@router.get("/get-auth-token")
def get_auth_token_endpoint(environment_name: str | None = None):
    """
    Fetch authentication token. Uses APP_ENVIRONMENT when environment_name is not provided.
    
    Args:
        environment_name: Optional environment name override.
    
    Returns:
        dict: {"access_token": "<token>"}
    """
    env = environment_name or APP_ENVIRONMENT
    return {"access_token": auth_get_auth_token(env)}
