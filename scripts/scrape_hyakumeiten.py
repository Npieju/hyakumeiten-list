from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://award.tabelog.com"
HYAKUMEITEN_ROOT = f"{BASE_URL}/hyakumeiten"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
GENRE_LINK_PATTERN = re.compile(r"^/hyakumeiten/(?P<slug>[a-z0-9_]+)$")


@dataclass(frozen=True)
class Genre:
    slug: str
    title: str
    year: int
    release_date: str
    url: str


@dataclass(frozen=True)
class Shop:
    name: str
    address: str
    description: str
    website: str
    google_maps_url: str
    year: int
    genre: str
    genre_slug: str
    release_date: str


def print_progress(message: str) -> None:
    print(f"[progress] {message}", file=sys.stderr, flush=True)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
    )
    return session


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_candidate_slugs(session: requests.Session) -> list[str]:
    soup = fetch_soup(session, HYAKUMEITEN_ROOT)
    slugs: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        match = GENRE_LINK_PATTERN.match(href)
        if match:
            slugs.add(match.group("slug"))

    return sorted(slugs)


def parse_genre_title(title_text: str, year: int) -> str:
    cleaned = title_text.strip()
    cleaned = cleaned.removeprefix("食べログ ")
    cleaned = cleaned.removesuffix(" [食べログ]")
    cleaned = cleaned.removesuffix(f" 百名店 {year}")
    return cleaned.strip()


def resolve_genres(session: requests.Session, year: int) -> list[Genre]:
    genres: list[Genre] = []
    candidate_slugs = extract_candidate_slugs(session)
    total_candidates = len(candidate_slugs)

    print_progress(f"resolving {year} genres from {total_candidates} candidates")

    for index, slug in enumerate(candidate_slugs, start=1):
        genre_url = f"{HYAKUMEITEN_ROOT}/{slug}/{year}"
        print_progress(f"checking genre {index}/{total_candidates}: {slug}")
        response = session.get(genre_url, timeout=30)
        if response.status_code == 404:
            continue

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        if title_tag is None or str(year) not in title_tag.get_text(strip=True):
            continue

        release_node = soup.select_one(".hyakumeiten-search__release-day")
        release_date = release_node.get_text(" ", strip=True) if release_node else ""
        title = parse_genre_title(title_tag.get_text(strip=True), year)

        genres.append(
            Genre(
                slug=slug,
                title=title,
                year=year,
                release_date=release_date,
                url=genre_url,
            )
        )

    return sorted(genres, key=lambda genre: genre.slug)


def parse_restaurant_json_ld(soup: BeautifulSoup) -> tuple[str, str]:
    for script in soup.select('script[type="application/ld+json"]'):
        raw_text = script.string or script.get_text(strip=True)
        if not raw_text:
            continue

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        candidates: list[dict] = []
        if isinstance(payload, dict):
            if payload.get("@type") == "Restaurant":
                candidates.append(payload)
            graph = payload.get("@graph")
            if isinstance(graph, list):
                candidates.extend(
                    item
                    for item in graph
                    if isinstance(item, dict) and item.get("@type") == "Restaurant"
                )
        elif isinstance(payload, list):
            candidates.extend(
                item
                for item in payload
                if isinstance(item, dict) and item.get("@type") == "Restaurant"
            )

        for restaurant in candidates:
            name = str(restaurant.get("name", "")).strip()
            address_payload = restaurant.get("address") or {}
            if not isinstance(address_payload, dict):
                address_payload = {}
            address = "".join(
                str(address_payload.get(key, "")).strip()
                for key in ("addressRegion", "addressLocality", "streetAddress")
            )
            if name and address:
                return name, address

    return "", ""


def build_google_maps_url(address: str, name: str) -> str:
    query = quote(f"{name} {address}".strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def fetch_shop(session: requests.Session, genre: Genre, shop_url: str) -> Shop:
    soup = fetch_soup(session, shop_url)
    name, address = parse_restaurant_json_ld(soup)

    if not name:
        heading = soup.select_one(".display-name span")
        name = heading.get_text(strip=True) if heading else ""
    if not address:
        address_node = soup.select_one(".rstinfo-table__address")
        address = address_node.get_text("", strip=True) if address_node else ""

    description = f"食べログ {genre.title} 百名店 {genre.year}"
    return Shop(
        name=name,
        address=address,
        description=description,
        website=shop_url,
        google_maps_url=build_google_maps_url(address, name),
        year=genre.year,
        genre=genre.title,
        genre_slug=genre.slug,
        release_date=genre.release_date,
    )


def scrape_genre_shops(
    session: requests.Session,
    genre: Genre,
    throttle_seconds: float,
) -> list[Shop]:
    print_progress(f"loading genre page: {genre.slug}")
    soup = fetch_soup(session, genre.url)
    shop_links: list[str] = []
    seen_links: set[str] = set()

    for anchor in soup.select("a.hyakumeiten-shop__target[href]"):
        shop_url = urljoin(BASE_URL, anchor["href"])
        if shop_url not in seen_links:
            seen_links.add(shop_url)
            shop_links.append(shop_url)

    shops: list[Shop] = []
    total_shops = len(shop_links)
    print_progress(f"found {total_shops} shops for {genre.slug}")
    for index, shop_url in enumerate(shop_links, start=1):
        if index == 1 or index == total_shops or index % 10 == 0:
            print_progress(f"fetching {genre.slug} shop {index}/{total_shops}")
        shops.append(fetch_shop(session, genre, shop_url))
        if throttle_seconds > 0:
            time.sleep(throttle_seconds)

    return shops


def write_csv(path: Path, rows: Iterable[dict[str, str | int]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def genre_rows(genres: Iterable[Genre]) -> Iterable[dict[str, str | int]]:
    for genre in genres:
        yield {
            "Year": genre.year,
            "Genre": genre.title,
            "Genre Slug": genre.slug,
            "Release Date": genre.release_date,
            "URL": genre.url,
        }


def shop_rows(shops: Iterable[Shop]) -> Iterable[dict[str, str | int]]:
    for shop in shops:
        yield {
            "Name": shop.name,
            "Address": shop.address,
            "Description": shop.description,
            "Website": shop.website,
            "Google Maps URL": shop.google_maps_url,
            "Year": shop.year,
            "Genre": shop.genre,
            "Genre Slug": shop.genre_slug,
            "Release Date": shop.release_date,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--genres-only", action="store_true")
    parser.add_argument("--genre", dest="genre_slugs", action="append")
    parser.add_argument("--throttle-seconds", type=float, default=0.3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = build_session()
    output_root = Path(args.output_dir) / str(args.year)

    all_genres = resolve_genres(session, args.year)
    genres = all_genres
    if args.genre_slugs:
        allowed = set(args.genre_slugs)
        genres = [genre for genre in all_genres if genre.slug in allowed]
        print_progress(
            f"filtered genres to {len(genres)} selected entries: {sorted(allowed)}"
        )

    if not all_genres:
        raise SystemExit(f"No genres found for year {args.year}.")

    write_csv(
        output_root / "genres.csv",
        genre_rows(all_genres),
        ["Year", "Genre", "Genre Slug", "Release Date", "URL"],
    )

    if args.genres_only:
        print(f"Wrote {len(all_genres)} genres to {output_root / 'genres.csv'}")
        return

    if not genres:
        raise SystemExit(
            f"No matching genres found for year {args.year}: {args.genre_slugs}"
        )

    all_shops: list[Shop] = []
    total_genres = len(genres)
    for index, genre in enumerate(genres, start=1):
        print_progress(f"scraping genre {index}/{total_genres}: {genre.slug}")
        shops = scrape_genre_shops(session, genre, args.throttle_seconds)
        all_shops.extend(shops)
        write_csv(
            output_root / "by_genre" / f"{genre.slug}.csv",
            shop_rows(shops),
            [
                "Name",
                "Address",
                "Description",
                "Website",
                "Google Maps URL",
                "Year",
                "Genre",
                "Genre Slug",
                "Release Date",
            ],
        )
        print(f"Wrote {len(shops)} shops for {genre.slug}")

    write_csv(
        output_root / "all.csv",
        shop_rows(all_shops),
        [
            "Name",
            "Address",
            "Description",
            "Website",
            "Google Maps URL",
            "Year",
            "Genre",
            "Genre Slug",
            "Release Date",
        ],
    )
    print(f"Wrote {len(all_shops)} shops to {output_root / 'all.csv'}")


if __name__ == "__main__":
    main()