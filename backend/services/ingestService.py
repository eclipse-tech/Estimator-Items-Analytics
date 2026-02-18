import uuid
from qdrant_client.models import VectorParams, Distance, PointStruct

from utils.constants import qdrant, COLLECTION_NAME_BRAHMA
from utils.dtos import (
    ApiResponseMetaDTO,
    EstimatorItemDTO,
    EstimatorResponseDTO,
    EstimatorResultDTO,
    AddToQdrantResponseDTO,
)
from utils.extractor import build_vector
from services.itemService import fetch_estimator_items

# Create collection if not exists


def init_collection() -> None:
    """
    Ensure the Qdrant collection exists, creating it if necessary.

    Checks if the collection (COLLECTION_NAME_BRAHMA) exists. If not found, creates it
    with vector configuration: size=4, distance=COSINE. This is safe to call
    multiple times - if the collection already exists, it does nothing.

    Raises:
        Exception: If collection creation fails (e.g., Qdrant connection error).

    Example:
        >>> init_collection()  # Creates collection if it doesn't exist
    """
    try:
        # If this call succeeds, the collection already exists.
        qdrant.get_collection(COLLECTION_NAME_BRAHMA)
        return
    except Exception as e:
        # Most likely "Not found: Collection ..." – create it.
        print(
            f"Qdrant collection {COLLECTION_NAME_BRAHMA} not found, creating it. Details: {e}")

    # Try to create (or recreate) the collection.
    try:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME_BRAHMA,
            vectors_config=VectorParams(
                size=4,
                distance=Distance.COSINE,
            ),
        )
    except Exception as e:
        print(
            f"Failed to create Qdrant collection {COLLECTION_NAME_BRAHMA}: {e}")
        raise e


def ingest_estimator_dto_into_qdrant(estimator_dto: EstimatorResponseDTO) -> dict:
    """
    Ingest estimator items from EstimatorResponseDTO into Qdrant collection.

    Converts each item in the DTO to a Qdrant point with:
    - Vector: Built from item name + identifier + typeIdentifier
    - Payload: name, typeIdentifier, identifier, image

    All points are upserted in a single batch operation.

    Args:
        estimator_dto: EstimatorResponseDTO containing result.data (list of EstimatorItemDTO).

    Returns:
        dict: {"inserted": <count>, "collection": "<collection_name>"}
            inserted is the number of items successfully added.

    Example:
        >>> dto = fetch_estimator_items("dev")
        >>> result = ingest_estimator_dto_into_qdrant(dto)
        >>> print(result["inserted"])
        60
    """

    points = []

    for item in estimator_dto.result.data:

        text = f"{item.name} {item.identifier} {item.typeIdentifier}"

        vector = build_vector(text)

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "name": item.name,
                "typeIdentifier": item.typeIdentifier,
                "identifier": item.identifier,
                "image": item.image
            }
        )

        points.append(point)

    if points:
        qdrant.upsert(
            collection_name=COLLECTION_NAME_BRAHMA,
            points=points
        )

    return {
        "inserted": len(points),
        "collection": COLLECTION_NAME_BRAHMA
    }


def ingest_data_to_qdrant(environment_name: str) -> dict:
    """
    Fetch estimator items from external API and ingest into Qdrant.

    Complete workflow:
    1. Ensures Qdrant collection exists (creates if needed)
    2. Fetches items from external API for the given environment
    3. Ingests all items into Qdrant collection

    Args:
        environment_name: Environment name (e.g., "dev", "uat", "prod", "local").
            Used to determine API base URL and authenticate.

    Returns:
        dict: {"inserted": <count>, "collection": "<collection_name>"}
            inserted is the number of items from the API response.

    Raises:
        RuntimeError: If API fetch fails or response is invalid.
        Exception: If Qdrant operations fail.

    Example:
        >>> result = ingest_data_to_qdrant("dev")
        >>> print(f"Inserted {result['inserted']} items into {result['collection']}")
        Inserted 60 items into estimator_items
    """
    init_collection()
    try:
        estimator_dto = fetch_estimator_items(environment_name)
        ingest_estimator_dto_into_qdrant(estimator_dto)
    except Exception as e:
        print(e)
        raise e
    return {
        "inserted": len(estimator_dto.result.data),
        "collection": COLLECTION_NAME_BRAHMA
    }


def add_items_to_qdrant(items: list) -> AddToQdrantResponseDTO:
    """
    Add one or more items directly to Qdrant collection.

    Unlike ingest_data_to_qdrant, this accepts items directly (not from external API).
    Items can be EstimatorItemDTO objects or dicts with name, typeIdentifier, identifier, image.

    Process:
    1. Ensures collection exists
    2. Normalizes items to EstimatorItemDTO format
    3. Builds vectors from name + identifier + typeIdentifier
    4. Upserts all points to Qdrant
    5. Returns response with inserted items

    Args:
        items: List of items to add. Each item can be:
            - EstimatorItemDTO object (has name, typeIdentifier, identifier, image attributes)
            - dict with keys: name, typeIdentifier, identifier, image
            Empty list returns success with empty data.

    Returns:
        AddToQdrantResponseDTO: Response with:
            - result.response: ApiResponseMetaDTO (status="SUCCESS", statusCode=200)
            - result.data: List of EstimatorItemDTO that were inserted

    Example:
        >>> items = [
        ...     EstimatorItemDTO(name="Test Item", typeIdentifier="TEST", identifier="TEST_ITM", image="{}")
        ... ]
        >>> result = add_items_to_qdrant(items)
        >>> print(result.result.response.status)
        "SUCCESS"
    """
    init_collection()
    trace_id = uuid.uuid4().hex[:16]
    response_meta = ApiResponseMetaDTO(
        status="SUCCESS",
        statusCode=200,
        message="Items added to Qdrant successfully",
        description="Items added to Qdrant successfully",
        traceId=trace_id,
    )
    if not items:
        return AddToQdrantResponseDTO(
            result=EstimatorResultDTO(response=response_meta, data=[])
        )
    # Normalize to list of dict-like items (name, typeIdentifier, identifier, image)
    normalized = []
    for it in items:
        if hasattr(it, "name"):
            normalized.append(it)
        elif isinstance(it, dict):
            normalized.append(
                EstimatorItemDTO(
                    name=it.get("name", ""),
                    typeIdentifier=it.get("typeIdentifier", ""),
                    identifier=it.get("identifier", ""),
                    image=it.get("image", ""),
                )
            )
        else:
            continue
    points = []
    for item in normalized:
        name = getattr(item, "name", "")
        type_id = getattr(item, "typeIdentifier", "")
        identifier = getattr(item, "identifier", "")
        image = getattr(item, "image", "")
        text = f"{name} {identifier} {type_id}"
        vector = build_vector(text)
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"name": name, "typeIdentifier": type_id,
                         "identifier": identifier, "image": image},
            )
        )
    if points:
        qdrant.upsert(collection_name=COLLECTION_NAME_BRAHMA, points=points)
    return AddToQdrantResponseDTO(
        result=EstimatorResultDTO(response=response_meta, data=normalized)
    )
