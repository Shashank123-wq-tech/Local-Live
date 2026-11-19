import logging
import math
import os
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GoogleMapsTextSearchClient:
    BASE_URL = "https://places.googleapis.com/v1"

    SEARCH_FIELDS = (
        "places.id,"
        "places.displayName,"
        "places.formattedAddress,"
        "places.location,"
        "places.rating,"
        "places.currentOpeningHours,"
        "places.businessStatus"
    )

    DETAIL_FIELDS = {
        "formatted_phone_number": "nationalPhoneNumber",
        "website": "websiteUri",
        "formatted_address": "formattedAddress",
        "name": "displayName",
        "rating": "rating",
        "opening_hours": "currentOpeningHours",
    }

    def __init__(self, google_api_key=None, osm_api_key=None):
        self.google_api_key = google_api_key or os.environ.get(
            "GOOGLE_MAPS_API_KEY", ""
        )
        self.osm_api_key = osm_api_key

        self.session = requests.Session()

        # Bounded connection retries. Do not retry billing/configuration errors.
        retry = Retry(
            total=2,
            connect=2,
            read=0,
            status=0,
            redirect=0,
            backoff_factor=0.5,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

        # Retains the existing OSRM travel-time approach.
        self.osrm_url = "https://router.project-osrm.org/table/v1/driving/"

    def _request(self, method, path, fields, body=None):
        if not self.google_api_key:
            logger.error("Places API: GOOGLE_MAPS_API_KEY is missing")
            return {}

        try:
            response = self.session.request(
                method,
                f"{self.BASE_URL}/{path}",
                headers={
                    "X-Goog-Api-Key": self.google_api_key,
                    "X-Goog-FieldMask": fields,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=(10, 20),
            )

            logger.info("Places API %s HTTP %s", path, response.status_code)

            payload = response.json()

            if not response.ok:
                error = payload.get("error", {})
                message = str(error.get("message", "Request failed"))
                message = message.replace(
                    self.google_api_key, "[REDACTED]"
                )
                logger.error(
                    "Places API error: status=%s message=%s",
                    error.get("status", response.status_code),
                    message,
                )
                return {}

            return payload

        except requests.RequestException as exc:
            # Do not print request headers or credential-bearing exceptions.
            logger.error(
                "Places API connection failure: %s",
                type(exc).__name__,
            )
            return {}
        except ValueError:
            logger.error("Places API returned invalid JSON")
            return {}

    @staticmethod
    def _normalize(place):
        """Convert the new Place object to the existing agent's field names."""
        location = place.get("location") or {}
        hours = place.get("currentOpeningHours") or {}

        return {
            "place_id": place.get("id", ""),
            "name": (place.get("displayName") or {}).get("text", ""),
            "formatted_address": place.get("formattedAddress"),
            "geometry": {
                "location": {
                    "lat": location.get("latitude"),
                    "lng": location.get("longitude"),
                }
            },
            "rating": place.get("rating"),
            "opening_hours": {
                "open_now": hours.get("openNow"),
            },
            "formatted_phone_number": place.get("nationalPhoneNumber"),
            "website": place.get("websiteUri"),
            "business_status": place.get("businessStatus"),
            "photos": [],
        }

    def _search(
        self,
        query,
        limit=5,
        latitude=None,
        longitude=None,
        radius=50000,
        rank="RELEVANCE",
    ):
        limit = max(1, min(int(limit), 20))

        body = {
            "textQuery": query,
            "pageSize": limit,
            "rankPreference": rank,
        }

        if latitude is not None and longitude is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    },
                    "radius": max(1.0, min(float(radius), 50000.0)),
                }
            }

        payload = self._request(
            "POST",
            "places:searchText",
            self.SEARCH_FIELDS,
            body,
        )

        results = []
        for place in payload.get("places", []):
            location = place.get("location") or {}
            if (
                location.get("latitude") is None
                or location.get("longitude") is None
            ):
                continue
            if place.get("businessStatus") == "CLOSED_PERMANENTLY":
                continue
            results.append(self._normalize(place))

        logger.info("Places API returned %d usable places", len(results))
        return results[:limit]

    def text_search(
        self, query, limit=3, latitude=None, longitude=None, radius=50000
    ):
        return self._search(
            query, limit, latitude, longitude, radius, "RELEVANCE"
        )

    def nearby_search_ranked_by_distance(
        self, query, latitude, longitude, limit=5
    ):
        # Text Search supports natural-language queries and distance ranking.
        return self._search(
            query, limit, latitude, longitude, 50000, "DISTANCE"
        )

    def keyword_search(
        self, query, latitude=None, longitude=None, limit=5, radius=50000
    ):
        return self._search(
            query, limit, latitude, longitude, radius, "RELEVANCE"
        )

    def get_place_details(self, place_id, fields=None):
        if not place_id:
            return {}

        requested = fields or ["formatted_phone_number", "website"]
        unsupported = set(requested) - set(self.DETAIL_FIELDS)
        if unsupported:
            raise ValueError(
                f"Unsupported place detail fields: {sorted(unsupported)}"
            )

        field_mask = ",".join(
            dict.fromkeys(self.DETAIL_FIELDS[field] for field in requested)
        )
        payload = self._request(
            "GET",
            f"places/{quote(place_id, safe='')}",
            field_mask,
        )
        return self._normalize(payload) if payload else {}

    def get_formatted_address(self, place):
        address = (
            place.get("formatted_address")
            or place.get("formattedAddress")
            or place.get("vicinity")
        )
        if address:
            return address

        place_id = place.get("place_id") or place.get("id")
        if not place_id:
            return None

        details = self.get_place_details(place_id, ["formatted_address"])
        return details.get("formatted_address")

    def get_photo_url(self, photo_reference, max_width=400):
        # Do not expose the backend API key in browser-visible URLs.
        return None

    def get_travel_times(
        self, origin_latitude, origin_longitude, destinations
    ):
        if not destinations:
            return []

        coordinates = [(origin_latitude, origin_longitude)] + destinations
        coordinate_text = ";".join(
            f"{longitude},{latitude}"
            for latitude, longitude in coordinates
        )

        try:
            response = self.session.get(
                self.osrm_url + coordinate_text,
                params={"annotations": "duration", "sources": "0"},
                timeout=(3, 5),
            )
            response.raise_for_status()
            payload = response.json()

            if payload.get("code") != "Ok":
                return ["N/A"] * len(destinations)

            durations = payload["durations"][0][1:]
            if len(durations) != len(destinations):
                return ["N/A"] * len(destinations)

            return [
                duration / 60.0
                if isinstance(duration, (int, float))
                and math.isfinite(duration)
                and duration >= 0
                else "N/A"
                for duration in durations
            ]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            logger.warning("Travel times unavailable")
            return ["N/A"] * len(destinations)

    def text_search_with_details(
        self, query, origin_latitude, origin_longitude,
        limit=3, radius=50000
    ):
        places = self.text_search(
            query, limit, origin_latitude, origin_longitude, radius
        )
        destinations = [
            (
                place["geometry"]["location"]["lat"],
                place["geometry"]["location"]["lng"],
            )
            for place in places
        ]
        times = self.get_travel_times(
            origin_latitude, origin_longitude, destinations
        )

        return [
            {
                "entity_name": place["name"],
                "address": place.get("formatted_address"),
                "rate": place.get("rating"),
                "estimated_travel_time": (
                    f"{travel_time:.2f} mins"
                    if isinstance(travel_time, (int, float))
                    else "N/A"
                ),
            }
            for place, travel_time in zip(places, times)
        ]


gmaps_text_search_client = GoogleMapsTextSearchClient(
    os.environ.get("GOOGLE_MAPS_API_KEY"),
    os.environ.get("ORS_API_KEY"),
)
