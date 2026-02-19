"""
Estimator Items Analytics API - Main Application

This module serves as the main entry point for the FastAPI application.
All routes are organized into separate modules and mounted with the v1/estimator/analytics prefix.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import route modules
from routes.items_routes import router as items_router
from routes.search_routes import router as search_router
from routes.ingest_routes import router as ingest_router
from routes.config_routes import router as config_router
from routes.auth_routes import router as auth_router

# Initialize FastAPI application
app = FastAPI(
    title="Estimator Items Analytics API",
    description="API for managing and searching estimator items with multilingual support",
    version="1.0.0",
)

# Configure CORS middleware
# Allow the static frontend (different port) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API version prefix
API_PREFIX = "/v1/estimator/analytics"

# Include all routers with the API prefix
app.include_router(items_router, prefix=API_PREFIX, tags=["Items"])
app.include_router(search_router, prefix=API_PREFIX, tags=["Search"])
app.include_router(ingest_router, prefix=API_PREFIX, tags=["Ingest"])
app.include_router(config_router, prefix=API_PREFIX, tags=["Config"])
app.include_router(auth_router, prefix=API_PREFIX, tags=["Auth"])


@app.get("/")
def root():
    """
    Root endpoint - API health check.

    Returns:
        dict: Basic API information and status.
    """
    return {
        "message": "Estimator Items Analytics API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status of the API.
    """
    return {"status": "healthy"}
