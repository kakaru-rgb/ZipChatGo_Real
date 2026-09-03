from typing import Any

import httpx

from app.schemas import PropertySearchArguments, PropertySearchResult


class PropertySearchError(RuntimeError):
    """Raised when the Spring property search API cannot provide a valid result."""


class PropertySearchTool:
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
        arguments = PropertySearchArguments.model_validate(raw_arguments)
        params: dict[str, str | int] = {"limit": 10}
        if arguments.keyword:
            params["keyword"] = arguments.keyword
        if arguments.property_type:
            params["propertyType"] = arguments.property_type
        if arguments.max_price is not None:
            params["maxPrice"] = arguments.max_price
        if arguments.legal_dong_code:
            params["legalDongCode"] = arguments.legal_dong_code
        if arguments.map_bounds is not None:
            params.update(
                {
                    "south": arguments.map_bounds.south,
                    "west": arguments.map_bounds.west,
                    "north": arguments.map_bounds.north,
                    "east": arguments.map_bounds.east,
                }
            )

        try:
            response = self._client.get("/api/map/properties/search", params=params)
            response.raise_for_status()
            result = PropertySearchResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exception:
            raise PropertySearchError("Spring property search request failed") from exception

        return result.model_dump()
