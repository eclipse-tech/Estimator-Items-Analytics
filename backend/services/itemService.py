import difflib
import json
import os
import uuid
import requests
from qdrant_client.models import Filter, FieldCondition, MatchAny
import sys
import re

from utils.constants import (
    get_headers,
    get_api_url,
    user_id,
    org_id,
    number,
    qdrant,
    COLLECTION_NAME_BRAHMA,
    COLLECTION_NAME_VISHANTI,
    API_REQUEST_TIMEOUT,
)
from utils.utils import (
    _get_items_identifiers_map,
    _get_items_full,
    _item_contains_token,
    _get_synonym_index,
    get_items_with_identifiers_path,
    invalidate_items_caches,
    normalize_city_name,
)
from utils.dtos import (
    ApiResponseMetaDTO,
    EstimatorItemDTO,
    EstimatorResponseDTO,
    EstimatorResultDTO,
    ExtractItemsWithIdentifiersResponseDTO,
    ItemWithIdentifiersDTO,
    VishantiItemDTO,
    AreaPriceStatsDTO,
    VishantiAggregatedItemDTO,
)
from services.authService import get_auth_token
from utils.mapper import map_to_estimator_dto
from utils.extractor import extract_item, normalize as extractor_normalize, split_variants


def fetch_estimator_items(environment_name: str) -> EstimatorResponseDTO:
    """
    Fetch estimator items from the external API for a given environment.

    Makes an authenticated GET request to the estimator items endpoint and returns
    the response mapped to EstimatorResponseDTO format.

    Args:
        environment_name: Environment name (e.g., "dev", "uat", "prod", "local").
            Used to determine the API base URL.

    Returns:
        EstimatorResponseDTO: Response containing result.response (metadata) and
            result.data (list of EstimatorItemDTO with name, typeIdentifier, identifier, image).

    Raises:
        RuntimeError: If the API request fails (non-200 status) or response is not valid JSON.
        requests.exceptions.RequestException: If network/connection error occurs.

    Example:
        >>> dto = fetch_estimator_items("dev")
        >>> print(dto.result.data[0].name)
        "3 Tier Base Unit Pullout"
    """
    print("method fetch_estimator_items called")
    try:
        headers = get_headers(get_auth_token(
            environment_name), user_id, org_id, number)
        response = requests.get(
            get_api_url(environment_name, "fetch_estimator_items"),
            headers=headers,
            timeout=API_REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise RuntimeError(
                f"Fetch estimator items failed: {response.status_code} {response.reason}; "
                f"body={response.text[:500]!r}"
            )

        try:
            data = response.json()
        except ValueError as e:
            # Surface a clear error instead of a raw JSONDecodeError
            raise RuntimeError(
                f"Estimator items response is not valid JSON: {e}; "
                f"status={response.status_code}; body={response.text[:500]!r}"
            )

        return map_to_estimator_dto(data)
    except requests.exceptions.RequestException as e:
        print(e)
        raise e
    except Exception as e:
        print(e)
        raise e


def fetch_items_from_qdrant_by_identifiers(identifiers: list) -> EstimatorResponseDTO:
    """
    Fetch items from Qdrant database by their identifiers.

    Queries the Qdrant collection using a filter to find all points whose payload
    "identifier" field matches any value in the provided list. Returns items in
    EstimatorResponseDTO format.

    Args:
        identifiers: List of identifier strings (e.g., ["BED_ITM_NW", "SOF_ITM_NW"]).
            Empty or None list returns empty result.

    Returns:
        EstimatorResponseDTO: Response with:
            - result.response: ApiResponseMetaDTO (status="SUCCESS", statusCode=200, etc.)
            - result.data: List of EstimatorItemDTO (name, typeIdentifier, identifier, image)

    Raises:
        Exception: If Qdrant query fails (connection error, collection not found, etc.).

    Example:
        >>> result = fetch_items_from_qdrant_by_identifiers(["BED_ITM_NW", "SOF_ITM_NW"])
        >>> print(len(result.result.data))
        2
    """
    print(
        f"identifiers in fetch_items_from_qdrant_by_identifiers: {identifiers}")
    trace_id = uuid.uuid4().hex[:16]
    response_meta = ApiResponseMetaDTO(
        status="SUCCESS",
        statusCode=200,
        message="Estimate Items fetch Successful",
        description="Estimate Items fetch Successful",
        traceId=trace_id,
    )
    if not identifiers:
        return EstimatorResponseDTO(
            result=EstimatorResultDTO(response=response_meta, data=[])
        )
    identifiers = [str(i).strip()
                   for i in identifiers if i is not None and str(i).strip()]
    if not identifiers:
        return EstimatorResponseDTO(
            result=EstimatorResultDTO(response=response_meta, data=[])
        )
    try:
        records, _ = qdrant.scroll(
            collection_name=COLLECTION_NAME_BRAHMA,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="identifier",
                        match=MatchAny(any=identifiers),
                    )
                ]
            ),
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        data = []
        print(f"records in fetch_items_from_qdrant_by_identifiers: {records}")
        for rec in records:
            p = dict(rec.payload) if rec.payload else {}
            data.append(
                EstimatorItemDTO(
                    name=p.get("name") or "",
                    typeIdentifier=p.get("typeIdentifier") or "",
                    identifier=p.get("identifier") or "",
                    image=p.get("image") or "",
                )
            )
        return EstimatorResponseDTO(
            result=EstimatorResultDTO(response=response_meta, data=data)
        )
    except Exception as e:
        print(f"fetch_items_from_qdrant_by_identifiers error: {e}")
        raise e


def search_items_by_query(query: str) -> EstimatorResponseDTO:
    """
    Search for items by query string using fuzzy matching and return from Qdrant.

    This is the main search method that:
    1. Extracts item names and identifiers from the query using fuzzy matching
       (handles typos like "bichana" -> "bichhana" -> "bed")
    2. Collects all unique identifiers from matched items
    3. Fetches the actual item data from Qdrant by those identifiers

    Args:
        query: Search query string (e.g., "bed", "sofa set", "bichana").
            Can be in any supported language (Hindi, Bengali, Tamil, etc.) or English.

    Returns:
        EstimatorResponseDTO: Response containing:
            - result.response: Success metadata
            - result.data: List of EstimatorItemDTO matching the query

    Example:
        >>> result = search_items_by_query("bed")
        >>> print(result.result.data[0].name)
        "Bed"

        >>> result = search_items_by_query("bichana")  # typo
        >>> print(result.result.data[0].name)  # still finds "bed"
        "Bed"
    """
    print(f"query in search_items_by_query: {query}")
    extracted = extract_items_with_identifiers_from_query_fuzzy(query)
    print(f"extracted in search_items_by_query: {extracted}")
    identifiers = []
    for item in extracted.data:
        identifiers.extend(item.identifiers or [])
    # Deduplicate while preserving order
    seen = set()
    unique_ids = [
        i for i in identifiers if i and i not in seen and not seen.add(i)]
    print(f"unique_ids in search_items_by_query: {unique_ids}")
    return fetch_items_from_qdrant_by_identifiers(unique_ids)


def extract_item_name_from_query(query: str) -> str | None:
    """
    Extract a single canonical item name from a search query.

    Uses the synonym index to match the query against item names and their
    multilingual variants (Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam).
    Returns the first matching canonical item name, or None if no match.

    Matching logic:
    1. Primary: Uses extractor over the synonym index (normalized matching)
    2. Fallback: If no match, tries fuzzy spelling correction (difflib) with 0.8 cutoff
    3. Returns None if still no match

    Args:
        query: Search query string (can be in any supported language or English).

    Returns:
        str | None: Canonical item name (e.g., "bed", "sofa set") if found,
            None if no match.

    Example:
        >>> extract_item_name_from_query("bed")
        "bed"

        >>> extract_item_name_from_query("बिस्तर")  # Hindi
        "bed"

        >>> extract_item_name_from_query("xyz123")
        None
    """
    index = _get_synonym_index()
    if not index:
        return None
    original_query = (query or "").strip()
    if not original_query:
        return None

    # 1) Primary: use extractor over the synonym index
    try:
        candidate = extract_item(original_query, index)
    except Exception:
        candidate = None
        def extractor_normalize(s): return (s or "").strip().lower()

    # 1b) If no candidate, try a fuzzy spelling correction over the index tokens.
    if not candidate:
        try:
            norm_q = extractor_normalize(original_query)
            q_tokens = norm_q.split()
            if q_tokens:
                vocab = list(index.keys())
                corrected_tokens = []
                for tok in q_tokens:
                    matches = difflib.get_close_matches(
                        tok, vocab, n=1, cutoff=0.8)
                    corrected_tokens.append(matches[0] if matches else tok)
                corrected_query = " ".join(corrected_tokens)
                if corrected_query != norm_q:
                    try:
                        candidate = extract_item(corrected_query, index)
                    except Exception:
                        pass
        except Exception:
            pass


def extract_items_with_identifiers_from_query(query: str) -> ExtractItemsWithIdentifiersResponseDTO:
    """
    Extract all matching item names from a query with their identifiers.

    Unlike extract_item_name_from_query, this returns multiple matches:
    - For multi-word queries: if a phrase matches exactly, returns only that phrase
    - For single-word queries: returns all items containing that word
    - For comma-separated queries (e.g., "bed, cot"): returns items matching any token

    Matching is done against:
    - Canonical item names (English)
    - All language variants (native and romanized forms)
    - Uses normalization for case-insensitive matching

    Args:
        query: Search query string. Can contain multiple terms separated by commas or spaces.
            Examples: "bed", "study table", "bed, cot", "स्टडी टेबल"

    Returns:
        ExtractItemsWithIdentifiersResponseDTO: Response with data list containing:
            - itemName: Canonical item name (e.g., "bed", "study table")
            - identifiers: List of identifier strings (e.g., ["BED_ITM_NW"])

    Example:
        >>> result = extract_items_with_identifiers_from_query("table")
        >>> print([item.itemName for item in result.data])
        ["console table", "centre table", "study table", ...]

        >>> result = extract_items_with_identifiers_from_query("study table")
        >>> print(result.data[0].itemName)
        "study table"
    """
    index = _get_synonym_index()
    if not index:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])
    q = (query or "").strip()
    if not q:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])
    id_map = _get_items_identifiers_map()
    all_item_names = set(index.values())
    def norm(s): return (extractor_normalize(s) if s else "")

    raw_tokens = [p.strip() for p in q.replace(",", " ").split() if p.strip()]
    tokens = [norm(t) for t in raw_tokens if t]
    if not tokens:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])

    # Phrase match: full query matches one item (e.g. "study table" -> "study table")
    matched = set()
    phrase_candidate = None
    try:
        phrase_candidate = extract_item(q, index)
        if phrase_candidate:
            matched.add(phrase_candidate)
    except Exception:
        pass

    items_full = _get_items_full()
    per_token_sets = []  # list of sets: items matching each token
    for token in tokens:
        if not token:
            continue
        token_matches = set()
        try:
            candidate = extract_item(token, index)
            if candidate:
                token_matches.add(candidate)
        except Exception:
            pass
        for item_name in all_item_names:
            item_norm = norm(item_name)
            if token in item_norm or token in item_norm.split():
                token_matches.add(item_name)
        for item_name, langs in items_full.items():
            if not isinstance(langs, dict):
                continue
            for forms in langs.values():
                if not isinstance(forms, dict):
                    continue
                for val in split_variants(forms.get("native", "")) + split_variants(forms.get("roman", "")):
                    phrase_norm = norm(val)
                    if not phrase_norm:
                        continue
                    if token in phrase_norm or token in phrase_norm.split():
                        token_matches.add(item_name)
                        break
        per_token_sets.append(token_matches)

    # Single word (e.g. "table"): return all items containing that word. Multi-word with phrase match (e.g. "study table"): return only that phrase match.
    if len(tokens) > 1 and phrase_candidate:
        matched = {phrase_candidate}
    elif per_token_sets:
        if len(per_token_sets) > 1:
            matched |= set.intersection(*per_token_sets)
        else:
            matched |= per_token_sets[0]

    if not matched and tokens:
        try:
            for token in tokens:
                for v in index.values():
                    if token in norm(v) or (len(token) > 2 and difflib.SequenceMatcher(None, token, norm(v)).ratio() > 0.6):
                        matched.add(v)
        except Exception:
            pass

    # Keep only items that actually contain the token(s) in name or variants (filters false positives like "console table" for "स्टडी")
    valid_tokens = [t for t in tokens if t]
    if valid_tokens:
        matched = {m for m in matched if any(_item_contains_token(
            m, token, items_full, norm) for token in valid_tokens)}

    data = [
        ItemWithIdentifiersDTO(
            itemName=item_name, identifiers=id_map.get(item_name, []))
        for item_name in sorted(matched)
    ]
    return ExtractItemsWithIdentifiersResponseDTO(data=data)


def _normalize_for_fuzzy(s: str) -> str:
    """
    Normalize string for fuzzy comparison.
    - lower
    - remove repeated characters (khatt -> khat)
    - apply extractor_normalize
    """
    if not s:
        return ""
    s = extractor_normalize(s)
    # remove repeated characters
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


def _fuzzy_match_token_to_items(token_norm: str, index: dict, cutoff: float = 0.75) -> set:
    """
    Strong fuzzy matcher that handles:
    - partial words
    - missing letters
    - typos
    - repeated letters
    - prefixes

    Example:
        wadro -> wardrobe
        khatt -> khat
    """

    if not token_norm or len(token_norm) < 2:
        return set()

    token = _normalize_for_fuzzy(token_norm)
    matches = set()

    for key, item_name in index.items():
        key_norm = _normalize_for_fuzzy(key)

        # 1️⃣ Direct substring
        if token in key_norm:
            matches.add(item_name)
            continue

        # 2️⃣ Prefix match (VERY IMPORTANT)
        if key_norm.startswith(token):
            matches.add(item_name)
            continue

        # 3️⃣ Sliding window fuzzy match
        # allows partial matching inside words
        for i in range(len(key_norm) - len(token) + 1):
            part = key_norm[i:i+len(token)]
            score = difflib.SequenceMatcher(None, token, part).ratio()
            if score >= cutoff:
                matches.add(item_name)
                break

        # 4️⃣ Full word fuzzy fallback
        else:
            score = difflib.SequenceMatcher(None, token, key_norm).ratio()
            if score >= cutoff:
                matches.add(item_name)

    return matches

def extract_items_with_identifiers_from_query_fuzzy(
    query: str,
    fuzzy_cutoff: float = 0.68,
) -> ExtractItemsWithIdentifiersResponseDTO:

    import difflib
    import re

    # ---------------- NORMALIZERS ---------------- #

    def normalize(s: str) -> str:
        if not s:
            return ""
        s = extractor_normalize(s)
        # remove repeated letters: khatt -> khat
        s = re.sub(r"(.)\1+", r"\1", s)
        return s


    def similarity(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()


    # ---------------- LOAD DATA ---------------- #

    index = _get_synonym_index()
    if not index:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])

    query = (query or "").strip()
    if not query:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])

    id_map = _get_items_identifiers_map()
    items_full = _get_items_full()

    all_item_names = set(index.values())

    tokens = [normalize(t) for t in query.replace(",", " ").split() if t.strip()]
    if not tokens:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])

    query_norm = normalize(query)

    # =====================================================
    # 1️⃣ EXACT PHRASE MATCH (highest priority)
    # =====================================================

    try:
        # Use existing extract_items_with_identifiers_from_query for exact matching
        # This handles:
        # - Single-word queries: returns ALL items containing that word (e.g., "table" -> 7 items)
        # - Multi-word queries: returns only exact phrase matches (e.g., "study table" -> 1 item)
        # - Comma-separated queries: returns items matching any token
        exact_matches = extract_items_with_identifiers_from_query(query)
        if exact_matches and exact_matches.data:
            return exact_matches
    except Exception:
        pass


    # =====================================================
    # 2️⃣ FUZZY PHRASE MATCH
    # =====================================================

    phrase_scores = {}

    for key, item in index.items():
        score = similarity(query_norm, normalize(key))
        if score >= fuzzy_cutoff:
            phrase_scores[item] = max(score, phrase_scores.get(item, 0))

    if phrase_scores:
        best_score = max(phrase_scores.values())
        best_items = [
            item for item, s in phrase_scores.items()
            if s >= best_score * 0.9
        ]

        return ExtractItemsWithIdentifiersResponseDTO(
            data=[
                ItemWithIdentifiersDTO(
                    itemName=item,
                    identifiers=id_map.get(item, []),
                )
                for item in sorted(best_items)
            ]
        )


    # =====================================================
    # 3️⃣ TOKEN LEVEL MATCHING WITH SCORING
    # =====================================================

    item_scores = {}

    for token in tokens:

        # ---------- check synonyms ---------- #
        for key, item in index.items():
            key_norm = normalize(key)

            score = 0

            # exact substring
            if token in key_norm:
                score = 1.0

            # prefix match
            elif key_norm.startswith(token):
                score = 0.95

            # partial fuzzy match
            else:
                # sliding window
                for i in range(len(key_norm) - len(token) + 1):
                    part = key_norm[i:i+len(token)]
                    sim = similarity(token, part)
                    if sim > score:
                        score = sim

                # full fuzzy
                sim_full = similarity(token, key_norm)
                score = max(score, sim_full)

            if score >= fuzzy_cutoff:
                item_scores[item] = max(score, item_scores.get(item, 0))


        # ---------- canonical name match ---------- #
        for item in all_item_names:
            item_norm = normalize(item)

            if token in item_norm:
                item_scores[item] = max(0.92, item_scores.get(item, 0))


        # ---------- native / roman variants ---------- #
        for item_name, langs in items_full.items():
            if not isinstance(langs, dict):
                continue

            for forms in langs.values():
                if not isinstance(forms, dict):
                    continue

                variants = (
                    split_variants(forms.get("native", ""))
                    + split_variants(forms.get("roman", ""))
                )

                for val in variants:
                    val_norm = normalize(val)

                    if token in val_norm:
                        item_scores[item_name] = max(
                            0.93,
                            item_scores.get(item_name, 0),
                        )


    # =====================================================
    # 4️⃣ FILTER LOW CONFIDENCE MATCHES
    # =====================================================

    if not item_scores:
        return ExtractItemsWithIdentifiersResponseDTO(data=[])

    best_score = max(item_scores.values())

    # keep only strong matches relative to best
    filtered_items = [
        item for item, score in item_scores.items()
        if score >= best_score * 0.7
    ]


    # =====================================================
    # 5️⃣ SORT BY SCORE
    # =====================================================

    filtered_items.sort(key=lambda x: (-item_scores[x], x))


    # =====================================================
    # 6️⃣ BUILD RESPONSE
    # =====================================================

    return ExtractItemsWithIdentifiersResponseDTO(
        data=[
            ItemWithIdentifiersDTO(
                itemName=item,
                identifiers=id_map.get(item, []),
            )
            for item in filtered_items
        ]
    )



def add_item_to_items_with_identifiers(item_payload: dict) -> dict:
    """
    Add or update an item in resources/items_with_identifiers.json.

    Writes a new item entry or updates an existing one in the items_with_identifiers.json
    file. The file is used by the extractor to map queries to item identifiers.
    After writing, invalidates in-memory caches so the next request reloads the file.

    Args:
        item_payload: JSON object containing:
            - itemName (str, required): The canonical item name (used as JSON key)
            - Language entries (optional): hindi, bengali, tamil, telugu, kannada, malayalam
              Each language entry should have: {"native": "...", "roman": "..."}
            - identifiers (list[str], optional): List of identifier strings

    Returns:
        dict: {"ok": True, "itemName": "<item_name>"} on success.

    Raises:
        ValueError: If itemName is missing or empty.
        IOError: If file cannot be read or written.

    Example:
        >>> payload = {
        ...     "itemName": "book shelf",
        ...     "hindi": {"native": "बुक शेल्फ", "roman": "buk shelf"},
        ...     "identifiers": ["BOK_ITM_NW"]
        ... }
        >>> result = add_item_to_items_with_identifiers(payload)
        >>> print(result)
        {"ok": True, "itemName": "book shelf"}
    """
    item_name = item_payload.get("itemName", "").strip()
    if not item_name:
        raise ValueError("itemName is required and cannot be empty")

    file_path = get_items_with_identifiers_path()
    
    # Load existing data
    data = {}
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise IOError(f"Failed to read {file_path}: {e}")

    # Build the item entry from payload (exclude itemName from entry fields)
    entry = {}
    for key, value in item_payload.items():
        if key == "itemName":
            continue
        entry[key] = value

    # Update or add the item
    data[item_name] = entry

    # Write back to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to write {file_path}: {e}")

    # Invalidate caches so next request reloads
    invalidate_items_caches()
    
    return {"ok": True, "itemName": item_name}


def fetch_estimator_items_vishanti(item_identifier: str | None = None) -> list[VishantiItemDTO]:
    """
    Fetch ALL items from the VISHANTI Qdrant collection and return them as VishantiItemDTO list.

    Uses Qdrant scroll pagination to read the full collection (no explicit external limit).
    """
    items: list[VishantiItemDTO] = []
    offset = None

    try:
        while True:
            scroll_kwargs = dict(
                collection_name=COLLECTION_NAME_VISHANTI,
                limit=1_000,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )

            # If an itemIdentifier is provided, filter on that payload field.
            if item_identifier:
                scroll_kwargs["scroll_filter"] = Filter(
                    must=[
                        FieldCondition(
                            key="item_identifier",
                            match=MatchAny(any=[item_identifier]),
                        )
                    ]
                )

            records, offset = qdrant.scroll(**scroll_kwargs)

            for rec in records:
                p = dict(rec.payload) if rec.payload else {}

                image = p.get("image")
                if isinstance(image, dict) and "default" in image:
                    image = image["default"]

                items.append(
                    VishantiItemDTO(
                        estimatorId=p.get("estimator_id"),
                        roomName=p.get("room_name") or "",
                        itemName=p.get("item_name") or "",
                        itemId=p.get("id"),
                        amount=float(p.get("amount") or 0),
                        area=p.get("area") or "",
                        projectName=p.get("project_name") or "",
                        attributes=p.get("attributes"),
                        attributesParsed=p.get("attributes_parsed"),
                        itemTypeIdentifier=p.get("item_type_identifier") or "",
                        itemIdentifier=p.get("item_identifier") or "",
                        userId=p.get("user_id") if "user_id" in p else 0,
                        image=image,
                    )
                )

            if not offset:
                break
    except Exception as e:
        print(f"fetch_estimator_items_vishanti: qdrant.scroll error: {e}")
        raise

    return items


def fetch_items_view(
    item_identifier: str | None = None
) -> list[VishantiAggregatedItemDTO]:
    """
    Build a consolidated view of Vishanti items with per-sqft or per-unit pricing.

    Price calculation:
    - WD items (with Measurement): price per sqft = amount / measurement_sqft
    - LF items (with Quantity): price per unit = amount / quantity
    - Others: total amount

    Groups by (city, price_type).
    """
    per_item: dict[str, dict] = {}
    offset = None

    while True:
        scroll_kwargs = dict(
            collection_name=COLLECTION_NAME_VISHANTI,
            limit=1_000,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        if item_identifier:
            scroll_kwargs["scroll_filter"] = Filter(
                must=[
                    FieldCondition(
                        key="item_identifier",
                        match=MatchAny(any=[item_identifier]),
                    )
                ]
            )
        records, offset = qdrant.scroll(**scroll_kwargs)

        for rec in records:
            p = dict(rec.payload) if rec.payload else {}
            identifier = (p.get("item_identifier") or "").strip()
            if not identifier:
                continue
            area_raw = (p.get("area") or "").strip()
            if not area_raw:
                continue
            # Normalize city name to handle typos/variations
            area = normalize_city_name(area_raw)
            amount = float(p.get("amount") or 0)
            if amount <= 0:
                continue

            # Filter out items without attributes or with empty attributes
            attrs_parsed = p.get("attributes_parsed") or {}
            if not attrs_parsed or (isinstance(attrs_parsed, dict) and len(attrs_parsed) == 0):
                continue

            # Calculate normalized price (per sqft or per unit)
            # Priority 1: If "Rate" or "Rate per Sqft" attribute exists in parsed attributes, use that directly
            # Priority 2: measurement_sqft > 0 means Per Sqft pricing (calculate from amount)
            # Priority 3: Quantity exists (LF items) means Per Unit pricing
            measurement_sqft = float(p.get("measurement_sqft") or 0.0)
            price_type = "Total"
            normalized_price = amount

            # First check: if Rate or Rate per Sqft attribute exists, use it directly
            rate_found = False
            if attrs_parsed:
                # Check for "Rate per Sqft" first
                if "Rate per Sqft" in attrs_parsed:
                    rate_str = attrs_parsed.get("Rate per Sqft", "").strip()
                    try:
                        # Try to extract number from strings like "1200 sqft" or just "1200"
                        rate = float(rate_str.split()[0]) if ' ' in rate_str else float(rate_str)
                        if rate > 0:
                            price_type = "Per Sqft"
                            normalized_price = rate
                            rate_found = True
                    except (ValueError, TypeError, IndexError):
                        pass
                # Check for "Rate" (general rate attribute)
                elif "Rate" in attrs_parsed:
                    rate_str = attrs_parsed.get("Rate", "").strip()
                    try:
                        # Try to extract number from strings like "1200" or "1200 sqft"
                        rate = float(rate_str.split()[0]) if ' ' in rate_str else float(rate_str)
                        if rate > 0:
                            price_type = "Per Sqft"
                            normalized_price = rate
                            rate_found = True
                    except (ValueError, TypeError, IndexError):
                        pass

            # Second check: if no Rate attribute and measurement_sqft exists and > 0, calculate per sqft price
            if not rate_found and measurement_sqft > 0:
                price_type = "Per Sqft"
                normalized_price = amount / measurement_sqft
            # Third check: if Quantity exists (LF items), calculate per unit price
            elif not rate_found and attrs_parsed and "Quantity" in attrs_parsed:
                qty_str = attrs_parsed.get("Quantity", "").strip()
                try:
                    # Try to extract number from strings like "5" or "5 units"
                    qty = float(qty_str.split()[0]) if ' ' in qty_str else float(qty_str)
                    if qty > 0:
                        price_type = "Per Unit"
                        normalized_price = amount / qty
                except (ValueError, TypeError, IndexError):
                    pass
            # Else: use total amount as-is (should rarely happen after filtering)

            if identifier not in per_item:
                img = p.get("image")
                if isinstance(img, dict) and "default" in img:
                    img = img["default"]
                per_item[identifier] = {
                    "itemName": p.get("item_name") or "",
                    "itemTypeIdentifier": p.get("item_type_identifier") or "",
                    "image": img,
                    "areaGroups": {},  # (area, price_type) -> [normalized_prices...]
                }

            entry = per_item[identifier]
            item_name = p.get("item_name") or ""
            item_type = p.get("item_type_identifier") or ""
            if not entry["itemName"] and item_name:
                entry["itemName"] = item_name
            if not entry["itemTypeIdentifier"] and item_type:
                entry["itemTypeIdentifier"] = item_type
            if entry["image"] is None and p.get("image"):
                img = p.get("image")
                entry["image"] = img["default"] if isinstance(img, dict) and "default" in img else img

            area_key = (area, price_type)
            groups = entry["areaGroups"]
            groups.setdefault(area_key, []).append(normalized_price)

        if not offset:
            break

    result: list[VishantiAggregatedItemDTO] = []

    for identifier, entry in per_item.items():
        area_groups = entry["areaGroups"]
        if not area_groups:
            continue

        area_stats: list[AreaPriceStatsDTO] = []
        for (area, price_type), prices in area_groups.items():
            if not prices:
                continue
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            area_stats.append(
                AreaPriceStatsDTO(
                    area=area,
                    priceType=price_type,
                    minPrice=min_price,
                    maxPrice=max_price,
                    avgPrice=avg_price,
                )
            )

        if not area_stats:
            continue

        result.append(
            VishantiAggregatedItemDTO(
                itemName=entry["itemName"],
                itemIdentifier=identifier,
                itemTypeIdentifier=entry["itemTypeIdentifier"],
                image=entry["image"],
                areaStats=area_stats,
            )
        )

    return result


def fetch_items_view_by_city(
    item_identifiers: list[str],
    city: str | None = None
) -> list[VishantiAggregatedItemDTO]:
    """
    Build a consolidated view of Vishanti items filtered by city.
    
    Similar to fetch_items_view but:
    - Accepts multiple item identifiers
    - Filters results by specified city
    
    Args:
        item_identifiers: List of item identifier strings to fetch
        city: City name to filter by (will be normalized for matching)
    
    Returns:
        list[VishantiAggregatedItemDTO]: Items with areaStats filtered to the specified city
    """
    if not item_identifiers:
        return []
    
    # Normalize the requested city for matching
    normalized_city = normalize_city_name(city) if city else None
    
    per_item: dict[str, dict] = {}
    offset = None

    while True:
        scroll_kwargs = dict(
            collection_name=COLLECTION_NAME_VISHANTI,
            limit=1_000,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        # Filter by multiple item identifiers
        scroll_kwargs["scroll_filter"] = Filter(
            must=[
                FieldCondition(
                    key="item_identifier",
                    match=MatchAny(any=item_identifiers),
                )
            ]
        )
        records, offset = qdrant.scroll(**scroll_kwargs)

        for rec in records:
            p = dict(rec.payload) if rec.payload else {}
            identifier = (p.get("item_identifier") or "").strip()
            if not identifier:
                continue
            area_raw = (p.get("area") or "").strip()
            if not area_raw:
                continue
            
            # Normalize city name to handle typos/variations
            area = normalize_city_name(area_raw)
            
            # If city filter is specified, skip records not matching
            if normalized_city and area.lower() != normalized_city.lower():
                continue
            
            amount = float(p.get("amount") or 0)
            if amount <= 0:
                continue

            # Filter out items without attributes or with empty attributes
            attrs_parsed = p.get("attributes_parsed") or {}
            if not attrs_parsed or (isinstance(attrs_parsed, dict) and len(attrs_parsed) == 0):
                continue

            # Calculate normalized price (same logic as fetch_items_view)
            measurement_sqft = float(p.get("measurement_sqft") or 0.0)
            price_type = "Total"
            normalized_price = amount

            # First check: if Rate or Rate per Sqft attribute exists, use it directly
            rate_found = False
            if attrs_parsed:
                # Check for "Rate per Sqft" first
                if "Rate per Sqft" in attrs_parsed:
                    rate_str = attrs_parsed.get("Rate per Sqft", "").strip()
                    try:
                        rate = float(rate_str.split()[0]) if ' ' in rate_str else float(rate_str)
                        if rate > 0:
                            price_type = "Per Sqft"
                            normalized_price = rate
                            rate_found = True
                    except (ValueError, TypeError, IndexError):
                        pass
                # Check for "Rate" (general rate attribute)
                elif "Rate" in attrs_parsed:
                    rate_str = attrs_parsed.get("Rate", "").strip()
                    try:
                        rate = float(rate_str.split()[0]) if ' ' in rate_str else float(rate_str)
                        if rate > 0:
                            price_type = "Per Sqft"
                            normalized_price = rate
                            rate_found = True
                    except (ValueError, TypeError, IndexError):
                        pass

            # Second check: if no Rate attribute and measurement_sqft exists and > 0
            if not rate_found and measurement_sqft > 0:
                price_type = "Per Sqft"
                normalized_price = amount / measurement_sqft
            # Third check: if Quantity exists (LF items), calculate per unit price
            elif not rate_found and attrs_parsed and "Quantity" in attrs_parsed:
                qty_str = attrs_parsed.get("Quantity", "").strip()
                try:
                    qty = float(qty_str.split()[0]) if ' ' in qty_str else float(qty_str)
                    if qty > 0:
                        price_type = "Per Unit"
                        normalized_price = amount / qty
                except (ValueError, TypeError, IndexError):
                    pass

            if identifier not in per_item:
                img = p.get("image")
                if isinstance(img, dict) and "default" in img:
                    img = img["default"]
                per_item[identifier] = {
                    "itemName": p.get("item_name") or "",
                    "itemTypeIdentifier": p.get("item_type_identifier") or "",
                    "image": img,
                    "areaGroups": {},  # (area, price_type) -> [normalized_prices...]
                }

            entry = per_item[identifier]
            item_name = p.get("item_name") or ""
            item_type = p.get("item_type_identifier") or ""
            if not entry["itemName"] and item_name:
                entry["itemName"] = item_name
            if not entry["itemTypeIdentifier"] and item_type:
                entry["itemTypeIdentifier"] = item_type
            if entry["image"] is None and p.get("image"):
                img = p.get("image")
                entry["image"] = img["default"] if isinstance(img, dict) and "default" in img else img

            area_key = (area, price_type)
            groups = entry["areaGroups"]
            groups.setdefault(area_key, []).append(normalized_price)

        if not offset:
            break

    result: list[VishantiAggregatedItemDTO] = []

    for identifier, entry in per_item.items():
        area_groups = entry["areaGroups"]
        if not area_groups:
            continue

        area_stats: list[AreaPriceStatsDTO] = []
        for (area, price_type), prices in area_groups.items():
            if not prices:
                continue
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            area_stats.append(
                AreaPriceStatsDTO(
                    area=area,
                    priceType=price_type,
                    minPrice=min_price,
                    maxPrice=max_price,
                    avgPrice=avg_price,
                )
            )

        if not area_stats:
            continue

        result.append(
            VishantiAggregatedItemDTO(
                itemName=entry["itemName"],
                itemIdentifier=identifier,
                itemTypeIdentifier=entry["itemTypeIdentifier"],
                image=entry["image"],
                areaStats=area_stats,
            )
        )

    return result
