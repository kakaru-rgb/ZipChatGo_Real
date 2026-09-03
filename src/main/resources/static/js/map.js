let map;
let allProperties = [];
let filteredProperties = [];
let selectedProperty = null;
let propertyListScrollTop = 0;

let propertyIndex = null;
let sidoIndex = null;
let sigunguIndex = null;
let dongIndex = null;

let markerMap = new Map();
let aiHighlightMarkerMap = new Map();
let infoMarker = null;
let renderTimer = null;

let allPois = [];
let poiIndexes = new Map();
let poiMarkerMap = new Map();
let poiInfoMarker = null;
let activePoiPopupItems = [];
let activePoiPopupIndex = 0;
let activePoiPopupPosition = null;
const activePoiCategories = new Set();

let distanceMeasureActive = false;
let distanceMeasureFinished = false;
let distanceMeasurePoints = [];
let distanceMeasurePolyline = null;
let distanceMeasurePreview = null;
let distanceMeasurePointMarkers = [];
let distanceMeasureSegmentLabels = [];
let distanceMeasureTotalLabel = null;

const MOBILE_MAP_MEDIA_QUERY = window.matchMedia("(max-width: 768px)");
const FAVORITE_PROPERTY_STORAGE_KEY = "zipchatgo.favoritePropertyIds";
const propertyPriceHistoryCache = new Map();
let mobileMapView = "map";
let favoritePropertyIds = loadFavoritePropertyIds();
let currentMapLocation = null;
let reverseGeocodeTimer = null;
let reverseGeocodeRequestSequence = 0;
const reverseGeocodeCache = new Map();
let legalDongRegions = [];
let selectedLegalDong = null;
let hoveredLegalDong = null;
let legalDongTooltipMarker = null;
let legalDongPolygonClickTime = 0;

const INITIAL_CENTER = new naver.maps.LatLng(37.40, 127.15);

const APP_MIN_ZOOM = 10; // 0단계
const APP_START_ZOOM = 11;   // 처음 화면 1단계
const APP_MAX_ZOOM = 18; // 8단계

const SIGUNGU_STAGE_MAX = 2; // 1~2단계
const DONG_STAGE_MAX = 4;    // 3~4단계
// 5~8단계: 개별물건

const MAX_VISIBLE_MARKERS = 700;
const MAX_LIST_ITEMS = 200;
const PROPERTY_CLUSTER_MARKER_WIDTH = 62;
const PROPERTY_CLUSTER_MARKER_HEIGHT = 60;
const PROPERTY_MARKER_WIDTH = 62;
const PROPERTY_MARKER_HEIGHT = 58;
const MAX_VISIBLE_POI_MARKERS = 500;
const MAX_BUS_ROUTES_PER_STOP = 30;
const REVERSE_GEOCODE_DELAY_MS = 400;
const REVERSE_GEOCODE_CACHE_LIMIT = 50;
const LEGAL_DONG_GEOJSON_URL = "/data/bundang_legal_dong.geojson";
const LEGAL_DONG_COLORS = Object.freeze([
  "#f4a6a6",
  "#f6c58f",
  "#f3df8b",
  "#a8d8a8",
  "#9fd9d2",
  "#a9c8f5",
  "#c6b1eb",
  "#e5add2"
]);

const PROPERTY_IMAGE_BASE_PATH = "/data/아파트_공통_이미지";
const APARTMENT_IMAGE_COUNT = 93;
const FLOORPLAN_IMAGE_VARIANTS = Object.freeze({
  "전용39": [1, 3, 4, 5, 6, 7, 9],
  "전용49": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "전용59": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
  "전용74": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "전용84": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "전용101": [1, 2, 3, 4, 5, 6],
  "전용114": [3, 5, 6, 7, 8, 9, 10, 11],
  "전용134이상": [2, 4, 5, 6, 8, 9, 10]
});

const POI_CATEGORY_CONFIG = {
  "공공기관": {
    label: "공공",
    className: "public",
    color: "#7a6fb5",
    icon: '<path d="M3 9h18M5 9v8m4-8v8m6-8v8m4-8v8M3 20h18M12 3l9 4H3l9-4Z"/>'
  },
  "교육": {
    label: "교육",
    className: "education",
    color: "#44896f",
    icon: '<path d="m3 9 9-5 9 5-9 5-9-5Zm4 3v5c3 2 7 2 10 0v-5m4-3v6"/>'
  },
  "교통": {
    label: "교통",
    className: "transport",
    color: "#397dae",
    icon: '<path d="M6 17h12a2 2 0 0 0 2-2V7c0-3-4-4-8-4S4 4 4 7v8a2 2 0 0 0 2 2Zm-2-7h16M7 20v-3m10 3v-3M8 14h.01M16 14h.01"/>'
  },
  "의료": {
    label: "의료",
    className: "medical",
    color: "#c46978",
    icon: '<path d="M12 21S4 16.5 4 9.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 8 3.5C20 16.5 12 21 12 21Z"/><path d="M8 12h2l1-3 2 6 1-3h2"/>'
  },
  "중개": {
    label: "중개",
    className: "brokerage",
    color: "#b86f0b",
    popupOffset: 54,
    icon: '<path d="m4 10 8-6 8 6v9H4v-9Z"/><path d="M7 11h10v5H7zM9 19v-3m6 3v-3"/>'
  }
};

const POI_VARIANT_CONFIG = {
  police: {
    className: "police",
    color: "#a94732"
  },
  earlyEducation: {
    className: "early-education",
    color: "#a97b16"
  }
};

map = new naver.maps.Map("map", {
  center: INITIAL_CENTER,
  zoom: APP_START_ZOOM,
  minZoom: APP_MIN_ZOOM,
  maxZoom: APP_MAX_ZOOM,
  zoomControl: false
});

window.zipchatgoMapState = Object.freeze({
  getSnapshot: getAiAppState
});

const propertyDataReady = loadProperties();

window.zipchatgoMapActions = Object.freeze({
  execute: executeAiMapActions
});

loadPois();
loadLegalDongBoundaries();

function getAiAppState() {
  const center = map.getCenter();
  const bounds = map.getBounds();
  const southWest = bounds.getSW();
  const northEast = bounds.getNE();
  const maxPrice = document.getElementById("priceFilter")?.value || "";

  return {
    current_page: "map",
    map_center: {
      lat: center.lat(),
      lng: center.lng()
    },
    zoom: map.getZoom(),
    current_region: getCurrentMapLocation(center)?.region || null,
    center_address: getCurrentMapLocation(center)?.address || null,
    map_bounds: {
      south: southWest.lat(),
      west: southWest.lng(),
      north: northEast.lat(),
      east: northEast.lng()
    },
    selected_region: selectedLegalDong ? {
      type: "legal_dong",
      code: selectedLegalDong.code,
      name: selectedLegalDong.name,
      full_name: selectedLegalDong.fullName,
      center: selectedLegalDong.center,
      bounds: selectedLegalDong.bounds
    } : null,
    selected_property_id: selectedProperty?.id != null ? String(selectedProperty.id) : null,
    favorite_property_ids: Array.from(favoritePropertyIds, String),
    filters: {
      keyword: document.getElementById("searchInput")?.value.trim() || null,
      property_type: document.getElementById("typeFilter")?.value || null,
      max_price: maxPrice ? Number(maxPrice) * 10000 : null
    }
  };
}

async function loadProperties() {
  try {
    const res = await fetch("/api/map/properties");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    reportFallbackDataSource(res, "매물");
    const data = await res.json();

    allProperties = data
      .map(item => ({
        ...item,
        id: String(item.id),
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        sale_price: Number(item.sale_price),
        deposit: Number(item.deposit),
        monthly_rent: Number(item.monthly_rent),
        maintenance_fee: Number(item.maintenance_fee),
        exclusive_area: Number(item.exclusive_area)
      }))
      .filter(item => !isNaN(item.latitude) && !isNaN(item.longitude));

    filteredProperties = allProperties;

    rebuildIndexes();

    // 처음 화면은 항상 1단계 고정
    map.setCenter(INITIAL_CENTER);
    map.setZoom(APP_START_ZOOM);

    bindEvents();
    scheduleReverseGeocode();

    if (!openRequestedPropertyFromUrl()) {
      renderList([]);
      scheduleRender();
    }

  } catch (err) {
    console.error("매물 데이터 로드 실패:", err);
    reportMapDataError("매물 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
}

async function loadPois() {
  try {
    const res = await fetch("/api/map/pois");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    reportFallbackDataSource(res, "주변 시설");
    const data = await res.json();

    allPois = data
      .map(item => ({
        ...item,
        poi_id: String(item.poi_id),
        latitude: Number(item.latitude),
        longitude: Number(item.longitude)
      }))
      .filter(item => (
        POI_CATEGORY_CONFIG[item.category] &&
        Number.isFinite(item.latitude) &&
        Number.isFinite(item.longitude)
      ));

    document.querySelectorAll(".poi-toggle").forEach(button => {
      const category = button.dataset.poiCategory;
      const count = allPois.filter(item => item.category === category).length;
      button.title = `${POI_CATEGORY_CONFIG[category].label} 시설 ${count.toLocaleString()}개`;
    });

    if (selectedProperty) {
      renderPropertyDetail(selectedProperty);
    }

    if (activePoiCategories.size) {
      rebuildPoiIndex();
      scheduleRender();
    }
  } catch (err) {
    console.error("POI 데이터 로드 실패:", err);
    reportMapDataError("주변 시설 데이터를 불러오지 못했습니다.");
  }
}

function reportMapDataError(message) {
  const status = document.getElementById("mapDataStatus");
  if (!status) return;

  const messages = status.textContent ? status.textContent.split(" ") : [];
  if (!messages.includes(message)) {
    status.textContent = status.textContent ? `${status.textContent} ${message}` : message;
  }
  status.hidden = false;
}

function reportFallbackDataSource(response, dataLabel) {
  if (response.headers.get("X-Map-Data-Source") !== "fallback-json") return;

  const status = document.getElementById("mapDataStatus");
  if (!status) return;

  const message = `TiDB 연결 문제로 ${dataLabel} 샘플 데이터를 표시하고 있습니다.`;
  if (!status.textContent.includes(message)) {
    status.textContent = status.textContent ? `${status.textContent} ${message}` : message;
  }
  status.classList.add("is-fallback");
  status.hidden = false;
}

function bindEvents() {
  naver.maps.Event.addListener(map, "idle", () => {
    scheduleRender();
    scheduleReverseGeocode();
    clearSelectedLegalDongWhenOutOfView();
  });
  naver.maps.Event.addListener(map, "dragstart", closeAllInfoPopups);
  naver.maps.Event.addListener(map, "zoomstart", closeAllInfoPopups);
  naver.maps.Event.addListener(map, "click", handleMapClick);
  naver.maps.Event.addListener(map, "mousemove", handleDistanceMeasureMouseMove);

  document.getElementById("map").addEventListener("contextmenu", event => {
    if (!distanceMeasureActive) return;

    event.preventDefault();
    finishDistanceMeasurement();
  });

  document.getElementById("searchBtn").addEventListener("click", applyFilters);

  document.getElementById("searchInput").addEventListener("keydown", e => {
    if (e.key === "Enter") applyFilters();
  });

  document.getElementById("typeFilter").addEventListener("change", applyFilters);
  document.getElementById("priceFilter").addEventListener("change", applyFilters);
  document.getElementById("propertyDetailBack").addEventListener("click", () => {
    showPropertyListView({ restoreScroll: true });

    if (isMobileMapLayout()) {
      setMobileMapView("list");
    }
  });
  document.getElementById("propertyFavoriteToggle").addEventListener("click", () => {
    if (selectedProperty) toggleFavoriteProperty(selectedProperty);
  });
  document.getElementById("mobilePropertyListBack").addEventListener("click", returnToMobileMap);
  document.getElementById("mobilePropertyDetailMap").addEventListener("click", returnToMobileMap);
  document.getElementById("distanceMeasureToggle").addEventListener("click", toggleDistanceMeasurement);
  document.getElementById("distanceMeasureUndo").addEventListener("click", undoDistanceMeasurePoint);
  document.getElementById("distanceMeasureFinish").addEventListener("click", finishDistanceMeasurement);
  document.getElementById("distanceMeasureClear").addEventListener("click", () => {
    resetDistanceMeasurement({ keepOpen: true });
  });
  document.getElementById("selectedLegalDongClear").addEventListener(
    "click",
    clearSelectedLegalDong
  );

  document.querySelectorAll(".poi-toggle").forEach(button => {
    button.addEventListener("click", () => togglePoiCategory(button));
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      if (isDistanceMeasurementOpen()) {
        closeDistanceMeasurement();
        return;
      }

      closeAllInfoPopups();
    }
  });

  MOBILE_MAP_MEDIA_QUERY.addEventListener("change", syncResponsiveMapLayout);
  window.addEventListener("storage", handleFavoriteStorageChange);
  syncResponsiveMapLayout();
}

function scheduleRender() {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(() => {
    render();
    renderPois();
  }, 180);
}

function applyFilters() {
  const keyword = document.getElementById("searchInput").value.trim();
  const type = document.getElementById("typeFilter").value;
  const maxPrice = document.getElementById("priceFilter").value;

  filteredProperties = allProperties.filter(item => {
    const searchText = `
      ${item.title || ""}
      ${item.description || ""}
      ${item.building_name || ""}
      ${item.address || ""}
      ${item.district || ""}
      ${item.lot_number || ""}
    `;

    const keywordOk = !keyword || searchText.includes(keyword);
    const typeOk = !type || item.property_type === type;
    const priceOk = !maxPrice || item.sale_price <= Number(maxPrice);

    return keywordOk && typeOk && priceOk;
  });

    rebuildIndexes();
    renderList([]);

    // 필터를 바꿔도 지도 줌/위치는 유지
    scheduleRender();
}

/* ===========================
   Supercluster Indexes
=========================== */

function rebuildIndexes() {
  propertyIndex = buildIndex(buildPropertyFeatures(filteredProperties), {
    map: props => ({
      areaSum: props.exclusiveArea || 0,
      priceSum: props.salePrice || 0,
      itemCount: 1
    }),
    reduce: (accumulated, props) => {
      accumulated.areaSum += props.areaSum;
      accumulated.priceSum += props.priceSum;
      accumulated.itemCount += props.itemCount;
    }
  });
  sidoIndex = buildIndex(buildRegionFeatures(filteredProperties, "sido"));
  sigunguIndex = buildIndex(buildRegionFeatures(filteredProperties, "sigungu"));
  dongIndex = buildIndex(buildRegionFeatures(filteredProperties, "dong"));
}

function buildIndex(features, options = {}) {
  const index = new Supercluster({
    radius: 80,
    maxZoom: APP_MAX_ZOOM,
    minPoints: 2,
    ...options
  });

  index.load(features);
  return index;
}

function buildPropertyFeatures(items) {
  return items.map(item => ({
    type: "Feature",
    properties: {
      markerType: "property",
      id: item.id,
      markerKey: `property-${item.id}`,
      exclusiveArea: item.exclusive_area,
      salePrice: item.sale_price,
      item
    },
    geometry: {
      type: "Point",
      coordinates: [item.longitude, item.latitude]
    }
  }));
}

function buildRegionFeatures(items, level) {
  const groups = {};

  items.forEach(item => {
    const name = getRegionName(item.district, level);

    if (!groups[name]) {
      groups[name] = {
        name,
        count: 0,
        priceSum: 0,
        prices: [],
        latSum: 0,
        lngSum: 0,
        level
      };
    }

    groups[name].count += 1;
    groups[name].priceSum += item.sale_price || 0;
    groups[name].prices.push(item.sale_price || 0);   // 추가
    groups[name].latSum += item.latitude;
    groups[name].lngSum += item.longitude;
  });

  return Object.values(groups).map(group => {
    const lat = group.latSum / group.count;
    const lng = group.lngSum / group.count;
    group.prices.sort((a, b) => a - b);

    const n = group.prices.length;

    let medianPrice;

    if (n % 2 === 1) {
        medianPrice = group.prices[Math.floor(n / 2)];
    } else {
        medianPrice =
            (group.prices[n / 2 - 1] + group.prices[n / 2]) / 2;
    }

    return {
      type: "Feature",
      properties: {
          markerType: "region",
          markerKey: `${level}-${group.name}`,
          level,
          name: group.name,
          count: group.count,
          medianPrice
      },
      geometry: {
        type: "Point",
        coordinates: [lng, lat]
      }
    };
  });
}

/* ===========================
   POI Index
=========================== */

function getPoiVariant(item) {
  if (
    item.category === "공공기관" &&
    /경찰서|경찰청|파출소|지구대/.test(
      `${item.name || ""} ${item.subcategory || ""}`
    )
  ) {
    return "police";
  }

  if (
    item.category === "교육" &&
    (
      item.source_type === "kindergarten" ||
      /유치원|어린이집|보육/.test(
        `${item.name || ""} ${item.subcategory || ""}`
      )
    )
  ) {
    return "earlyEducation";
  }

  return null;
}

function getPoiMarkerConfig(category, variant) {
  const categoryConfig = POI_CATEGORY_CONFIG[category];
  const variantConfig = POI_VARIANT_CONFIG[variant];

  return variantConfig
    ? { ...categoryConfig, ...variantConfig }
    : categoryConfig;
}

function togglePoiCategory(button) {
  const category = button.dataset.poiCategory;
  const willActivate = !activePoiCategories.has(category);

  if (willActivate) {
    activePoiCategories.add(category);
  } else {
    activePoiCategories.delete(category);
  }

  button.setAttribute("aria-pressed", String(willActivate));
  closePoiInfoPopup();
  rebuildPoiIndex();
  scheduleRender();
}

function rebuildPoiIndex() {
  clearPoiMarkers();
  poiIndexes = new Map();

  if (!allPois.length || !activePoiCategories.size) {
    return;
  }

  activePoiCategories.forEach(category => {
    const coordinateGroups = new Map();

    allPois.forEach(item => {
      if (item.category !== category) return;

      const coordinateKey = `${item.latitude}|${item.longitude}`;

      if (!coordinateGroups.has(coordinateKey)) {
        coordinateGroups.set(coordinateKey, {
          coordinateKey,
          latitude: item.latitude,
          longitude: item.longitude,
          items: []
        });
      }

      coordinateGroups.get(coordinateKey).items.push(item);
    });

    const features = Array.from(coordinateGroups.values()).map(group => ({
      type: "Feature",
      properties: {
        markerType: "poi",
        markerKey: `poi-${category}-${group.coordinateKey}`,
        coordinateKey: group.coordinateKey,
        category,
        variant: getPoiVariant(group.items[0]),
        items: group.items
      },
      geometry: {
        type: "Point",
        coordinates: [group.longitude, group.latitude]
      }
    }));

    const index = new Supercluster({
      radius: 56,
      maxZoom: APP_MAX_ZOOM,
      minPoints: 2,
      map: props => ({
        policeCount: props.variant === "police" ? 1 : 0,
        earlyEducationCount: props.variant === "earlyEducation" ? 1 : 0
      }),
      reduce: (accumulated, props) => {
        accumulated.policeCount += props.policeCount;
        accumulated.earlyEducationCount += props.earlyEducationCount;
      }
    });

    index.load(features);
    poiIndexes.set(category, index);
  });
}

/* ===========================
   Render
=========================== */

function render() {
  if (!propertyIndex || !sidoIndex || !sigunguIndex || !dongIndex) return;

  const bounds = map.getBounds();
  const zoom = map.getZoom();
  const stage = getAppZoomStage(zoom);
  const bbox = getBbox(bounds);

  if (stage === 0) {
    renderRegionFromIndex(sidoIndex, bbox, zoom, "sido");
    return;
  }

  if (stage <= SIGUNGU_STAGE_MAX) {
    renderRegionFromIndex(sigunguIndex, bbox, zoom, "sigungu");
    return;
  }

  if (stage <= DONG_STAGE_MAX) {
    renderRegionFromIndex(dongIndex, bbox, zoom, "dong");
    return;
  }

  renderPropertiesFromIndex(bbox);
}

function renderPois() {
  const stage = getAppZoomStage(map.getZoom());

  if (
    !poiIndexes.size ||
    stage <= DONG_STAGE_MAX
  ) {
    clearPoiMarkers();
    return;
  }

  const bbox = getBbox(map.getBounds());
  const zoom = map.getZoom();
  const visibleFeatures = [];

  for (const [category, index] of poiIndexes.entries()) {
    const remaining = MAX_VISIBLE_POI_MARKERS - visibleFeatures.length;

    if (remaining <= 0) break;

    index
      .getClusters(bbox, zoom)
      .slice(0, remaining)
      .forEach(feature => {
        visibleFeatures.push({ category, index, feature });
      });
  }

  const nextKeys = new Set();

  visibleFeatures.forEach(({ category, index, feature }) => {
    const [lng, lat] = feature.geometry.coordinates;
    const props = feature.properties;
    const key = props.cluster
      ? `poi-cluster-${category}-${props.cluster_id}`
      : props.markerKey;

    nextKeys.add(key);

    if (!poiMarkerMap.has(key)) {
      const marker = props.cluster
        ? createPoiClusterMarker(feature, lat, lng, index, category)
        : createPoiMarker(feature, lat, lng);

      poiMarkerMap.set(key, marker);
    } else {
      poiMarkerMap.get(key).setPosition(new naver.maps.LatLng(lat, lng));
    }
  });

  removeUnusedPoiMarkers(nextKeys);
}

function renderPoiMarkerContent(category, config, title, count = 0) {
  const badge = count > 1
    ? `<span class="poi-marker-badge">${count > 99 ? "99+" : count.toLocaleString()}</span>`
    : "";

  if (category === "중개") {
    return `
      <div class="brokerage-marker" title="${escapeHtml(title)}">
        <svg class="brokerage-marker-shape" viewBox="0 0 42 48" aria-hidden="true">
          <path class="brokerage-marker-house"
                d="M21 2 39 14v21c0 2.2-1.8 4-4 4h-7l-7 8-7-8H7c-2.2 0-4-1.8-4-4V14L21 2Z"></path>
          <path class="brokerage-marker-roof"
                d="M21 2 39 14v5L21 8 3 19v-5L21 2Z"></path>
        </svg>
        <span class="brokerage-marker-sign">중개</span>
        ${badge}
      </div>
    `;
  }

  return `
    <div class="poi-marker ${config.className}" title="${escapeHtml(title)}">
      <svg class="poi-marker-icon" viewBox="0 0 24 24" aria-hidden="true">
        ${config.icon}
      </svg>
      ${badge}
    </div>
  `;
}

function getPoiMarkerAnchor(category) {
  return category === "중개"
    ? new naver.maps.Point(21, 47)
    : new naver.maps.Point(15, 15);
}

function createPoiClusterMarker(feature, lat, lng, index, category) {
  const props = feature.properties;
  const clusterId = props.cluster_id;
  const count = Number(props.point_count || 0);
  let variant = null;

  if (Number(props.policeCount || 0) === count) {
    variant = "police";
  } else if (Number(props.earlyEducationCount || 0) === count) {
    variant = "earlyEducation";
  }

  const config = getPoiMarkerConfig(category, variant);
  const marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(lat, lng),
    map,
    clickable: !distanceMeasureActive,
    zIndex: 180,
    icon: {
      content: renderPoiMarkerContent(
        category,
        config,
        `${config.label} 시설 ${count.toLocaleString()}곳`,
        count
      ),
      anchor: getPoiMarkerAnchor(category)
    }
  });

  naver.maps.Event.addListener(marker, "click", () => {
    if (distanceMeasureActive) return;

    const position = marker.getPosition();

    if (map.getZoom() < APP_MAX_ZOOM) {
      const nextZoom = Math.min(
        index.getClusterExpansionZoom(clusterId),
        APP_MAX_ZOOM
      );

      moveMapTo(position, nextZoom);
      return;
    }

    const items = getPoiItemsFromCluster(index, clusterId, props.point_count);
    openPoiInfoPopup(items, position);
  });

  return marker;
}

function createPoiMarker(feature, lat, lng) {
  const items = feature.properties.items || [];
  const categories = [...new Set(items.map(item => item.category))];
  const category = categories[0];
  const config = categories.length === 1
    ? getPoiMarkerConfig(category, feature.properties.variant)
    : {
        label: "주변 시설",
        className: "mixed",
        icon: '<circle cx="7" cy="12" r="2"/><circle cx="17" cy="7" r="2"/><circle cx="16" cy="17" r="2"/><path d="m9 11 6-3m-6 5 5 3"/>'
      };
  const marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(lat, lng),
    map,
    clickable: !distanceMeasureActive,
    zIndex: 190,
    icon: {
      content: renderPoiMarkerContent(
        category,
        config,
        items[0]?.name || config.label,
        items.length
      ),
      anchor: getPoiMarkerAnchor(category)
    }
  });

  naver.maps.Event.addListener(marker, "click", () => {
    if (distanceMeasureActive) return;

    openPoiInfoPopup(items, marker.getPosition());
  });

  return marker;
}

function getPoiItemsFromCluster(index, clusterId, pointCount) {
  return index
    .getLeaves(clusterId, pointCount, 0)
    .flatMap(leaf => leaf.properties.items || []);
}

function renderRegionFromIndex(index, bbox, zoom, level) {
  const features = index.getClusters(bbox, zoom);
  const nextKeys = new Set();

  features.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const props = feature.properties;

    let regionFeature = feature;

    if (props.cluster) {
      regionFeature = makeMergedRegionFeature(index, feature, level);
    }

    const key = regionFeature.properties.markerKey;
    nextKeys.add(key);

    if (!markerMap.has(key)) {
      const marker = createRegionMarker(regionFeature, lat, lng);
      markerMap.set(key, marker);
    } else {
      markerMap.get(key).setPosition(new naver.maps.LatLng(lat, lng));
    }
  });

  removeUnusedMarkers(nextKeys);
}

function renderPropertiesFromIndex(bbox) {
  const zoom = map.getZoom();

  // 현재 줌보다 한 단계 더 세밀하게 조회한다. 개별 매물은 최대한 많이
  // 보여주면서도, 밀집 지역은 Supercluster로 묶어 마커 DOM 수를 제한한다.
  const clusterZoom = Math.min(zoom + 1, APP_MAX_ZOOM);
  const clusters = propertyIndex
    .getClusters(bbox, clusterZoom)
    .slice(0, MAX_VISIBLE_MARKERS);
  const nextKeys = new Set();

  clusters.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const props = feature.properties;

    if (props.cluster) {
      const key = `property-cluster-${props.cluster_id}`;
      nextKeys.add(key);

      if (!markerMap.has(key)) {
        const marker = createPropertyClusterMarker(feature, lat, lng);
        markerMap.set(key, marker);
      } else {
        markerMap.get(key).setPosition(new naver.maps.LatLng(lat, lng));
      }

      return;
    }

    const item = props.item;
    const key = props.markerKey;
    nextKeys.add(key);

    if (!markerMap.has(key)) {
      const marker = createPropertyMarker(item);
      markerMap.set(key, marker);
    } else {
      markerMap.get(key).setPosition(
        new naver.maps.LatLng(item.latitude, item.longitude)
      );
    }
  });

  removeUnusedMarkers(nextKeys);
}

function createPropertyClusterMarker(feature, lat, lng) {
  const props = feature.properties;
  const clusterId = feature.properties.cluster_id;
  const itemCount = props.itemCount || props.point_count || 1;
  const averageArea = props.areaSum / itemCount;
  const averagePrice = props.priceSum / itemCount;

  const marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(lat, lng),
    map,
    clickable: !distanceMeasureActive,
    icon: {
      content: `
        <div class="cluster-marker">
          <svg class="cluster-marker-shape" viewBox="0 0 62 60" aria-hidden="true">
            <path d="M2 20Q1 18 3 17L28 2Q31 0 34 2L59 17Q61 18 60 20T57 22H56V56Q56 58 54 58H8Q6 58 6 56V22H5Q3 22 2 20Z"></path>
            <path class="cluster-marker-roof-highlight" d="M4 17.5 28.5 2.7Q31 1.2 33.5 2.7L58 17.5Q59.5 18.5 58.5 20H3.5Q2.5 18.5 4 17.5Z"></path>
          </svg>
          <div class="cluster-count">${formatAreaPyeong(averageArea)}</div>
          <div class="cluster-label">${formatPriceToEok(averagePrice)}</div>
          <div class="cluster-size">(${itemCount.toLocaleString()})</div>
        </div>
      `,
      anchor: new naver.maps.Point(
        PROPERTY_CLUSTER_MARKER_WIDTH / 2,
        PROPERTY_CLUSTER_MARKER_HEIGHT / 2
      )
    }
  });

  naver.maps.Event.addListener(marker, "click", () => {
    if (distanceMeasureActive) return;

    const items = propertyIndex
      .getLeaves(clusterId, props.point_count, 0)
      .map(leaf => leaf.properties.item)
      .filter(Boolean);

    renderList(items, { openMobileList: true });

    const nextZoom = Math.min(
      propertyIndex.getClusterExpansionZoom(clusterId),
      APP_MAX_ZOOM
    );

    moveMapTo(marker.getPosition(), nextZoom);
  });

  return marker;
}

function makeMergedRegionFeature(index, cluster, level) {
  const leaves = index.getLeaves(
    cluster.properties.cluster_id,
    cluster.properties.point_count,
    0
  );

  let count = 0;
  let priceSum = 0;

  leaves.forEach(leaf => {
    count += leaf.properties.count || 0;
    priceSum += (leaf.properties.avgPrice || 0) * (leaf.properties.count || 0);
  });

  const avgPrice = count ? priceSum / count : 0;
  const [lng, lat] = cluster.geometry.coordinates;

  return {
    type: "Feature",
    properties: {
      markerType: "region",
      markerKey: `${level}-cluster-${cluster.properties.cluster_id}`,
      level,
      name: level === "sido" ? "주변시도" : level === "sigungu" ? "주변지역" : "주변동",
      count,
      avgPrice
    },
    geometry: {
      type: "Point",
      coordinates: [lng, lat]
    }
  };
}

/* ===========================
   Markers
=========================== */

function createRegionMarker(feature, lat, lng) {
  const props = feature.properties;
  const [featureLng, featureLat] = feature.geometry.coordinates;

  const marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(lat ?? featureLat, lng ?? featureLng),
    map,
    clickable: !distanceMeasureActive,
    icon: {
      content: `
        <div class="region-marker ${props.level}">
          <div class="region-name">${props.name}</div>
          <div class="region-price">
              <span class="deal-type">매</span>
              <span class="deal-price">${formatPriceToEok(props.medianPrice)}</span>
          </div>
          <div class="region-count">(${Number(props.count || 0).toLocaleString()})</div>
        </div>
      `,
      anchor: new naver.maps.Point(55, 42)
    }
  });

  naver.maps.Event.addListener(marker, "click", () => {
    if (distanceMeasureActive) return;

    renderList([]);

    let nextZoom;

    if (props.level === "sido") {
      nextZoom = APP_START_ZOOM; // 1단계
    } else if (props.level === "sigungu") {
      nextZoom = APP_START_ZOOM + 2; // 3단계
    } else {
      nextZoom = APP_START_ZOOM + 4; // 5단계
    }

    moveMapTo(marker.getPosition(), nextZoom);
  });

  return marker;
}

function createPropertyMarker(item) {
  const marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(item.latitude, item.longitude),
    map,
    clickable: !distanceMeasureActive,
    icon: {
      content: renderPropertyMarkerContent(item),
      anchor: new naver.maps.Point(
        PROPERTY_MARKER_WIDTH / 2,
        PROPERTY_MARKER_HEIGHT / 2
      )
    }
  });

  naver.maps.Event.addListener(marker, "click", () => {
    if (distanceMeasureActive) return;

    closeInfoWindow();
    renderList([item], { openMobileList: true });
  });

  return marker;
}

async function loadLegalDongBoundaries() {
  try {
    const response = await fetch(LEGAL_DONG_GEOJSON_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const geojson = await response.json();
    const features = Array.isArray(geojson?.features) ? geojson.features : [];
    legalDongRegions = features.map(createLegalDongRegion).filter(Boolean);

    if (!legalDongRegions.length) {
      throw new Error("법정동 경계가 없습니다.");
    }
  } catch (error) {
    console.error("법정동 경계 데이터 로드 실패:", error);
    reportMapDataError("법정동 경계를 불러오지 못했습니다.");
  }
}

function createLegalDongRegion(feature, index) {
  const code = String(feature?.properties?.legal_dong_code || "").trim();
  const name = String(feature?.properties?.legal_dong_name || "").trim();
  const geometry = feature?.geometry;

  if (!code || !name || !geometry) return null;

  const polygonCoordinates = geometry.type === "Polygon"
    ? [geometry.coordinates]
    : geometry.type === "MultiPolygon"
      ? geometry.coordinates
      : [];
  if (!polygonCoordinates.length) return null;

  const bounds = getLegalDongCoordinateBounds(polygonCoordinates);
  if (!bounds) return null;

  const region = {
    code,
    name,
    fullName: `경기도 성남시 분당구 ${name}`,
    color: LEGAL_DONG_COLORS[index % LEGAL_DONG_COLORS.length],
    bounds,
    center: {
      lat: (bounds.south + bounds.north) / 2,
      lng: (bounds.west + bounds.east) / 2
    },
    polygons: []
  };

  region.polygons = polygonCoordinates.map(coordinates => {
    const polygon = new naver.maps.Polygon({
      map,
      paths: coordinates.map(ring => (
        ring.map(([lng, lat]) => new naver.maps.LatLng(lat, lng))
      )),
      clickable: true,
      zIndex: 1,
      ...getLegalDongStyle(region)
    });

    naver.maps.Event.addListener(polygon, "mouseover", event => {
      if (distanceMeasureActive) return;
      hoveredLegalDong = region;
      updateLegalDongStyles();
      showLegalDongTooltip(region, event.coord);
    });
    naver.maps.Event.addListener(polygon, "mousemove", event => {
      if (!distanceMeasureActive && legalDongTooltipMarker && event.coord) {
        legalDongTooltipMarker.setPosition(event.coord);
      }
    });
    naver.maps.Event.addListener(polygon, "mouseout", () => {
      if (hoveredLegalDong === region) hoveredLegalDong = null;
      updateLegalDongStyles();
      hideLegalDongTooltip();
    });
    naver.maps.Event.addListener(polygon, "click", event => {
      if (distanceMeasureActive) {
        addDistanceMeasurePoint(event.coord);
        return;
      }
      legalDongPolygonClickTime = Date.now();
      selectLegalDong(region);
    });

    return polygon;
  });

  return region;
}

function getLegalDongCoordinateBounds(polygons) {
  let south = Infinity;
  let west = Infinity;
  let north = -Infinity;
  let east = -Infinity;

  polygons.forEach(polygon => {
    polygon.forEach(ring => {
      ring.forEach(coordinate => {
        const lng = Number(coordinate?.[0]);
        const lat = Number(coordinate?.[1]);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        south = Math.min(south, lat);
        west = Math.min(west, lng);
        north = Math.max(north, lat);
        east = Math.max(east, lng);
      });
    });
  });

  return [south, west, north, east].every(Number.isFinite)
    ? { south, west, north, east }
    : null;
}

function getLegalDongStyle(region) {
  const selected = selectedLegalDong === region;
  const hovered = hoveredLegalDong === region;

  return {
    fillColor: region.color,
    fillOpacity: selected ? 0.34 : hovered ? 0.22 : 0.035,
    strokeColor: selected ? "#2878c8" : region.color,
    strokeOpacity: selected ? 0.95 : hovered ? 0.8 : 0.42,
    strokeWeight: selected ? 3 : hovered ? 2.5 : 1.25
  };
}

function updateLegalDongStyles() {
  legalDongRegions.forEach(region => {
    const style = getLegalDongStyle(region);
    region.polygons.forEach(polygon => polygon.setOptions(style));
  });
}

function selectLegalDong(region) {
  selectedLegalDong = region;
  updateLegalDongStyles();
  updateSelectedLegalDongBadge();
}

function clearSelectedLegalDong() {
  if (!selectedLegalDong) return;
  selectedLegalDong = null;
  updateLegalDongStyles();
  updateSelectedLegalDongBadge();
}

function clearSelectedLegalDongWhenOutOfView() {
  if (!selectedLegalDong) return;

  const viewport = map.getBounds();
  const southWest = viewport.getSW();
  const northEast = viewport.getNE();
  const region = selectedLegalDong.bounds;
  const intersects = !(
    northEast.lat() < region.south ||
    southWest.lat() > region.north ||
    northEast.lng() < region.west ||
    southWest.lng() > region.east
  );

  if (!intersects) clearSelectedLegalDong();
}

function updateSelectedLegalDongBadge() {
  const badge = document.getElementById("selectedLegalDongBadge");
  const name = document.getElementById("selectedLegalDongName");
  if (!badge || !name) return;

  badge.hidden = !selectedLegalDong;
  name.textContent = selectedLegalDong?.fullName || "";
}

function showLegalDongTooltip(region, position) {
  if (!position) return;

  if (!legalDongTooltipMarker) {
    legalDongTooltipMarker = new naver.maps.Marker({
      map,
      clickable: false,
      zIndex: 1000,
      icon: {
        content: '<div class="legal-dong-tooltip"></div>',
        anchor: new naver.maps.Point(0, 42)
      }
    });
  }

  legalDongTooltipMarker.setIcon({
    content: `<div class="legal-dong-tooltip">${escapeHtml(region.name)}</div>`,
    anchor: new naver.maps.Point(0, 42)
  });
  legalDongTooltipMarker.setPosition(position);
  legalDongTooltipMarker.setMap(map);
}

function hideLegalDongTooltip() {
  legalDongTooltipMarker?.setMap(null);
}

function scheduleReverseGeocode() {
  clearTimeout(reverseGeocodeTimer);
  reverseGeocodeTimer = setTimeout(updateCurrentMapLocation, REVERSE_GEOCODE_DELAY_MS);
}

function updateCurrentMapLocation() {
  if (!naver.maps.Service?.reverseGeocode) return;

  const center = map.getCenter();
  const cacheKey = getReverseGeocodeCacheKey(center);
  const cached = reverseGeocodeCache.get(cacheKey);

  if (cached) {
    currentMapLocation = cached;
    return;
  }

  const requestSequence = ++reverseGeocodeRequestSequence;
  naver.maps.Service.reverseGeocode({ coords: center }, (status, response) => {
    if (
      status !== naver.maps.Service.Status.OK ||
      requestSequence !== reverseGeocodeRequestSequence ||
      getReverseGeocodeCacheKey(map.getCenter()) !== cacheKey
    ) return;

    const result = response?.v2;
    const regionResult = result?.results?.find(item => item?.region);
    const region = regionResult
      ? ["area1", "area2", "area3", "area4"]
          .map(area => regionResult.region?.[area]?.name)
          .filter(Boolean)
          .join(" ")
      : null;
    const address = result?.address?.roadAddress || result?.address?.jibunAddress || region;

    if (!region && !address) return;

    currentMapLocation = { cacheKey, region, address };
    reverseGeocodeCache.set(cacheKey, currentMapLocation);

    if (reverseGeocodeCache.size > REVERSE_GEOCODE_CACHE_LIMIT) {
      reverseGeocodeCache.delete(reverseGeocodeCache.keys().next().value);
    }
  });
}

function getCurrentMapLocation(center) {
  if (!currentMapLocation) return null;
  return currentMapLocation.cacheKey === getReverseGeocodeCacheKey(center)
    ? currentMapLocation
    : null;
}

function getReverseGeocodeCacheKey(position) {
  return `${position.lat().toFixed(4)},${position.lng().toFixed(4)}`;
}

function renderPropertyMarkerContent(item, highlighted = false) {
  const highlightClass = highlighted ? " is-ai-highlighted" : "";

  return `
    <div class="property-marker${highlightClass}">
      <svg class="property-marker-shape" viewBox="0 0 62 58" aria-hidden="true">
        <path d="M2 20Q1 18 3 17L28 2Q31 0 34 2L59 17Q61 18 60 20T57 22H56V54Q56 56 54 56H8Q6 56 6 54V22H5Q3 22 2 20Z"></path>
        <path class="property-marker-roof-highlight" d="M4 17.5 28.5 2.7Q31 1.2 33.5 2.7L58 17.5Q59.5 18.5 58.5 20H3.5Q2.5 18.5 4 17.5Z"></path>
      </svg>
      <div class="property-area">${formatAreaPyeong(item.exclusive_area)}</div>
      <div class="property-marker-price">
          <span class="deal-type">매</span>
          <span class="deal-price">${formatPriceToEok(item.sale_price)}</span>
      </div>
    </div>
  `;
}

async function executeAiMapActions(actions) {
  if (!Array.isArray(actions)) return;

  await propertyDataReady;

  actions.forEach(action => {
    if (!action || typeof action.type !== "string") return;

    if (action.type === "MOVE_MAP") {
      const lat = Number(action.lat);
      const lng = Number(action.lng);
      const zoom = Number(action.zoom);

      if (
        Number.isFinite(lat) && lat >= -90 && lat <= 90 &&
        Number.isFinite(lng) && lng >= -180 && lng <= 180 &&
        Number.isInteger(zoom) && zoom >= APP_MIN_ZOOM && zoom <= APP_MAX_ZOOM
      ) {
        moveMapTo(new naver.maps.LatLng(lat, lng), zoom);
      }
      return;
    }

    if (action.type === "FIT_BOUNDS") {
      const items = getPropertiesForAiAction(action.property_ids);
      if (items.length) {
        renderList(items);
        fitMapToData(items);
      }
      return;
    }

    if (action.type === "HIGHLIGHT_PROPERTIES") {
      highlightAiProperties(getPropertiesForAiAction(action.property_ids));
      return;
    }

    if (action.type === "OPEN_PROPERTY") {
      const item = allProperties.find(property => property.id === String(action.property_id));
      if (!item) return;

      openPropertyDetail(item);
      moveMapTo(new naver.maps.LatLng(item.latitude, item.longitude), APP_MAX_ZOOM);
    }
  });
}

function getPropertiesForAiAction(propertyIds) {
  if (!Array.isArray(propertyIds)) return [];

  const ids = new Set(propertyIds.slice(0, 10).map(String));
  return allProperties.filter(property => ids.has(property.id));
}

function highlightAiProperties(items) {
  clearAiHighlightMarkers();

  items.forEach(item => {
    const marker = new naver.maps.Marker({
      position: new naver.maps.LatLng(item.latitude, item.longitude),
      map,
      clickable: !distanceMeasureActive,
      zIndex: 250,
      icon: {
        content: renderPropertyMarkerContent(item, true),
        anchor: new naver.maps.Point(
          PROPERTY_MARKER_WIDTH / 2,
          PROPERTY_MARKER_HEIGHT / 2
        )
      }
    });

    naver.maps.Event.addListener(marker, "click", () => {
      if (!distanceMeasureActive) renderList([item], { openMobileList: true });
    });
    aiHighlightMarkerMap.set(item.id, marker);
  });
}

function clearAiHighlightMarkers() {
  for (const marker of aiHighlightMarkerMap.values()) marker.setMap(null);
  aiHighlightMarkerMap.clear();
}

/* ===========================
   Responsive Mobile Views
=========================== */

function isMobileMapLayout() {
  return MOBILE_MAP_MEDIA_QUERY.matches;
}

function setMobileMapView(view) {
  mobileMapView = view;

  const body = document.body;
  const mapElement = document.getElementById("map");
  const listOpen = isMobileMapLayout() && view === "list";
  const detailOpen = isMobileMapLayout() && view === "detail";

  body.classList.toggle("mobile-map-list-open", listOpen);
  body.classList.toggle("mobile-map-detail-open", detailOpen);
  mapElement.setAttribute("aria-hidden", String(listOpen || detailOpen));

  if (listOpen || detailOpen) {
    closeAllInfoPopups();
  }

  if (!listOpen && !detailOpen) {
    requestAnimationFrame(() => map.autoResize());
  }
}

function openMobilePropertyList() {
  if (!isMobileMapLayout()) return;

  const sidebar = document.getElementById("propertySidebar");
  sidebar.scrollTop = 0;
  setMobileMapView("list");
}

function returnToMobileMap() {
  if (!isMobileMapLayout()) return;

  showPropertyListView();
  setMobileMapView("map");
}

function openRequestedPropertyFromUrl() {
  const propertyId = new URLSearchParams(window.location.search).get("property_id");
  if (!propertyId) return false;

  const item = allProperties.find(property => property.id === String(propertyId));
  if (!item) return false;

  const position = new naver.maps.LatLng(item.latitude, item.longitude);

  map.setCenter(position);
  map.setZoom(APP_MAX_ZOOM);
  renderList([item]);
  openPropertyDetail(item);

  requestAnimationFrame(() => {
    clearTimeout(renderTimer);
    render();
    showPropertyInfo(item);
  });

  return true;
}

function syncResponsiveMapLayout(event = MOBILE_MAP_MEDIA_QUERY) {
  if (event.matches) {
    if (isDistanceMeasurementOpen()) {
      closeDistanceMeasurement();
    }

    const detailView = document.getElementById("propertyDetailView");
    setMobileMapView(detailView.hidden ? "map" : "detail");
  } else {
    document.body.classList.remove("mobile-map-list-open", "mobile-map-detail-open");
    document.getElementById("map").setAttribute("aria-hidden", "false");
    mobileMapView = "map";
  }

  requestAnimationFrame(() => map.autoResize());
}

/* ===========================
   List
=========================== */

function getStableImageIndex(item, length, salt = "") {
  if (!length) return 0;

  const seed = `${item?.id || ""}|${item?.building_name || ""}|${salt}`;
  let hash = 2166136261;

  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return (hash >>> 0) % length;
}

function getApartmentImagePath(item) {
  const imageNumber = getStableImageIndex(item, APARTMENT_IMAGE_COUNT, "apartment") + 1;
  const filename = `apartment_${String(imageNumber).padStart(3, "0")}.jpg`;

  return `${PROPERTY_IMAGE_BASE_PATH}/이미지/${filename}`;
}

function classifyFloorplanCategory(exclusiveArea) {
  const area = Number(exclusiveArea);
  if (!Number.isFinite(area)) return null;

  if (area < 40) return "전용39";
  if (area < 54) return "전용49";
  if (area < 66) return "전용59";
  if (area < 79) return "전용74";
  if (area < 93) return "전용84";
  if (area < 109) return "전용101";
  if (area < 125) return "전용114";
  return "전용134이상";
}

function getFloorplanImagePath(item) {
  const category = classifyFloorplanCategory(item?.exclusive_area);
  const variants = FLOORPLAN_IMAGE_VARIANTS[category];
  if (!category || !variants?.length) return "";

  const variantIndex = getStableImageIndex(item, variants.length, `floorplan:${category}`);
  const imageNumber = String(variants[variantIndex]).padStart(2, "0");
  const categoryCode = category === "전용134이상" ? "134_plus" : category.replace("전용", "");

  return `${PROPERTY_IMAGE_BASE_PATH}/평면도/${category}/floorplan_${categoryCode}_${imageNumber}.jpg`;
}

function loadFavoritePropertyIds() {
  try {
    const storedValue = JSON.parse(localStorage.getItem(FAVORITE_PROPERTY_STORAGE_KEY) || "[]");
    if (!Array.isArray(storedValue)) return new Set();

    return new Set(storedValue.map(id => String(id)));
  } catch (error) {
    console.warn("관심 매물 목록을 불러오지 못했습니다:", error);
    return new Set();
  }
}

function saveFavoritePropertyIds() {
  try {
    localStorage.setItem(
      FAVORITE_PROPERTY_STORAGE_KEY,
      JSON.stringify(Array.from(favoritePropertyIds))
    );
  } catch (error) {
    console.warn("관심 매물 목록을 저장하지 못했습니다:", error);
  }
}

function isFavoriteProperty(item) {
  return Boolean(item?.id) && favoritePropertyIds.has(String(item.id));
}

function toggleFavoriteProperty(item) {
  const propertyId = String(item?.id || "");
  if (!propertyId) return;

  if (favoritePropertyIds.has(propertyId)) {
    favoritePropertyIds.delete(propertyId);
  } else {
    favoritePropertyIds.add(propertyId);
  }

  saveFavoritePropertyIds();
  syncFavoriteIndicators();
}

function syncFavoriteToggle(item = selectedProperty) {
  const button = document.getElementById("propertyFavoriteToggle");
  if (!button) return;

  const isFavorite = isFavoriteProperty(item);
  const label = isFavorite ? "관심 매물에서 삭제" : "관심 매물에 추가";

  button.classList.toggle("is-active", isFavorite);
  button.setAttribute("aria-pressed", String(isFavorite));
  button.setAttribute("aria-label", label);
  button.title = label;
}

function syncFavoriteIndicators() {
  document.querySelectorAll("[data-favorite-property-id]").forEach(badge => {
    const isFavorite = favoritePropertyIds.has(String(badge.dataset.favoritePropertyId || ""));
    badge.classList.toggle("is-visible", isFavorite);
  });

  syncFavoriteToggle();
}

function handleFavoriteStorageChange(event) {
  if (event.key !== FAVORITE_PROPERTY_STORAGE_KEY && event.key !== null) return;

  favoritePropertyIds = loadFavoritePropertyIds();
  syncFavoriteIndicators();
}

function renderList(items, { openMobileList = false } = {}) {
  showPropertyListView();

  const list = document.getElementById("propertyList");
  const count = document.getElementById("resultCount");
  const mobileCount = document.getElementById("mobileResultCount");

  count.textContent = items.length.toLocaleString();
  mobileCount.textContent = items.length.toLocaleString();
  list.innerHTML = "";

  if (items.length > MAX_LIST_ITEMS) {
    const notice = document.createElement("div");
    notice.className = "notice";
    notice.textContent = `현재 화면에 ${items.length.toLocaleString()}개 매물이 있습니다. 확대하면 더 정확히 볼 수 있습니다.`;
    list.appendChild(notice);
  }

  items.slice(0, MAX_LIST_ITEMS).forEach(item => {
    const propertyName = item.building_name || item.title || "매물";
    const apartmentImagePath = getApartmentImagePath(item);
    const favoriteClass = isFavoriteProperty(item) ? " is-visible" : "";
    const card = document.createElement("div");
    card.className = "property-card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${propertyName} 상세정보 보기`);

    card.innerHTML = `
      <div class="property-thumbnail">
        <img src="${escapeHtml(apartmentImagePath)}"
             alt="${escapeHtml(propertyName)} 대표 사진"
             loading="lazy"
             decoding="async">
        <span class="property-favorite-badge${favoriteClass}"
              data-favorite-property-id="${escapeHtml(item.id)}"
              aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 21S4 16.5 4 9.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 8 3.5C20 16.5 12 21 12 21Z"/>
          </svg>
        </span>
        <span class="property-image-watermark" aria-hidden="true">SAMPLE</span>
      </div>
      <div class="property-info">
        <div class="property-title">${item.title || item.building_name || "매물"}</div>
        <div class="property-price">${formatPrice(item.sale_price)}</div>
        <div class="property-meta">
          ${item.property_type || ""} · ${item.exclusive_area || "-"}㎡ · ${item.floor || "-"}층
        </div>
        <div class="property-address">${item.address || ""}</div>
      </div>
    `;

    const selectProperty = () => {
      openPropertyDetail(item);

      if (isMobileMapLayout()) {
        closeInfoWindow();
        return;
      }

      const stage = getAppZoomStage(map.getZoom());

      if (stage <= DONG_STAGE_MAX) {
        const pos = new naver.maps.LatLng(item.latitude, item.longitude);

        moveMapTo(pos, APP_MAX_ZOOM);

        setTimeout(() => {
          clearTimeout(renderTimer);
          render();
          showPropertyInfo(item);
        }, 550);
        return;
      }

      showPropertyInfo(item);
    };

    card.addEventListener("click", selectProperty);
    card.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectProperty();
      }
    });

    list.appendChild(card);
  });

  if (openMobileList) {
    openMobilePropertyList();
  }
}

/* ===========================
   Distance Measure Tool
=========================== */

function isDistanceMeasurementOpen() {
  return !document.getElementById("distanceMeasurePanel").hidden;
}

function DistanceMeasureLineOverlay(options) {
  this.path = [...(options.path || [])];
  this.strokeColor = options.strokeColor || "#1e88ff";
  this.strokeOpacity = options.strokeOpacity ?? 1;
  this.strokeWeight = options.strokeWeight || 3;
  this.strokeStyle = options.strokeStyle || "solid";
  this.zIndex = options.zIndex || 1500;
  this.element = null;
  this.lineElement = null;
  this.setMap(options.map || null);
}

DistanceMeasureLineOverlay.prototype = new naver.maps.OverlayView();
DistanceMeasureLineOverlay.prototype.constructor = DistanceMeasureLineOverlay;

DistanceMeasureLineOverlay.prototype.onAdd = function() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");

  svg.classList.add("distance-measure-line-overlay");
  svg.style.zIndex = String(this.zIndex);
  svg.setAttribute("aria-hidden", "true");

  line.setAttribute("fill", "none");
  line.setAttribute("stroke", this.strokeColor);
  line.setAttribute("stroke-opacity", String(this.strokeOpacity));
  line.setAttribute("stroke-width", String(this.strokeWeight));
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("stroke-linejoin", "round");

  if (this.strokeStyle === "shortdash") {
    line.setAttribute("stroke-dasharray", "6 6");
  }

  svg.appendChild(line);
  this.element = svg;
  this.lineElement = line;
  this.getPanes().overlayImage.appendChild(svg);
};

DistanceMeasureLineOverlay.prototype.draw = function() {
  if (!this.getMap() || !this.element || this.path.length < 2) return;

  const projection = this.getProjection();
  const offsets = this.path.map(point => projection.fromCoordToOffset(point));
  const padding = this.strokeWeight + 4;
  const minX = Math.min(...offsets.map(point => point.x)) - padding;
  const minY = Math.min(...offsets.map(point => point.y)) - padding;
  const maxX = Math.max(...offsets.map(point => point.x)) + padding;
  const maxY = Math.max(...offsets.map(point => point.y)) + padding;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const points = offsets
    .map(point => `${point.x - minX},${point.y - minY}`)
    .join(" ");

  this.element.style.left = `${minX}px`;
  this.element.style.top = `${minY}px`;
  this.element.setAttribute("width", String(width));
  this.element.setAttribute("height", String(height));
  this.element.setAttribute("viewBox", `0 0 ${width} ${height}`);
  this.lineElement.setAttribute("points", points);
};

DistanceMeasureLineOverlay.prototype.onRemove = function() {
  this.element?.remove();
  this.element = null;
  this.lineElement = null;
};

DistanceMeasureLineOverlay.prototype.setPath = function(path) {
  this.path = [...path];
  this.draw();
};

DistanceMeasureLineOverlay.prototype.getDistance = function() {
  let total = 0;

  for (let index = 1; index < this.path.length; index += 1) {
    const start = this.path[index - 1];
    const end = this.path[index];

    total += calculateDistanceMeters(
      start.lat(),
      start.lng(),
      end.lat(),
      end.lng()
    );
  }

  return total;
};

function toggleDistanceMeasurement() {
  if (isMobileMapLayout()) return;

  if (isDistanceMeasurementOpen()) {
    closeDistanceMeasurement();
    return;
  }

  startDistanceMeasurement();
}

function startDistanceMeasurement() {
  if (isMobileMapLayout()) return;

  closeAllInfoPopups();
  resetDistanceMeasurement({ keepOpen: true });
}

function closeDistanceMeasurement() {
  resetDistanceMeasurement({ keepOpen: false });
}

function resetDistanceMeasurement({ keepOpen = false } = {}) {
  clearDistanceMeasureOverlays();
  distanceMeasurePoints = [];
  distanceMeasureActive = keepOpen;
  distanceMeasureFinished = false;
  setMapMarkersInteractive(!distanceMeasureActive);

  document.getElementById("distanceMeasurePanel").hidden = !keepOpen;
  document.getElementById("distanceMeasureToggle").setAttribute(
    "aria-pressed",
    String(keepOpen)
  );
  document.getElementById("map").classList.toggle(
    "is-distance-measuring",
    keepOpen
  );

  updateDistanceMeasureUi();
}

function handleMapClick(event) {
  if (distanceMeasureActive) {
    addDistanceMeasurePoint(event.coord);
    return;
  }

  if (Date.now() - legalDongPolygonClickTime < 150) return;
  clearSelectedLegalDong();
}

function setMapMarkersInteractive(interactive) {
  for (const marker of markerMap.values()) {
    marker.setClickable(interactive);
  }

  for (const marker of poiMarkerMap.values()) {
    marker.setClickable(interactive);
  }

  legalDongRegions.forEach(region => {
    region.polygons.forEach(polygon => polygon.setOptions({ clickable: interactive }));
  });

  if (!interactive) {
    hoveredLegalDong = null;
    hideLegalDongTooltip();
    updateLegalDongStyles();
  }
}

function addDistanceMeasurePoint(coord) {
  if (!distanceMeasureActive || !coord) return false;

  clearDistanceMeasurePreview();
  distanceMeasurePoints.push(coord);
  renderDistanceMeasurement();
  return true;
}

function handleDistanceMeasureMouseMove(event) {
  if (
    !distanceMeasureActive ||
    !distanceMeasurePoints.length ||
    !event.coord
  ) {
    return;
  }

  const lastPoint = distanceMeasurePoints[distanceMeasurePoints.length - 1];
  const previewPath = [lastPoint, event.coord];

  if (!distanceMeasurePreview) {
    distanceMeasurePreview = new DistanceMeasureLineOverlay({
      map,
      path: previewPath,
      strokeColor: "#1e88ff",
      strokeOpacity: 0.62,
      strokeWeight: 2,
      strokeStyle: "shortdash",
      zIndex: 1450
    });
    return;
  }

  distanceMeasurePreview.setPath(previewPath);
}

function undoDistanceMeasurePoint() {
  if (
    (!distanceMeasureActive && !distanceMeasureFinished) ||
    !distanceMeasurePoints.length
  ) {
    return;
  }

  if (distanceMeasureFinished) {
    distanceMeasureActive = true;
    distanceMeasureFinished = false;
    setMapMarkersInteractive(false);
    document.getElementById("map").classList.add("is-distance-measuring");
  }

  distanceMeasurePoints.pop();
  clearDistanceMeasurePreview();
  renderDistanceMeasurement();
}

function finishDistanceMeasurement() {
  if (!distanceMeasureActive || distanceMeasurePoints.length < 2) return;

  distanceMeasureActive = false;
  distanceMeasureFinished = true;
  setMapMarkersInteractive(true);
  clearDistanceMeasurePreview();
  document.getElementById("map").classList.remove("is-distance-measuring");
  renderDistanceMeasurement();
}

function renderDistanceMeasurement() {
  clearDistanceMeasureResultOverlays();

  distanceMeasurePointMarkers = distanceMeasurePoints.map((point, index) => {
    const isStart = index === 0;
    const isEnd = distanceMeasurePoints.length > 1 && index === distanceMeasurePoints.length - 1;
    const markerClass = isStart ? " is-start" : isEnd ? " is-end" : "";

    return new naver.maps.Marker({
      map,
      position: point,
      clickable: false,
      zIndex: 1600,
      icon: {
        content: `<div class="distance-point-marker${markerClass}"></div>`,
        anchor: new naver.maps.Point(8.5, 8.5)
      }
    });
  });

  if (distanceMeasurePoints.length >= 2) {
    distanceMeasurePolyline = new DistanceMeasureLineOverlay({
      map,
      path: distanceMeasurePoints,
      strokeColor: "#1e88ff",
      strokeOpacity: 0.9,
      strokeWeight: 4,
      zIndex: 1500
    });

    for (let index = 1; index < distanceMeasurePoints.length; index += 1) {
      const start = distanceMeasurePoints[index - 1];
      const end = distanceMeasurePoints[index];
      const segmentDistance = calculateDistanceMeters(
        start.lat(),
        start.lng(),
        end.lat(),
        end.lng()
      );
      const midpoint = new naver.maps.LatLng(
        (start.lat() + end.lat()) / 2,
        (start.lng() + end.lng()) / 2
      );

      distanceMeasureSegmentLabels.push(new naver.maps.Marker({
        map,
        position: midpoint,
        clickable: false,
        zIndex: 1590,
        icon: {
          content: `<div class="distance-segment-label">${formatMeasuredDistance(segmentDistance)}</div>`,
          anchor: new naver.maps.Point(0, 0)
        }
      }));
    }

    const totalDistance = getDistanceMeasureTotal();
    const lastPoint = distanceMeasurePoints[distanceMeasurePoints.length - 1];
    const totalLabelContent = distanceMeasureFinished
      ? renderDistanceResultPopup(totalDistance)
      : `<div class="distance-total-label">총 ${formatMeasuredDistance(totalDistance)}</div>`;

    distanceMeasureTotalLabel = new naver.maps.Marker({
      map,
      position: lastPoint,
      clickable: false,
      zIndex: 1610,
      icon: {
        content: totalLabelContent,
        anchor: new naver.maps.Point(0, 0)
      }
    });
  }

  updateDistanceMeasureUi();
}

function getDistanceMeasureTotal() {
  return distanceMeasurePolyline
    ? distanceMeasurePolyline.getDistance()
    : 0;
}

function renderDistanceResultPopup(distance) {
  const walkingMinutes = estimateTravelMinutes(distance, 4);
  const bicycleMinutes = estimateTravelMinutes(distance, 15);

  return `
    <div class="distance-result-popup"
         aria-label="총 거리 ${formatMeasuredDistance(distance)}, 도보 ${walkingMinutes}분, 자전거 ${bicycleMinutes}분">
      <strong>총 ${formatMeasuredDistance(distance)}</strong>
      <span><em>도보</em><b>${walkingMinutes}분</b></span>
      <span><em>자전거</em><b>${bicycleMinutes}분</b></span>
    </div>
  `;
}

function estimateTravelMinutes(distance, speedKilometersPerHour) {
  if (!Number.isFinite(distance) || distance <= 0) return 0;

  const metersPerMinute = (speedKilometersPerHour * 1000) / 60;
  return Math.max(1, Math.ceil(distance / metersPerMinute));
}

function updateDistanceMeasureUi() {
  const pointCount = distanceMeasurePoints.length;
  const totalDistance = getDistanceMeasureTotal();
  const guide = document.getElementById("distanceMeasureGuide");

  document.getElementById("distanceMeasurePointCount").textContent = `${pointCount.toLocaleString()}개 지점`;
  document.getElementById("distanceMeasureTotal").textContent = pointCount >= 2
    ? formatMeasuredDistance(totalDistance)
    : "—";
  document.getElementById("distanceMeasureUndo").disabled = (
    (!distanceMeasureActive && !distanceMeasureFinished) || pointCount === 0
  );
  document.getElementById("distanceMeasureFinish").disabled = (
    !distanceMeasureActive || pointCount < 2
  );

  if (distanceMeasureFinished) {
    guide.textContent = "측정이 완료되었습니다. 초기화하거나 거리 버튼을 눌러 종료할 수 있습니다.";
  } else if (pointCount === 0) {
    guide.textContent = "지도를 클릭해 시작점을 지정하세요.";
  } else if (pointCount === 1) {
    guide.textContent = "다음 지점을 클릭하면 구간 거리가 표시됩니다.";
  } else {
    guide.textContent = "지점을 더 추가하거나 완료 버튼을 눌러 측정을 마치세요.";
  }
}

function clearDistanceMeasurePreview() {
  if (!distanceMeasurePreview) return;

  distanceMeasurePreview.setMap(null);
  distanceMeasurePreview = null;
}

function clearDistanceMeasureResultOverlays() {
  if (distanceMeasurePolyline) {
    distanceMeasurePolyline.setMap(null);
    distanceMeasurePolyline = null;
  }

  distanceMeasurePointMarkers.forEach(marker => marker.setMap(null));
  distanceMeasurePointMarkers = [];

  distanceMeasureSegmentLabels.forEach(marker => marker.setMap(null));
  distanceMeasureSegmentLabels = [];

  if (distanceMeasureTotalLabel) {
    distanceMeasureTotalLabel.setMap(null);
    distanceMeasureTotalLabel = null;
  }
}

function clearDistanceMeasureOverlays() {
  clearDistanceMeasurePreview();
  clearDistanceMeasureResultOverlays();
}

function formatMeasuredDistance(distance) {
  if (!Number.isFinite(distance) || distance < 0) return "—";

  if (distance < 1000) {
    return `${Math.round(distance).toLocaleString()}m`;
  }

  const digits = distance < 10000 ? 2 : 1;
  return `${Number((distance / 1000).toFixed(digits)).toLocaleString()}km`;
}

/* ===========================
   Property Detail Panel
=========================== */

function showPropertyListView({ restoreScroll = false } = {}) {
  const sidebar = document.getElementById("propertySidebar");
  const listView = document.getElementById("propertyListView");
  const detailView = document.getElementById("propertyDetailView");
  const detailWasOpen = !detailView.hidden;

  selectedProperty = null;
  listView.hidden = false;
  detailView.hidden = true;
  sidebar.classList.remove("is-detail-open");

  if (restoreScroll && detailWasOpen) {
    requestAnimationFrame(() => {
      sidebar.scrollTop = propertyListScrollTop;
    });
  } else if (detailWasOpen) {
    sidebar.scrollTop = 0;
  }
}

function openPropertyDetail(item) {
  const sidebar = document.getElementById("propertySidebar");
  const listView = document.getElementById("propertyListView");
  const detailView = document.getElementById("propertyDetailView");

  propertyListScrollTop = sidebar.scrollTop;
  selectedProperty = item;
  listView.hidden = true;
  detailView.hidden = false;
  sidebar.classList.add("is-detail-open");
  renderPropertyDetail(item);
  sidebar.scrollTop = 0;

  if (isMobileMapLayout()) {
    setMobileMapView("detail");
  }
}

function renderPropertyDetail(item) {
  const content = document.getElementById("propertyDetailContent");

  if (!content || !item) return;

  syncFavoriteToggle(item);

  const sameComplexItems = getSameComplexProperties(item);
  const samePyeongItems = sameComplexItems.filter(candidate => (
    getRoundedPyeong(candidate.exclusive_area) === getRoundedPyeong(item.exclusive_area)
  ));
  const complexSaleItems = sameComplexItems.filter(candidate => candidate.sale_price > 0);
  const samePyeongSaleItems = samePyeongItems.filter(candidate => candidate.sale_price > 0);
  const complexAveragePrice = getAverageValue(complexSaleItems, "sale_price");
  const samePyeongAveragePrice = getAverageValue(samePyeongSaleItems, "sale_price");
  const recentThreeMonthItems = getRecentTransactions(samePyeongSaleItems, 3);
  const recentThreeMonthAveragePrice = getAverageValue(recentThreeMonthItems, "sale_price");
  const latestTransaction = getLatestTransaction(samePyeongSaleItems);
  const availableAreas = getComplexAreaSummary(sameComplexItems);
  const proximity = getPropertyProximity(item);
  const propertyName = item.title || item.building_name || "매물";
  const detailArea = formatDetailArea(item.exclusive_area);

  content.innerHTML = `
    <div class="property-detail-media" aria-label="매물 이미지 영역">
      ${renderPropertyMediaSlot(item, propertyName)}
    </div>

    <div class="property-detail-summary">
      <div class="property-detail-kicker">
        ${escapeHtml([item.property_type, detailArea].filter(Boolean).join(" · "))}
      </div>
      <h2>${escapeHtml(propertyName)}</h2>
      <div class="property-detail-price">
        ${renderDetailText(formatOptionalPrice(item.sale_price))}
      </div>
      <p class="property-detail-address">${escapeHtml(item.address || "")}</p>
    </div>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("기본정보")}
      <dl class="property-detail-field-grid">
        ${renderDetailField("매물번호", item.id)}
        ${renderDetailField("매물 유형", item.property_type)}
        ${renderDetailField("전용면적", detailArea)}
        ${renderDetailField("층수", formatOptionalUnit(item.floor, "층"))}
        ${renderDetailField("매매가", formatOptionalPrice(item.sale_price))}
        ${renderDetailField("관리비", formatOptionalPrice(item.maintenance_fee))}
        ${renderDetailField("보증금", formatOptionalPrice(item.deposit))}
        ${renderDetailField("월세", formatOptionalPrice(item.monthly_rent))}
        ${renderDetailField("준공연도", formatOptionalUnit(item.built_year, "년"))}
        ${renderDetailField("등록일", item.created_at)}
        ${renderDetailField("주소", item.address, true)}
        ${renderDetailField("지번", item.lot_number, true)}
      </dl>
    </section>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("가격 정보", "최근 12개월 실거래 기준")}
      <div class="property-price-grid">
        ${renderPriceCard(
          `같은 단지 평균 (${complexSaleItems.length.toLocaleString()}건)`,
          formatOptionalPrice(complexAveragePrice),
          true
        )}
        ${renderPriceCard(
          `같은 평수 평균 (${samePyeongSaleItems.length.toLocaleString()}건)`,
          formatOptionalPrice(samePyeongAveragePrice)
        )}
        ${renderPriceCard(
          `최근 3개월 평균 (${recentThreeMonthItems.length.toLocaleString()}건)`,
          formatOptionalPrice(recentThreeMonthAveragePrice)
        )}
        ${renderPriceCard(
          latestTransaction
            ? `최근 실거래가 (${formatContractDate(latestTransaction.contract_date)})`
            : "최근 실거래가",
          formatOptionalPrice(latestTransaction?.sale_price)
        )}
      </div>
    </section>

    <section class="property-detail-section property-price-history-section"
             data-price-history-property-id="${escapeHtml(item.id)}">
      <div class="property-price-history-heading">
        <div>
          <h3>매매가 평균 추이</h3>
          <p>같은 단지 · 같은 평형 월별 실거래</p>
        </div>
        <div class="property-price-history-period" aria-label="조회 기간">
          <button type="button" data-price-history-years="1">1년</button>
          <button type="button" class="is-active" data-price-history-years="3">3년</button>
        </div>
      </div>
      <div class="property-price-history-legend" aria-hidden="true">
        <span class="price"><i></i>매매가</span>
        <span class="volume"><i></i>거래량</span>
      </div>
      <div class="property-price-history-chart" role="img" aria-label="매매가 평균과 거래량 추이">
        <p class="property-price-history-status">가격 추이를 불러오고 있어요.</p>
      </div>
    </section>

    <section class="property-detail-section property-floorplan-section">
      ${renderDetailSectionHeading("평면도")}
      ${renderFloorplanMediaSlot(item)}
    </section>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("단지정보")}
      <dl class="property-detail-field-grid">
        ${renderDetailField("단지명", item.building_name, true)}
        ${renderDetailField("준공연도", formatOptionalUnit(item.built_year, "년"))}
        ${renderDetailField("등록 매물", sameComplexItems.length ? `${sameComplexItems.length.toLocaleString()}개` : "")}
        ${renderDetailField("보유 면적", availableAreas, true)}
        ${renderDetailField("총 세대수", "")}
        ${renderDetailField("총 동수", "")}
        ${renderDetailField("시공사", "")}
        ${renderDetailField("난방 방식", "")}
        ${renderDetailField("세대당 주차", "")}
        ${renderDetailField("용적률 / 건폐율", "")}
        ${renderDetailField("단지 주소", item.address, true)}
      </dl>
    </section>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("주변시설", "직선거리 기준")}
      <div class="property-facility-list">
        ${renderFacilityItem("교통", "교통", "transport", proximity.facilities["교통"])}
        ${renderFacilityItem("의료", "의료", "medical", proximity.facilities["의료"])}
        ${renderFacilityItem("공공", "공공기관", "public", proximity.facilities["공공기관"])}
        ${renderFacilityItem("중개", "중개", "brokerage", proximity.facilities["중개"])}
      </div>
    </section>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("주변 학교", "거리 기준 · 배정학군 정보 아님")}
      <div class="property-school-list">
        ${renderSchoolItem("초", "초등학교", proximity.schools.elementary)}
        ${renderSchoolItem("중", "중학교", proximity.schools.middle)}
        ${renderSchoolItem("고", "고등학교", proximity.schools.high)}
      </div>
    </section>

    <section class="property-detail-section">
      ${renderDetailSectionHeading("매물 설명")}
      <div class="property-detail-description-slot">${escapeHtml(item.description || "")}</div>
    </section>
  `;

  initializePropertyPriceHistory(item.id);
}

function renderPropertyMediaSlot(item, propertyName) {
  const imagePath = getApartmentImagePath(item);

  return `
    <div class="property-media-slot is-main">
      <img src="${escapeHtml(imagePath)}"
           alt="${escapeHtml(propertyName)} 대표 사진"
           decoding="async">
      <span class="property-image-watermark" aria-hidden="true">SAMPLE</span>
    </div>
  `;
}

function renderFloorplanMediaSlot(item) {
  const imagePath = getFloorplanImagePath(item);
  const category = classifyFloorplanCategory(item?.exclusive_area);

  if (!imagePath) {
    return `
      <div class="property-floorplan-slot" role="img" aria-label="평면도 이미지 없음">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 4h16v16H4zM10 4v7H4m16 2h-6v7m0-9h3V7"/>
        </svg>
        <span>평면도 이미지가 없습니다</span>
      </div>
    `;
  }

  return `
    <div class="property-floorplan-slot">
      <img src="${escapeHtml(imagePath)}"
           alt="${escapeHtml(category)} 평면도"
           loading="lazy"
           decoding="async">
      <span class="property-image-watermark is-floorplan" aria-hidden="true">SAMPLE</span>
    </div>
  `;
}

function renderDetailSectionHeading(title, note = "") {
  return `
    <div class="property-detail-section-heading">
      <h3>${escapeHtml(title)}</h3>
      ${note ? `<span>${escapeHtml(note)}</span>` : ""}
    </div>
  `;
}

function renderDetailField(label, value, wide = false) {
  return `
    <div class="property-detail-field${wide ? " is-wide" : ""}">
      <dt>${escapeHtml(label)}</dt>
      <dd>${renderDetailText(value)}</dd>
    </div>
  `;
}

function renderPriceCard(label, value, primary = false) {
  return `
    <div class="property-price-card${primary ? " is-primary" : ""}">
      <span>${escapeHtml(label)}</span>
      <strong>${renderDetailText(value)}</strong>
    </div>
  `;
}

function initializePropertyPriceHistory(propertyId) {
  const section = document.querySelector("[data-price-history-property-id]");
  if (!section || String(section.dataset.priceHistoryPropertyId) !== String(propertyId)) return;

  section.querySelectorAll("[data-price-history-years]").forEach(button => {
    button.addEventListener("click", () => {
      const years = Number(button.dataset.priceHistoryYears);
      section.querySelectorAll("[data-price-history-years]").forEach(candidate => {
        candidate.classList.toggle("is-active", candidate === button);
      });
      loadPropertyPriceHistory(propertyId, years);
    });
  });

  loadPropertyPriceHistory(propertyId, 3);
}

async function loadPropertyPriceHistory(propertyId, years) {
  const cacheKey = `${propertyId}:${years}`;
  const chart = getActivePriceHistoryChart(propertyId);
  if (!chart) return;

  chart.innerHTML = '<p class="property-price-history-status">가격 추이를 불러오고 있어요.</p>';

  try {
    let rows = propertyPriceHistoryCache.get(cacheKey);
    if (!rows) {
      const response = await fetch(
        `/api/map/properties/${encodeURIComponent(propertyId)}/price-history?years=${years}`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      rows = await response.json();
      propertyPriceHistoryCache.set(cacheKey, rows);
    }

    const activeChart = getActivePriceHistoryChart(propertyId);
    if (!activeChart) return;
    renderPropertyPriceHistoryChart(activeChart, rows, years);
  } catch (error) {
    console.error("매매가 추이를 불러오지 못했습니다:", error);
    const activeChart = getActivePriceHistoryChart(propertyId);
    if (activeChart) {
      activeChart.innerHTML = '<p class="property-price-history-status is-error">가격 추이를 불러오지 못했어요.</p>';
    }
  }
}

function getActivePriceHistoryChart(propertyId) {
  const section = document.querySelector("[data-price-history-property-id]");
  if (!section || String(section.dataset.priceHistoryPropertyId) !== String(propertyId)) return null;
  return section.querySelector(".property-price-history-chart");
}

function renderPropertyPriceHistoryChart(container, rows, years) {
  const series = buildMonthlyPriceHistory(rows, years);
  const tradedMonths = series.filter(item => item.averagePrice > 0);

  if (!tradedMonths.length) {
    container.innerHTML = '<p class="property-price-history-status">해당 기간의 실거래 내역이 없어요.</p>';
    return;
  }

  const width = 380;
  const height = 240;
  const left = 48;
  const right = 12;
  const top = 12;
  const priceBottom = 158;
  const volumeTop = 174;
  const volumeBottom = 205;
  const plotWidth = width - left - right;
  const prices = tradedMonths.map(item => item.averagePrice);
  const rawMin = Math.min(...prices);
  const rawMax = Math.max(...prices);
  const padding = Math.max((rawMax - rawMin) * 0.12, rawMax * 0.03, 1);
  const minPrice = Math.max(0, rawMin - padding);
  const maxPrice = rawMax + padding;
  const maxTrades = Math.max(...series.map(item => item.tradeCount), 1);
  const x = index => left + (series.length === 1 ? plotWidth / 2 : index * plotWidth / (series.length - 1));
  const y = price => top + (maxPrice - price) / (maxPrice - minPrice || 1) * (priceBottom - top);
  const grid = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const gridY = top + ratio * (priceBottom - top);
    const value = maxPrice - ratio * (maxPrice - minPrice);
    return `<line x1="${left}" y1="${gridY}" x2="${width - right}" y2="${gridY}"/>`
      + `<text x="${left - 7}" y="${gridY + 4}" text-anchor="end">${escapeHtml(formatChartPrice(value))}</text>`;
  }).join("");
  const linePoints = series
    .map((item, index) => item.averagePrice > 0 ? `${x(index)},${y(item.averagePrice)}` : null)
    .filter(Boolean)
    .join(" ");
  const bars = series.map((item, index) => {
    if (!item.tradeCount) return "";
    const barHeight = Math.max(3, item.tradeCount / maxTrades * (volumeBottom - volumeTop));
    return `<rect x="${x(index) - 2}" y="${volumeBottom - barHeight}" width="4" height="${barHeight}" rx="2">`
      + `<title>${escapeHtml(formatHistoryTooltip(item))}</title></rect>`;
  }).join("");
  const points = series.map((item, index) => {
    if (!item.averagePrice) return "";
    return `<circle cx="${x(index)}" cy="${y(item.averagePrice)}" r="4">`
      + `<title>${escapeHtml(formatHistoryTooltip(item))}</title></circle>`;
  }).join("");
  const tickIndexes = [...new Set([0, ...Array.from({ length: 3 }, (_, index) => (
    Math.round((index + 1) * (series.length - 1) / 4)
  )), series.length - 1])];
  const labels = tickIndexes.map(index => (
    `<text x="${x(index)}" y="228" text-anchor="middle">${escapeHtml(formatHistoryMonth(series[index].month))}</text>`
  )).join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <g class="property-price-history-grid">${grid}</g>
      <text class="property-price-history-volume-label" x="${left - 7}" y="${volumeTop + 5}" text-anchor="end">거래량</text>
      <g class="property-price-history-bars">${bars}</g>
      <polyline class="property-price-history-line" points="${linePoints}"/>
      <g class="property-price-history-points">${points}</g>
      <g class="property-price-history-labels">${labels}</g>
    </svg>
  `;
}

function buildMonthlyPriceHistory(rows, years) {
  const byMonth = new Map((Array.isArray(rows) ? rows : []).map(row => [
    String(row.month || ""),
    {
      averagePrice: Number(row.average_price || 0),
      tradeCount: Number(row.trade_count || 0)
    }
  ]));
  const monthCount = years * 12;
  const current = new Date();
  const start = new Date(current.getFullYear(), current.getMonth() - monthCount + 1, 1);

  return Array.from({ length: monthCount }, (_, index) => {
    const date = new Date(start.getFullYear(), start.getMonth() + index, 1);
    const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    const value = byMonth.get(month) || {};
    return { month, averagePrice: value.averagePrice || 0, tradeCount: value.tradeCount || 0 };
  });
}

function formatHistoryTooltip(item) {
  return `${formatHistoryMonth(item.month)}  평균 ${formatOptionalPrice(item.averagePrice) || "-"}  거래 ${item.tradeCount.toLocaleString()}건`;
}

function formatHistoryMonth(month) {
  const [year, value] = String(month).split("-");
  return `${String(year).slice(-2)}.${value}`;
}

function formatChartPrice(price) {
  const eok = Number(price) / 100000000;
  return `${Number(eok.toFixed(eok >= 10 ? 0 : 1))}억`;
}

function renderDetailText(value) {
  const normalized = String(value ?? "").trim();

  return normalized && normalized !== "-"
    ? escapeHtml(normalized)
    : '<span class="property-detail-empty" aria-label="정보 없음"></span>';
}

function renderFacilityItem(shortLabel, category, className, nearest) {
  const name = nearest?.item?.name || "";
  const distance = nearest ? formatDistance(nearest.distance) : "";

  return `
    <div class="property-facility-item">
      <span class="property-facility-icon ${className}">${escapeHtml(shortLabel)}</span>
      <div class="property-facility-copy">
        <span>${escapeHtml(category)}</span>
        ${name ? `<strong>${escapeHtml(name)}</strong>` : renderDetailText("")}
      </div>
      <span class="property-facility-distance">${distance ? escapeHtml(distance) : renderDetailText("")}</span>
    </div>
  `;
}

function renderSchoolItem(shortLabel, label, nearest) {
  const name = nearest?.item?.name || "";
  const distance = nearest ? formatDistance(nearest.distance) : "";

  return `
    <div class="property-school-item">
      <span class="property-school-icon">${escapeHtml(shortLabel)}</span>
      <div class="property-school-copy">
        <span>${escapeHtml(label)}</span>
        ${name ? `<strong>${escapeHtml(name)}</strong>` : renderDetailText("")}
      </div>
      <span class="property-school-distance">${distance ? escapeHtml(distance) : renderDetailText("")}</span>
    </div>
  `;
}

function getSameComplexProperties(item) {
  const buildingName = String(item.building_name || "").trim();
  const address = String(item.address || "").trim();

  return allProperties.filter(candidate => {
    const candidateBuildingName = String(candidate.building_name || "").trim();
    const candidateAddress = String(candidate.address || "").trim();

    if (buildingName && address) {
      return candidateBuildingName === buildingName && candidateAddress === address;
    }

    if (buildingName) {
      return candidateBuildingName === buildingName;
    }

    return address && candidateAddress === address;
  });
}

function getComplexAreaSummary(items) {
  const areas = [...new Set(
    items
      .map(item => Number(item.exclusive_area))
      .filter(area => Number.isFinite(area) && area > 0)
      .map(area => Number(area.toFixed(4)))
  )].sort((a, b) => a - b);

  if (!areas.length) return "";

  const visibleAreas = areas.slice(0, 6).map(area => `${area}㎡`);
  const remaining = areas.length - visibleAreas.length;

  return remaining > 0
    ? `${visibleAreas.join(" · ")} 외 ${remaining}개`
    : visibleAreas.join(" · ");
}

function getAverageValue(items, key) {
  const values = items
    .map(item => Number(item[key]))
    .filter(value => Number.isFinite(value) && value > 0);

  if (!values.length) return 0;

  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function getRecentTransactions(items, months) {
  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setMonth(cutoff.getMonth() - months);

  return items.filter(item => {
    const contractDate = parseContractDate(item.contract_date);
    return contractDate && contractDate >= cutoff;
  });
}

function getLatestTransaction(items) {
  return items.reduce((latest, item) => {
    const itemDate = parseContractDate(item.contract_date);
    if (!itemDate) return latest;

    const latestDate = parseContractDate(latest?.contract_date);
    return !latestDate || itemDate > latestDate ? item : latest;
  }, null);
}

function parseContractDate(value) {
  const normalized = String(value ?? "").trim();
  if (!normalized) return null;

  const date = new Date(`${normalized.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatContractDate(value) {
  const date = parseContractDate(value);
  if (!date) return "";

  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}`;
}

function getRoundedPyeong(area) {
  const numericArea = Number(area);

  return Number.isFinite(numericArea) && numericArea > 0
    ? Math.round(numericArea / 3.3058)
    : null;
}

function formatDetailArea(area) {
  const numericArea = Number(area);
  const pyeong = getRoundedPyeong(numericArea);

  if (!Number.isFinite(numericArea) || numericArea <= 0 || pyeong === null) {
    return "";
  }

  return `${numericArea}㎡ (${pyeong}평)`;
}

function formatOptionalPrice(value) {
  const numericValue = Number(value);

  return Number.isFinite(numericValue) && numericValue > 0
    ? formatPrice(numericValue)
    : "";
}

function formatOptionalUnit(value, unit) {
  const normalized = String(value ?? "").trim();

  return normalized ? `${normalized}${unit}` : "";
}

function getPropertyProximity(item) {
  const facilityCategories = new Set(["교통", "의료", "공공기관", "중개"]);
  const result = {
    facilities: {
      "교통": null,
      "의료": null,
      "공공기관": null,
      "중개": null
    },
    schools: {
      elementary: null,
      middle: null,
      high: null
    }
  };
  const latitude = Number(item.latitude);
  const longitude = Number(item.longitude);

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return result;
  }

  allPois.forEach(poi => {
    const facilityCategory = facilityCategories.has(poi.category)
      ? poi.category
      : null;
    const schoolLevel = poi.category === "교육"
      ? getSchoolLevel(poi)
      : null;

    if (!facilityCategory && !schoolLevel) return;

    const distance = calculateDistanceMeters(
      latitude,
      longitude,
      Number(poi.latitude),
      Number(poi.longitude)
    );

    if (!Number.isFinite(distance)) return;

    if (
      facilityCategory &&
      (!result.facilities[facilityCategory] || distance < result.facilities[facilityCategory].distance)
    ) {
      result.facilities[facilityCategory] = { item: poi, distance };
    }

    if (
      schoolLevel &&
      (!result.schools[schoolLevel] || distance < result.schools[schoolLevel].distance)
    ) {
      result.schools[schoolLevel] = { item: poi, distance };
    }
  });

  return result;
}

function getSchoolLevel(poi) {
  const schoolText = `${poi.subcategory || ""} ${poi.name || ""}`;

  if (schoolText.includes("초등학교")) return "elementary";
  if (schoolText.includes("중학교")) return "middle";
  if (schoolText.includes("고등학교")) return "high";

  return null;
}

function calculateDistanceMeters(lat1, lng1, lat2, lng2) {
  if (![lat1, lng1, lat2, lng2].every(Number.isFinite)) return NaN;

  const earthRadius = 6371000;
  const toRadians = value => value * Math.PI / 180;
  const latitudeDelta = toRadians(lat2 - lat1);
  const longitudeDelta = toRadians(lng2 - lng1);
  const startLatitude = toRadians(lat1);
  const endLatitude = toRadians(lat2);
  const haversine = (
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(startLatitude) * Math.cos(endLatitude) *
    Math.sin(longitudeDelta / 2) ** 2
  );

  return 2 * earthRadius * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function formatDistance(distance) {
  if (!Number.isFinite(distance)) return "";

  if (distance < 1000) {
    return `${Math.max(1, Math.round(distance / 10) * 10).toLocaleString()}m`;
  }

  return `${Number((distance / 1000).toFixed(1))}km`;
}

/* ===========================
   Property Info Popup
=========================== */

function openInfoWindow(item, marker) {
  closePoiInfoPopup();

  const html = `
    <div style="
      width:270px;
      transform:translate(-50%, calc(-100% - ${PROPERTY_MARKER_HEIGHT / 2}px));
      background:white;
      border-radius:16px;
      box-shadow:0 4px 18px rgba(0,0,0,0.25);
      overflow:hidden;
      font-family:Arial, 'Noto Sans KR', sans-serif;
      pointer-events:none;
    ">
      <div style="padding:13px;">
        <div style="font-weight:bold; font-size:15px; margin-bottom:6px;">
          ${item.title || item.building_name || "매물"}
        </div>

        <div style="color:#1E88FF; font-weight:bold; font-size:17px; margin-bottom:6px;">
          ${formatPrice(item.sale_price)}
        </div>

        <div style="font-size:13px; color:#555; line-height:1.5;">
          ${item.property_type || ""} · ${item.exclusive_area || "-"}㎡ · ${item.floor || "-"}층<br>
          ${item.building_name || ""}<br>
          ${item.address || ""}
        </div>
      </div>
    </div>
  `;

  closeInfoWindow();

  infoMarker = new naver.maps.Marker({
    position: marker.getPosition(),
    map,
    zIndex: 1000,
    clickable: false,
    icon: {
      content: html,
      anchor: new naver.maps.Point(0, 0)
    }
  });
}

function showPropertyInfo(item) {
  const key = `property-${item.id}`;
  let marker = markerMap.get(key);

  if (!marker) {
    marker = createPropertyMarker(item);
    markerMap.set(key, marker);
  }

  openInfoWindow(item, marker);
}

function closeInfoWindow() {
  if (!infoMarker) return;

  infoMarker.setMap(null);
  infoMarker = null;
}

function openPoiInfoPopup(items, position) {
  if (!items.length) return;

  closeInfoWindow();
  activePoiPopupItems = items;
  activePoiPopupIndex = 0;
  activePoiPopupPosition = position;
  renderPoiInfoPopup();
}

function renderPoiInfoPopup() {
  const item = activePoiPopupItems[activePoiPopupIndex];

  if (!item || !activePoiPopupPosition) return;

  if (poiInfoMarker) {
    poiInfoMarker.setMap(null);
  }

  const config = POI_CATEGORY_CONFIG[item.category] || {
    label: item.category || "주변 시설",
    color: "#52627a"
  };
  const address = item.road_address || [
    item.province,
    item.city,
    item.town
  ].filter(Boolean).join(" ");
  const phoneNumber = String(item.phone_number || "").trim();
  const phone = phoneNumber
    ? `
        <div class="poi-info-phone">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6.6 3.5 9 8.3 6.9 10c1.2 2.7 3.4 4.9 6.1 6.1l1.7-2.1 4.8 2.4-.7 3.1c-.2.8-.9 1.3-1.7 1.3C9.5 20.3 3.7 14.5 3.2 6.9c0-.8.5-1.5 1.3-1.7l2.1-.7Z"/>
          </svg>
          ${escapeHtml(phoneNumber)}
        </div>
      `
    : "";
  const brokerageInfo = item.category === "중개"
    ? `
        <div class="poi-info-brokerage">
          <div class="poi-info-brokerage-row">
            <span>영업상태</span>
            <strong class="poi-info-status${item.business_status === "영업중" ? " is-open" : ""}">
              ${escapeHtml(item.business_status || "정보 없음")}
            </strong>
          </div>
          <div class="poi-info-brokerage-row">
            <span>중개업자</span>
            <strong>${escapeHtml(item.representative_name || "정보 없음")}</strong>
          </div>
          <div class="poi-info-brokerage-row is-wide">
            <span>등록번호</span>
            <strong>${escapeHtml(item.registration_number || "정보 없음")}</strong>
          </div>
        </div>
      `
    : "";
  const rawBusRoutes = Array.isArray(item.bus_routes)
    ? item.bus_routes.filter(Boolean)
    : [];
  const busRoutes = rawBusRoutes.length <= MAX_BUS_ROUTES_PER_STOP
    ? rawBusRoutes
    : [];
  const busRouteInfo = busRoutes.length
    ? `
        <div class="poi-info-routes">
          <div class="poi-info-routes-label">
            운행 버스 ${busRoutes.length.toLocaleString()}개
          </div>
          <div class="poi-info-route-list">
            ${busRoutes.map(route => (
              `<span class="poi-info-route">${escapeHtml(route)}</span>`
            )).join("")}
          </div>
        </div>
      `
    : "";
  const hasMultipleItems = activePoiPopupItems.length > 1;
  const navigation = hasMultipleItems
    ? `
        <div class="poi-info-nav">
          <button type="button"
                  aria-label="이전 시설"
                  onmousedown="event.stopPropagation()"
                  onclick="event.stopPropagation(); changePoiPopupPage(-1)">‹</button>
          <span class="poi-info-page">
            ${activePoiPopupIndex + 1} / ${activePoiPopupItems.length}
          </span>
          <button type="button"
                  aria-label="다음 시설"
                  onmousedown="event.stopPropagation()"
                  onclick="event.stopPropagation(); changePoiPopupPage(1)">›</button>
        </div>
      `
    : "";
  const html = `
    <div class="poi-info-popup"
         style="--poi-color:${config.color};--poi-popup-offset:${config.popupOffset || 22}px">
      <div class="poi-info-accent"></div>
      <div class="poi-info-body">
        <div class="poi-info-category">
          ${escapeHtml(config.label)} · ${escapeHtml(item.subcategory || "시설")}
        </div>
        <div class="poi-info-name">${escapeHtml(item.name || "이름 없는 시설")}</div>
        <div class="poi-info-address">${escapeHtml(address || "주소 정보 없음")}</div>
        ${brokerageInfo}
        ${phone}
        ${busRouteInfo}
        ${navigation}
      </div>
    </div>
  `;

  poiInfoMarker = new naver.maps.Marker({
    position: activePoiPopupPosition,
    map,
    zIndex: 1100,
    icon: {
      content: html,
      anchor: new naver.maps.Point(0, 0)
    }
  });
}

function changePoiPopupPage(direction) {
  const itemCount = activePoiPopupItems.length;

  if (itemCount < 2) return;

  activePoiPopupIndex = (
    activePoiPopupIndex + direction + itemCount
  ) % itemCount;

  renderPoiInfoPopup();
}

function closePoiInfoPopup() {
  if (poiInfoMarker) {
    poiInfoMarker.setMap(null);
    poiInfoMarker = null;
  }

  activePoiPopupItems = [];
  activePoiPopupIndex = 0;
  activePoiPopupPosition = null;
}

function closeAllInfoPopups() {
  closeInfoWindow();
  closePoiInfoPopup();
}

/* ===========================
   Helpers
=========================== */

function getAppZoomStage(zoom) {
  return zoom - APP_START_ZOOM + 1;
}

function moveMapTo(position, zoom) {
  map.morph(position, zoom, {
    duration: 500,
    easing: "easeOutCubic"
  });
}

function getBbox(bounds) {
  const sw = bounds.getSW();
  const ne = bounds.getNE();

  return [
    sw.lng(),
    sw.lat(),
    ne.lng(),
    ne.lat()
  ];
}

function getVisiblePropertiesByIndex(bbox) {
  return propertyIndex
    .getClusters(bbox, APP_MAX_ZOOM + 1)
    .map(feature => feature.properties.item)
    .filter(Boolean);
}

function removeUnusedMarkers(nextKeys) {
  for (const [key, marker] of markerMap.entries()) {
    if (!nextKeys.has(key)) {
      marker.setMap(null);
      markerMap.delete(key);
    }
  }
}

function removeUnusedPoiMarkers(nextKeys) {
  for (const [key, marker] of poiMarkerMap.entries()) {
    if (!nextKeys.has(key)) {
      marker.setMap(null);
      poiMarkerMap.delete(key);
    }
  }
}

function clearPoiMarkers() {
  for (const marker of poiMarkerMap.values()) {
    marker.setMap(null);
  }

  poiMarkerMap.clear();
}

function fitMapToData(items) {
  if (!items.length) return;

  const bounds = new naver.maps.LatLngBounds();

  items.forEach(item => {
    bounds.extend(new naver.maps.LatLng(item.latitude, item.longitude));
  });

  map.fitBounds(bounds);
}

function getRegionName(district, level) {
  if (!district) return "기타";

  const parts = district.trim().split(/\s+/);

  if (level === "sido") {
  const sido = parts[0];

  if (sido === "서울특별시") return "서울시";
  if (sido === "경기도") return "경기도";

  return sido;
  }

  if (level === "sigungu") {
    const sido = parts[0];
    const si = parts.find(p => p.endsWith("시"));
    const gu = parts.find(p => p.endsWith("구"));

    if (sido === "서울특별시") {
      return `서울시 ${gu || ""}`.trim();
    }

    if (si && gu) return `${si} ${gu}`;
    if (si) return si;
    if (gu) return gu;

    return district;
  }

  if (level === "dong") {
    const dong = parts.find(p => p.endsWith("동"));
    if (dong) return dong;

    const eup = parts.find(p => p.endsWith("읍"));
    if (eup) return eup;

    const myeon = parts.find(p => p.endsWith("면"));
    if (myeon) return myeon;

    return parts[parts.length - 1];
  }

  return district;
}

function formatPrice(price) {
  if (!price || isNaN(price)) return "-";

  const eok = Math.floor(price / 100000000);
  const man = Math.floor((price % 100000000) / 10000);

  if (eok > 0 && man > 0) {
    return `${eok}억 ${man.toLocaleString()}만`;
  }

  if (eok > 0) {
    return `${eok}억`;
  }

  return `${man.toLocaleString()}만`;
}

function formatPriceToEok(price) {
  if (!price || isNaN(price)) return "-";

  const eok = price / 100000000;

  if (eok >= 10) {
    return `${Number(eok.toFixed(1)).toString()}억`;
  }

  return `${Number(eok.toFixed(1)).toString()}억`;
}

function formatAreaPyeong(area) {
  if (!area || isNaN(area)) return "-평";

  const pyeong = area / 3.3058;
  return `${Math.round(pyeong)}평`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
