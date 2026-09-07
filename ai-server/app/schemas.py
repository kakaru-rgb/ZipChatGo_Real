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
    zoom: int | None = Field(default=None, ge=0, le=8)
    current_region: str | None = None
    center_address: str | None = None
    map_bounds: MapBounds | None = None
    current_legal_dong: SelectedRegion | None = None
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
    | SelectRegionAction,
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
