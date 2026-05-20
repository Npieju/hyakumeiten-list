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
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarContent = document.getElementById("sidebar-content");
const mapHudStatus = document.getElementById("map-hud-status");
const mapHudFilters = document.getElementById("map-hud-filters");
const mapLegend = document.getElementById("map-legend");
const mapLegendPreview = document.getElementById("map-hud-legend-preview");
const reservationFields = document.getElementById("reservation-fields");
const searchModeButtons = Array.from(document.querySelectorAll(".search-mode-button"));
const genreToggleGroup = document.getElementById("genre-toggle-group");
const genreToggleAllButton = document.getElementById("genre-toggle-all");
const genrePicker = document.getElementById("genre-picker");
const genrePickerSummary = document.getElementById("genre-picker-summary");

let selectedShopId = null;
let lastItems = [];
let markerByShopId = new Map();
let fetchTimer = null;
let genreFilters = [];
let selectedGenres = new Set();
let searchMode = "static";

const STATUS_LABELS = {
  open: "営業",
  bookable: "予約可能",
  sold_out: "空席なし",
  booking_closed: "受付外",
  temporarily_closed: "休業日",
  link_only: "予約リンクあり",
  no_info: "情報なし",
  not_supported: "情報なし",
  provider_unlinked: "情報なし",
  provider_error: "取得失敗",
  unknown: "要確認",
};

const STATUS_CLASS_NAMES = {
  static: "is-static",
  open: "is-open",
  bookable: "is-bookable",
  sold_out: "is-sold-out",
  booking_closed: "is-booking-closed",
  temporarily_closed: "is-temporarily-closed",
  link_only: "is-link-only",
  no_info: "is-no-info",
  not_supported: "is-not-supported",
  provider_unlinked: "is-unlinked",
  provider_error: "is-error",
  unknown: "is-unknown",
  skipped: "is-skipped",
};

const STATUS_SYMBOLS = {
  static: "•",
  open: "営",
  bookable: "O",
  sold_out: "X",
  booking_closed: "-",
  temporarily_closed: "休",
  link_only: "予",
  no_info: "?",
  not_supported: "?",
  provider_unlinked: "?",
  provider_error: "!",
  unknown: "?",
  skipped: "…",
};

const STATIC_LEGEND_ITEMS = [
  { status: "static", label: "静的検索のみ" },
];

const MULTI_YEAR_LEGEND_ITEM = {
  status: "static",
  label: "複数年掲載",
  decorated: true,
};

const BUSINESS_LEGEND_ITEMS = [
  { status: "open", label: "営業" },
  { status: "temporarily_closed", label: "休業日" },
  { status: "no_info", label: "情報なし" },
  { status: "skipped", label: "未評価" },
];

const RESERVATION_LEGEND_ITEMS = [
  { status: "bookable", label: "予約可能" },
  { status: "sold_out", label: "空席なし" },
  { status: "booking_closed", label: "受付外" },
  { status: "temporarily_closed", label: "休業日" },
  { status: "link_only", label: "予約リンクあり" },
  { status: "no_info", label: "情報なし" },
  { status: "skipped", label: "未評価" },
];

const SEARCH_LIMIT = 300;

function genreSelectionIsAll() {
  return selectedGenres.size === 0 || selectedGenres.size === genreFilters.length;
}

function allGenresExplicitlySelected() {
  return genreFilters.length > 0 && selectedGenres.size === genreFilters.length;
}

function selectedGenreFilterEntries() {
  if (genreSelectionIsAll()) {
    return [];
  }

  return genreFilters.filter((genre) => selectedGenres.has(genre.slug));
}

function selectedGenreRequestSlugs() {
  return selectedGenreFilterEntries().flatMap((genre) => genre.slugs);
}

function genreSummaryLabel() {
  const selectedEntries = selectedGenreFilterEntries();
  if (selectedEntries.length === 0) {
    return "All";
  }
  if (selectedEntries.length <= 2) {
    return selectedEntries.map((genre) => genre.label).join(", ");
  }
  return `${selectedEntries.length}件選択`;
}

function renderGenreToggles() {
  if (!genreToggleGroup || !genrePickerSummary) {
    return;
  }

  genrePickerSummary.textContent = genreSummaryLabel();
  if (genreToggleAllButton) {
    genreToggleAllButton.textContent = allGenresExplicitlySelected() ? "全解除" : "全選択";
  }
  genreToggleGroup.innerHTML = genreFilters.map((genre) => `
    <label class="genre-option ${selectedGenres.has(genre.slug) ? "is-active" : ""}" title="${genre.label}">
      <input type="checkbox" data-genre-slug="${genre.slug}" ${selectedGenres.has(genre.slug) ? "checked" : ""}>
      <span>${genre.label}</span>
    </label>
  `).join("");
}

async function loadGenreFilters() {
  const response = await fetch("/v1/metadata/genres");
  if (!response.ok) {
    throw new Error(`Genre metadata request failed: ${response.status}`);
  }
  const payload = await response.json();
  genreFilters = Array.isArray(payload.items) ? payload.items : [];
  renderGenreToggles();
}

function providerInputValue() {
  return document.getElementById("provider-input").value;
}

function businessCheckEnabled() {
  return searchMode === "business" || searchMode === "reservation";
}

function hasReservationLink(shop) {
  return Array.isArray(shop.providers)
    && shop.providers.some((provider) => provider.reservation_url);
}

function reservationEnabled() {
  return searchMode === "reservation";
}

function syncSearchModeButtons() {
  for (const button of searchModeButtons) {
    const active = button.dataset.searchMode === searchMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function setSearchMode(nextMode) {
  searchMode = nextMode;
  syncSearchModeButtons();
  syncReservationFields();
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "静的検索";
}

function statusClassName(status) {
  return STATUS_CLASS_NAMES[status] || "is-unknown";
}

function statusSymbol(status) {
  return STATUS_SYMBOLS[status] || "?";
}

function summaryStatus(shop) {
  return shop.reservation_summary?.status || null;
}

function hasSkippedProvider(shop) {
  return Array.isArray(shop.providers) && shop.providers.some((provider) => provider.source === "skipped");
}

function businessDisplayStatus(shop) {
  if (!Array.isArray(shop.providers) || shop.providers.length === 0) {
    return "no_info";
  }

  const statuses = shop.providers.map((provider) => provider.status);
  if (statuses.includes("bookable") || statuses.includes("sold_out")) {
    return "open";
  }
  if (statuses.includes("temporarily_closed")) {
    return "temporarily_closed";
  }
  if (statuses.includes("provider_error")) {
    return "provider_error";
  }
  if (hasSkippedProvider(shop)) {
    return "skipped";
  }
  return "no_info";
}

function displayStatus(shop) {
  if (businessCheckEnabled() && !reservationEnabled()) {
    return businessDisplayStatus(shop);
  }

  const status = summaryStatus(shop);
  if (hasSkippedProvider(shop) && status === "unknown") {
    return "skipped";
  }
  if (status === "not_supported" && hasReservationLink(shop)) {
    return "link_only";
  }
  if (status === "not_supported" || status === "provider_unlinked") {
    return "no_info";
  }
  return status;
}

function statusLabelForShop(shop) {
  const status = displayStatus(shop);
  if (status === "skipped") {
    return "未評価";
  }
  return statusLabel(status);
}

function statusClassForShop(shop) {
  return statusClassName(displayStatus(shop) || "static");
}

function statusMetaMarkup(shop) {
  const status = displayStatus(shop);
  if (!status) {
    return `<div class="result-status-row is-static"><span class="result-status-dot"></span><span class="result-status-text">静的検索結果</span></div>`;
  }

  return `
    <div class="result-status-row ${statusClassName(status)}">
      <span class="result-status-dot"></span>
      <span class="result-status-text">${statusLabelForShop(shop)}</span>
    </div>
  `;
}

function businessStatusFromReservationStatus(status) {
  if (status === "bookable" || status === "sold_out") {
    return { label: "営業", className: "business-chip-open" };
  }
  if (status === "temporarily_closed") {
    return { label: "休業日", className: "business-chip-closed" };
  }
  return { label: "営業情報なし", className: "business-chip-unknown" };
}

function businessStatusForShop(shop) {
  if (!Array.isArray(shop.providers) || shop.providers.length === 0) {
    return { label: "営業情報なし", className: "business-chip-unknown" };
  }

  const statuses = shop.providers.map((provider) => provider.status);
  if (statuses.includes("bookable") || statuses.includes("sold_out")) {
    return { label: "営業", className: "business-chip-open" };
  }
  if (statuses.includes("temporarily_closed")) {
    return { label: "休業日", className: "business-chip-closed" };
  }
  return { label: "営業情報なし", className: "business-chip-unknown" };
}

function businessStatusMarkup(shop) {
  const business = businessStatusForShop(shop);
  return `<span class="status-chip small ${business.className}">${business.label}</span>`;
}

function currentFilterSummary() {
  const year = document.getElementById("year-input").value.trim();
  const nameQuery = document.getElementById("name-input").value.trim();
  const parts = [];

  if (year) {
    parts.push(`Year ${year}`);
  }
  if (!genreSelectionIsAll()) {
    parts.push(`Genre ${genreSummaryLabel()}`);
  }
  if (nameQuery) {
    parts.push(`Name ${nameQuery}`);
  }
  if (businessCheckEnabled()) {
    parts.push("営業確認");
  }
  if (reservationEnabled()) {
    const reservationStatus = document.getElementById("reservation-status-input").value;
    parts.push("空席確認");
    if (reservationStatus) {
      parts.push(`予約 ${statusLabel(reservationStatus)}`);
    }
  }

  return parts.join(" / ") || "Viewport search";
}

function updateMapHud(primary, secondary = currentFilterSummary()) {
  mapHudStatus.textContent = primary;
  mapHudFilters.textContent = secondary;
}

function legendItems() {
  const items = reservationEnabled()
    ? RESERVATION_LEGEND_ITEMS
    : businessCheckEnabled()
      ? BUSINESS_LEGEND_ITEMS
      : STATIC_LEGEND_ITEMS;

  return [...items, MULTI_YEAR_LEGEND_ITEM];
}

function hasMultipleYears(shop) {
  return Array.isArray(shop.years) && shop.years.length > 1;
}

function legendDecorationClass(item) {
  return item.decorated ? "has-multi-year-mark" : "";
}

function legendItemMarkup(item) {
  return `<span class="map-legend-item"><i class="map-legend-dot ${statusClassName(item.status)} ${legendDecorationClass(item)}"></i>${item.label}</span>`;
}

function legendPreviewMarkup(item) {
  return `<i class="map-legend-dot ${statusClassName(item.status)} ${legendDecorationClass(item)}"></i>`;
}

function updateLegend() {
  const items = legendItems();
  mapLegend.innerHTML = items.map(legendItemMarkup).join("");
  mapLegendPreview.innerHTML = items.slice(0, 4).map(legendPreviewMarkup).join("");
}

function buildParams() {
  const bounds = map.getBounds();
  const params = new URLSearchParams();
  const year = document.getElementById("year-input").value.trim();
  const nameQuery = document.getElementById("name-input").value.trim();
  const genreSlugs = selectedGenreRequestSlugs();

  if (year) {
    params.append("year", year);
  }
  for (const genreSlug of genreSlugs) {
    params.append("genre_slug", genreSlug);
  }
  if (nameQuery) {
    params.append("name_query", nameQuery);
  }

  params.append("min_lat", String(bounds.getSouth()));
  params.append("max_lat", String(bounds.getNorth()));
  params.append("min_lng", String(bounds.getWest()));
  params.append("max_lng", String(bounds.getEast()));
  params.append("limit", String(SEARCH_LIMIT));

  return params;
}

function buildAvailabilityPayload() {
  const bounds = map.getBounds();
  const year = document.getElementById("year-input").value.trim();
  const nameQuery = document.getElementById("name-input").value.trim();
  const reservationStatus = document.getElementById("reservation-status-input").value;
  const provider = providerInputValue();
  const genreSlugs = selectedGenreRequestSlugs();

  const filters = {
    year: year ? [Number(year)] : [],
    genre_slug: genreSlugs,
    region: [],
    prefecture: [],
    bounding_box: {
      min_lat: bounds.getSouth(),
      max_lat: bounds.getNorth(),
      min_lng: bounds.getWest(),
      max_lng: bounds.getEast(),
    },
    name_query: nameQuery || null,
    address_query: null,
    has_multiple_years: false,
  };

  return {
    filters,
    reservation: {
      date: document.getElementById("reservation-date-input").value,
      party_size: Number(document.getElementById("party-size-input").value || "2"),
      time_window: document.getElementById("time-window-input").value,
      status: reservationEnabled() && reservationStatus ? [reservationStatus] : [],
      provider: reservationEnabled() && provider ? [provider] : [],
    },
    limit: SEARCH_LIMIT,
    offset: 0,
  };
}

function reservationLinkMarkup(provider) {
  if (!provider.reservation_url) {
    return '<span class="provider-link-missing">リンクなし</span>';
  }

  return `<a class="provider-link" href="${provider.reservation_url}" target="_blank" rel="noreferrer">予約ページ</a>`;
}

function reservationLinksMarkup(shop) {
  if (!shop.providers || shop.providers.length === 0) {
    return "";
  }

  const linkedProviders = shop.providers.filter((provider) => provider.reservation_url);
  if (linkedProviders.length === 0) {
    return "";
  }

  return `
    <div class="popup-links popup-links-reservation">
      ${linkedProviders
        .map((provider) => `<a href="${provider.reservation_url}" target="_blank" rel="noreferrer">${provider.provider} 予約</a>`)
        .join("")}
    </div>
  `;
}

function reservationSummaryMarkup(shop) {
  if (!shop.reservation_summary) {
    return "";
  }
  return `<span class="status-chip ${statusClassForShop(shop)}">${statusLabelForShop(shop)}</span>`;
}

function statusChipGroupMarkup(shop) {
  if (!businessCheckEnabled()) {
    return "";
  }

  const chips = [businessStatusMarkup(shop)];
  const reservationMarkup = reservationEnabled() ? reservationSummaryMarkup(shop) : "";
  if (reservationMarkup) {
    chips.push(reservationMarkup);
  }
  return `<span class="status-chip-group">${chips.join("")}</span>`;
}

function providerRowsMarkup(shop) {
  if (!shop.providers || shop.providers.length === 0) {
    return "";
  }

  const showReservationDetails = reservationEnabled();

  return shop.providers
    .map((provider) => {
      const business = businessStatusFromReservationStatus(provider.status);
      const slots = provider.available_slots.length > 0
        ? provider.available_slots.join(", ")
        : "-";
      const sourceLabel = provider.source === "skipped"
        ? "未評価"
        : provider.source === "cache"
          ? "cache"
          : provider.source === "live"
            ? "live"
            : "";
      const providerStatusLabel = provider.source === "skipped"
        ? "未評価"
        : statusLabel(provider.status);
      const providerStatusClass = provider.source === "skipped"
        ? statusClassName("skipped")
        : statusClassName(provider.status);
      return `
        <div class="provider-row">
          <span class="provider-name">${provider.provider || "unlinked"}</span>
          <span class="status-chip small ${business.className}">${business.label}</span>
          ${showReservationDetails ? `<span class="status-chip small ${providerStatusClass}">${providerStatusLabel}</span>` : ""}
          ${showReservationDetails ? `<span class="provider-slots">${slots}</span>` : ""}
          ${showReservationDetails ? reservationLinkMarkup(provider) : ""}
          <span class="provider-source">${sourceLabel}</span>
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
      ${statusChipGroupMarkup(shop)}
      <div>${shop.address}</div>
      <div class="popup-genres">${genres}</div>
      <div class="provider-list">${providerRowsMarkup(shop)}</div>
      ${reservationLinksMarkup(shop)}
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
          ${statusChipGroupMarkup(shop)}
        </div>
        ${statusMetaMarkup(shop)}
        <span>${shop.address}</span>
        <small>${shop.genres.map((genre) => genre.genre_slug).join(", ")}</small>
        ${businessCheckEnabled() ? `<small>${providerRowsMarkup(shop)}</small>` : ""}
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
    const status = displayStatus(shop) || "static";
    const multiYearClass = hasMultipleYears(shop) ? " is-multi-year" : "";
    const marker = L.marker([shop.latitude, shop.longitude], {
      icon: L.divIcon({
        className: `map-pin ${statusClassName(status)}${multiYearClass}`,
        html: `<span data-symbol="${statusSymbol(status)}"></span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
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
  updateMapHud("検索中...", currentFilterSummary());

  if (businessCheckEnabled()) {
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

    if (businessCheckEnabled()) {
      resultCount.textContent = String(payload.items.length);
      const cachePercent = Math.round((payload.cache_hit_ratio || 0) * 100);
      statusText.textContent = `${payload.items.length} / ${payload.total} shops, cache ${cachePercent}%`;
      updateMapHud(`${payload.items.length} / ${payload.total} shops`, `${currentFilterSummary()} / Cache ${cachePercent}%`);
      warningText.textContent = payload.warning === "live_check_limit_exceeded"
        ? "live check 上限に達したため、表示中に未評価の店舗が含まれます。条件を絞ってください。"
        : "";
    } else {
      resultCount.textContent = String(payload.returned);
      statusText.textContent = `${payload.returned} / ${payload.total} shops`;
      updateMapHud(`${payload.returned} / ${payload.total} shops`, currentFilterSummary());
      warningText.textContent = payload.truncated && payload.warning
        ? `表示範囲内の件数が多いため、先頭 ${SEARCH_LIMIT} 件のみ表示しています。`
        : "";
    }
  } catch (error) {
    statusText.textContent = "検索に失敗しました";
    updateMapHud("検索に失敗しました", currentFilterSummary());
    warningText.textContent = error instanceof Error ? error.message : String(error);
    resultCount.textContent = "0";
    lastItems = [];
    renderMarkers([]);
    renderList([]);
  }
}

function syncReservationFields() {
  reservationFields.classList.remove("is-disabled");
  updateLegend();
}

function syncSidebarState() {
  const collapsed = window.innerWidth <= 960 && sidebarContent.classList.contains("is-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.textContent = collapsed ? "絞り込み" : "閉じる";
}

function setSidebarCollapsed(collapsed) {
  sidebarContent.classList.toggle("is-collapsed", collapsed);
  syncSidebarState();
}

function syncSidebarForViewport() {
  if (window.innerWidth <= 960) {
    if (!sidebarContent.dataset.mobileInitialized) {
      setSidebarCollapsed(true);
      sidebarContent.dataset.mobileInitialized = "true";
      return;
    }
    syncSidebarState();
    return;
  }

  sidebarContent.classList.remove("is-collapsed");
  delete sidebarContent.dataset.mobileInitialized;
  syncSidebarState();
}

function scheduleRefresh() {
  window.clearTimeout(fetchTimer);
  fetchTimer = window.setTimeout(() => {
    refresh();
  }, 250);
}

genreToggleGroup.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) {
    return;
  }

  const slug = target.dataset.genreSlug || "";
  if (!slug) {
    return;
  }

  if (target.checked) {
    selectedGenres.add(slug);
  } else {
    selectedGenres.delete(slug);
  }

  if (selectedGenres.size === genreFilters.length) {
    selectedGenres.clear();
  }

  renderGenreToggles();
  scheduleRefresh();
});

genreToggleAllButton.addEventListener("click", () => {
  if (allGenresExplicitlySelected()) {
    selectedGenres.clear();
  } else {
    selectedGenres = new Set(genreFilters.map((genre) => genre.slug));
  }

  renderGenreToggles();
  scheduleRefresh();
});

document.addEventListener("click", (event) => {
  if (!genrePicker || !genrePicker.open) {
    return;
  }

  if (genrePicker.contains(event.target)) {
    return;
  }

  genrePicker.open = false;
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const submitter = event.submitter;
  const nextMode = submitter instanceof HTMLButtonElement && submitter.dataset.searchMode
    ? submitter.dataset.searchMode
    : "static";
  setSearchMode(nextMode);
  scheduleRefresh();
});

sidebarToggle.addEventListener("click", () => {
  setSidebarCollapsed(!sidebarContent.classList.contains("is-collapsed"));
});

map.on("moveend", scheduleRefresh);
window.addEventListener("resize", syncSidebarForViewport);

async function init() {
  syncSearchModeButtons();
  syncReservationFields();
  syncSidebarForViewport();
  updateLegend();
  updateMapHud("地図を読み込み中...", currentFilterSummary());
  try {
    await loadGenreFilters();
  } catch (error) {
    warningText.textContent = error instanceof Error ? error.message : String(error);
  }
  await refresh();
}

init();