"""
FastAPI web application for PlacePilot.
Serves the webapp interface and handles Telegram webhooks.
"""

import json
import base64
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import settings
from ..core.logging import get_logger
from ..integrations import telegram_client
from ..models.pydantic_models import TelegramUpdate, HealthCheck

# Setup paths
WEBAPP_DIR = Path(__file__).parent
STATIC_DIR = WEBAPP_DIR / "static"
TEMPLATES_DIR = WEBAPP_DIR / "templates"

# Initialize FastAPI
app = FastAPI(
    title="PlacePilot WebApp",
    description="Web interface and webhook handler for PlacePilot Telegram bot",
    version=settings.app_version
)

# Setup logging
logger = get_logger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def webapp_home(request: Request):
    """Serve the main webapp interface."""
    
    # Get places data from query params
    data_param = request.query_params.get("data", "")
    places_data = []
    
    if data_param:
        try:
            # Decode base64 data
            places_json = base64.urlsafe_b64decode(data_param.encode()).decode()
            places_data = json.loads(places_json)
        except Exception as e:
            logger.warning(f"Failed to decode webapp data: {e}")
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "places_data": json.dumps(places_data),
            "has_data": bool(places_data)
        }
    )


@app.get("/health")
async def health_check() -> HealthCheck:
    """Health check endpoint."""
    
    # Check database health
    try:
        from ..core.database import check_database_health
        db_healthy = await check_database_health()
    except Exception:
        db_healthy = False
    
    # Check external APIs
    apis_health = {}
    if settings.api.openai_api_key != "test-key-not-real":
        try:
            from ..integrations import openai_client, foursquare_client
            apis_health["openai"] = await openai_client.check_health()
            apis_health["foursquare"] = await foursquare_client.check_health()
        except Exception:
            apis_health["openai"] = False
            apis_health["foursquare"] = False
    else:
        apis_health["openai"] = False
        apis_health["foursquare"] = False
    
    # Determine overall status
    all_healthy = db_healthy and any(apis_health.values())
    status = "healthy" if all_healthy else "degraded"
    
    return HealthCheck(
        status=status,
        version=settings.app_version,
        database=db_healthy,
        redis=True,  # TODO: Add Redis health check
        apis=apis_health
    )


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    
    try:
        # Parse update data
        update_data = await request.json()
        
        logger.info("Received Telegram webhook update")
        logger.debug(f"Update data: {update_data}")
        
        # Validate webhook (optional - you can add Telegram webhook validation here)
        
        # Process update through Telegram client
        if telegram_client.application:
            # Create Update object and process
            from telegram import Update
            update = Update.de_json(update_data, telegram_client.application.bot)
            
            # Process update
            await telegram_client.application.process_update(update)
        else:
            logger.error("Telegram application not initialized")
            raise HTTPException(status_code=500, detail="Bot not ready")
        
        return JSONResponse({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/places")
async def get_places(
    lat: float,
    lng: float,
    query: Optional[str] = None,
    radius: Optional[int] = 1000
):
    """API endpoint to get places data."""
    
    try:
        from ..integrations import foursquare_client
        
        # Search places
        response = await foursquare_client.search_places(
            latitude=lat,
            longitude=lng,
            query=query,
            radius=radius,
            limit=20
        )
        
        places = response.get("results", [])
        
        # Enrich with photos
        places = await foursquare_client.enrich_places_with_photos(places)
        
        return JSONResponse({
            "success": True,
            "places": places,
            "count": len(places)
        })
        
    except Exception as e:
        logger.error(f"Places API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/contribute")
async def contribute_place(place_data: Dict[str, Any]):
    """API endpoint to contribute a new place."""
    
    try:
        # TODO: Integrate with data management agent
        # For now, just log the contribution
        
        logger.info(f"Place contribution received: {place_data.get('name', 'Unknown')}")
        
        return JSONResponse({
            "success": True,
            "message": "Place contribution received and will be reviewed"
        })
        
    except Exception as e:
        logger.error(f"Contribution API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    
    logger.info("Starting PlacePilot WebApp")
    
    # Initialize database
    try:
        from ..core.database import init_db
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Initialize agents
    try:
        from ..agents import agent_registry
        await agent_registry.initialize_all()
        logger.info(f"{len(agent_registry.get_all_agents())} agents initialized")
    except Exception as e:
        logger.error(f"Agent initialization failed: {e}")
    
    logger.info("WebApp startup completed")


# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    
    logger.info("Shutting down PlacePilot WebApp")
    
    try:
        from ..core.database import close_db
        from ..agents import agent_registry
        from ..integrations import foursquare_client
        
        await agent_registry.cleanup_all()
        await close_db()
        await foursquare_client.close()
        
        logger.info("WebApp shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.webapp.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        workers=settings.server.workers
    ) 