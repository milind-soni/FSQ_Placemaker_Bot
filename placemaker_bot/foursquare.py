import requests
from typing import Any, Dict, List

from .config import settings


class FoursquareClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.foursquare_api_key
        self.search_base = "https://places-api.foursquare.com/places/search"
        self.photo_base = "https://api.foursquare.com/v3/places/{fsq_id}/photos?limit=5"

    def search(self, *, ll: str, fields: str, params: Dict[str, Any]) -> Dict[str, Any]:
        q = {"ll": ll, "fields": fields, **params}
        headers = {
            "accept": "application/json",
            "X-Places-Api-Version": "2025-02-05",
            "Authorization": f"Bearer {self.api_key}",
        }
        resp = requests.get(self.search_base, params=q, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def photos(self, fsq_place_id: str) -> List[Dict[str, Any]]:
        headers = {"accept": "application/json", "Authorization": f"Bearer {self.api_key}"}
        url = self.photo_base.format(fsq_id=fsq_place_id)
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [] 