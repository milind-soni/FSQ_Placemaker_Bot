"""
Foursquare API client for PlacePilot.
Provides interface to Foursquare Places API with error handling and rate limiting.
"""

import asyncio
from typing import Dict, Any, Optional, List
import httpx

from ..core.config import settings
from ..core.logging import get_logger, LoggerMixin
from ..core.exceptions import FoursquareAPIError

logger = get_logger(__name__)


class FoursquareClient(LoggerMixin):
    """Async Foursquare API client."""
    
    def __init__(self):
        self.api_key = settings.api.foursquare_api_key
        self.base_url = "https://api.foursquare.com/v3"
        self.places_base_url = "https://places-api.foursquare.com/places"
        self._max_retries = 3
        self._retry_delay = 1.0
        
        # HTTP client with timeout and connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for API requests."""
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Places-Api-Version": "2025-02-05"
        }
    
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an API request with retry logic."""
        
        headers = self._get_headers()
        
        for attempt in range(self._max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data
                )
                
                response.raise_for_status()
                
                self.log_with_context(
                    "debug",
                    f"Foursquare API request successful",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    attempt=attempt + 1
                )
                
                return response.json()
                
            except httpx.HTTPStatusError as e:
                error_msg = f"Foursquare API HTTP error: {e.response.status_code}"
                if e.response.status_code == 429:  # Rate limited
                    if attempt < self._max_retries:
                        wait_time = self._retry_delay * (2 ** attempt)
                        self.logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                
                self.logger.error(f"{error_msg}: {e.response.text}")
                raise FoursquareAPIError(error_msg, status_code=e.response.status_code)
                
            except httpx.RequestError as e:
                if attempt == self._max_retries:
                    self.logger.error(f"Foursquare API request failed: {e}")
                    raise FoursquareAPIError(f"Request failed: {e}")
                
                self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self._retry_delay * (2 ** attempt))
    
    async def search_places(
        self,
        latitude: float,
        longitude: float,
        query: Optional[str] = None,
        radius: Optional[int] = None,
        limit: Optional[int] = None,
        open_now: Optional[bool] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        categories: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for places using Foursquare Places API."""
        
        url = f"{self.places_base_url}/search"
        
        params = {
            "ll": f"{latitude},{longitude}",
            "fields": "fsq_place_id,name,distance,hours,price,rating,categories"
        }
        
        if query:
            params["query"] = query
        if radius:
            params["radius"] = radius
        if limit:
            params["limit"] = limit
        else:
            params["limit"] = 10
        if open_now:
            params["open_now"] = "true"
        if min_price:
            params["min_price"] = min_price
        if max_price:
            params["max_price"] = max_price
        if categories:
            params["fsq_category_ids"] = categories
        
        self.log_with_context(
            "info",
            f"Searching places",
            latitude=latitude,
            longitude=longitude,
            query=query,
            radius=radius,
            limit=limit
        )
        
        try:
            response = await self._make_request("GET", url, params=params)
            results = response.get("results", [])
            
            self.log_with_context(
                "info",
                f"Found {len(results)} places",
                results_count=len(results)
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Place search failed: {e}")
            raise
    
    async def get_place_photos(self, place_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get photos for a specific place."""
        
        url = f"{self.base_url}/places/{place_id}/photos"
        params = {"limit": limit}
        
        try:
            response = await self._make_request("GET", url, params=params)
            
            if isinstance(response, list):
                photos = response
            else:
                photos = response.get("photos", response.get("results", []))
            
            self.log_with_context(
                "debug",
                f"Retrieved {len(photos)} photos for place",
                place_id=place_id,
                photo_count=len(photos)
            )
            
            return photos
            
        except Exception as e:
            self.logger.warning(f"Failed to get photos for place {place_id}: {e}")
            return []
    
    async def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific place."""
        
        url = f"{self.base_url}/places/{place_id}"
        params = {
            "fields": "fsq_place_id,name,geocodes,location,categories,chains,hours,price,rating,popularity,stats,photos"
        }
        
        try:
            response = await self._make_request("GET", url, params=params)
            
            self.log_with_context(
                "debug",
                f"Retrieved place details",
                place_id=place_id
            )
            
            return response
            
        except Exception as e:
            self.logger.warning(f"Failed to get place details for {place_id}: {e}")
            return None
    
    async def format_place_image_url(
        self, 
        photo_data: Dict[str, Any], 
        width: int = 300, 
        height: int = 225
    ) -> Optional[str]:
        """Format a place photo URL with specified dimensions."""
        
        try:
            prefix = photo_data.get("prefix", "")
            suffix = photo_data.get("suffix", "")
            
            if not prefix or not suffix:
                return None
            
            return f"{prefix}{width}x{height}{suffix}"
            
        except Exception as e:
            self.logger.warning(f"Failed to format photo URL: {e}")
            return None
    
    async def enrich_places_with_photos(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich place results with photo URLs."""
        
        for place in places:
            fsq_id = place.get("fsq_place_id")
            if not fsq_id:
                place["image_url"] = None
                continue
            
            try:
                photos = await self.get_place_photos(fsq_id, limit=1)
                if photos:
                    photo_url = await self.format_place_image_url(photos[0])
                    place["image_url"] = photo_url
                else:
                    place["image_url"] = None
            except Exception as e:
                self.logger.warning(f"Failed to get photo for place {fsq_id}: {e}")
                place["image_url"] = None
        
        return places
    
    async def check_health(self) -> bool:
        """Check if Foursquare API is healthy."""
        try:
            # Simple search to test API connectivity
            await self.search_places(
                latitude=40.7128,
                longitude=-74.0060,
                limit=1
            )
            return True
        except Exception as e:
            self.logger.error(f"Foursquare health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


# Global Foursquare client instance
foursquare_client = FoursquareClient() 