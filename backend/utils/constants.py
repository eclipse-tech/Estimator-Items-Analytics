from qdrant_client import QdrantClient
import os
import sys
url = "https://dev.letsmultiply.co/v2/api/login/generate-otp"

user_id = 1287
org_id = 402
number = 8079871340
token = "your_token_here"

_ITEMS_IDENTIFIERS_MAP = None
_ITEMS_FULL = None
_SYNONYM_INDEX = None


def get_headers(token, user_id, org_id, number):
    """Headers for authenticated (Bearer token) API calls."""
    return {
        "Content-Type": "application/json",
        "X-USER-ROLE": "CONTRACTOR",
        "X-CHANNEL": "CONTRACTOR_APP",
        "Authorization": f"Bearer {token}",
        "X-SERVICE-TYPE": "PROCUREMENT",
        "X-LOGIN-ROLE": "CONTRACTOR",
        "X-PAYMENT-MODE": "WEBPAGE",
        "X-PAYMENT-CLIENT": "JUSPAY",
        "X-USER-NAME": str(number),
        "X-ORG-ID": str(org_id),
        "X-LOGGED-IN": str(number),
        "X-USER-ID": str(user_id),
    }


def get_bootstrap_headers(number, user_id=user_id, org_id=org_id):
    """
    Headers for pre-auth flows such as OTP generation/verification,
    where we don't yet have a Bearer token.
    """
    return {
        "Content-Type": "application/json",
        "X-USER-ROLE": "CONTRACTOR",
        "X-CHANNEL": "CONTRACTOR_APP",
        "X-SERVICE-TYPE": "PROCUREMENT",
        "X-LOGIN-ROLE": "CONTRACTOR",
        "X-PAYMENT-MODE": "WEBPAGE",
        "X-PAYMENT-CLIENT": "JUSPAY",
        "X-USER-NAME": str(number),
        "X-ORG-ID": str(org_id),
        "X-LOGGED-IN": str(number),
        "X-USER-ID": str(user_id),
    }


api_hosts = {
    'local': 'http://localhost:8000',  # external estimator API (different service)
    'dev': 'https://dev.letsmultiply.co',
    'uat': 'https://stage.letsmultiply.co',
    'prod': 'https://letsmultiply.co'
}

api_paths = {
    'genrate_auth_url': '/v2/api/login/generate-otp',
    'verify_otp': '/v2/api/login/validate-otp',
    'fetch_estimator_items': f"/v4/api/org/{org_id}/user/{user_id}/estimator/items"
}

COLLECTION_NAME_BRAHMA = "static_items"

COLLECTION_NAME_VISHANTI = "vishanti_items"

default_otp = "1234"


def get_default_otp():
    return default_otp


# Allow overriding host/port via environment for containerized deployments.
QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

# Single source of truth for environment (local, dev, uat, prod).
# Reads APP_ENVIRONMENT first, then ENRICH_ENVIRONMENT for backward compat.
APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", os.environ.get("ENRICH_ENVIRONMENT", "dev"))

# Timeout for outbound HTTP requests (auth, fetch items). Large data requests need longer timeouts.
API_REQUEST_TIMEOUT = int(os.environ.get("API_REQUEST_TIMEOUT", "60000"))

qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


# Add workspace root so we can import multilingual_item_extractor
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_APP_DIR)))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

_ITEM_JSON_PATH = os.environ.get("ITEM_SYNONYM_JSON_PATH")
if not _ITEM_JSON_PATH:
    # Prefer items.json from backend/resources (container-safe relative path)
    _candidates = [
        os.path.join(os.path.dirname(_APP_DIR), "resources", "items.json"),
    ]
    _ITEM_JSON_PATH = next(
        (p for p in _candidates if os.path.isfile(p)), _candidates[0])

# Path to query_result.csv in backend/resources (used by enrich_static_items, enrich_items_with_identifiers)
QUERY_RESULT_CSV_PATH = os.path.join(os.path.dirname(
    _APP_DIR), "resources", "item_identifiers_map.csv")

# Path to city.csv for city name normalization
CITY_CSV_PATH = os.path.join(os.path.dirname(_APP_DIR), "resources", "city.csv")

# Path to city canonical mapping
CITY_CANONICAL_MAPPING_PATH = os.path.join(os.path.dirname(_APP_DIR), "resources", "city_canonical_mapping.json")


def get_api_url(environment_name, path_key, **kwargs):
    path_template = api_paths[path_key]
    base = api_hosts.get(environment_name, api_hosts.get("local", ""))
    # When running in Docker with env=local, use host to reach estimator API on host machine
    if environment_name == "local" and os.environ.get("API_HOST_OVERRIDE"):
        base = os.environ.get("API_HOST_OVERRIDE", base)
    return base + path_template.format(**kwargs)


# -------------------------
# DB Credentials Brahma (single JSON-like dict)
# -------------------------
dbCred = {
    "local": {
        "db": {
            "host": os.environ.get("MYSQL_HOST_OVERRIDE", "localhost"),
            "port": int(os.environ.get("MYSQL_PORT_OVERRIDE", "3306")),
            "user": "root",
            "password": "Chayan@1340",
            "database": "brahma"
        },
        "ssh": None   # no ssh for local
    },

    "dev": {
        "db": {
            "host": "localhost",   # tunneled
            "port": 3307,
            "user": "admin",
            "password": "fMZewU6YGm7mNJycCm1R",
            "database": "brahma"
        },
        "ssh": {
            "ssh_host": "1.tcp.in.ngrok.io",
            "ssh_port": 20043,
            "ssh_user": "Solstice-Dev-Server",
            "pem_file": "/Users/chayanchakraborty/Downloads/shared-key.pem",
            "remote_db_host": "localhost",
            "remote_db_port": 3307
        }
    },

    "uat": {
        "db": {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "super_user",
            "password": "pass",
            "database": "brahma"
        },
        "ssh": {
            "ssh_host": "uat-bastion-host",
            "ssh_port": 22,
            "ssh_user": "ec2-user",
            "pem_file": "/path/to/uat.pem",
            "remote_db_host": "localhost",
            "remote_db_port": 3306
        }
    },

    "prod": {
        "db": {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "cron_read_user",
            "password": "pass",
            "database": "brahma"
        },
        "ssh": {
            "ssh_host": "prod-bastion-host",
            "ssh_port": 22,
            "ssh_user": "ec2-user",
            "pem_file": "/path/to/prod.pem",
            "remote_db_host": "localhost",
            "remote_db_port": 3306
        }
    }
}

# -------------------------
# SQL Query - To Fetch Item Names and Identifiers from Brahma (for enrich_items_with_identifiers)
# -------------------------

QUERY_BRAHMA = """
SELECT name, identifier
FROM brahma.item_v2
WHERE is_active = 1;
"""

# -------------------------
# SQL Query - To Fetch Items Data from item (for enrich_items_with_identifiers)
# -------------------------

QUERY_VISHANTI = """SELECT e.id AS estimator_id, r.name AS room_name, i.name AS item_name, i.id, i.amount,
           a.city AS area, p.name AS project_name, i.attributes, i.type_identifier as item_type_identifier, i.identifier as item_identifier,
           e.user_id, i.image
    FROM vishanti.item i
    JOIN vishanti.room r ON r.id = i.room_id
    JOIN vishanti.estimator e ON e.id = r.estimator_id
    JOIN zeus.project p ON e.project_id = p.id
    JOIN zeus.address a ON a.project_id = p.id
    LEFT JOIN shield.internal_users iu on e.user_id = iu.user_id
    WHERE iu.user_id IS NULL &&  e.status = 'FINALIZED';"""

#
# This utility script enriches `resources/items.json` with item identifiers
# from `resources/query_result.csv` by matching on item names.
# - CSV is expected to have columns: "name", "identifier" (semicolon- or comma-separated)
# - JSON keys are the canonical item names (e.g. "console table")
# - Matching is done using the same normalization as `utils.extractor.normalize`.
#
# It writes a new file `items_with_identifiers.json` next to the original,
# leaving the original `items.json` untouched.
#

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Match entrypoint.sh logic: resources live right under the project/app root.
BACKEND_DIR = os.path.dirname(_THIS_DIR)
RESOURCES_DIR = os.path.join(BACKEND_DIR, "resources")

ITEMS_JSON_IN = os.path.join(RESOURCES_DIR, "items.json")
ITEMS_JSON_OUT = os.path.join(RESOURCES_DIR, "items_with_identifiers.json")
ITEM_IDENTIFIERS_MAP_CSV_PATH = os.path.join(
    RESOURCES_DIR, "item_identifiers_map.csv")
