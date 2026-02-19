from qdrant_client import QdrantClient
import os
import sys

# Environment-specific auth credentials
_auth_credentials = {
    "local": {
        "user_id": 1287,
        "org_id": 402,
        "number": 8079871340,
        "token": "your_token_here"
    },
    "dev": {
        "user_id": 926,
        "org_id": 4873,
        "number": 9619250067,
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5NjE5MjUwMDY3IiwiY3JlZGVudGlhbHMiOiJORGN4TUE9PSIsImNoYW5uZWwiOiJDT05UUkFDVE9SX0FQUCIsInVzZXJSb2xlIjoiQ09OVFJBQ1RPUiIsImV4cCI6MTc3OTEyOTAwMCwidXNlcklkIjo5MjYsImFwcFVzZXJMb2dpbklkIjo1NTN9.2qDagGP1710mJ4h53ZpaLRtHO6Ky3SGl6IWgdEvEI1Q"
    },
    "uat": {
        "user_id": 1287,
        "org_id": 402,
        "number": 8079871340,
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI4MDc5ODcxMzQwIiwiY3JlZGVudGlhbHMiOiJOems1T1E9PSIsImNoYW5uZWwiOiJBRE1JTl9XRUIiLCJ1c2VyUm9sZSI6IkFETUlOIiwiZXhwIjoxNzc5MTI5MDAwLCJ1c2VySWQiOjEyODcsImFwcFVzZXJMb2dpbklkIjo4ODY5fQ.YTSeUS137yypsRLThnXidxYLqJ5oIKWGTCbN-JL50kI"
    },
    "prod": {
        "user_id": 1287,
        "org_id": 402,
        "number": 8079871340,
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI4MDc5ODcxMzQwIiwiY3JlZGVudGlhbHMiOiJOems1T1E9PSIsImNoYW5uZWwiOiJBRE1JTl9XRUIiLCJ1c2VyUm9sZSI6IkFETUlOIiwiZXhwIjoxNzc5MTI5MDAwLCJ1c2VySWQiOjEyODcsImFwcFVzZXJMb2dpbklkIjo4ODY5fQ.YTSeUS137yypsRLThnXidxYLqJ5oIKWGTCbN-JL50kI"
    }
}

_ITEMS_IDENTIFIERS_MAP = None
_ITEMS_FULL = None
_SYNONYM_INDEX = None


def get_auth_config(environment_name=None):
    """Get auth credentials for the specified environment."""
    if environment_name is None:
        environment_name = os.environ.get(
            "APP_ENVIRONMENT", os.environ.get("ENRICH_ENVIRONMENT", "dev"))
    return _auth_credentials.get(environment_name, _auth_credentials["dev"])


# Backward compatibility - these will use the current APP_ENVIRONMENT
def _get_current_env():
    return os.environ.get("APP_ENVIRONMENT", os.environ.get("ENRICH_ENVIRONMENT", "dev"))


def user_id(): return get_auth_config(_get_current_env())["user_id"]
def org_id(): return get_auth_config(_get_current_env())["org_id"]
def number(): return get_auth_config(_get_current_env())["number"]
def token(): return get_auth_config(_get_current_env())["token"]


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


def get_bootstrap_headers(number=None, user_id=None, org_id=None, environment_name=None):
    """
    Headers for pre-auth flows such as OTP generation/verification,
    where we don't yet have a Bearer token.
    """
    if environment_name is None:
        environment_name = _get_current_env()

    auth_config = get_auth_config(environment_name)

    if number is None:
        number = auth_config["number"]
    if user_id is None:
        user_id = auth_config["user_id"]
    if org_id is None:
        org_id = auth_config["org_id"]

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


shared_api_hosts = {
    "shared_api_host": 'https://shield-prod.letsmultiply.app'
}

api_hosts = {
    # external estimator API (different service)
    'local': 'http://localhost:8000',
    # 'https://dev.letsmultiply.co',
    'dev': shared_api_hosts['shared_api_host'],
    # 'https://stage.letsmultiply.co',
    'uat': shared_api_hosts['shared_api_host'],
    'prod': shared_api_hosts['shared_api_host']  # 'https://letsmultiply.co'
}


def get_api_paths(environment_name=None):
    """Get API paths with environment-specific user_id and org_id."""
    if environment_name is None:
        environment_name = _get_current_env()

    auth_config = get_auth_config(environment_name)

    return {
        'genrate_auth_url': '/v2/api/login/generate-otp',
        'verify_otp': '/v2/api/login/validate-otp',
        'fetch_estimator_items': f"/v4/api/org/{auth_config['org_id']}/user/{auth_config['user_id']}/estimator/items"
    }


# Deprecated: Keep for backward compatibility but use get_api_paths() instead
api_paths = get_api_paths()

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
APP_ENVIRONMENT = os.environ.get(
    "APP_ENVIRONMENT", os.environ.get("ENRICH_ENVIRONMENT", "dev"))

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
CITY_CSV_PATH = os.path.join(
    os.path.dirname(_APP_DIR), "resources", "city.csv")

# Path to city canonical mapping
CITY_CANONICAL_MAPPING_PATH = os.path.join(os.path.dirname(
    _APP_DIR), "resources", "city_canonical_mapping.json")


def get_api_url(environment_name, path_key, **kwargs):
    """Get full API URL for the specified environment and path."""
    # Get environment-specific API paths
    paths = get_api_paths(environment_name)
    path_template = paths[path_key]

    base = api_hosts.get(environment_name, api_hosts.get("local", ""))
    # When running in Docker with env=local, use host to reach estimator API on host machine
    if environment_name == "local" and os.environ.get("API_HOST_OVERRIDE"):
        base = os.environ.get("API_HOST_OVERRIDE", base)
    return base + path_template.format(**kwargs)


# -------------------------
# DB Credentials Brahma (single JSON-like dict)
# -------------------------

# Shared configuration for dev, uat, and prod
_shared_db_config = {
    "db": {
        "host": "solstice-prod-rds.cjkcxc4q21f9.ap-south-1.rds.amazonaws.com",   # tunneled
        "port": 3306,
        "user": "cron_read_user",
        "password": "J5drbt7yHT8NAj4",
        "database": "brahma"
    },
    "ssh": {
        "ssh_host": "43.205.215.140",
        "ssh_user": "ec2-user",
        "pem_file": os.environ.get("SSH_PKEY_PATH", "/run/secrets/shared-key.pem"),
        "remote_db_host": "solstice-prod-rds.cjkcxc4q21f9.ap-south-1.rds.amazonaws.com",
        "remote_db_port": 3306
    }
}

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

    "dev": _shared_db_config,
    "uat": _shared_db_config,
    "prod": _shared_db_config
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
