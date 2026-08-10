const CATEGORY_META = {
  food: { label: "음식점", icon: "🍜", color: "#e85c3e" },
  cafe: { label: "카페", icon: "☕", color: "#986344" },
  laundry: { label: "코인세탁방", icon: "🫧", color: "#397ec1" },
  convenience: { label: "편의점", icon: "🏪", color: "#6951c5" },
  mart: { label: "대형마트", icon: "🛒", color: "#c68a25" },
  subway: { label: "지하철역", icon: "🚇", color: "#2677be" },
  park: { label: "공원", icon: "🌳", color: "#2e8e59" },
  hospital: { label: "병원", icon: "🏥", color: "#d94f5d" },
  pharmacy: { label: "약국", icon: "💊", color: "#118d87" },
};

const state = {
  data: null,
  selected: new Set(["convenience", "hospital", "pharmacy", "subway"]),
  priority: ["convenience", "hospital", "pharmacy", "subway"],
  areaId: "all",
  mapMode: "facility",
  tableExpanded: false,
  naverMap: null,
  boundaries: [],
  boundariesLoaded: false,
  markers: [],
  overlayFrame: null,
  mapEventsBound: false,
  shouldFocusMap: false,
};

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value || "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const allAreas = () => state.data.areas;
const selectedArea = () => state.areaId === "all" ? null : allAreas().find((area) => area.id === state.areaId);
const scoreArea = (area) => [...state.selected].reduce((sum, id) => sum + (area.counts[id] || 0), 0);
const selectedPriority = () => state.priority.filter((id) => state.selected.has(id));

function syncPriority() {
  state.priority = state.priority.filter((id) => state.selected.has(id));
  state.data.categories.forEach(({ id }) => {
    if (state.selected.has(id) && !state.priority.includes(id)) state.priority.push(id);
  });
}

function categoryThreshold(id) {
  const counts = allAreas().map((area) => area.counts[id] || 0).sort((a, b) => a - b);
  return counts[Math.floor(counts.length / 2)] || 1;
}

const meetsCondition = (area, id) => (area.counts[id] || 0) >= categoryThreshold(id);

function recommendationScore(area) {
  const priority = selectedPriority();
  const priorityHits = priority.map((id) => Number(meetsCondition(area, id)));
  const normalized = priority.reduce((sum, id) => sum + Math.min((area.counts[id] || 0) / Math.max(...allAreas().map((item) => item.counts[id] || 0), 1), 1), 0);
  return { area, priorityHits, met: priorityHits.reduce((sum, hit) => sum + hit, 0), total: priority.length, normalized };
}

const rankingResults = () => [...allAreas()].map(recommendationScore).sort((a, b) => {
  for (let index = 0; index < Math.max(a.priorityHits.length, b.priorityHits.length); index += 1) {
    if ((a.priorityHits[index] || 0) !== (b.priorityHits[index] || 0)) return (b.priorityHits[index] || 0) - (a.priorityHits[index] || 0);
  }
  return b.normalized - a.normalized || scoreArea(b.area) - scoreArea(a.area) || a.area.name.localeCompare(b.area.name, "ko");
});
const rankings = () => rankingResults().map((result) => result.area);
const detailArea = () => selectedArea() || rankings()[0];
const selectedFacilities = () => state.data.facilities.filter((item) => state.selected.has(item.category));
const facilitiesForArea = (areaId) => selectedFacilities().filter((item) => item.area_id === areaId);

function colorForScore(score, min, max) {
  const ratio = max === min ? 0.55 : (score - min) / (max - min);
  const start = [218, 236, 231], end = [231, 89, 55];
  return `rgb(${start.map((value, index) => Math.round(value + (end[index] - value) * ratio)).join(",")})`;
}

function setArea(areaId) {
  state.areaId = state.areaId === areaId ? "all" : areaId;
  state.tableExpanded = false;
  state.shouldFocusMap = true;
  render();
}

function renderCategoryButtons() {
  $("category-list").innerHTML = state.data.categories.map(({ id, label }) => {
    const meta = CATEGORY_META[id] || { icon: "•", color: "#526660" };
    return `<button class="category-button ${state.selected.has(id) ? "active" : ""}" data-category="${id}" type="button" aria-pressed="${state.selected.has(id)}" style="--category-color:${meta.color}"><span>${meta.icon}</span><b>${label}</b><small>${allAreas().reduce((sum, area) => sum + (area.counts[id] || 0), 0).toLocaleString("ko-KR")}개</small><i>✓</i></button>`;
  }).join("");
  document.querySelectorAll(".category-button").forEach((button) => button.addEventListener("click", () => {
    const id = button.dataset.category;
    if (state.selected.has(id)) {
      state.selected.delete(id);
    } else state.selected.add(id);
    syncPriority();
    state.tableExpanded = false;
    render();
  }));
}

function movePriority(id, direction) {
  const index = state.priority.indexOf(id);
  const next = index + direction;
  if (index < 0 || next < 0 || next >= state.priority.length) return;
  [state.priority[index], state.priority[next]] = [state.priority[next], state.priority[index]];
  render();
}

function renderPriorityEditor() {
  const priority = selectedPriority();
  $("priority-summary").textContent = priority.length
    ? `1순위 ${CATEGORY_META[priority[0]].label}부터 순서대로 추천에 반영해요.`
    : "카테고리를 하나 이상 골라야 추천 순위를 만들 수 있어요.";
  $("priority-list").innerHTML = priority.map((id, index) => {
    const meta = CATEGORY_META[id];
    return `<div class="priority-chip"><span>${index + 1}</span><b>${meta.icon} ${meta.label}</b><div><button data-priority-id="${id}" data-move="-1" type="button" aria-label="${meta.label} 우선순위 올리기" ${index === 0 ? "disabled" : ""}>↑</button><button data-priority-id="${id}" data-move="1" type="button" aria-label="${meta.label} 우선순위 내리기" ${index === priority.length - 1 ? "disabled" : ""}>↓</button></div></div>`;
  }).join("") || `<p class="empty-message">위에서 필요한 생활조건을 골라봐.</p>`;
  document.querySelectorAll("[data-priority-id]").forEach((button) => button.addEventListener("click", () => movePriority(button.dataset.priorityId, Number(button.dataset.move))));
}

function renderMetrics() {
  const ranked = rankings(), top = ranked[0];
  $("facility-total").textContent = `${selectedFacilities().length.toLocaleString("ko-KR")}개`;
  $("top-area").textContent = state.selected.size ? top.name : "—";
  $("top-area-detail").textContent = state.selected.size ? `내 취향 시설 ${scoreArea(top).toLocaleString("ko-KR")}개` : "카테고리를 골라봐";
  $("category-count").textContent = `${state.selected.size}개`;
  $("area-count").textContent = `${allAreas().length}곳`;
}

function renderInsight() {
  const focus = detailArea();
  const ranked = rankings();
  if (!state.selected.size) {
    $("insight-panel").innerHTML = `<p class="eyebrow">PICK A VIBE</p><h3>어떤 동네가 궁금해?</h3><p class="empty-message">위에서 카테고리를 하나 이상 고르면, 내 취향에 맞는 동네를 바로 보여줄게.</p>`;
    return;
  }
  const label = state.areaId === "all" ? "지금 제일 찰떡인 곳" : "지금 보고 있는 동네";
  const categoryRows = [...state.selected].map((id) => {
    const meta = CATEGORY_META[id];
    return `<li><span>${meta.icon} ${meta.label}</span><b>${(focus.counts[id] || 0).toLocaleString("ko-KR")}개</b></li>`;
  }).join("");
  $("insight-panel").innerHTML = `<p class="eyebrow">${label}</p><h3>${focus.name}</h3><div class="focus-score"><strong>${scoreArea(focus).toLocaleString("ko-KR")}</strong><span>개, 내 취향 시설</span></div><ul class="area-count-list">${categoryRows}</ul><div class="ranking-summary"><span>이런 동네도 있어</span><b>${ranked.filter((area) => area.id !== focus.id).slice(0, 2).map((area) => `${area.name} ${scoreArea(area)}개`).join(" · ") || "—"}</b></div>`;
}

function renderRecommendations() {
  const results = rankingResults().slice(0, 3);
  const priority = selectedPriority();
  $("selection-count").textContent = priority.length ? `${priority.length}개 조건 · 1순위 ${CATEGORY_META[priority[0]].label}` : "조건 선택 필요";
  $("ranking-list").innerHTML = results.map((result, index) => {
    const { area, met, total } = result;
    const reason = total === 0 ? "생활조건을 먼저 골라봐." : met === total ? "고른 생활조건을 모두 충족해요." : `${total - met}개 조건은 기준보다 조금 아쉬워요.`;
    const icons = priority.map((id, priorityIndex) => `<span class="mini-condition ${meetsCondition(area, id) ? "met" : "miss"}" title="${priorityIndex + 1}순위 ${CATEGORY_META[id].label}">${priorityIndex < 3 ? `<b>${priorityIndex + 1}</b>` : ""}${CATEGORY_META[id].icon}</span>`).join("");
    return `<button class="rank-card ${state.areaId === area.id ? "active" : ""}" data-ranking-area="${area.id}" type="button"><span class="rank-number">${index + 1}</span><div><div class="rank-title"><strong>${area.name}</strong><span>${met}/${total} 충족</span></div><div class="mini-conditions">${icons}</div><p>${reason}</p></div><b class="rank-arrow">→</b></button>`;
  }).join("");
  document.querySelectorAll("[data-ranking-area]").forEach((button) => button.addEventListener("click", () => setArea(button.dataset.rankingArea)));
}

function renderDetailReport() {
  const area = detailArea();
  const result = recommendationScore(area);
  const priority = selectedPriority();
  $("detail-title").textContent = `${area.name} 상세 분석`;
  $("detail-score").textContent = priority.length ? `${result.met}/${result.total}` : "—";
  $("detail-summary").textContent = priority.length
    ? `${area.name}은 내가 고른 ${result.total}가지 생활조건 중 ${result.met}가지를 시흥시 6개 생활권의 중앙값 이상으로 충족해.`
    : "생활조건을 고르면 이 동네가 왜 추천됐는지 보여줄게.";
  $("condition-bars").innerHTML = priority.map((id, index) => {
    const count = area.counts[id] || 0;
    const threshold = categoryThreshold(id);
    const met = meetsCondition(area, id);
    const ratio = Math.min(count / Math.max(...allAreas().map((item) => item.counts[id] || 0), 1), 1);
    return `<div class="condition-row"><div><span><b>${index + 1}</b> ${CATEGORY_META[id].icon} ${CATEGORY_META[id].label}</span><strong>${count.toLocaleString("ko-KR")}개</strong></div><i><b class="${met ? "met" : "miss"}" style="width:${ratio * 100}%"></b></i><small>${met ? `기준 충족 · 중앙값 ${threshold}개 이상` : `참고 · 중앙값 ${threshold}개 미만`}</small></div>`;
  }).join("") || `<p class="empty-message">카테고리를 하나 이상 선택해줘.</p>`;
  $("detail-facility-total").textContent = priority.length ? `선택 조건에 맞는 실제 시설은 ${facilitiesForArea(area.id).length.toLocaleString("ko-KR")}개야.` : "";
}

function renderBars() {
  const ranked = rankings(), max = Math.max(...ranked.map(scoreArea), 1);
  $("bar-chart").innerHTML = ranked.map((area, index) => `<button class="bar-row ${state.areaId === area.id ? "selected" : ""}" data-area="${area.id}" type="button"><span class="bar-rank">${String(index + 1).padStart(2, "0")}</span><strong>${area.name}</strong><span class="bar-track"><i style="width:${scoreArea(area) / max * 100}%"></i></span><b>${scoreArea(area).toLocaleString("ko-KR")}개</b></button>`).join("");
  document.querySelectorAll(".bar-row").forEach((button) => button.addEventListener("click", () => setArea(button.dataset.area)));
}

function renderMix() {
  const area = detailArea();
  const rows = [...state.selected].map((id) => ({ id, count: area.counts[id] || 0 })).sort((a, b) => b.count - a.count);
  if (!rows.length) {
    $("mix-heading").textContent = "이 동네엔 뭐가 많을까?";
    $("mix-chart").innerHTML = `<p class="empty-message">카테고리를 고르면 여기서 동네별 구성을 비교할 수 있어.</p>`;
    return;
  }
  const max = Math.max(...rows.map((row) => row.count), 1);
  $("mix-heading").textContent = `${area.name}엔 뭐가 많을까?`;
  $("mix-chart").innerHTML = rows.map(({ id, count }) => {
    const meta = CATEGORY_META[id];
    return `<div class="mix-row"><span>${meta.icon} ${meta.label}</span><i><b style="width:${count / max * 100}%;background:${meta.color}"></b></i><strong>${count.toLocaleString("ko-KR")}개</strong></div>`;
  }).join("");
}

function renderTable() {
  const area = detailArea();
  const rows = facilitiesForArea(area.id).sort((a, b) => a.name.localeCompare(b.name, "ko"));
  const shown = state.tableExpanded ? rows : rows.slice(0, 12);
  $("records-heading").textContent = `${area.name} 내 취향 시설 리스트`;
  $("records-description").textContent = `내가 고른 ${state.selected.size}가지 취향에 맞는 곳이 ${rows.length.toLocaleString("ko-KR")}개 있어.`;
  $("record-table").innerHTML = shown.map((item) => {
    const meta = CATEGORY_META[item.category];
    return `<tr><td>${area.name}</td><td><span class="kind-tag" style="--tag-color:${meta.color}">${meta.icon} ${meta.label}</span></td><td><strong>${escapeHtml(item.name)}</strong></td><td>${escapeHtml(item.address)}</td><td>${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">카카오 장소 ↗</a>` : "—"}</td></tr>`;
  }).join("") || `<tr><td colspan="5">선택한 카테고리에 해당하는 시설이 없습니다.</td></tr>`;
  $("table-filter").textContent = state.tableExpanded ? "접기" : `${rows.length.toLocaleString("ko-KR")}개 다 보기`;
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

async function loadBoundaries() {
  const response = await fetch("/static/data/siheung_dong_boundaries.geojson");
  if (!response.ok) throw new Error("행정동 경계를 불러오지 못했습니다.");
  const geojson = await response.json();
  state.boundaries = geojson.features.map((feature) => {
    const area = allAreas().find((item) => item.id === feature.properties.id);
    const geometry = feature.geometry;
    const rings = geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
    return { area, rings };
  }).filter(({ area, rings }) => area && Array.isArray(rings));
  state.boundariesLoaded = state.boundaries.length > 0;
}

function boundaryStyle(area) {
  if (!state.selected.size) return { fill: "#d8dfdc", opacity: 0.28, stroke: "#8d9b9d", strokeWidth: 1.5 };
  const scores = allAreas().map(scoreArea), score = scoreArea(area);
  const selected = state.areaId === area.id;
  return {
    fill: colorForScore(score, Math.min(...scores), Math.max(...scores)),
    opacity: selected ? 0.82 : 0.56,
    stroke: selected ? "#102841" : "#8f3b28",
    strokeWidth: selected ? 4.5 : 2.2,
  };
}

function bindSvgAreaClicks() {
  $("area-map").querySelectorAll(".district").forEach((node) => node.addEventListener("click", () => setArea(node.dataset.area)));
}

function renderFallbackMap() {
  if (!state.boundariesLoaded) return;
  const svg = $("area-map");
  const points = state.boundaries.flatMap(({ rings }) => rings.flatMap((ring) => ring));
  const lngs = points.map(([lng]) => lng), lats = points.map(([, lat]) => lat);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs), minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const project = ([lng, lat]) => [5 + (lng - minLng) / (maxLng - minLng) * 90, 4 + (maxLat - lat) / (maxLat - minLat) * 80];
  svg.innerHTML = state.boundaries.map(({ area, rings }) => {
    const style = boundaryStyle(area);
    const path = rings.map((ring) => ring.map((coordinate, index) => {
      const [x, y] = project(coordinate);
      return `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(" ") + " Z").join(" ");
    return `<path class="district ${state.areaId === area.id ? "selected" : ""}" data-area="${area.id}" d="${path}" fill="${style.fill}" fill-opacity="${style.opacity}" stroke="${style.stroke}" stroke-width="${style.strokeWidth / 2.4}"><title>${area.name}: ${scoreArea(area)}개</title></path>`;
  }).join("");
  bindSvgAreaClicks();
}

function renderMapOverlay() {
  if (!state.naverMap || !state.boundariesLoaded) return;
  const svg = $("area-map"), size = state.naverMap.getSize(), projection = state.naverMap.getProjection();
  svg.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  svg.innerHTML = state.boundaries.map(({ area, rings }) => {
    const style = boundaryStyle(area);
    const path = rings.map((ring) => ring.map(([lng, lat], index) => {
      const point = projection.fromCoordToOffset(new naver.maps.LatLng(lat, lng));
      return `${index ? "L" : "M"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
    }).join(" ") + " Z").join(" ");
    return `<path class="district ${state.areaId === area.id ? "selected" : ""}" data-area="${area.id}" d="${path}" fill="${style.fill}" fill-opacity="${style.opacity}" stroke="${style.stroke}" stroke-width="${style.strokeWidth}"><title>${area.name}: ${scoreArea(area)}개</title></path>`;
  }).join("");
}

function scheduleOverlayRender() {
  if (!state.naverMap || state.overlayFrame !== null) return;
  state.overlayFrame = requestAnimationFrame(() => {
    state.overlayFrame = null;
    renderMapOverlay();
  });
}

function renderMarkers() {
  state.markers.forEach((marker) => marker.setMap(null));
  state.markers = [];
  if (!state.naverMap || !window.naver?.maps) return;
  const facilities = state.areaId === "all" ? selectedFacilities() : facilitiesForArea(state.areaId);
  facilities.slice(0, 260).forEach((item) => {
    const meta = CATEGORY_META[item.category];
    const marker = new naver.maps.Marker({
      map: state.naverMap,
      position: new naver.maps.LatLng(item.lat, item.lng),
      title: `${item.name} · ${meta.label}`,
      icon: { content: `<span class="facility-dot" style="--dot-color:${meta.color}" title="${escapeHtml(item.name)}"></span>`, size: new naver.maps.Size(12, 12), anchor: new naver.maps.Point(6, 6) },
    });
    naver.maps.Event.addListener(marker, "click", () => setArea(item.area_id));
    state.markers.push(marker);
  });
}

function focusMap() {
  if (!state.naverMap || !state.shouldFocusMap) return;
  state.shouldFocusMap = false;
  const area = selectedArea();
  if (area) {
    state.naverMap.panTo(new naver.maps.LatLng(area.center[0], area.center[1]));
    state.naverMap.setZoom(13, true);
  } else {
    state.naverMap.panTo(new naver.maps.LatLng(37.391, 126.756));
    state.naverMap.setZoom(11, true);
  }
}

function renderMap() {
  if (state.naverMap && window.naver?.maps) {
    const svg = $("area-map");
    svg.classList.toggle("is-hidden", state.mapMode !== "admin");
    if (state.mapMode === "admin") renderMapOverlay();
    else svg.innerHTML = "";
    renderMarkers();
    focusMap();
  } else {
    $("area-map").classList.remove("is-hidden");
    renderFallbackMap();
  }
  $("map-legend").hidden = state.mapMode !== "admin";
  $("map-footnote").textContent = state.mapMode === "admin"
    ? "선택한 시설이 많은 생활권일수록 진하게 보여. 현재는 6개 비교 생활권 경계야."
    : "시설 보기는 지도를 자유롭게 움직여 볼 수 있어. 마커는 최대 260개까지 보여줘.";
}

function initializeNaverMap() {
  state.naverMap = new naver.maps.Map("naver-map", { center: new naver.maps.LatLng(37.391, 126.756), zoom: 11, minZoom: 10, zoomControl: false, mapDataControl: false, scaleControl: false });
  document.querySelector(".map-canvas").classList.add("map-ready");
  if (!state.mapEventsBound) {
    ["center_changed", "zoom_changed", "bounds_changed", "size_changed", "projection_changed", "idle"].forEach((eventName) => naver.maps.Event.addListener(state.naverMap, eventName, scheduleOverlayRender));
    state.mapEventsBound = true;
  }
}

function bindControls() {
  $("reset-filters").addEventListener("click", () => { state.selected = new Set(state.data.categories.map((item) => item.id)); syncPriority(); state.tableExpanded = false; render(); });
  $("clear-filters").addEventListener("click", () => { state.selected = new Set(); syncPriority(); state.tableExpanded = false; render(); });
  $("table-filter").addEventListener("click", () => { state.tableExpanded = !state.tableExpanded; renderTable(); });
  $("map-zoom-in").addEventListener("click", () => state.naverMap?.setZoom(Math.min(21, state.naverMap.getZoom() + 1), true));
  $("map-zoom-out").addEventListener("click", () => state.naverMap?.setZoom(Math.max(10, state.naverMap.getZoom() - 1), true));
  const canvas = document.querySelector(".map-canvas");
  $("map-fullscreen").addEventListener("click", async () => {
    if (document.fullscreenElement === canvas) await document.exitFullscreen();
    else await canvas.requestFullscreen();
  });
  document.addEventListener("fullscreenchange", () => requestAnimationFrame(() => { state.naverMap?.autoResize(); scheduleOverlayRender(); }));
  document.querySelectorAll("[data-map-mode]").forEach((button) => button.addEventListener("click", () => {
    state.mapMode = button.dataset.mapMode;
    document.querySelectorAll("[data-map-mode]").forEach((item) => item.classList.toggle("active", item === button));
    renderMap();
  }));
}

function render() {
  syncPriority();
  renderCategoryButtons();
  renderPriorityEditor();
  renderMetrics();
  renderInsight();
  renderRecommendations();
  renderDetailReport();
  renderBars();
  renderMix();
  renderTable();
  renderMap();
}

async function init() {
  try {
    const response = await fetch("/api/infrastructure");
    if (!response.ok) throw new Error("생활 인프라 데이터를 불러오지 못했습니다.");
    state.data = await response.json();
    await loadBoundaries();
    bindControls();
    const configResponse = await fetch("/api/config");
    const config = configResponse.ok ? await configResponse.json() : {};
    if (config.naver_maps_key_id) {
      try {
        await loadNaverMaps(config.naver_maps_key_id);
        initializeNaverMap();
      } catch (error) {
        $("map-footnote").textContent = "네이버 지도를 불러오지 못해 행정동 경계 지도를 표시합니다.";
        console.warn(error);
      }
    }
    render();
  } catch (error) {
    document.body.innerHTML = `<main class="fatal"><h1>생활 인프라 지도를 불러오지 못했습니다.</h1><p>${escapeHtml(error.message)}</p></main>`;
  }
}

init();
