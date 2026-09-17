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


class SelectedPropertySummary(BaseModel):
    id: str = Field(min_length=1, max_length=30)
    title: str | None = Field(default=None, max_length=120)
    building_name: str | None = Field(default=None, max_length=120)
    property_type: str | None = Field(default=None, max_length=30)
    sale_price: int | None = Field(default=None, ge=0)
    address: str | None = Field(default=None, max_length=200)


class AppState(BaseModel):
    current_page: str
    map_center: MapCenter | None = None
    zoom: int | None = Field(default=None, ge=0, le=8)
    current_region: str | None = None
    center_address: str | None = None
    map_bounds: MapBounds | None = None
    current_legal_dong: SelectedRegion | None = None
    selected_region: SelectedRegion | str | None = None
    selected_property_id: str | None = None
    selected_property: SelectedPropertySummary | None = None
    favorite_property_ids: list[str] = Field(default_factory=list)
    filters: PropertyFilters | None = None


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class RecentPropertySummary(BaseModel):
    id: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=120)
    sale_price: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class RecentContext(BaseModel):
    recent_property_ids: list[int] = Field(default_factory=list, max_length=10)
    last_referenced_property_id: int | None = Field(default=None, ge=1)
    recent_properties: list[RecentPropertySummary] = Field(default_factory=list, max_length=10)


class ChatRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str = Field(min_length=1, max_length=1000)
    app_state: AppState | None = None
    history: list[ConversationMessage] = Field(default_factory=list, max_length=8)
    recent_context: RecentContext = Field(default_factory=RecentContext)


class MoveMapAction(BaseModel):
    type: Literal["MOVE_MAP"] = "MOVE_MAP"
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zoom: int = Field(ge=6, le=8)


class ZoomMapAction(BaseModel):
    type: Literal["ZOOM_MAP"] = "ZOOM_MAP"
    delta: Literal[-3, -2, -1, 1, 2, 3]


class FitBoundsAction(BaseModel):
    type: Literal["FIT_BOUNDS"] = "FIT_BOUNDS"
    property_ids: list[int] = Field(min_length=1, max_length=10)


class HighlightPropertiesAction(BaseModel):
    type: Literal["HIGHLIGHT_PROPERTIES"] = "HIGHLIGHT_PROPERTIES"
    property_ids: list[int] = Field(min_length=1, max_length=10)


class OpenPropertyAction(BaseModel):
    type: Literal["OPEN_PROPERTY"] = "OPEN_PROPERTY"
    property_id: int = Field(ge=1)


class AddFavoriteAction(BaseModel):
    type: Literal["ADD_FAVORITE"] = "ADD_FAVORITE"
    property_id: int = Field(ge=1)


class RemoveFavoriteAction(BaseModel):
    type: Literal["REMOVE_FAVORITE"] = "REMOVE_FAVORITE"
    property_id: int = Field(ge=1)


BUNDANG_LEGAL_DONG_NAME_VALUES = (
    "분당동",
    "수내동",
    "정자동",
    "율동",
    "서현동",
    "이매동",
    "야탑동",
    "판교동",
    "삼평동",
    "백현동",
    "금곡동",
    "궁내동",
    "동원동",
    "구미동",
    "운중동",
    "대장동",
    "석운동",
    "하산운동",
)


BUNDANG_LEGAL_DONG_NAMES = Literal[
    "분당동",
    "수내동",
    "정자동",
    "율동",
    "서현동",
    "이매동",
    "야탑동",
    "판교동",
    "삼평동",
    "백현동",
    "금곡동",
    "궁내동",
    "동원동",
    "구미동",
    "운중동",
    "대장동",
    "석운동",
    "하산운동",
]


class SelectRegionAction(BaseModel):
    type: Literal["SELECT_REGION"] = "SELECT_REGION"
    region_name: BUNDANG_LEGAL_DONG_NAMES


class AdjacentLegalDongArguments(BaseModel):
    region_name: BUNDANG_LEGAL_DONG_NAMES


UiAction = Annotated[
    MoveMapAction
    | ZoomMapAction
    | FitBoundsAction
    | HighlightPropertiesAction
    | OpenPropertyAction
    | AddFavoriteAction
    | RemoveFavoriteAction
    | SelectRegionAction,
    Field(discriminator="type"),
]


class ChatResponse(BaseModel):
    message: str
    actions: list[UiAction] = Field(default_factory=list)
    recent_context: RecentContext = Field(default_factory=RecentContext)


class PropertySearchArguments(BaseModel):
    keyword: str | None = Field(default=None, max_length=100)
    property_type: Literal["아파트", "오피스텔", "빌라"] | None = None
    max_price: int | None = Field(default=None, ge=0, le=100_000_000_000)
    limit: int | None = Field(default=None, ge=1, le=20)
    sort_by: Literal["sale_price"] | None = None
    sort_order: Literal["asc", "desc"] | None = None
    map_bounds: MapBounds | None = None
    legal_dong_code: str | None = Field(default=None, pattern=r"^\d{8}$")


class PropertySearchResult(BaseModel):
    total_count: int = Field(ge=0)
    properties: list[dict[str, Any]]


class PropertiesByIdsArguments(BaseModel):
    property_ids: list[int] = Field(min_length=1, max_length=50)


class PropertiesByIdsResult(BaseModel):
    requested_ids: list[int]
    properties: list[dict[str, Any]]
    missing_ids: list[int]


class TransitStationSearchArguments(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class TransitStationSearchResult(BaseModel):
    total_count: int = Field(ge=0)
    stations: list[dict[str, Any]]


class LawSearchArguments(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    law_names: list[str] = Field(default_factory=list, max_length=8)
