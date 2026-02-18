import mysql.connector
import os
from uuid import uuid4
import json
import re
from dbConfig.mysqlConnectionConfig import get_mysql_connection
from utils.constants import QUERY_VISHANTI, qdrant, COLLECTION_NAME_VISHANTI
from qdrant_client.models import VectorParams, Distance
from utils.amount_calculator import AmountCalculatorUtils


def fetch_data_from_vishanti(environment: str):
    connection, tunnel = get_mysql_connection(environment)
    cursor = connection.cursor(dictionary=True)

    cursor.execute(QUERY_VISHANTI)
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return rows


ATTRIBUTE_MAP = {
    "RPSF_LBR_WD_ATTR": "Rate per Sqft",
    "RAT_WD_ATTR": "Rate",
    "RAT_OTH_ATTR": "Rate",
    "RAT_FC_ATTR": "Rate",
    "QNT_ACCS_ATTR": "Quantity",
    "QUA_LF_ATTR": "Quantity",
    "PPU_ACCS_ATTR": "Price/Unit",
    "PPU_LF_ATTR": "Price/Unit",
    "PRI_LBR_WD_ATTR": "Price",
    "MES_WD_ATTR": "Measurement",
    "MES_OTH_ATTR": "Measurement",
    "MES_FC_ATTR": "Measurement",
    "MAT_WD_ATTR": "Material",
    "FIN_WD_ATTR": "Finish",
    "DES_ACCS_ATTR": "Description",
    "DES_FC_ATTR": "Description",
    "DES_LF_ATTR": "Description",
    "DES_WD_ATTR": "Description",
    "DES_OTH_ATTR": "Description",
    "BRD_ACCS_ATTR": "Brand",
}


def init_collection() -> None:
    """
    Ensure the Qdrant collection exists, creating it if necessary.

    Checks if the collection (COLLECTION_NAME_VISHANTI) exists. If not found, creates it
    with vector configuration: size=4, distance=COSINE. This is safe to call
    multiple times - if the collection already exists, it does nothing.

    Raises:
        Exception: If collection creation fails (e.g., Qdrant connection error).

    Example:
        >>> init_collection()  # Creates collection if it doesn't exist
    """
    try:
        # If this call succeeds, the collection already exists.
        qdrant.get_collection(COLLECTION_NAME_VISHANTI)
        return
    except Exception as e:
        # Most likely "Not found: Collection ..." – create it.
        print(
            f"Qdrant collection {COLLECTION_NAME_VISHANTI} not found, creating it. Details: {e}")

    # Try to create (or recreate) the collection.
    try:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME_VISHANTI,
            vectors_config=VectorParams(
                size=4,
                distance=Distance.COSINE,
            ),
        )
    except Exception as e:
        print(
            f"Failed to create Qdrant collection {COLLECTION_NAME_VISHANTI}: {e}")
        raise e


def parse_item_attributes(attr_json: str) -> dict:
    if not attr_json or attr_json in ("null", "NULL"):
        return {}
    try:
        attrs = json.loads(attr_json) if isinstance(
            attr_json, str) else attr_json
        if not isinstance(attrs, dict):
            return {}
    except Exception:
        return {}
    parsed = {}
    for key, val in attrs.items():
        label = ATTRIBUTE_MAP.get(key, key)
        if isinstance(val, dict):
            if key.startswith("MES_"):
                width = val.get("width")
                length = val.get("length")
                unit = val.get("selectedOption", "")
                if width and length:
                    parsed[label] = f"{width}x{length} {unit}".strip()
                elif unit:
                    parsed[label] = unit
            elif "value" in val and "selectedOption" in val:
                parsed[label] = f"{val['value']} {val['selectedOption']}".strip(
                )
            elif "value" in val:
                parsed[label] = str(val["value"])
            elif "selectedOption" in val:
                parsed[label] = str(val["selectedOption"])
            else:
                parsed[label] = " ".join(
                    f"{k}:{v}" for k, v in val.items() if v not in (None, "", "null")
                )
        else:
            if val not in (None, "", "null"):
                parsed[label] = str(val)
    return parsed


def measurement_to_sqft(measurement) -> float:
    if measurement is None:
        return 0.0
    if isinstance(measurement, (int, float)):
        return float(measurement)
    s = str(measurement).lower()
    is_inches = "inch" in s
    s = s.replace("feet", "").replace("ft", "").replace(
        "inches", "").replace("inch", "")
    m = re.match(r"(\d+(\.\d+)?)x(\d+(\.\d+)?)", s)
    if m:
        w = float(m.group(1))
        l = float(m.group(3))
        if is_inches:
            w /= 12
            l /= 12
        return w * l
    try:
        return float(s)
    except Exception:
        return 0.0


async def ingest_to_qdrant_vishanti(environment: str):
    init_collection()
    data = fetch_data_from_vishanti(environment)

    for row in data:
        # row is a dict (cursor(dictionary=True)), so unpack by keys, not by iteration.
        estimator_id = row.get("estimator_id")
        room_name = row.get("room_name")
        item_name = row.get("item_name")
        item_id = row.get("id")
        amount = row.get("amount")
        area = row.get("area")
        project_name = row.get("project_name")
        attributes = row.get("attributes")
        item_type_identifier = row.get("item_type_identifier")
        item_identifier = row.get("item_identifier")
        user_id = row.get("user_id")
        image = row.get("image")

        # Qdrant expects point id as unsigned int or UUID
        try:
            point_id = int(item_id)
        except (TypeError, ValueError):
            point_id = str(uuid4())

        if isinstance(image, dict) and "default" in image:
            image = image["default"]

        parsed_attrs = parse_item_attributes(attributes)
        measurement = parsed_attrs.get("Measurement")
        measurement_sqft = measurement_to_sqft(measurement)

        # Calculate amount if missing/null
        amount_to_store = amount
        try:
            if not amount_to_store or amount_to_store == 0:
                if item_type_identifier:
                    dummy_item = type("Item", (), {"attributes": attributes})()
                    calculated_amount = AmountCalculatorUtils.calc_item_amount(
                        item_type_identifier, dummy_item
                    )
                    if calculated_amount and calculated_amount > 0:
                        amount_to_store = calculated_amount
        except Exception:
            pass

        # Since you don't need semantic vectors, insert a fixed-dimension dummy vector.
        # Collection is configured with size=4, so we must send 4 dims.
        dummy_vector = [0.0, 0.0, 0.0, 0.0]

        qdrant.upsert(
            collection_name=COLLECTION_NAME_VISHANTI,
            points=[
                {
                    "id": point_id,
                    "vector": dummy_vector,
                    "payload": {
                        "estimator_id": estimator_id,
                        "room_name": room_name,
                        "item_name": item_name,
                        "amount": amount_to_store,
                        "area": area,
                        "project_name": project_name,
                        "attributes": attributes,
                        "attributes_parsed": parsed_attrs,
                        "measurement_sqft": measurement_sqft,
                        "id": item_id,
                        "item_identifier": item_identifier,
                        "item_type_identifier": item_type_identifier,
                        "image": image
                    }
                }
            ]
        )
