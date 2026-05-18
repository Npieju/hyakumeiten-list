const TOKYO_VIEW = {
  center: [35.6764, 139.6993],
  zoom: 11,
};

const map = L.map("map", {
  zoomControl: true,
}).setView(TOKYO_VIEW.center, TOKYO_VIEW.zoom);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const markersLayer = L.layerGroup().addTo(map);
const resultList = document.getElementById("result-list");
const resultCount = document.getElementById("result-count");
const statusText = document.getElementById("status-text");
const warningText = document.getElementById("warning-text");
const form = document.getElementById("search-form");

let selectedShopId = null;
let lastItems = [];
let markerByShopId = new Map();
let fetchTimer = null;

function buildParams() {
  const bounds = map.getBounds();
  const params = new URLSearchParams();
  const year = document.getElementById("year-input").value.trim();
  const genreSlug = document.getElementById("genre-input").value.trim();
  const nameQuery = document.getElementById("name-input").value.trim();
  const region = document.getElementById("region-input").value;
  const hasMultipleYears = document.getElementById("multiple-years-input").checked;

  if (year) {
    params.append("year", year);
  }
  if (genreSlug) {
    params.append("genre_slug", genreSlug);
  }
  if (nameQuery) {
    params.append("name_query", nameQuery);
  }
  if (region) {
    params.append("region", region);
  }
  if (hasMultipleYears) {
    params.append("has_multiple_years", "true");
  }

  params.append("min_lat", String(bounds.getSouth()));
  params.append("max_lat", String(bounds.getNorth()));
  params.append("min_lng", String(bounds.getWest()));
  params.append("max_lng", String(bounds.getEast()));
  params.append("limit", "100");

  return params;
}

function shopPopup(shop) {
  const genres = shop.genres
    .map((genre) => `${genre.year} ${genre.genre_name}`)
    .join("<br>");

  return `
    <div class="popup-card">
      <strong>${shop.name}</strong>
      <div>${shop.address}</div>
      <div class="popup-genres">${genres}</div>
      <div class="popup-links">
        <a href="${shop.tabelog_url}" target="_blank" rel="noreferrer">Tabelog</a>
        <a href="${shop.google_maps_url}" target="_blank" rel="noreferrer">Google Maps</a>
      </div>
    </div>
  `;
}

function renderList(items) {
  resultList.innerHTML = "";

  for (const shop of items) {
    const item = document.createElement("li");
    item.className = "result-item";
    if (shop.shop_id === selectedShopId) {
      item.classList.add("active");
    }

    item.innerHTML = `
      <button type="button" class="result-button">
        <strong>${shop.name}</strong>
        <span>${shop.address}</span>
        <small>${shop.genres.map((genre) => genre.genre_slug).join(", ")}</small>
      </button>
    `;

    item.querySelector("button").addEventListener("click", () => {
      selectedShopId = shop.shop_id;
      const marker = markerByShopId.get(shop.shop_id);
      if (marker) {
        map.setView(marker.getLatLng(), Math.max(map.getZoom(), 14));
        marker.openPopup();
      }
      renderList(lastItems);
    });

    resultList.appendChild(item);
  }
}

function renderMarkers(items) {
  markersLayer.clearLayers();
  markerByShopId = new Map();

  for (const shop of items) {
    const marker = L.marker([shop.latitude, shop.longitude]);
    marker.bindPopup(shopPopup(shop));
    marker.on("click", () => {
      selectedShopId = shop.shop_id;
      renderList(lastItems);
    });
    marker.addTo(markersLayer);
    markerByShopId.set(shop.shop_id, marker);
  }
}

async function fetchShops() {
  statusText.textContent = "検索中...";
  warningText.textContent = "";

  const response = await fetch(`/v1/shops/search?${buildParams().toString()}`);
  if (!response.ok) {
    throw new Error(`Search request failed: ${response.status}`);
  }

  return response.json();
}

async function refresh() {
  try {
    const payload = await fetchShops();
    lastItems = payload.items;

    if (!payload.items.some((shop) => shop.shop_id === selectedShopId)) {
      selectedShopId = null;
    }

    renderMarkers(payload.items);
    renderList(payload.items);

    resultCount.textContent = String(payload.returned);
    statusText.textContent = `${payload.returned} / ${payload.total} shops`;
    warningText.textContent = payload.truncated && payload.warning
      ? "表示範囲内の件数が多いため、一部のみ表示しています。"
      : "";
  } catch (error) {
    statusText.textContent = "検索に失敗しました";
    warningText.textContent = error instanceof Error ? error.message : String(error);
    resultCount.textContent = "0";
    lastItems = [];
    renderMarkers([]);
    renderList([]);
  }
}

function scheduleRefresh() {
  window.clearTimeout(fetchTimer);
  fetchTimer = window.setTimeout(() => {
    refresh();
  }, 250);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  scheduleRefresh();
});

map.on("moveend", scheduleRefresh);

refresh();