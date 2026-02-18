import csv
import json
import os
import sys
from typing import Dict, List, Set

# Ensure project root (/app in container) is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


from utils.constants import ITEMS_JSON_IN, ITEMS_JSON_OUT, ITEM_IDENTIFIERS_MAP_CSV_PATH , BACKEND_DIR
from utils.extractor import normalize


def _canonical_key(name: str) -> str:
    """Normalize and lower for case-insensitive matching."""
    return (normalize(name) or "").lower()


def build_identifier_index(csv_path: str) -> Dict[str, Set[str]]:
    """
    Build a mapping from normalized (case-insensitive) item name -> set of identifiers
    based on query_result.csv.
    """
    index: Dict[str, Set[str]] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        # Support semicolon- or comma-delimited CSV (e.g. "name";"identifier" vs name,identifier)
        first_line = f.readline()
        f.seek(0)
        delimiter = ";" if ";" in first_line else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            name = (row.get("name") or "").strip()
            identifier = (row.get("identifier") or "").strip()
            if not name or not identifier:
                continue
            key = _canonical_key(name)
            if not key:
                continue
            index.setdefault(key, set()).add(identifier)
    return index


def enrich_items_with_identifiers(
    items_path: str, csv_path: str, out_path: str
) -> None:
    """
    Load items.json and query_result.csv, add identifiers for matching
    item names, and write a new JSON file.
    """
    with open(items_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    id_index = build_identifier_index(csv_path)

    updated: Dict[str, dict] = {}
    unmatched: List[str] = []

    for item_name, langs in items.items():
        lookup_key = _canonical_key(item_name)
        identifiers = id_index.get(lookup_key)
        if identifiers is None and lookup_key:
            # Fallback: match any index key that equals when compared case-insensitively
            for k, v in id_index.items():
                if k.lower() == lookup_key:
                    identifiers = v
                    break

        if identifiers:
            ids_list = sorted(identifiers)
            enriched = dict(langs)
            enriched["identifiers"] = ids_list
            updated[item_name] = enriched
        else:
            unmatched.append(item_name)

    # Write JSON: one line per language (compact), then "identifiers" last
    def dump_compact(obj):
        return json.dumps(obj, ensure_ascii=False)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("{\n")
        item_blocks = []
        for item_name, obj in updated.items():
            inner_lines = []
            for key, value in obj.items():
                inner_lines.append(f'        {dump_compact(key)}: {dump_compact(value)},')
            # Remove trailing comma from last line (replace last "," with "")
            if inner_lines:
                inner_lines[-1] = inner_lines[-1][:-1]
            item_blocks.append(
                f'    {dump_compact(item_name)}: {{\n' + "\n".join(inner_lines) + "\n    }"
            )
        f.write(",\n".join(item_blocks))
        f.write("\n}\n")

    print(f"Written enriched items to: {out_path}")
    print(f"Total items: {len(items)}")
    print(f"Items with identifiers: {sum(1 for v in updated.values() if 'identifiers' in v)}")
    print(f"Items without identifiers: {len(unmatched)}")


if __name__ == "__main__":
    enrich_items_with_identifiers(ITEMS_JSON_IN, ITEM_IDENTIFIERS_MAP_CSV_PATH, ITEMS_JSON_OUT)

