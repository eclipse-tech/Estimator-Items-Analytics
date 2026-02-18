
import unicodedata
import re

def normalize(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.lower()

    # remove zero-width chars (Bengali / Indic safe)
    text = text.replace("\u200c", "").replace("\u200d", "")

    # Keep alphanumeric chars, spaces, AND Unicode combining marks (for Indic scripts)
    # Combining marks (category Mn, Mc) are essential for Hindi, Tamil, Kannada, etc.
    text = "".join(
        ch if ch.isalnum() or ch.isspace() or unicodedata.category(ch) in ('Mn', 'Mc') else " "
        for ch in text
    )

    text = re.sub(r"\s+", " ", text).strip()
    return text

def split_variants(text: str):
    if not text:
        return []

    text = text.replace("，", ",").replace("、", ",")
    return [t.strip() for t in text.split(",") if t.strip()]

def build_synonym_index(item_json: dict):
    synonym_index = {}

    for item, langs in item_json.items():
        # Index the canonical item name itself and its tokens
        item_norm = normalize(item)
        if item_norm:
            if item_norm not in synonym_index:
                synonym_index[item_norm] = item
            for tok in item_norm.split():
                if tok:
                    if tok not in synonym_index:
                        synonym_index[tok] = item

        for forms in langs.values():
            for val in split_variants(forms.get("native", "")):
                phrase_norm = normalize(val)
                if phrase_norm:
                    # Full phrase
                    if phrase_norm not in synonym_index:
                        synonym_index[phrase_norm] = item
                    # Also index individual tokens so queries like "स्टोरेज"
                    # can match "स्टोरेज कैबिनेट"
                    for tok in phrase_norm.split():
                        if tok:
                            if tok not in synonym_index:
                                synonym_index[tok] = item
            for val in split_variants(forms.get("roman", "")):
                phrase_norm = normalize(val)
                if phrase_norm:
                    if phrase_norm not in synonym_index:
                        synonym_index[phrase_norm] = item
                    for tok in phrase_norm.split():
                        if tok:
                            if tok not in synonym_index:
                                synonym_index[tok] = item

    return synonym_index

def extract_item(query: str, synonym_index: dict):
    """
    Extract the best single matching item name from a query.
    Prefers longer n-gram matches (e.g., "study table" over "table").
    
    Returns:
        str | None: The canonical item name if found, None otherwise.
    """
    query_norm = normalize(query)
    tokens = query_norm.split()
    token_count = len(tokens)
    print(f"Token count: {token_count}")
    max_n=max(10, token_count)
    best_item = None
    best_len = 0

    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i:i+n])
            if gram in synonym_index and n > best_len:
                best_item = synonym_index[gram]
                best_len = n

    return best_item


def extract_all_items(query: str, synonym_index: dict):
    """
    Extract ALL matching item names from a query.
    
    For single-word queries like "table", returns all items that contain "table"
    (e.g., "console table", "centre table", "study table").
    
    For multi-word queries, tries to match the full phrase first. If found,
    returns only that item. Otherwise, returns items matching any token.
    
    Args:
        query: Search query string
        synonym_index: Dictionary mapping normalized keys to canonical item names
        
    Returns:
        list[str]: List of canonical item names that match the query
        
    Examples:
        >>> extract_all_items("table", index)
        ["console table", "centre table", "study table", ...]
        
        >>> extract_all_items("study table", index)
        ["study table"]
    """
    query_norm = normalize(query)
    tokens = query_norm.split()
    
    if not tokens:
        return []
    
    # Try to find longest matching phrase first
    max_n = max(10, len(tokens))
    best_len = 0
    phrase_matches = set()
    
    for n in range(1, min(max_n, len(tokens)) + 1):
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i:i+n])
            if gram in synonym_index:
                if n > best_len:
                    phrase_matches = {synonym_index[gram]}
                    best_len = n
                elif n == best_len:
                    phrase_matches.add(synonym_index[gram])
    
    # If we found a multi-word phrase match, return only those
    if best_len > 1:
        return list(phrase_matches)
    
    # For single-word queries, collect all items where the word appears
    # This handles cases like "table" matching "console table", "study table", etc.
    matched_items = set()
    
    for token in tokens:
        # Direct lookup if token exists as a key
        if token in synonym_index:
            matched_items.add(synonym_index[token])
        
        # Also check if token appears in multi-word keys
        for key, item in synonym_index.items():
            if token in key.split():
                matched_items.add(item)
    
    return list(matched_items)


def build_vector(text: str):
    return [
        len(text) % 10,
        sum(ord(c) for c in text) % 10,
        len(text.split()) % 10,
        1
    ]
