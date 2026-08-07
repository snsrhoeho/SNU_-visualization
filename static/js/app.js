const state = { data: null, area: "all", housing: "all", rate: 0.05, scope: "siheung", tableFiltered: false, naverMap: null, mapOverlays: [], boundariesLoaded: false, boundaryPositions: {}, boundaryOverlays: [], boundaryInteractionBound: false, boundaryFrameId: null };
const $ = (id) => document.getElementById(id);
const won = (value) => `${Math.round(value).toLocaleString("ko-KR")}만원`;
const convertedRent = (deposit, monthly) => monthly + (deposit * state.rate / 12);

// 행정동 경계 위에 동별 지표 마커를 놓기 위한 대표 좌표다.
const AREA_LOCATIONS = {
  baegot: [37.3676, 126.7299],
  jeongwang1: [37.3507, 126.7425],
  jeongwang2: [37.3574, 126.7352],
  daeya: [37.4433, 126.7892],
  sincheon: [37.4383, 126.7871],
  eunhaeng: [37.4402, 126.8032],
};

function privateRent(area) { return convertedRent(area.private_deposit, area.private_monthly); }
function hasPublicData(area) { return Number.isFinite(area.public_deposit) && Number.isFinite(area.public_monthly); }
function publicRent(area) { return hasPublicData(area) ? convertedRent(area.public_deposit, area.public_monthly) : null; }
function activeAreas() { return state.area === "all" ? state.data.areas : state.data.areas.filter((area) => area.id === state.area); }
function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const i = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[i] : (sorted[i - 1] + sorted[i]) / 2;
}
function rentColor(value, min, max) {
  const t = max === min ? 0.5 : (value - min) / (max - min);
  const start = [202, 225, 224], end = [224, 79, 45];
  return `rgb(${start.map((v, i) => Math.round(v + (end[i] - v) * t)).join(",")})`;
}

function renderMetrics() {
  const areas = activeAreas();
  const privateMedian = median(areas.map(privateRent));
  const publicAreas = areas.filter(hasPublicData);
  const publicMedian = publicAreas.length ? median(publicAreas.map(publicRent)) : null;
  const units = publicAreas.reduce((sum, area) => sum + (area.supply_units || 0), 0);
  const records = areas.reduce((sum, area) => sum + (area.deals || 0) + (area.notices || 0), 0);
  $("private-rent").textContent = won(privateMedian);
  $("public-supply").textContent = publicAreas.length ? `${units.toLocaleString("ko-KR")}호` : "자료 없음";
  $("saving-rate").textContent = state.data.meta.data_mode === "partial_sources" ? "부분 자료" : `${Math.max(0, (1 - publicMedian / privateMedian) * 100).toFixed(1)}%`;
  $("record-count").textContent = `${records.toLocaleString("ko-KR")}건`;
}

function selectArea(id) {
  state.area = state.area === id ? "all" : id;
  $("area-filter").value = state.area;
  render();
}

function loadNaverMaps(keyId) {
  if (window.naver?.maps) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${encodeURIComponent(keyId)}`;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("네이버 지도 라이브러리를 불러오지 못했습니다."));
    document.head.appendChild(script);
  });
}

function mapPosition(area) {
  const coordinate = state.boundaryPositions[area.id] || AREA_LOCATIONS[area.id];
  return coordinate ? new naver.maps.LatLng(coordinate[0], coordinate[1]) : null;
}

function initializeNaverMap() {
  const capital = state.scope === "capital";
  state.naverMap = new naver.maps.Map("naver-map", {
    center: new naver.maps.LatLng(capital ? 37.55 : 37.3903, capital ? 126.95 : 126.7788),
    zoom: capital ? 8 : 11,
    minZoom: capital ? 7 : 10,
    zoomControl: false,
    mapDataControl: false,
    scaleControl: false,
  });
  document.querySelector(".map-canvas").classList.add("map-ready");
  $("map-footnote").textContent = `${capital ? "시·군·구" : "행정동"} 경계의 색상은 민간 환산월세, 진하기는 관측 거래 표본 수입니다. 마커를 눌러 지역을 강조하세요.`;
}

function boundaryStyle(area) {
  if (!area) return { fillColor: "#d9eeea", fillOpacity: 0.5, strokeColor: "#12958e", strokeWeight: 3, zIndex: 1 };
  const values = state.data.areas.map(privateRent);
  const deals = state.data.areas.map((item) => item.deals);
  const density = Math.max(...deals) === Math.min(...deals) ? 0.5 : (area.deals - Math.min(...deals)) / (Math.max(...deals) - Math.min(...deals));
  const selected = state.area === area.id;
  const color = rentColor(privateRent(area), Math.min(...values), Math.max(...values));
  return {
    fillColor: color,
    fillOpacity: Math.min(0.9, 0.5 + density * 0.3 + (selected ? 0.1 : 0)),
    strokeColor: selected ? "#102841" : "#8f3b28",
    strokeOpacity: Math.min(1, 0.72 + density * 0.28),
    strokeWeight: selected ? 5 : 2.5 + density * 1.5,
    zIndex: 1,
    clickable: true,
  };
}

function renderAdminBoundarySvg() {
  if (!state.naverMap || !state.boundariesLoaded) return;
  const map = $("area-map");
  const size = state.naverMap.getSize();
  const projection = state.naverMap.getProjection();
  map.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  map.setAttribute("width", String(size.width));
  map.setAttribute("height", String(size.height));
  map.innerHTML = state.boundaryOverlays.map(({ area, rings }) => {
    const style = boundaryStyle(area);
    const path = rings.map((ring) => ring.map(([lng, lat], index) => {
      const point = projection.fromCoordToOffset(new naver.maps.LatLng(lat, lng));
      return `${index ? "L" : "M"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
    }).join(" ") + " Z").join(" ");
    return `<path class="district ${state.area === area.id ? "selected" : ""}" data-area="${area.id}" d="${path}" fill="${style.fillColor}" fill-opacity="${style.fillOpacity}" stroke="${style.strokeColor}" stroke-opacity="${style.strokeOpacity}" stroke-width="${style.strokeWeight}"></path>`;
  }).join("");
  map.querySelectorAll(".district").forEach((node) => node.addEventListener("click", () => selectArea(node.dataset.area)));
}

function scheduleBoundaryRender() {
  if (!state.boundariesLoaded || state.boundaryFrameId !== null) return;
  state.boundaryFrameId = requestAnimationFrame(() => {
    state.boundaryFrameId = null;
    renderAdminBoundarySvg();
  });
}

async function loadAdminBoundaries() {
  const boundaryFile = state.scope === "capital" ? "capital_sigungu_boundaries.geojson" : "siheung_dong_boundaries.geojson";
  const response = await fetch(`/static/data/${boundaryFile}`);
  if (!response.ok) throw new Error("행정동 경계를 불러오지 못했습니다.");
  const geojson = await response.json();
  geojson.features.forEach((feature) => {
    const { id, center_lat: lat, center_lng: lng } = feature.properties;
    if (Number.isFinite(lat) && Number.isFinite(lng)) state.boundaryPositions[id] = [lat, lng];
  });
  state.boundaryOverlays = geojson.features.map((feature) => {
    const coordinates = feature.geometry.coordinates;
    const rings = feature.geometry.type === "MultiPolygon" ? coordinates.flat() : coordinates;
    return { area: state.data.areas.find((item) => item.id === feature.properties.id), rings };
  }).filter(({ area, rings }) => area && Array.isArray(rings));
  if (!state.boundaryOverlays.length) throw new Error("행정동 경계가 비어 있습니다.");
  if (!state.boundaryInteractionBound) {
    ["center_changed", "zoom_changed", "bounds_changed", "size_changed", "projection_changed", "idle"].forEach((eventName) => {
      naver.maps.Event.addListener(state.naverMap, eventName, scheduleBoundaryRender);
    });
    state.boundaryInteractionBound = true;
  }
  $("naver-map").dataset.boundaryCount = String(state.boundaryOverlays.length);
  state.boundariesLoaded = true;
}

function renderNaverMap() {
  state.mapOverlays.forEach(({ marker, circle }) => {
    marker.setMap(null);
    if (circle) circle.setMap(null);
  });
  state.mapOverlays = [];
  if (state.boundariesLoaded) renderAdminBoundarySvg();

  state.data.areas.forEach((area) => {
    const position = mapPosition(area);
    if (!position) return;
    const selected = state.area === area.id;
    const circle = state.boundariesLoaded ? null : new naver.maps.Circle({
      map: state.naverMap,
      center: position,
      radius: 300,
      fillColor: "#f16643",
      fillOpacity: selected ? 0.55 : 0.3,
      strokeColor: selected ? "#102841" : "#f16643",
      strokeWeight: selected ? 4 : 2,
      clickable: true,
    });
    const marker = new naver.maps.Marker({
      map: state.naverMap,
      position,
      zIndex: 10,
      title: `${area.name}: 민간 ${won(privateRent(area))}, 공공 공급 ${area.supply_units ?? "자료 미확보"}${area.supply_units === null ? "" : "호"}`,
      icon: {
        content: `<div class="map-pin ${selected ? "selected" : ""}">${area.name}<small>거래 ${area.deals}건 · 공급 ${area.supply_units ?? "미확보"}${area.supply_units === null ? "" : "호"}</small></div>`,
        size: new naver.maps.Size(110, 44),
        anchor: new naver.maps.Point(55, 22),
      },
    });
    const choose = () => selectArea(area.id);
    if (circle) naver.maps.Event.addListener(circle, "click", choose);
    naver.maps.Event.addListener(marker, "click", choose);
    state.mapOverlays.push({ marker, circle });
  });
  if (state.area !== "all") {
    const selectedArea = state.data.areas.find((area) => area.id === state.area);
    const position = selectedArea && mapPosition(selectedArea);
    if (position) state.naverMap.panTo(position);
  }
}

function renderMap() {
  if (state.naverMap && window.naver?.maps) {
    renderNaverMap();
    return;
  }
  const map = $("area-map");
  if (state.scope === "capital") {
    map.innerHTML = `<text class="map-label" x="50" y="44" text-anchor="middle">네이버 지도와 시·군·구 경계를 불러오는 중입니다.</text>`;
    return;
  }
  const values = state.data.areas.map(privateRent);
  const min = Math.min(...values), max = Math.max(...values);
  map.innerHTML = state.data.areas.map((area) => {
    const radius = 2.2 + Math.sqrt(area.supply_units) * 0.62;
    return `<g class="district-group" data-area="${area.id}" tabindex="0" role="button" aria-label="${area.name} 선택">
      <polygon class="district ${state.area === area.id ? "selected" : ""}" points="${area.polygon}" fill="${rentColor(privateRent(area), min, max)}"></polygon>
      <circle class="bubble" cx="${area.x}" cy="${area.y}" r="${radius}"></circle>
      <text class="map-label" x="${area.x}" y="${area.y - radius - 3}">${area.name}</text>
      <text class="map-label" x="${area.x}" y="${area.y + radius + 4}">${area.supply_units}호</text>
    </g>`;
  }).join("");
  map.querySelectorAll(".district-group").forEach((node) => {
    node.addEventListener("click", () => selectArea(node.dataset.area));
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectArea(node.dataset.area); }
    });
  });
}

function renderInsights() {
  const areas = activeAreas();
  const high = [...areas].sort((a, b) => privateRent(b) - privateRent(a))[0];
  const publicAreas = areas.filter(hasPublicData);
  const title = state.area === "all" ? `${state.scope === "capital" ? "수도권" : "시흥시"} 핵심 관찰` : `${areas[0].name} 관찰`;
  const first = `<div class="insight"><div class="insight-label">HIGH RENT</div><p><strong>${high.name}</strong>의 민간 환산월세는 <strong>${won(privateRent(high))}</strong>으로 선택 범위에서 가장 높습니다.</p></div>`;
  if (!publicAreas.length) {
    $("insight-panel").innerHTML = `<p class="eyebrow">READ THE PATTERN</p><h3>${title}</h3>${first}<div class="insight"><div class="insight-label">PUBLIC DATA</div><p>이 지역의 청년 공공임대 공식 공고 자료는 아직 수집하지 않았습니다. 공급 0호로 해석하지 않습니다.</p></div>`;
    return;
  }
  const low = [...publicAreas].sort((a, b) => a.supply_units - b.supply_units)[0];
  const gap = [...publicAreas].sort((a, b) => (privateRent(b) - publicRent(b)) - (privateRent(a) - publicRent(a)))[0];
  $("insight-panel").innerHTML = `<p class="eyebrow">READ THE PATTERN</p><h3>${title}</h3>${first}
    <div class="insight"><div class="insight-label">LOW SUPPLY</div><p><strong>${low.name}</strong>은 현재 확보한 공식 공고 기준 공급이 <strong>${low.supply_units}호</strong>입니다.</p></div>
    <div class="insight"><div class="insight-label">LARGEST GAP</div><p><strong>${gap.name}</strong>은 현재 확보한 공고 기준 민간과 공공 환산월세 차이가 <strong>${won(privateRent(gap) - publicRent(gap))}</strong>입니다.</p></div>`;
}

function renderTrend() {
  const trend = state.data.monthly_trend, width = 560, height = 245, left = 38, right = 14, top = 20, bottom = 33;
  const min = Math.floor(Math.min(...trend.map((d) => d.rent)) - 2), max = Math.ceil(Math.max(...trend.map((d) => d.rent)) + 2);
  const x = (i) => left + i * (width - left - right) / (trend.length - 1);
  const y = (v) => top + (max - v) * (height - top - bottom) / (max - min);
  const points = trend.map((d, i) => `${x(i)},${y(d.rent)}`).join(" ");
  const grids = Array.from({ length: 4 }, (_, i) => { const value = min + i * (max - min) / 3; return `<line class="grid-line" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text class="axis-label" x="1" y="${y(value) + 3}">${value.toFixed(0)}</text>`; }).join("");
  const labels = trend.map((d, i) => i % 2 === 0 ? `<text class="axis-label" x="${x(i)}" y="${height - 8}" text-anchor="middle">${d.month.slice(5)}</text>` : "").join("");
  $("trend-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><defs><linearGradient id="trend-gradient" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#f16643" stop-opacity=".24"/><stop offset="1" stop-color="#f16643" stop-opacity="0"/></linearGradient></defs>${grids}<line class="axis" x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}"/><polygon class="trend-area" points="${left},${height - bottom} ${points} ${x(trend.length - 1)},${height - bottom}"/><polyline class="trend-line" points="${points}"/>${trend.map((d, i) => `<circle class="trend-point" cx="${x(i)}" cy="${y(d.rent)}" r="3.5"><title>${d.month}: ${d.rent}만원</title></circle>`).join("")}${labels}</svg>`;
}

function renderScatter() {
  const areas = state.data.areas.filter(hasPublicData), width = 560, height = 245, left = 40, right = 18, top = 19, bottom = 34;
  if (!areas.length) { $("scatter-chart").innerHTML = "<p>비교 가능한 공공임대 가격·공급 자료가 아직 없습니다.</p>"; return; }
  const maxX = Math.max(...areas.map((a) => a.supply_units)) + 4, maxY = Math.ceil(Math.max(...areas.map(privateRent)) / 10) * 10 + 5;
  const x = (value) => left + value * (width - left - right) / maxX;
  const y = (value) => top + (maxY - value) * (height - top - bottom) / (maxY - 35);
  const grids = [40, 50, 60].map((value) => `<line class="grid-line" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text class="axis-label" x="3" y="${y(value) + 3}">${value}</text>`).join("");
  $("scatter-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${grids}<line class="axis" x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}"/><line class="axis" x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}"/>${areas.map((area) => `<circle class="scatter-dot ${state.area === area.id ? "selected" : ""}" data-area="${area.id}" cx="${x(area.supply_units)}" cy="${y(privateRent(area))}" r="${4 + Math.sqrt(area.deals) * .65}"><title>${area.name}: 공급 ${area.supply_units}호, 민간 ${won(privateRent(area))}</title></circle><text class="scatter-label" x="${x(area.supply_units) + 7}" y="${y(privateRent(area)) + 3}">${area.name}</text>`).join("")}<text class="axis-label" x="${width - right}" y="${height - 8}" text-anchor="end">공급 호수 →</text><text class="axis-label" x="${left}" y="12">민간 환산월세</text></svg>`;
  $("scatter-chart").querySelectorAll(".scatter-dot").forEach((node) => node.addEventListener("click", () => selectArea(node.dataset.area)));
}

function renderBars() {
  const areas = state.data.areas, max = Math.max(...areas.flatMap((area) => hasPublicData(area) ? [privateRent(area), publicRent(area)] : [privateRent(area)]));
  $("bar-chart").innerHTML = `<div class="bar-key"><span><i class="private"></i>민간</span><span><i class="public"></i>공공(확보 지역만)</span></div>${areas.map((area) => `<div class="bar-row" data-area="${area.id}" role="button" tabindex="0"><strong class="bar-name">${area.name}</strong><div class="bar-track"><div class="bar private" style="width:${privateRent(area) / max * 100}%"></div></div><div class="bar-track">${hasPublicData(area) ? `<div class="bar public" style="width:${publicRent(area) / max * 100}%"></div>` : ""}</div><span class="bar-value">${won(privateRent(area))}</span></div>`).join("")}`;
  $("bar-chart").querySelectorAll(".bar-row").forEach((node) => node.addEventListener("click", () => selectArea(node.dataset.area)));
}

function renderTable() {
  const areaName = state.area === "all" ? null : state.data.areas.find((area) => area.id === state.area).name;
  const rows = state.data.listings.filter((row) => (!areaName || row.area === areaName) && (state.housing === "all" || (state.housing === "private" ? row.kind.startsWith("민간") : row.kind.startsWith("청년"))));
  const shown = state.tableFiltered ? rows : rows.slice(0, 5);
  $("record-table").innerHTML = shown.map((row) => `<tr><td>${row.area}</td><td><span class="kind-tag ${row.kind.startsWith("민간") ? "private" : "public"}">${row.kind}</span></td><td>${row.area_m2}㎡</td><td>${won(row.deposit)}</td><td>${won(row.monthly)}</td><td><strong>${won(convertedRent(row.deposit, row.monthly))}</strong></td><td>${row.date}</td><td><a href="${row.url}" target="_blank" rel="noopener noreferrer">${row.source} ↗</a></td></tr>`).join("") || `<tr><td colspan="8">선택한 조건에 해당하는 상세 레코드가 없습니다.</td></tr>`;
  $("table-filter").textContent = state.tableFiltered ? "접기" : "전체 보기";
}

function renderSources() {
  const mapSource = { name: state.scope === "capital" ? "시·군·구 경계" : "행정동 경계", organization: "OpenStreetMap contributors", description: state.scope === "capital" ? "수도권 시·군·구 경계" : "배곧동·정왕1·2동·대야동·신천동·은행동 경계", url: "https://www.openstreetmap.org/copyright" };
  $("source-list").innerHTML = [...state.data.sources, mapSource].map((source) => `<li><a href="${source.url}" target="_blank" rel="noopener noreferrer">${source.name} ↗</a><br/><span>${source.organization} · ${source.description}</span></li>`).join("");
}

function render() { renderMetrics(); renderMap(); renderInsights(); renderTrend(); renderScatter(); renderBars(); renderTable(); }

function bindMapFullscreen() {
  const canvas = document.querySelector(".map-canvas");
  const button = $("map-fullscreen");
  const sync = () => {
    const expanded = document.fullscreenElement === canvas;
    button.textContent = expanded ? "×" : "⛶";
    button.setAttribute("aria-label", expanded ? "전체 화면 닫기" : "지도를 전체 화면으로 보기");
    requestAnimationFrame(() => state.naverMap?.autoResize());
  };
  button.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement === canvas) await document.exitFullscreen();
      else await canvas.requestFullscreen();
    } catch (error) {
      console.warn("전체 화면 전환에 실패했습니다.", error);
    }
  });
  document.addEventListener("fullscreenchange", sync);
}

function bindMapZoomControls() {
  const changeZoom = (amount) => {
    if (!state.naverMap) return;
    const nextZoom = Math.max(state.scope === "capital" ? 7 : 10, Math.min(21, state.naverMap.getZoom() + amount));
    state.naverMap.setZoom(nextZoom, true);
  };
  $("map-zoom-in").addEventListener("click", () => changeZoom(1));
  $("map-zoom-out").addEventListener("click", () => changeZoom(-1));
}

function bindControls() {
  $("area-filter").addEventListener("change", (event) => { state.area = event.target.value; render(); });
  $("housing-filter").addEventListener("change", (event) => { state.housing = event.target.value; renderTable(); });
  $("rate-filter").addEventListener("change", (event) => { state.rate = Number(event.target.value); render(); });
  $("reset-filters").addEventListener("click", () => { state.area = "all"; state.housing = "all"; state.rate = 0.05; $("area-filter").value = "all"; $("housing-filter").value = "all"; $("rate-filter").value = "0.05"; render(); });
  $("table-filter").addEventListener("click", () => { state.tableFiltered = !state.tableFiltered; renderTable(); });
  bindMapFullscreen();
  bindMapZoomControls();
}

async function init() {
  try {
    state.scope = new URLSearchParams(window.location.search).get("scope") === "capital" ? "capital" : "siheung";
    const response = await fetch(`/api/dashboard?scope=${state.scope}`);
    if (!response.ok) throw new Error("데이터를 불러오지 못했습니다.");
    state.data = await response.json();
    const configResponse = await fetch("/api/config");
    const config = configResponse.ok ? await configResponse.json() : {};
    const meta = state.data.meta;
    $("period-label").textContent = meta.period;
    $("updated-label").textContent = meta.updated_at;
    $("footer-updated").textContent = meta.updated_at;
    if (meta.data_mode !== "actual") { const banner = $("demo-banner"); banner.textContent = `${meta.data_mode === "demo" ? "시연 모드" : "자료 범위 안내"} — ${meta.notice}`; banner.classList.add("show"); }
    if (state.scope === "capital") {
      document.title = "수도권 청년 주거 지도";
      document.querySelector(".hero .eyebrow").textContent = "CAPITAL REGION · YOUTH SINGLE-PERSON HOUSING";
      document.querySelector(".hero h1").innerHTML = "수도권 청년<br /><em>주거 지도</em>";
      $("area-filter").firstElementChild.textContent = "수도권 전체";
      document.querySelector(".map-section h2").textContent = "민간 임대료와 확인된 공공임대 공급";
      document.querySelector(".map-canvas").setAttribute("aria-label", "수도권 시·군·구별 비교 지도");
      document.querySelector(".naver-map").setAttribute("aria-label", "네이버 지도 기반 수도권 시·군·구별 비교 지도");
    }
    state.data.areas.forEach((area) => $("area-filter").insertAdjacentHTML("beforeend", `<option value="${area.id}">${area.name}</option>`));
    renderSources(); bindControls();
    if (config.naver_maps_key_id) {
      try {
        await loadNaverMaps(config.naver_maps_key_id);
        initializeNaverMap();
        try {
          await loadAdminBoundaries();
        } catch (boundaryError) {
          $("map-footnote").textContent = "행정동 경계를 불러오지 못해 대표 좌표 기준으로 표시합니다.";
          console.warn(boundaryError);
        }
      } catch (mapError) {
        $("map-footnote").textContent = "네이버 지도를 불러오지 못해 기본 비교 지도를 표시합니다.";
        console.warn(mapError);
      }
    } else {
      $("map-footnote").textContent = "NAVER_MAPS_KEY_ID를 설정하면 실제 네이버 지도 위에서 비교할 수 있습니다.";
    }
    render();
  } catch (error) {
    document.body.innerHTML = `<main class="fatal"><h1>데이터를 불러오지 못했습니다.</h1><p>${error.message}</p><p>서버의 <code>/health</code> 주소와 배포 로그를 확인하세요.</p></main>`;
  }
}

init();
