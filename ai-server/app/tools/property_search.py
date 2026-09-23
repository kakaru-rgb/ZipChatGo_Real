import logging
from typing import Any

import httpx

from app.config import safe_search_log, search_diagnostics_enabled
from app.schemas import (
    PropertiesByIdsArguments,
    PropertiesByIdsResult,
    PropertySearchArguments,
    PropertySearchResult,
)


class PropertySearchError(RuntimeError):
    """Raised when the Spring property search API cannot provide a valid result."""


def format_sale_price(sale_price: Any) -> str | None:
    """Format the DB/API sale price, whose canonical unit is Korean won."""
    if isinstance(sale_price, bool) or not isinstance(sale_price, (int, float)):
        return None

    price = int(sale_price)
    if price < 0:
        return None

    eok, remainder = divmod(price, 100_000_000)
    man = remainder // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    if man:
        return f"{man:,}만원"
    return f"{price:,}원"


def _add_sale_price_displays(properties: list[dict[str, Any]]) -> None:
    for item in properties:
        display = format_sale_price(item.get("sale_price"))
        if display is not None:
            item["sale_price_display"] = display


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
        params: dict[str, str | int | float] = {"limit": arguments.limit or 10}
        if arguments.keyword:
            params["keyword"] = arguments.keyword
        if arguments.property_type:
            params["propertyType"] = arguments.property_type
        if arguments.max_price is not None:
            params["maxPrice"] = arguments.max_price
        if arguments.search_mode != "properties":
            params["searchMode"] = arguments.search_mode
        if arguments.exact_building_name:
            params["exactBuildingName"] = arguments.exact_building_name
        if arguments.exclusive_area is not None:
            params["exclusiveArea"] = arguments.exclusive_area
        if arguments.search_mode == "selected_building_transactions" and arguments.selected_property_id is not None:
            params["selectedPropertyId"] = arguments.selected_property_id
        if arguments.sort_by:
            params["sortBy"] = arguments.sort_by
        if arguments.sort_order:
            params["sortOrder"] = arguments.sort_order
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

        if search_diagnostics_enabled():
            logging.getLogger("uvicorn.error").info(
                "[property-search:%x] spring_query_params=%s",
                id(raw_arguments),
                safe_search_log(params),
            )

        try:
            response = self._client.get("/api/map/properties/search", params=params)
            response.raise_for_status()
            result = PropertySearchResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exception:
            raise PropertySearchError("Spring property search request failed") from exception

        output = result.model_dump(exclude_defaults=True)
        _add_sale_price_displays(output.get("properties", []))
        return output

    def get_by_ids(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = PropertiesByIdsArguments.model_validate(raw_arguments)
        property_ids = list(dict.fromkeys(arguments.property_ids))
        if any(property_id < 1 for property_id in property_ids):
            raise PropertySearchError("Property IDs must be positive")

        try:
            response = self._client.get(
                "/api/map/properties/by-ids",
                params={"ids": ",".join(str(property_id) for property_id in property_ids)},
            )
            response.raise_for_status()
            result = PropertiesByIdsResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exception:
            raise PropertySearchError("Spring property lookup request failed") from exception

        output = result.model_dump()
        _add_sale_price_displays(output.get("properties", []))
        return output
