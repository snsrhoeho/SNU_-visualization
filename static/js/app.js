const CATEGORIES = [
  { id: "food", label: "음식점", icon: "🍜", threshold: 10, color: "#ff6b45" },
  { id: "cafe", label: "카페", icon: "☕", threshold: 3, color: "#a86c49" },
  { id: "laundry", label: "코인세탁방", icon: "🫧", threshold: 1, color: "#3c8dde" },
  { id: "convenience", label: "편의점", icon: "🏪", threshold: 2, color: "#7356c9" },
  { id: "mart", label: "마트", icon: "🛒", threshold: 1, color: "#de9a32" },
  { id: "subway", label: "지하철역", icon: "🚇", threshold: 1, color: "#2978c8" },
  { id: "bus", label: "버스정류장", icon: "🚌", threshold: 2, color: "#268c73" },
  { id: "park", label: "공원·러닝", icon: "🌳", threshold: 1, color: "#3c9b5f" },
  { id: "hospital", label: "병원", icon: "🏥", threshold: 1, color: "#e85665" },
  { id: "pharmacy", label: "약국", icon: "💊", threshold: 1, color: "#17a7a2" },
];

const state = {
  data: null,
  selected: new Set(["food", "cafe", "convenience", "hospital", "subway"]),
  minutes: 10,
  areaId: null,
  zoom: 1,
};

const $ = (id) => document.getElementById(id);
const category = (id) => CATEGORIES.find((item) => item.id === id);
const area = (id) => state.data.areas.find((item) => item.id === id);
const walkFactor = () => ({ 5: 0.18, 10: 0.38, 15: 0.62 }[state.minutes]);
const accessibleCount = (item, id) => {
  if (id === "bus") return Math.max(0, Math.round(item.bus * walkFactor()));
  if (id === "subway") return item.station_walk <= state.minutes ? 1 : 0;
  return Math.max(0, Math.round((item.counts[id] || 0) * walkFactor()));
};
const meets = (item, id) => accessibleCount(item, id) >= category(id).threshold;

function scoreArea(item) {
  const chosen = [...state.selected];
  const met = chosen.filter((id) => meets(item, id)).length;
  const totalFacilities = chosen.reduce((sum, id) => sum + accessibleCount(item, id), 0);
  return { item, met, total: chosen.length, ratio: chosen.length ? met / chosen.length : 0, totalFacilities };
}

function ranking() {
  return state.data.areas.map(scoreArea).sort((a, b) => b.met - a.met || b.totalFacilities - a.totalFacilities || a.item.station_walk - b.item.station_walk);
}

function renderCategoryButtons() {
  $("category-list").innerHTML = CATEGORIES.map((item) => `<button class="category-button ${state.selected.has(item.id) ? "active" : ""}" data-category="${item.id}" type="button" aria-pressed="${state.selected.has(item.id)}"><span>${item.icon}</span><b>${item.label}</b><i>✓</i></button>`).join("");
  document.querySelectorAll(".category-button").forEach((button) => button.addEventListener("click", () => {
    const id = button.dataset.category;
    if (state.selected.has(id)) {
      if (state.selected.size === 1) return;
      state.selected.delete(id);
    } else state.selected.add(id);
    render();
  }));
}

function mapColor(ratio) {
  if (ratio >= 1) return "#ff6642";
  if (ratio >= 0.75) return "#ff9478";
  if (ratio >= 0.5) return "#ffc2af";
  if (ratio > 0) return "#ffe4d9";
  return "#e9ece8";
}

function markerOffset(facility, index) {
  const base = area(facility.area);
  const seed = [...String(facility.id || index)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const angle = (seed % 360) * Math.PI / 180;
  const radius = 2.8 + (seed % 7) * 0.55;
  return [base.x + Math.cos(angle) * radius, base.y + Math.sin(angle) * radius];
}

function renderMap() {
  const scores = ranking();
  const scoreById = Object.fromEntries(scores.map((result) => [result.item.id, result]));
  const paths = state.data.areas.map((item) => {
    const result = scoreById[item.id];
    const selected = state.areaId === item.id;
    return `<g class="district-group ${selected ? "selected" : ""}" data-area="${item.id}" tabindex="0" role="button" aria-label="${item.name}, ${result.met}/${result.total} 조건 충족"><polygon points="${item.polygon}" fill="${mapColor(result.ratio)}"></polygon><text x="${item.x}" y="${item.y - 1.1}">${item.name}</text><text class="district-score" x="${item.x}" y="${item.y + 3.5}">${result.met}/${result.total}</text></g>`;
  }).join("");
  const visible = state.data.facilities.filter((facility) => state.selected.has(facility.category) && (!state.areaId || facility.area === state.areaId)).slice(0, state.areaId ? 80 : 100);
  const markers = visible.map((facility, index) => {
    const [x, y] = markerOffset(facility, index);
    const meta = category(facility.category);
    return `<circle class="facility-marker" cx="${x}" cy="${y}" r=".85" fill="${meta.color}"><title>${facility.name} · ${meta.label}</title></circle>`;
  }).join("");
  $("life-map").innerHTML = `<g class="map-stage" style="transform:scale(${state.zoom});transform-origin:center">${paths}${markers}</g>`;
  document.querySelectorAll(".district-group").forEach((node) => {
    const choose = () => { state.areaId = node.dataset.area; render(); $("detail").scrollIntoView({ behavior: "smooth", block: "start" }); };
    node.addEventListener("click", choose);
    node.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); } });
  });
  const perfect = scores.filter((result) => result.ratio === 1).length;
  $("map-caption").textContent = perfect ? `선택 조건을 모두 충족한 동네가 ${perfect}곳 있어요` : "상대적으로 조건을 많이 충족한 동네를 진하게 표시해요";
}

function conditionSummary(result) {
  return [...state.selected].map((id) => `<span class="mini-condition ${meets(result.item, id) ? "met" : "miss"}" title="${category(id).label}">${category(id).icon}</span>`).join("");
}

function renderRanking() {
  const results = ranking().slice(0, 3);
  if (!state.areaId) state.areaId = results[0].item.id;
  $("selection-count").textContent = `${state.selected.size}개 조건`;
  $("ranking-list").innerHTML = results.map((result, index) => `<button class="rank-card ${state.areaId === result.item.id ? "active" : ""}" data-area="${result.item.id}" type="button"><span class="rank-number">${index + 1}</span><div><div class="rank-title"><strong>${result.item.name}</strong><span>${result.met}/${result.total} 충족</span></div><div class="mini-conditions">${conditionSummary(result)}</div><p>${result.met === result.total ? "선택한 생활 조건을 모두 만족해요" : `${result.total - result.met}개 조건이 기준에 조금 못 미쳐요`}</p></div><b class="rank-arrow">→</b></button>`).join("");
  document.querySelectorAll(".rank-card").forEach((button) => button.addEventListener("click", () => { state.areaId = button.dataset.area; render(); $("detail").scrollIntoView({ behavior: "smooth" }); }));
}

function renderDetail() {
  const item = area(state.areaId);
  const result = scoreArea(item);
  $("detail-title").textContent = `${item.name}, 생활핏 ${Math.round(result.ratio * 100)}%`;
  $("detail-summary").textContent = `${result.total}개 선택 조건 중 ${result.met}개를 충족합니다. 실제 수치를 확인하고 내 생활 방식과 맞는지 판단해 보세요.`;
  $("detail-score").textContent = `${result.met}/${result.total}`;
  $("condition-bars").innerHTML = [...state.selected].map((id) => {
    const count = accessibleCount(item, id);
    const meta = category(id);
    const ok = meets(item, id);
    const text = id === "subway" ? `${item.station} ${item.station_walk}분` : `${count}개 / 기준 ${meta.threshold}개`;
    const width = Math.min(100, count / Math.max(1, meta.threshold) * 70);
    return `<div class="condition-row"><span>${meta.icon} ${meta.label}</span><div><i style="width:${width}%;background:${meta.color}"></i></div><b class="${ok ? "ok" : "no"}">${ok ? "충족" : "미충족"}<small>${text}</small></b></div>`;
  }).join("");
  $("station-info").textContent = `${item.station} · 도보 약 ${item.station_walk}분`;
  $("bus-info").textContent = `도보권 ${accessibleCount(item, "bus")}개 · ${item.routes}개 노선`;
  $("rent-info").textContent = `월세 ${item.rent}만원 · 전세 ${item.jeonse.toLocaleString("ko-KR")}만원`;
  $("naver-realestate").href = `https://new.land.naver.com/complexes?ms=${encodeURIComponent(item.name)}`;
  $("naver-route").href = `https://map.naver.com/p/search/${encodeURIComponent(`시흥시 ${item.name}`)}`;
  renderFacilities(item);
}

function renderFacilities(item) {
  const selectedFacilities = state.data.facilities.filter((facility) => facility.area === item.id && state.selected.has(facility.category));
  const unique = [];
  const seen = new Set();
  for (const facility of selectedFacilities) {
    const key = `${facility.name}-${facility.address}`;
    if (!seen.has(key)) { seen.add(key); unique.push(facility); }
    if (unique.length >= 8) break;
  }
  $("facility-hint").textContent = `${state.minutes}분 도보권 추정 · ${selectedFacilities.length.toLocaleString("ko-KR")}개 원본 시설 중 일부`;
  $("facility-list").innerHTML = unique.length ? unique.map((facility) => `<a class="facility-card" href="${facility.url}" target="_blank" rel="noreferrer"><span style="background:${category(facility.category).color}18;color:${category(facility.category).color}">${category(facility.category).icon}</span><div><small>${category(facility.category).label}</small><strong>${facility.name}</strong><p>${facility.address || "주소 정보 없음"}</p></div><b>↗</b></a>`).join("") : `<p class="empty-state">선택한 조건에 해당하는 시설 데이터가 없습니다.</p>`;
}

function renderCriteria() {
  $("criteria-list").innerHTML = CATEGORIES.map((item) => `<div><span>${item.icon} ${item.label}</span><b>도보권 내 ${item.threshold}개 이상</b></div>`).join("");
}

function render() {
  renderCategoryButtons();
  renderRanking();
  renderMap();
  renderDetail();
}

function bindControls() {
  document.querySelectorAll("#walk-segment button").forEach((button) => button.addEventListener("click", () => {
    state.minutes = Number(button.dataset.minutes);
    document.querySelectorAll("#walk-segment button").forEach((item) => item.classList.toggle("active", item === button));
    $("walk-description").textContent = `도보 ${state.minutes}분 · 약 ${{ 5: "330m", 10: "670m", 15: "1km" }[state.minutes]}`;
    render();
  }));
  $("criteria-button").addEventListener("click", () => $("criteria-dialog").showModal());
  document.querySelector(".dialog-close").addEventListener("click", () => $("criteria-dialog").close());
  $("criteria-dialog").addEventListener("click", (event) => { if (event.target === $("criteria-dialog")) $("criteria-dialog").close(); });
  $("zoom-in").addEventListener("click", () => { state.zoom = Math.min(1.35, state.zoom + 0.1); renderMap(); });
  $("zoom-out").addEventListener("click", () => { state.zoom = Math.max(0.8, state.zoom - 0.1); renderMap(); });
  $("view-map").addEventListener("click", () => $("ranking").scrollIntoView({ behavior: "smooth" }));
  $("mobile-menu").addEventListener("click", () => document.querySelector(".topbar nav").classList.toggle("open"));
}

async function init() {
  try {
    const response = await fetch("/api/life-fit");
    if (!response.ok) throw new Error("데이터 응답을 확인할 수 없습니다.");
    state.data = await response.json();
    $("facility-total").textContent = state.data.facilities.length.toLocaleString("ko-KR");
    $("data-notice").textContent = state.data.meta.notice;
    $("updated-at").textContent = state.data.meta.updated_at;
    renderCriteria();
    bindControls();
    render();
  } catch (error) {
    document.body.innerHTML = `<main class="fatal"><h1>시흥생활핏을 불러오지 못했습니다.</h1><p>${error.message}</p></main>`;
  }
}

init();
