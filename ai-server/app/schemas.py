from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MapCenter(BaseModel):
    lat: float
    lng: float


class MapBounds(BaseModel):
    south: float
    west: float
    north: float
    east: float


class PropertyFilters(BaseModel):
    keyword: str | None = None
    property_type: str | None = None
    max_price: int | None = None


class AppState(BaseModel):
    current_page: str
    map_center: MapCenter | None = None
    zoom: int | None = None
    map_bounds: MapBounds | None = None
    selected_region: str | None = None
    selected_property_id: str | None = None
    favorite_property_ids: list[str] = Field(default_factory=list)
    filters: PropertyFilters | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str = Field(min_length=1, max_length=1000)
    app_state: AppState | None = None


class ChatResponse(BaseModel):
    message: str
