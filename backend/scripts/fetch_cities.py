#!/usr/bin/env python3
"""
Fetch unique cities from the database and generate:
1. city.csv - List of unique city names
2. city_canonical_mapping.json - Mapping of normalized city names to canonical forms

This script connects to the database using credentials from utils.constants.dbCred
and fetches cities from finalized estimators.
"""

import csv
import json
import os
import sys
import unicodedata
import re
from mysql.connector import Error

# -------------------------------------------------
# Ensure project root is on sys.path BEFORE local imports
# -------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# -------------------------------------------------
# Imports from project
# -------------------------------------------------
from dbConfig.mysqlConnectionConfig import get_mysql_connection
from utils.constants import (
    APP_ENVIRONMENT,
    CITY_CSV_PATH,
    CITY_CANONICAL_MAPPING_PATH,
    RESOURCES_DIR
)

# -------------------------------------------------
# SQL Query to fetch cities
# -------------------------------------------------

QUERY_CITIES = """
SELECT DISTINCT(a.city) as city
FROM vishanti.estimator e
LEFT JOIN zeus.address a ON a.project_id = e.project_id
WHERE e.status = 'FINALIZED'
  AND a.city IS NOT NULL
  AND TRIM(a.city) != ''
ORDER BY a.city;
"""

# -------------------------------------------------
# Normalization function (similar to extractor.normalize)
# -------------------------------------------------


def normalize_city(text: str) -> str:
    """
    Normalize city name for matching:
    - NFKC Unicode normalization
    - Lowercase
    - Remove special chars (keep alphanumeric and spaces)
    - Collapse multiple spaces
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.lower()

    # Remove zero-width chars
    text = text.replace("\u200c", "").replace("\u200d", "")

    # Keep alphanumeric and spaces, replace others with space
    text = "".join(
        ch if ch.isalnum() or ch.isspace() else " "
        for ch in text
    )

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


# -------------------------------------------------
# Core methods
# -------------------------------------------------


def fetch_cities_from_db(environment: str):
    """
    Fetch unique city names from the database.

    Args:
        environment: Environment name (local, dev, uat, prod)

    Returns:
        list[str]: List of unique city names (non-empty)

    Raises:
        Various exceptions if database connection fails
    """
    connection = None
    cursor = None
    tunnel = None

    try:
        print(f"🔌 Connecting to database (environment: {environment})...")
        connection, tunnel = get_mysql_connection(environment)
        cursor = connection.cursor(dictionary=True)

        print(f"📊 Executing query to fetch cities...")
        cursor.execute(QUERY_CITIES)
        rows = cursor.fetchall()

        if not rows:
            print("⚠️  No cities found in database.")
            return []

        # Extract city names and filter out empty strings
        cities = [
            row['city'].strip()
            for row in rows
            if row.get('city') and row['city'].strip()
        ]

        print(f"✅ Found {len(cities)} unique cities")
        return cities

    except (Error, ValueError) as e:
        print(f"❌ Database error: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        if tunnel:
            tunnel.stop()


def write_cities_csv(cities: list[str], output_file: str):
    """
    Write cities to CSV file.

    Args:
        cities: List of city names
        output_file: Path to output CSV file
    """
    if not cities:
        print("⚠️  No cities to write to CSV")
        return

    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write CSV with header
    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["city"])  # Header
        for city in cities:
            writer.writerow([city])

    print(f"✅ Cities written to {output_file}")


def load_manual_typos() -> dict:
    """
    Load manually curated city typos from city_typos_manual.json
    
    Returns:
        dict: Mapping of canonical city names to their typo variants
    """
    manual_typos_path = os.path.join(RESOURCES_DIR, "city_typos_manual.json")
    
    if not os.path.exists(manual_typos_path):
        print(f"   ⚠️  Manual typos file not found: {manual_typos_path}")
        return {}
    
    try:
        with open(manual_typos_path, "r", encoding="utf-8") as f:
            typos = json.load(f)
        print(f"   ✅ Loaded manual typos for {len(typos)} cities")
        return typos
    except Exception as e:
        print(f"   ⚠️  Error loading manual typos: {e}")
        return {}


def find_canonical_match(city_normalized: str, manual_typos: dict) -> str | None:
    """
    Find which canonical city a normalized city name belongs to.
    
    Handles both exact matches and multi-word cities (e.g., "Bangalore Sarjapur" matches "Bangalore").
    
    Args:
        city_normalized: Normalized city name
        manual_typos: Manual typo mappings
        
    Returns:
        Canonical city name if match found, None otherwise
    """
    # Try exact match first
    for canonical, variants in manual_typos.items():
        for variant in variants:
            if city_normalized == variant.lower():
                return canonical
    
    # Try matching first word for multi-word cities (e.g., "bangalore sarjapur" -> "bangalore")
    words = city_normalized.split()
    if len(words) > 1:
        first_word = words[0]
        for canonical, variants in manual_typos.items():
            for variant in variants:
                if first_word == variant.lower():
                    return canonical
    
    return None


def generate_canonical_mapping(cities: list[str], output_file: str):
    """
    Generate a canonical mapping JSON file for city name normalization.

    Merges database cities with manually curated typo variations to create
    a comprehensive mapping from canonical city names to all their variants.

    Structure:
    {
        "Bangalore": ["bangalore", "bengaluru", "bengalore", "banglore", ...],
        "Hyderabad": ["hyderabad", "hydrabad", ...],
        ...
    }

    Args:
        cities: List of city names from database
        output_file: Path to output JSON file
    """
    if not cities:
        print("⚠️  No cities to generate mapping")
        return

    print("\n   📚 Loading manual typo variations...")
    manual_typos = load_manual_typos()
    
    # Start with manual typos as base (already in correct format)
    mapping = {canonical: list(variants) for canonical, variants in manual_typos.items()}
    
    print(f"   🔍 Processing {len(cities)} cities from database...")
    
    # Track new cities not in manual typos
    new_cities = []
    matched_count = 0
    
    for city in cities:
        city_normalized = normalize_city(city).lower()
        
        if not city_normalized:
            continue
        
        # Try to find which canonical city this belongs to
        canonical_match = find_canonical_match(city_normalized, manual_typos)
        
        if canonical_match:
            # Add to existing canonical city if not already there
            if city.lower() not in mapping[canonical_match]:
                mapping[canonical_match].append(city.lower())
            matched_count += 1
        else:
            # New city not in manual typos - create new entry
            # Use proper case version as canonical
            canonical = city if city[0].isupper() else city.title()
            
            if canonical not in mapping:
                mapping[canonical] = [city.lower()]
                new_cities.append(canonical)
            elif city.lower() not in mapping[canonical]:
                mapping[canonical].append(city.lower())
    
    # Sort variants within each canonical for consistency
    for canonical in mapping:
        mapping[canonical] = sorted(set(mapping[canonical]))
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write JSON (sorted by canonical name for readability)
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(mapping, file, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\n✅ Canonical mapping written to {output_file}")
    print(f"   📊 Statistics:")
    print(f"      Total canonical cities: {len(mapping)}")
    print(f"      Database cities matched to typos: {matched_count}")
    print(f"      New cities from database: {len(new_cities)}")
    
    # Show total variants
    total_variants = sum(len(variants) for variants in mapping.values())
    print(f"      Total variants: {total_variants}")
    
    # Show examples of cities with most variants
    cities_by_variant_count = sorted(mapping.items(), key=lambda x: len(x[1]), reverse=True)
    if cities_by_variant_count:
        print(f"\n   🏆 Top cities by variant count:")
        for canonical, variants in cities_by_variant_count[:5]:
            print(f"      {canonical}: {len(variants)} variant(s)")


def fetch_and_generate_city_files(environment: str):
    """
    Main workflow:
    1. Fetch cities from database
    2. Write to city.csv
    3. Generate city_canonical_mapping.json

    Args:
        environment: Environment name (local, dev, uat, prod)
    """
    try:
        print("\n" + "="*60)
        print("🌍 City Data Fetch & Generation Script")
        print("="*60)

        # Step 1: Fetch cities from database
        cities = fetch_cities_from_db(environment)

        if not cities:
            print("\n⚠️  No cities found. Skipping file generation.")
            return

        # Step 2: Write CSV
        print(f"\n📝 Writing cities to CSV...")
        write_cities_csv(cities, CITY_CSV_PATH)

        # Step 3: Generate canonical mapping
        print(f"\n🗺️  Generating canonical mapping...")
        generate_canonical_mapping(cities, CITY_CANONICAL_MAPPING_PATH)

        print("\n" + "="*60)
        print("✅ City data fetch and generation completed successfully!")
        print("="*60)
        print(f"   CSV: {CITY_CSV_PATH}")
        print(f"   JSON: {CITY_CANONICAL_MAPPING_PATH}")
        print(f"   Total cities: {len(cities)}")
        print()

    except (Error, ValueError) as e:
        # Don't crash container startup if DB isn't reachable
        print(f"\n⚠️  Skipping city data fetch (cannot connect): {e}")
        print("   Container will continue with existing city files if available.\n")
        return

    except Exception as e:
        # Catch-all for unexpected issues
        print(f"\n⚠️  Unexpected error during city data fetch: {e}")
        print("   Container will continue with existing city files if available.\n")
        import traceback
        traceback.print_exc()
        return


# -------------------------------------------------
# Script entry point
# -------------------------------------------------


if __name__ == "__main__":
    fetch_and_generate_city_files(APP_ENVIRONMENT)
