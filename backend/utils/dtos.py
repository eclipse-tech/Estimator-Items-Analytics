from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ApiResponseMetaDTO:
    status: str
    statusCode: int
    message: str
    description: str
    traceId: Optional[str]


@dataclass
class EstimatorItemDTO:
    name: str
    typeIdentifier: str
    identifier: str
    image: str


@dataclass
class EstimatorResultDTO:
    response: ApiResponseMetaDTO
    data: List[EstimatorItemDTO]


@dataclass
class EstimatorResponseDTO:
    result: EstimatorResultDTO


@dataclass
class ItemWithIdentifiersDTO:
    itemName: str
    identifiers: List[str]


@dataclass
class ExtractItemsWithIdentifiersResponseDTO:
    data: List[ItemWithIdentifiersDTO]


@dataclass
class AddToQdrantResponseDTO:
    """
    Response DTO for adding items to Qdrant. Same shape as EstimatorResponseDTO:
    result.response (meta) + result.data (list of inserted items).
    """
    result: EstimatorResultDTO


@dataclass
class VishantiItemDTO:
    """
    DTO representing a single row returned by QUERY_VISHANTI in constants.py.

    Two item types:
    - Type 1 (LF): attributes with Quantity, Price/Unit; measurement_sqft often 0
    - Type 2 (WD): attributes with Material, Finish, Rate, Measurement; measurement_sqft computed
    """
    estimatorId: int
    roomName: str
    itemName: str
    itemId: int
    amount: float
    area: str
    projectName: str
    attributes: Any  # raw JSON string from vishanti.item.attributes
    attributesParsed: Optional[Dict[str, str]]  # human-readable e.g. {"Quantity":"1","Price/Unit":"40000"}
    itemTypeIdentifier: str
    itemIdentifier: str
    userId: int
    image: Optional[str]


@dataclass
class AreaPriceStatsDTO:
    """
    Per-area price statistics for a Vishanti item.
    Shows price per sqft (for WD items) or per unit (for LF items).
    """
    area: str
    priceType: str  # "Per Sqft" | "Per Unit" | "Total"
    minPrice: float
    maxPrice: float
    avgPrice: float


@dataclass
class VishantiAggregatedItemDTO:
    """
    Aggregated view of a Vishanti item with per-area price stats.

    - itemName: canonical name of the item
    - itemIdentifier: unique identifier for the item
    - itemTypeIdentifier: type identifier for the item
    - image: image URL or serialized image data
    - areaStats: list of per-area (city) price stats
    """
    itemName: str
    itemIdentifier: str
    itemTypeIdentifier: str
    image: Optional[str]
    areaStats: List[AreaPriceStatsDTO]
