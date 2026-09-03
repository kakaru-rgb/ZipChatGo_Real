from typing import Any

import httpx

from app.schemas import TransitStationSearchArguments, TransitStationSearchResult


class TransitStationSearchError(RuntimeError):
    """Raised when the Spring transit station API cannot provide a valid result."""


class TransitStationTool:
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
        arguments = TransitStationSearchArguments.model_validate(raw_arguments)

        try:
            response = self._client.get(
                "/api/map/transit/stations/search",
                params={"query": arguments.query, "limit": 5},
            )
            response.raise_for_status()
            result = TransitStationSearchResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exception:
            raise TransitStationSearchError(
                "Spring transit station search request failed"
            ) from exception

        return result.model_dump()
