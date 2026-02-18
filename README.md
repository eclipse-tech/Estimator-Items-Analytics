# Estimator-Items-Analytics

A FastAPI-based analytics platform for searching and managing estimator items with multilingual support.

## API Structure

The API follows a modular architecture with routes organized by functionality. All endpoints are prefixed with `/v1/api/analytics`.

### API Endpoints

#### Base URL
- Local: `http://localhost:8090/v1/api/analytics`

#### Search Routes (`/v1/api/analytics`)
- `GET /search-fuzz` - Fuzzy search for quick text matching
- `POST /search` - Legacy search endpoint (deprecated)
- `GET /search-items` - Main search endpoint with multilingual support

#### Items Routes (`/v1/api/analytics`)
- `GET /fetch-items` - Fetch estimator items from external API
- `GET /vishanti-items` - Fetch all items from Vishanti Qdrant collection
- `GET /vishanti-items-view` - Aggregated view with pricing statistics
- `GET /vishanti-items-by-city` - **NEW** Aggregated view filtered by city (supports multiple items)
- `POST /add-items-to-qdrant` - Add items directly to Qdrant
- `GET /extract-item` - Extract single canonical item name from query
- `GET /extract-items-with-identifiers` - Extract all matching items with identifiers
- `GET /extract-items-with-identifiers-fuzzy` - Extract with fuzzy matching for typos
- `GET /items-by-identifiers` - Fetch items from Qdrant by identifiers
- `POST /items-with-identifiers` - Add/update items in resources file

#### Ingest Routes (`/v1/api/analytics`)
- `POST /ingest` - Ingest estimator items into Qdrant database

#### Config Routes (`/v1/api/analytics`)
- `GET /config` - Get application configuration

#### Auth Routes (`/v1/api/analytics`)
- `GET /get-auth-token` - Fetch authentication token

#### Health Check
- `GET /` - Root endpoint with API information
- `GET /health` - Health check endpoint

## Project Structure

```
backend/
├── routes/
│   ├── __init__.py
│   ├── controller.py          # Main app with router configuration
│   ├── items_routes.py        # Item management endpoints
│   ├── search_routes.py       # Search functionality endpoints
│   ├── ingest_routes.py       # Data ingestion endpoints
│   ├── config_routes.py       # Configuration endpoints
│   └── auth_routes.py         # Authentication endpoints
├── services/                  # Business logic layer
├── utils/                     # Helper functions and utilities
├── resources/                 # Static resources and data files
└── scripts/                   # Data enrichment scripts
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.10+

### Running with Docker

1. Update the shared key path in `docker-compose.yml` if needed
2. Start the services:
```bash
docker-compose up --build
```

3. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8090/v1/api/analytics
- API Documentation: http://localhost:8090/docs
- Qdrant: http://localhost:6333

4. Container names:
- Backend: `estimator-backend`
- Frontend: `estimator-frontend`
- Qdrant: `estimator-qdrant`

## Key Features Explained

### 🌍 City Canonical Mapping System

The application includes an intelligent city name normalization system that handles typos and variations:

- **Automatic Grouping**: "Bangalore", "Bengaluru", "Bangalore Sarjapur" → all map to "Bangalore"
- **Typo Tolerance**: "banglore", "bengalore", "banaglore" → recognized as "Bangalore"
- **Multi-language Support**: "हैदराबाद" (Hindi), "హైదరాబాద్" (Telugu) → map to "Hyderabad"
- **Multi-word Cities**: "Bangalore Sarjapur" extracts base city "Bangalore"

#### How It Works
1. **Manual Typos** (`city_typos_manual.json`): Curated list of typo variations for major cities
2. **Database Sync** (`fetch_cities.py`): Fetches cities from database and merges with manual typos
3. **Smart Matching**: Two-pass matching (exact + first-word) for comprehensive coverage

See [`CITY_MAPPING_README.md`](backend/CITY_MAPPING_README.md) for detailed documentation.

### 📊 New: Multi-Item City-Filtered Analytics

The `/vishanti-items-by-city` endpoint allows fetching analytics for multiple items filtered by city:

**Example Request:**
```bash
GET /v1/api/analytics/vishanti-items-by-city?itemIdentifiers=WAR_ITM_NW,BED_ITM_NW&city=Bangalore
```

**Response:**
```json
[
  {
    "itemName": "Wardrobe",
    "itemIdentifier": "WAR_ITM_NW",
    "itemTypeIdentifier": "WD",
    "image": "...",
    "areaStats": [
      {
        "area": "Bangalore",
        "priceType": "Per Sqft",
        "minPrice": 100.0,
        "maxPrice": 27930.0,
        "avgPrice": 1099.70
      }
    ]
  },
  {
    "itemName": "Bed",
    "itemIdentifier": "BED_ITM_NW",
    "itemTypeIdentifier": "WD",
    "image": "...",
    "areaStats": [
      {
        "area": "Bangalore",
        "priceType": "Per Sqft",
        "minPrice": 500.0,
        "maxPrice": 2500.0,
        "avgPrice": 1200.50
      }
    ]
  }
]
```

## Recent Changes

### v1.1.0 - City Mapping & Multi-Item Analytics
- ✅ **NEW**: Added `/vishanti-items-by-city` endpoint for multi-item city-filtered analytics
- ✅ **NEW**: Intelligent city canonical mapping system with typo tolerance
- ✅ **NEW**: Manual typo curation system (`city_typos_manual.json`)
- ✅ Enhanced `fetch_cities.py` to merge database cities with manual typos
- ✅ Added multi-language city name support (Hindi, Telugu)
- ✅ Custom container names for easier management

### v1.0.0 - Route Refactoring & API Versioning
- ✅ Organized routes into separate modules by functionality
- ✅ Added `/v1/api/analytics` prefix to all API endpoints
- ✅ Updated frontend to use new API prefix
- ✅ Fixed docker-compose.yml volume path for renamed folder
- ✅ Updated entrypoint.sh to reference new route structure
- ✅ Added comprehensive API documentation

## Features

### Search & Extraction
- 🔍 **Multilingual search**: Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, English
- 🎯 **Fuzzy matching**: Handles typos in item and city names
- 🗣️ **Voice search**: Browser-based voice input support
- 🔤 **Smart extraction**: Extracts item names from natural language queries

### Data & Analytics
- 💾 **Qdrant vector database**: Fast similarity search and storage
- 📊 **Price analytics**: Per-sqft, per-unit, and total pricing
- 🌍 **City-based filtering**: Filter analytics by city with typo tolerance
- 📈 **Multi-item analytics**: Query multiple items in single request
- 🏙️ **City normalization**: Handles 70+ typo variations per major city

### Integration & Deployment
- 🔄 **Data ingestion**: Automated sync from external APIs
- 🐳 **Dockerized**: Complete containerized setup
- 🔌 **REST API**: Well-documented OpenAPI/Swagger interface
- 🔐 **Authentication**: Token-based auth for external APIs

## API Examples

### Search for Items
```bash
# Search with typos
curl "http://localhost:8090/v1/api/analytics/search-items?query=wardobe"

# Multilingual search
curl "http://localhost:8090/v1/api/analytics/search-items?query=अलमारी"
```

### Get City-Filtered Analytics
```bash
# Single item, single city
curl "http://localhost:8090/v1/api/analytics/vishanti-items-by-city?itemIdentifiers=WAR_ITM_NW&city=Bangalore"

# Multiple items, single city (handles typos)
curl "http://localhost:8090/v1/api/analytics/vishanti-items-by-city?itemIdentifiers=WAR_ITM_NW,BED_ITM_NW,SOF_ITM_NW&city=bengaluru"

# Multiple items, no city filter (all cities)
curl "http://localhost:8090/v1/api/analytics/vishanti-items-by-city?itemIdentifiers=WAR_ITM_NW,BED_ITM_NW"
```

### Extract Items from Query
```bash
# Extract with fuzzy matching
curl "http://localhost:8090/v1/api/analytics/extract-items-with-identifiers-fuzzy?query=study tabel&fuzzy_cutoff=0.75"
```

## Configuration Files

### City Typo Management
- **`backend/resources/city_typos_manual.json`**: Manually curated city typos
  - Edit this file to add new typo variations
  - Supports multi-language city names
  - Automatically merged with database cities

- **`backend/resources/city_canonical_mapping.json`**: Generated mapping (auto-created)
  - Created by `fetch_cities.py` on container startup
  - Merges manual typos with database cities
  - Used for city name normalization

### Item Identifiers
- **`backend/resources/items_with_identifiers.json`**: Item name to identifier mapping
  - Generated by enrichment scripts
  - Supports multilingual item names
  - Used for search and extraction

## Useful Commands

```bash
# View logs
docker logs estimator-backend
docker logs estimator-frontend
docker logs estimator-qdrant

# Restart a specific service
docker-compose restart backend

# Rebuild after code changes
docker-compose up --build backend

# Run city fetch script manually
docker exec estimator-backend python scripts/fetch_cities.py

# Access Python shell in container
docker exec -it estimator-backend python

# View API documentation
open http://localhost:8090/docs
```

## Troubleshooting

### City Names Not Matching
1. Check `city_typos_manual.json` for the city
2. Add new variants if needed
3. Restart backend: `docker-compose restart backend`
4. Verify in generated `city_canonical_mapping.json`

### Items Not Found in Search
1. Check if item exists in Qdrant: `GET /vishanti-items`
2. Run ingest if needed: `POST /ingest`
3. Check item identifier mapping: `items_with_identifiers.json`

### API Returns 404
- Ensure you're using the correct prefix: `/v1/api/analytics`
- Check API docs: http://localhost:8090/docs
- Verify container is running: `docker ps`

## Documentation

- [City Mapping System](backend/CITY_MAPPING_README.md) - Detailed city normalization guide
- [Migration Guide](MIGRATION_GUIDE.md) - API migration from v0 to v1
- [API Documentation](http://localhost:8090/docs) - Interactive Swagger UI