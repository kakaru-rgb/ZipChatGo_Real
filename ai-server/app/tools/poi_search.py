from typing import Any

import httpx

from app.schemas import PoiSearchArguments, PoiSearchResult


class PoiSearchError(RuntimeError):
    """Raised when the Spring POI search API cannot provide a valid result."""


class PoiSearchTool:
    def __init__(
        self,
        spring_base_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=spring_base_url.rstrip("/"),
            timeout=10.0,
        )

    def search(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = PoiSearchArguments.model_validate(raw_arguments)
        params = {
            key: value
            for key, value in arguments.model_dump().items()
            if value is not None
        }

        try:
            response = self._client.get("/api/map/pois/search", params=params)
            response.raise_for_status()
            result = PoiSearchResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exception:
            raise PoiSearchError("Spring POI search request failed") from exception

        return result.model_dump()
