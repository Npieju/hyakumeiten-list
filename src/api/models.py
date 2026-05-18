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