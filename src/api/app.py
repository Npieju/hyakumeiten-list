from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.availability import ReservationQuery, search_availability
from src.api.genres import list_genre_filters
from src.api.models import AvailabilitySearchRequest, AvailabilitySearchResponse, SearchResponse
from src.api.search import SearchFilters, search_shops


BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Hyakumeiten Map API")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
	return FileResponse(
		WEB_DIR / "index.html",
		headers={
			"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
			"Pragma": "no-cache",
			"Expires": "0",
		},
	)


@app.get("/v1/metadata/genres")
def genres_metadata(db_path: str = "data/app/hyakummeiten.sqlite3") -> dict[str, object]:
	return list_genre_filters(db_path=db_path)


@app.get("/v1/shops/search", response_model=SearchResponse)
def shops_search(
	year: Annotated[list[int] | None, Query()] = None,
	genre_slug: Annotated[list[str] | None, Query()] = None,
	region: Annotated[list[str] | None, Query()] = None,
	prefecture: Annotated[list[str] | None, Query()] = None,
	name_query: str | None = None,
	address_query: str | None = None,
	min_lat: float | None = None,
	max_lat: float | None = None,
	min_lng: float | None = None,
	max_lng: float | None = None,
	has_multiple_years: bool = False,
	limit: int = 300,
	offset: int = 0,
	db_path: str = "data/app/hyakummeiten.sqlite3",
) -> dict[str, object]:
	filters = SearchFilters(
		db_path=db_path,
		years=year or [],
		genre_slugs=genre_slug or [],
		regions=region or [],
		prefectures=prefecture or [],
		name_query=name_query,
		address_query=address_query,
		min_lat=min_lat,
		max_lat=max_lat,
		min_lng=min_lng,
		max_lng=max_lng,
		has_multiple_years=has_multiple_years,
		limit=max(1, min(limit, 500)),
		offset=max(0, offset),
	)
	return search_shops(filters)


@app.post("/v1/shops/availability-search", response_model=AvailabilitySearchResponse)
def shops_availability_search(request: AvailabilitySearchRequest) -> dict[str, object]:
	bbox = request.filters.bounding_box
	filters = SearchFilters(
		db_path=request.db_path,
		years=request.filters.year,
		genre_slugs=request.filters.genre_slug,
		regions=request.filters.region,
		prefectures=request.filters.prefecture,
		name_query=request.filters.name_query,
		address_query=request.filters.address_query,
		min_lat=None if bbox is None else bbox.min_lat,
		max_lat=None if bbox is None else bbox.max_lat,
		min_lng=None if bbox is None else bbox.min_lng,
		max_lng=None if bbox is None else bbox.max_lng,
		has_multiple_years=request.filters.has_multiple_years,
		limit=max(1, min(request.limit, 500)),
		offset=max(0, request.offset),
	)
	reservation = ReservationQuery(
		date=request.reservation.date,
		party_size=request.reservation.party_size,
		time_window=request.reservation.time_window,
		statuses=request.reservation.status,
		providers=request.reservation.provider,
	)
	return search_availability(
		filters,
		reservation,
		limit=max(1, min(request.limit, 500)),
		offset=max(0, request.offset),
	)


def main() -> None:
	host = os.environ.get("HOST", "0.0.0.0")
	port = int(os.environ.get("PORT", "8000"))
	uvicorn.run("src.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
	main()