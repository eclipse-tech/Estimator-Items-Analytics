"""Data ingestion routes for loading data into Qdrant."""
from fastapi import APIRouter
from services.ingestVishantiDump import ingest_to_qdrant_vishanti
from services.ingestService import ingest_data_to_qdrant
from utils.constants import APP_ENVIRONMENT

router = APIRouter()


@router.post("/ingest")
async def ingest(environment_name: str | None = None):
    """
    Ingest estimator items from external API into Qdrant database.

    Uses APP_ENVIRONMENT from constants when environment_name is not provided.

    Example:
        POST /ingest
        POST /ingest?environment_name=uat
    """
    env = environment_name or APP_ENVIRONMENT
    ingest_data_to_qdrant(env)
    return await ingest_to_qdrant_vishanti(env)
