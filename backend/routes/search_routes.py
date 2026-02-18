"""Search-related routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from services.itemService import search_items_by_query

router = APIRouter()


class Query(BaseModel):
    query: str

@router.get("/search-items")
def search_items_endpoint(query: str = ""):
    """
    Main search endpoint: search for items by query and return from Qdrant.

    Complete search workflow:
    1. Extracts item names and identifiers from query using fuzzy matching
       (handles typos like "bichana" -> "bichhana" -> "bed")
    2. Collects all unique identifiers from matched items
    3. Fetches actual item data from Qdrant by those identifiers
    4. Returns items in EstimatorResponseDTO format

    This is the primary endpoint used by the frontend search UI. It combines
    multilingual query extraction with Qdrant database lookup.

    Args:
        query: Search query string. Can be in any supported language (Hindi, Bengali,
            Tamil, Telugu, Kannada, Malayalam) or English. Supports typos via fuzzy matching.
            Examples: "bed", "sofa set", "bichana" (typo), "स्टडी टेबल"

    Returns:
        EstimatorResponseDTO: Response containing:
            - result.response: ApiResponseMetaDTO (status="SUCCESS", statusCode=200)
            - result.data: List of EstimatorItemDTO matching the query
                Each item has: name, typeIdentifier, identifier, image

    Raises:
        HTTPException: If Qdrant query fails or extraction fails.

    Example:
        GET /search-items?query=bed
        Response: {
            "result": {
                "response": {"status": "SUCCESS", "statusCode": 200, ...},
                "data": [
                    {"name": "Bed", "typeIdentifier": "...", "identifier": "BED_ITM_NW", "image": "..."}
                ]
            }
        }

        GET /search-items?query=bichana  # typo still works
        Response: {
            "result": {
                "response": {"status": "SUCCESS", ...},
                "data": [{"name": "Bed", ...}]  # finds "bed" despite typo
            }
        }
    """
    return search_items_by_query(query)
