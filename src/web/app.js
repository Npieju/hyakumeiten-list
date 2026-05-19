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
const reservationEnabledInput = document.getElementById("reservation-enabled-input");
const reservationFields = document.getElementById("reservation-fields");

let selectedShopId = null;
let lastItems = [];
let markerByShopId = new Map();
let fetchTimer = null;

const STATUS_LABELS = {
  bookable: "予約可能",
  sold_out: "空席なし",
  booking_closed: "受付終了",
  temporarily_closed: "臨時休業",
  not_supported: "予約対象外",
  provider_unlinked: "未紐付け",
  provider_error: "取得失敗",
  unknown: "要確認",
};

const STATUS_CLASS_NAMES = {
  bookable: "is-bookable",
  sold_out: "is-sold-out",
  booking_closed: "is-booking-closed",
  temporarily_closed: "is-booking-closed",
  not_supported: "is-not-supported",
  provider_unlinked: "is-unlinked",
  provider_error: "is-error",
  unknown: "is-unknown",
};

function reservationEnabled() {
  return reservationEnabledInput.checked;
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "静的検索";
}

function statusClassName(status) {
  return STATUS_CLASS_NAMES[status] || "is-unknown";
}

function summaryStatus(shop) {
  return shop.reservation_summary?.status || null;
}

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

function buildAvailabilityPayload() {
  const bounds = map.getBounds();
  const year = document.getElementById("year-input").value.trim();
  const genreSlug = document.getElementById("genre-input").value.trim();
  const nameQuery = document.getElementById("name-input").value.trim();
  const region = document.getElementById("region-input").value;
  const hasMultipleYears = document.getElementById("multiple-years-input").checked;
  const reservationStatus = document.getElementById("reservation-status-input").value;
  const provider = document.getElementById("provider-input").value;

  const filters = {
    year: year ? [Number(year)] : [],
    genre_slug: genreSlug ? [genreSlug] : [],
    region: region ? [region] : [],
    prefecture: [],
    bounding_box: {
      min_lat: bounds.getSouth(),
      max_lat: bounds.getNorth(),
      min_lng: bounds.getWest(),
      max_lng: bounds.getEast(),
    },
    name_query: nameQuery || null,
    address_query: null,
    has_multiple_years: hasMultipleYears,
  };

  return {
    filters,
    reservation: {
      date: document.getElementById("reservation-date-input").value,
      party_size: Number(document.getElementById("party-size-input").value || "2"),
      time_window: document.getElementById("time-window-input").value,
      status: reservationStatus ? [reservationStatus] : [],
      provider: provider ? [provider] : [],
    },
    limit: 100,
    offset: 0,
  };
}

function reservationSummaryMarkup(shop) {
  if (!shop.reservation_summary) {
    return "";
  }
  const status = shop.reservation_summary.status;
  return `<span class="status-chip ${statusClassName(status)}">${statusLabel(status)}</span>`;
}

function providerRowsMarkup(shop) {
  if (!shop.providers || shop.providers.length === 0) {
    return "";
  }

  return shop.providers
    .map((provider) => {
      const slots = provider.available_slots.length > 0
        ? provider.available_slots.join(", ")
        : "-";
      return `
        <div class="provider-row">
          <span class="provider-name">${provider.provider || "unlinked"}</span>
          <span class="status-chip small ${statusClassName(provider.status)}">${statusLabel(provider.status)}</span>
          <span class="provider-slots">${slots}</span>
        </div>
      `;
    })
    .join("");
}

function shopPopup(shop) {
  const genres = shop.genres
    .map((genre) => `${genre.year} ${genre.genre_name}`)
    .join("<br>");

  return `
    <div class="popup-card">
      <strong>${shop.name}</strong>
      ${reservationSummaryMarkup(shop)}
      <div>${shop.address}</div>
      <div class="popup-genres">${genres}</div>
      <div class="provider-list">${providerRowsMarkup(shop)}</div>
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
        <div class="result-title-row">
          <strong>${shop.name}</strong>
          ${reservationSummaryMarkup(shop)}
        </div>
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
    const status = summaryStatus(shop);
    const marker = L.marker([shop.latitude, shop.longitude], {
      icon: L.divIcon({
        className: `map-pin ${statusClassName(status)}`,
        html: `<span></span>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      }),
    });
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

  if (reservationEnabled()) {
    const response = await fetch("/v1/shops/availability-search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildAvailabilityPayload()),
    });
    if (!response.ok) {
      throw new Error(`Availability request failed: ${response.status}`);
    }
    return response.json();
  }

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

    if (reservationEnabled()) {
      resultCount.textContent = String(payload.items.length);
      const cachePercent = Math.round((payload.cache_hit_ratio || 0) * 100);
      statusText.textContent = `${payload.items.length} / ${payload.total} shops, cache ${cachePercent}%`;
      warningText.textContent = payload.warning === "live_check_limit_exceeded"
        ? "live check 上限に達したため、一部は未評価です。条件を絞ってください。"
        : "";
    } else {
      resultCount.textContent = String(payload.returned);
      statusText.textContent = `${payload.returned} / ${payload.total} shops`;
      warningText.textContent = payload.truncated && payload.warning
        ? "表示範囲内の件数が多いため、一部のみ表示しています。"
        : "";
    }
  } catch (error) {
    statusText.textContent = "検索に失敗しました";
    warningText.textContent = error instanceof Error ? error.message : String(error);
    resultCount.textContent = "0";
    lastItems = [];
    renderMarkers([]);
    renderList([]);
  }
}

function syncReservationFields() {
  reservationFields.classList.toggle("is-disabled", !reservationEnabled());
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

reservationEnabledInput.addEventListener("change", () => {
  syncReservationFields();
  scheduleRefresh();
});

map.on("moveend", scheduleRefresh);

syncReservationFields();
refresh();