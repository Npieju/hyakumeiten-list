from __future__ import annotations

from pydantic import BaseModel


class GenreEntry(BaseModel):
	year: int
	genre_slug: str
	genre_name: str


class ShopItem(BaseModel):
	shop_id: str
	name: str
	address: str
	latitude: float
	longitude: float
	region: str
	prefecture: str
	tabelog_url: str
	google_maps_url: str
	years: list[int]
	genres: list[GenreEntry]


class SearchResponse(BaseModel):
	total: int
	returned: int
	truncated: bool
	warning: str | None = None
	items: list[ShopItem]


class BoundingBoxRequest(BaseModel):
	min_lat: float | None = None
	max_lat: float | None = None
	min_lng: float | None = None
	max_lng: float | None = None


class AvailabilityFiltersRequest(BaseModel):
	year: list[int] = []
	genre_slug: list[str] = []
	region: list[str] = []
	prefecture: list[str] = []
	bounding_box: BoundingBoxRequest | None = None
	name_query: str | None = None
	address_query: str | None = None
	has_multiple_years: bool = False


class ReservationRequest(BaseModel):
	date: str
	party_size: int
	time_window: str
	status: list[str] = []
	provider: list[str] = []


class AvailabilitySearchRequest(BaseModel):
	filters: AvailabilityFiltersRequest
	reservation: ReservationRequest
	limit: int = 20
	offset: int = 0
	db_path: str = "data/app/hyakummeiten.sqlite3"


class ReservationSummary(BaseModel):
	status: str
	status_reason: str


class ProviderAvailabilityItem(BaseModel):
	provider: str | None = None
	status: str
	status_reason: str
	reservation_url: str | None = None
	available_slots: list[str]
	checked_at: str | None = None
	expires_at: str | None = None
	raw_payload_hash: str | None = None
	source: str


class AvailabilityShopItem(ShopItem):
	reservation_summary: ReservationSummary
	providers: list[ProviderAvailabilityItem]


class AvailabilitySearchResponse(BaseModel):
	total: int
	cache_hit_ratio: float
	live_checks: int
	warning: str | None = None
	items: list[AvailabilityShopItem]