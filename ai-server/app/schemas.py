from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MapCenter(BaseModel):
    lat: float
    lng: float


class MapBounds(BaseModel):
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)


class PropertyFilters(BaseModel):
    keyword: str | None = None
    property_type: str | None = None
    max_price: int | None = None


class SelectedRegion(BaseModel):
    type: Literal["legal_dong"]
    code: str = Field(pattern=r"^\d{8}$")
    name: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=100)
    center: MapCenter
    bounds: MapBounds


class AppState(BaseModel):
    current_page: str
    map_center: MapCenter | None = None
    zoom: int | None = None
    current_region: str | None = None
    center_address: str | None = None
    map_bounds: MapBounds | None = None
    selected_region: SelectedRegion | str | None = None
    selected_property_id: str | None = None
    favorite_property_ids: list[str] = Field(default_factory=list)
    filters: PropertyFilters | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str = Field(min_length=1, max_length=1000)
    app_state: AppState | None = None


class MoveMapAction(BaseModel):
    type: Literal["MOVE_MAP"] = "MOVE_MAP"
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zoom: int = Field(ge=10, le=18)


class FitBoundsAction(BaseModel):
    type: Literal["FIT_BOUNDS"] = "FIT_BOUNDS"
    property_ids: list[int] = Field(min_length=1, max_length=10)


class HighlightPropertiesAction(BaseModel):
    type: Literal["HIGHLIGHT_PROPERTIES"] = "HIGHLIGHT_PROPERTIES"
    property_ids: list[int] = Field(min_length=1, max_length=10)


class OpenPropertyAction(BaseModel):
    type: Literal["OPEN_PROPERTY"] = "OPEN_PROPERTY"
    property_id: int = Field(ge=1)


UiAction = Annotated[
    MoveMapAction | FitBoundsAction | HighlightPropertiesAction | OpenPropertyAction,
    Field(discriminator="type"),
]


class ChatResponse(BaseModel):
    message: str
    actions: list[UiAction] = Field(default_factory=list)


class PropertySearchArguments(BaseModel):
    keyword: str | None = Field(default=None, max_length=100)
    property_type: Literal["아파트", "오피스텔", "빌라"] | None = None
    max_price: int | None = Field(default=None, ge=0, le=100_000_000_000)
    map_bounds: MapBounds | None = None
    legal_dong_code: str | None = Field(default=None, pattern=r"^\d{8}$")


class PropertySearchResult(BaseModel):
    total_count: int = Field(ge=0)
    properties: list[dict[str, Any]]


class TransitStationSearchArguments(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class TransitStationSearchResult(BaseModel):
    total_count: int = Field(ge=0)
    stations: list[dict[str, Any]]
