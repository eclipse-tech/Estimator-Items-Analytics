import os
import json
import csv
import difflib
from utils.constants import _ITEM_JSON_PATH, _SYNONYM_INDEX, _ITEMS_FULL, _ITEMS_IDENTIFIERS_MAP, CITY_CSV_PATH, CITY_CANONICAL_MAPPING_PATH
from utils.extractor import split_variants, build_synonym_index
import requests

_CANONICAL_CITIES = None
_CITY_MAPPING = None


def get_items_with_identifiers_path():
    """Path to resources/items_with_identifiers.json."""
    return os.path.join(os.path.dirname(_ITEM_JSON_PATH), "items_with_identifiers.json")


def invalidate_items_caches():
    """Clear in-memory caches so next request reloads items_with_identifiers.json."""
    global _ITEMS_FULL, _ITEMS_IDENTIFIERS_MAP
    _ITEMS_FULL = None
    _ITEMS_IDENTIFIERS_MAP = None


def _get_items_full():
    """Load full items JSON (for scanning native/roman variants). Does not affect _get_synonym_index."""
    global _ITEMS_FULL
    if _ITEMS_FULL is not None:
        return _ITEMS_FULL
    try:
        path_with_id = os.path.join(os.path.dirname(_ITEM_JSON_PATH), "items_with_identifiers.json")
        path = path_with_id if os.path.isfile(path_with_id) else _ITEM_JSON_PATH
        with open(path, "r", encoding="utf-8") as f:
            _ITEMS_FULL = json.load(f)
    except Exception as e:
        print("⚠️ Could not load items full:", e)
        _ITEMS_FULL = {}
    return _ITEMS_FULL


def _get_items_identifiers_map():
    """Load item_name -> identifiers[] from items_with_identifiers.json if present."""
    global _ITEMS_IDENTIFIERS_MAP
    if _ITEMS_IDENTIFIERS_MAP is not None:
        return _ITEMS_IDENTIFIERS_MAP
    _ITEMS_IDENTIFIERS_MAP = {}
    try:
        path = os.path.join(os.path.dirname(_ITEM_JSON_PATH), "items_with_identifiers.json")
        if not os.path.isfile(path):
            return _ITEMS_IDENTIFIERS_MAP
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item_name, entry in data.items():
            if isinstance(entry, dict) and "identifiers" in entry:
                ids = entry["identifiers"]
                _ITEMS_IDENTIFIERS_MAP[item_name] = ids if isinstance(ids, list) else []
    except Exception as e:
        print("⚠️ Could not load items_with_identifiers:", e)
    return _ITEMS_IDENTIFIERS_MAP


def _item_contains_token(item_name, token, items_full, norm):
    """True if token appears in item name or in any native/roman variant (as word or substring)."""
    if not token:
        return True
    item_norm = norm(item_name)
    if token == item_norm or token in (item_norm.split() if item_norm else []) or (token in item_norm if item_norm else False):
        return True
    langs = items_full.get(item_name)
    if not isinstance(langs, dict):
        return False
    for forms in langs.values():
        if not isinstance(forms, dict):
            continue
        for val in split_variants(forms.get("native", "")) + split_variants(forms.get("roman", "")):
            phrase_norm = norm(val)
            if not phrase_norm:
                continue
            if token == phrase_norm or token in phrase_norm.split() or token in phrase_norm:
                return True
    return False

def _get_synonym_index():
    """Load item synonym JSON and build index once (demo.py style)."""
    global _SYNONYM_INDEX
    if _SYNONYM_INDEX is not None:
        return _SYNONYM_INDEX
    try:
        if not os.path.isfile(_ITEM_JSON_PATH):
            print(f"⚠️ items.json not found at: {_ITEM_JSON_PATH}")
            _SYNONYM_INDEX = {}
            return _SYNONYM_INDEX

        with open(_ITEM_JSON_PATH, "r", encoding="utf-8") as f:
            item_json = json.load(f)

        _SYNONYM_INDEX = build_synonym_index(item_json)
    except Exception as e:
        print("⚠️ Could not load multilingual item extractor synonym index:", e)
        _SYNONYM_INDEX = {}
    return _SYNONYM_INDEX

def _extract_token_from_response(response: requests.Response) -> str:
    """
    Try to extract an access token from common locations in the OTP validation
    response. Prefer headers, then JSON body.
    """
    # Header variants
    for key in ("access_token", "access-token", "Access-Token", "X-Access-Token"):
        token = response.headers.get(key)
        if token:
            return token.strip()

    auth = response.headers.get("Authorization") or response.headers.get("authorization")
    if auth:
        auth = auth.strip()
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip() or auth
        return auth

    # Fallback to JSON body if present
    try:
        data = response.json()
    except Exception:
        data = None

    if isinstance(data, dict):
        for key in ("access_token", "accessToken", "token"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    raise RuntimeError(
        "OTP validation response did not contain an access token in headers or JSON. "
        f"status={response.status_code}; body={response.text[:500]!r}"
    )


def _load_city_mapping():
    """
    Load city canonical mapping from JSON file.
    Returns dict: {canonical: [variant1, variant2, ...]}
    """
    global _CITY_MAPPING
    if _CITY_MAPPING is not None:
        return _CITY_MAPPING
    
    _CITY_MAPPING = {}
    try:
        with open(CITY_CANONICAL_MAPPING_PATH, "r", encoding="utf-8") as f:
            _CITY_MAPPING = json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load city_canonical_mapping.json: {e}")
        _CITY_MAPPING = {}
    
    return _CITY_MAPPING


def normalize_city_name(city: str) -> str:
    """
    Normalize city name to canonical form using predefined mapping.
    
    Maps variations like:
    - bangalore, bangalor, bengaluru, banglore → Bangalore
    - hyderabad, hydrabad, haydrabad → Hyderabad
    
    Args:
        city: Raw city name (may contain typos)
    
    Returns:
        Canonical city name if match found, otherwise returns original city.
    
    Example:
        >>> normalize_city_name("bangalor")
        "Bangalore"
        >>> normalize_city_name("hydrabad")
        "Hyderabad"
    """
    if not city:
        return city
    
    city_stripped = city.strip()
    city_lower = city_stripped.lower()
    
    mapping = _load_city_mapping()
    
    # Check if it's already a canonical name
    if city_stripped in mapping:
        return city_stripped
    
    # Check variants mapping
    for canonical, variants in mapping.items():
        if city_lower in [v.lower() for v in variants]:
            return canonical
        # Also check if the city_stripped matches canonical (case-insensitive)
        if city_lower == canonical.lower():
            return canonical
    
    # No match: return original
    return city_stripped