const CATEGORIES = [
  { id: "food", label: "음식점", icon: "🍜", threshold: 10, color: "#ff6b45" },
  { id: "cafe", label: "카페", icon: "☕", threshold: 3, color: "#a86c49" },
  { id: "good_price", label: "착한가격업소", icon: "🏷️", threshold: 1, color: "#e35d35" },
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
  priority: ["food", "cafe", "convenience", "hospital", "subway"],
  minutes: 10,
  areaId: null,
  zoom: 1,
  page: "home",
};

let routeAnimationFrame = null;

const $ = (id) => document.getElementById(id);
const category = (id) => CATEGORIES.find((item) => item.id === id);
const area = (id) => state.data.areas.find((item) => item.id === id);
const runningRoute = (id) => state.data.running_routes.find((item) => item.id === id);
const PAGE_IDS = new Set(["home", "map", "detail", "running", "about"]);
const walkFactor = () => ({ 5: 0.18, 10: 0.38, 15: 0.62 }[state.minutes]);
const accessibleCount = (item, id) => {
  if (id === "bus") return Number.isFinite(item.bus) ? Math.max(0, Math.round(item.bus * walkFactor())) : 0;
  if (id === "subway") return Number.isFinite(item.station_walk) && item.station_walk <= state.minutes ? 1 : 0;
  return Math.max(0, Math.round((item.counts[id] || 0) * walkFactor()));
};

function visibleFacilities() {
  return state.data.facilities
    .filter((facility) => state.selected.has(facility.category) && (!state.areaId || facility.area === state.areaId))
    .sort((a, b) => state.priority.indexOf(a.category) - state.priority.indexOf(b.category))
    .slice(0, state.areaId ? 80 : 100);
}
const meets = (item, id) => accessibleCount(item, id) >= category(id).threshold;

function scoreArea(item) {
  const chosen = state.priority;
  const met = chosen.filter((id) => meets(item, id)).length;
  const totalFacilities = chosen.reduce((sum, id) => sum + accessibleCount(item, id), 0);
  const priorityHits = chosen.map((id) => Number(meets(item, id)));
  return { item, met, total: chosen.length, ratio: chosen.length ? met / chosen.length : 0, totalFacilities, priorityHits };
}

function ranking() {
  return state.data.areas.map(scoreArea).sort((a, b) => {
    for (let index = 0; index < state.priority.length; index += 1) {
      if (a.priorityHits[index] !== b.priorityHits[index]) return b.priorityHits[index] - a.priorityHits[index];
    }
    return b.met - a.met || b.totalFacilities - a.totalFacilities || (a.item.station_walk ?? Infinity) - (b.item.station_walk ?? Infinity);
  });
}

function renderCategoryButtons() {
  $("category-list").innerHTML = CATEGORIES.map((item) => {
    const priority = state.priority.indexOf(item.id);
    const featured = item.id === "good_price";
    return `<button class="category-button ${priority >= 0 ? "active" : ""} ${featured ? "featured" : ""}" data-category="${item.id}" type="button" aria-pressed="${priority >= 0}" ${featured ? 'title="행정안전부 착한가격업소 현황 기반"' : ""}><span>${item.icon}</span><b>${item.label}</b><i>${priority + 1}</i><small aria-hidden="true">${priority >= 0 ? "✓" : ""}</small></button>`;
  }).join("");
  document.querySelectorAll(".category-button").forEach((button) => button.addEventListener("click", () => {
    const id = button.dataset.category;
    if (state.selected.has(id)) {
      if (state.selected.size === 1) return;
      state.selected.delete(id);
      state.priority = state.priority.filter((item) => item !== id);
    } else {
      state.selected.add(id);
      state.priority.push(id);
    }
    render();
  }));
  renderPriorityEditor();
}

function movePriority(id, direction) {
  const index = state.priority.indexOf(id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= state.priority.length) return;
  [state.priority[index], state.priority[target]] = [state.priority[target], state.priority[index]];
  render();
}

function renderPriorityEditor() {
  $("priority-list").innerHTML = state.priority.map((id, index) => {
    const meta = category(id);
    return `<div class="priority-chip ${index < 3 ? "top" : ""}"><span>${index + 1}</span><b>${meta.icon} ${meta.label}</b><div><button data-id="${id}" data-move="-1" type="button" aria-label="${meta.label} 우선순위 올리기" ${index === 0 ? "disabled" : ""}>↑</button><button data-id="${id}" data-move="1" type="button" aria-label="${meta.label} 우선순위 내리기" ${index === state.priority.length - 1 ? "disabled" : ""}>↓</button></div></div>`;
  }).join("");
  $("priority-summary").textContent = `1순위 ${category(state.priority[0]).label}부터 차례로 추천에 반영`;
  document.querySelectorAll(".priority-chip button").forEach((button) => button.addEventListener("click", () => movePriority(button.dataset.id, Number(button.dataset.move))));
}

function mapColor(ratio) {
  if (ratio >= 1) return "#168457";
  if (ratio >= 0.75) return "#58ae7d";
  if (ratio >= 0.5) return "#a8d6ba";
  if (ratio > 0) return "#dceee3";
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
    return `<g class="district-group" data-area="${item.id}" tabindex="0" role="button" aria-label="${item.name}, ${result.met}/${result.total} 조건 충족"><polygon points="${item.polygon}" fill="${mapColor(result.ratio)}"></polygon><text x="${item.x}" y="${item.y - 1.1}">${item.name}</text><text class="district-score" x="${item.x}" y="${item.y + 3.5}">${result.met}/${result.total}</text></g>`;
  }).join("");
  const visible = visibleFacilities();
  const markers = visible.map((facility, index) => {
    const [x, y] = markerOffset(facility, index);
    const meta = category(facility.category);
    return `<circle class="facility-marker" cx="${x}" cy="${y}" r=".85" fill="${meta.color}"><title>${facility.name} · ${meta.label}</title></circle>`;
  }).join("");
  $("life-map").innerHTML = `<g class="map-stage" style="transform:scale(${state.zoom});transform-origin:center">${paths}${markers}</g>`;
  document.querySelectorAll(".district-group").forEach((node) => {
    const choose = () => { state.areaId = node.dataset.area; render(); };
    node.addEventListener("click", choose);
    node.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); } });
  });
  const perfect = scores.filter((result) => result.ratio === 1).length;
  $("map-caption").textContent = perfect ? `선택 조건을 모두 충족한 동네가 ${perfect}곳 있어요` : "상대적으로 조건을 많이 충족한 동네를 진하게 표시해요";
}

function conditionSummary(result) {
  return state.priority.map((id, index) => `<span class="mini-condition ${meets(result.item, id) ? "met" : "miss"}" title="${index + 1}순위 ${category(id).label}">${index < 3 ? `<b>${index + 1}</b>` : ""}${category(id).icon}</span>`).join("");
}

function renderRanking() {
  const results = ranking().slice(0, 3);
  if (!state.areaId) state.areaId = results[0].item.id;
  $("selection-count").textContent = `${state.selected.size}개 조건 · 1순위 ${category(state.priority[0]).label}`;
  $("ranking-list").innerHTML = results.map((result, index) => `<button class="rank-card ${state.areaId === result.item.id ? "active" : ""}" data-area="${result.item.id}" type="button"><span class="rank-number">${index + 1}</span><div><div class="rank-title"><strong>${result.item.name}</strong><span>${result.met}/${result.total} 충족</span></div><div class="mini-conditions">${conditionSummary(result)}</div><p>${result.met === result.total ? "선택한 생활 조건을 모두 만족해요" : `${result.total - result.met}개 조건이 기준에 조금 못 미쳐요`}</p></div><b class="rank-arrow">→</b></button>`).join("");
  document.querySelectorAll(".rank-card").forEach((button) => button.addEventListener("click", () => { state.areaId = button.dataset.area; render(); }));
}

function renderDetail() {
  const item = area(state.areaId);
  const result = scoreArea(item);
  $("detail-title").textContent = `${item.name}, 생활핏 ${Math.round(result.ratio * 100)}%`;
  $("detail-summary").textContent = `${result.total}개 선택 조건 중 ${result.met}개를 충족합니다. 실제 수치를 확인하고 내 생활 방식과 맞는지 판단해 보세요.`;
  $("detail-score").textContent = `${result.met}/${result.total}`;
  $("condition-bars").innerHTML = state.priority.map((id, index) => {
    const count = accessibleCount(item, id);
    const meta = category(id);
    const ok = meets(item, id);
    const text = id === "bus" && item.bus == null
      ? "법정동 버스 데이터 연결 예정"
      : id === "subway"
        ? `${item.station || "역 정보 없음"} · 약 ${item.station_walk ?? "—"}분 추정`
        : `${count}개 / 기준 ${meta.threshold}개`;
    const width = Math.min(100, count / Math.max(1, meta.threshold) * 70);
    return `<div class="condition-row"><span><em>${index + 1}</em>${meta.icon} ${meta.label}</span><div><i style="width:${width}%;background:${meta.color}"></i></div><b class="${ok ? "ok" : "no"}">${ok ? "충족" : "미충족"}<small>${text}</small></b></div>`;
  }).join("");
  $("station-info").textContent = item.station ? `${item.station} · 약 ${item.station_walk}분 추정` : "역 접근성 데이터 없음";
  $("bus-info").textContent = item.bus == null ? "법정동 버스 데이터 연결 예정" : `도보권 ${accessibleCount(item, "bus")}개 · ${item.routes}개 노선`;
  $("rent-info").textContent = item.rent == null ? "법정동 주거비 데이터 연결 예정" : `월세 ${item.rent}만원 · 전세 ${item.jeonse.toLocaleString("ko-KR")}만원`;
  $("naver-realestate").href = `https://new.land.naver.com/complexes?ms=${encodeURIComponent(item.name)}`;
  $("naver-route").href = `https://map.naver.com/p/search/${encodeURIComponent(`시흥시 ${item.name}`)}`;
  renderFacilities(item);
}

function renderFacilities(item) {
  const selectedFacilities = state.data.facilities.filter((facility) => facility.area === item.id && state.selected.has(facility.category));
  $("facility-hint").textContent = `${state.minutes}분 도보권 추정 · 우선순위별 최대 3곳`;
  $("facility-list").innerHTML = state.priority.map((id, index) => {
    const meta = category(id);
    const seen = new Set();
    const facilities = selectedFacilities.filter((facility) => facility.category === id).filter((facility) => {
      const key = `${facility.name}-${facility.address}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 3);
    const cards = facilities.length ? facilities.map((facility) => {
      const menu = facility.category === "good_price" && facility.menus?.length
        ? facility.menus.slice(0, 2).map((item) => `${item.name} ${Number(item.price).toLocaleString("ko-KR")}원`).join(" · ")
        : "";
      return `<a class="facility-card ${facility.category === "good_price" ? "good-price" : ""}" href="${facility.url}" target="_blank" rel="noreferrer"><span style="background:${meta.color}18;color:${meta.color}">${meta.icon}</span><div><small>${meta.label}${facility.business_type ? ` · ${facility.business_type}` : ""}</small><strong>${facility.name}</strong><p>${menu || facility.menu_summary || facility.address || "주소 정보 없음"}</p></div><b>↗</b></a>`;
    }).join("") : `<p class="facility-empty">등록된 시설 정보가 없어요</p>`;
    return `<section class="facility-group ${index === 0 ? "primary-group" : ""}"><div class="facility-group-head"><span>${index + 1}순위</span><h4>${meta.icon} ${meta.label}</h4><b>도보권 추정 ${accessibleCount(item, id)}개</b></div><div class="facility-card-grid">${cards}</div></section>`;
  }).join("");
}

function fitRoutePoints(points, width = 100, height = 64, padding = 8) {
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const scale = Math.min((width - padding * 2) / Math.max(maxX - minX, 1), (height - padding * 2) / Math.max(maxY - minY, 1));
  const offsetX = (width - (maxX - minX) * scale) / 2;
  const offsetY = (height - (maxY - minY) * scale) / 2;
  return points.map(([x, y]) => [offsetX + (x - minX) * scale, offsetY + (y - minY) * scale]);
}

function stopRouteAnimation() {
  if (routeAnimationFrame) cancelAnimationFrame(routeAnimationFrame);
  routeAnimationFrame = null;
}

function animateRoutePreview() {
  stopRouteAnimation();
  const path = $("route-modal-path");
  const runner = $("route-modal-runner");
  if (!path || !runner) return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  path.style.strokeDashoffset = `${length}`;
  path.getBoundingClientRect();
  path.style.strokeDashoffset = "0";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) {
    const point = path.getPointAtLength(length * 0.55);
    runner.setAttribute("transform", `translate(${point.x} ${point.y})`);
    return;
  }
  const startedAt = performance.now() + 500;
  const duration = 7000;
  const move = (now) => {
    const progress = Math.min(1, Math.max(0, (now - startedAt) / duration));
    const point = path.getPointAtLength(length * progress);
    const previous = path.getPointAtLength(Math.max(0, length * progress - 0.5));
    const next = path.getPointAtLength(Math.min(length, length * progress + 0.5));
    const angle = progress < 1
      ? Math.atan2(next.y - point.y, next.x - point.x) * 180 / Math.PI
      : Math.atan2(point.y - previous.y, point.x - previous.x) * 180 / Math.PI;
    runner.setAttribute("transform", `translate(${point.x} ${point.y}) rotate(${angle})`);
    if (progress < 1) routeAnimationFrame = requestAnimationFrame(move);
    else routeAnimationFrame = null;
  };
  routeAnimationFrame = requestAnimationFrame(move);
}

function openRouteDialog(routeId) {
  const route = runningRoute(routeId);
  const areaName = area(route.area).name;
  const points = fitRoutePoints(route.svg_points);
  const pointText = points.map((point) => point.map((value) => value.toFixed(2)).join(",")).join(" ");
  const [startX, startY] = points[0];
  const [finishX, finishY] = points[points.length - 1];
  $("route-dialog-area").textContent = areaName;
  $("route-dialog-difficulty").textContent = route.difficulty;
  $("route-dialog-title").textContent = route.name;
  $("route-dialog-summary").textContent = route.summary;
  $("route-dialog-distance").textContent = `${route.distance_km} km`;
  $("route-dialog-duration").textContent = `${route.duration_min}분`;
  $("route-dialog-surface").textContent = route.surface;
  $("route-dialog-highlights").innerHTML = route.highlights.map((item) => `<span># ${item}</span>`).join("");
  $("route-dialog-basis").textContent = route.basis;
  $("route-detail-svg").innerHTML = `
    <defs><linearGradient id="route-gradient" x1="0" x2="1"><stop stop-color="#79c892"/><stop offset=".55" stop-color="#176b4d"/><stop offset="1" stop-color="#0d3f2c"/></linearGradient><filter id="runner-shadow"><feDropShadow dx="0" dy="1" stdDeviation="1" flood-opacity=".28"/></filter></defs>
    <g class="route-street-grid"><path d="M-5 13H105M-5 31H105M-5 50H105M18-5V69M43-5V69M72-5V69"/><path d="M-10 60L34-8M28 70L83-8M61 70L110 11"/></g>
    <polyline class="route-halo" points="${pointText}"></polyline>
    <polyline id="route-modal-path" points="${pointText}"></polyline>
    <g class="route-endpoint route-start" transform="translate(${startX} ${startY})"><circle r="3.2"/><text y=".9">S</text></g>
    <g class="route-endpoint route-finish" transform="translate(${finishX} ${finishY})"><circle r="3.2"/><text y=".9">F</text></g>
    <g id="route-modal-runner" class="route-runner" filter="url(#runner-shadow)"><circle cy="-2.6" r="1.55"/><path d="M0-1L-1 2.2M-.2.1L2 1.1M-1 2.2L-2.5 4.7M-1 2.2L1.1 4.2M-.4-.1L-2.3 1"/></g>`;
  const dialog = $("route-dialog");
  if (!dialog.open) dialog.showModal();
  requestAnimationFrame(animateRoutePreview);
}

function renderRunningRoutes() {
  const routes = [...state.data.running_routes];
  $("running-list").innerHTML = routes.map((route) => {
    const areaName = area(route.area).name;
    const previewPoints = route.svg_points.map((point) => point.join(",")).join(" ");
    const [startX, startY] = route.svg_points[0];
    return `<button class="running-card" data-route="${route.id}" type="button"><div class="route-preview"><svg viewBox="0 0 104 90" aria-hidden="true"><polyline points="${previewPoints}"></polyline><circle cx="${startX}" cy="${startY}" r="2"></circle></svg><span>${areaName}</span></div><div class="route-card-top"><span>${areaName}</span><b>${route.difficulty}</b></div><h3>${route.name}</h3><p>${route.summary}</p><div class="route-stats"><span><strong>${route.distance_km}</strong>km</span><span><strong>${route.duration_min}</strong>분</span><span>${route.surface}</span></div><div class="route-tags">${route.highlights.map((item) => `<i>#${item}</i>`).join("")}</div><div class="route-action">상세 코스 보기<span>↗</span></div></button>`;
  }).join("");
  $("running-summary").textContent = "코스를 선택하면 상세 지도를 팝업으로 보여드려요.";
  document.querySelectorAll(".running-card").forEach((button) => button.addEventListener("click", () => {
    openRouteDialog(button.dataset.route);
  }));
}

function renderCriteria() {
  $("criteria-list").innerHTML = CATEGORIES.map((item) => `<div><span>${item.icon} ${item.label}</span><b>도보권 내 ${item.threshold}개 이상</b></div>`).join("");
}

function render() {
  renderCategoryButtons();
  renderRanking();
  renderMap();
  renderDetail();
  renderRunningRoutes();
}

function showPage(pageId, updateHash = true) {
  const nextPage = PAGE_IDS.has(pageId) ? pageId : "home";
  state.page = nextPage;
  document.querySelectorAll(".app-page").forEach((page) => {
    const active = page.dataset.page === nextPage;
    page.hidden = !active;
    page.classList.toggle("active", active);
  });
  document.querySelectorAll("[data-page-link]").forEach((link) => link.classList.toggle("active", link.dataset.pageLink === nextPage));
  document.querySelector(".topbar nav").classList.remove("open");
  if (updateHash && location.hash !== `#${nextPage}`) history.pushState(null, "", `#${nextPage}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (nextPage === "map" && state.data) requestAnimationFrame(renderMap);
}

function bindControls() {
  document.querySelectorAll("[data-page-link]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    showPage(link.dataset.pageLink);
  }));
  window.addEventListener("popstate", () => showPage(location.hash.slice(1), false));
  document.querySelectorAll("#walk-segment button").forEach((button) => button.addEventListener("click", () => {
    state.minutes = Number(button.dataset.minutes);
    document.querySelectorAll("#walk-segment button").forEach((item) => item.classList.toggle("active", item === button));
    $("walk-description").textContent = `도보 ${state.minutes}분 · 약 ${{ 5: "330m", 10: "670m", 15: "1km" }[state.minutes]}`;
    render();
  }));
  $("criteria-button").addEventListener("click", () => $("criteria-dialog").showModal());
  document.querySelector(".dialog-close").addEventListener("click", () => $("criteria-dialog").close());
  $("criteria-dialog").addEventListener("click", (event) => { if (event.target === $("criteria-dialog")) $("criteria-dialog").close(); });
  $("route-dialog-close").addEventListener("click", () => $("route-dialog").close());
  $("route-dialog").addEventListener("click", (event) => { if (event.target === $("route-dialog")) $("route-dialog").close(); });
  $("route-dialog").addEventListener("close", stopRouteAnimation);
  $("route-replay").addEventListener("click", animateRoutePreview);
  $("zoom-in").addEventListener("click", () => { state.zoom = Math.min(1.35, state.zoom + 0.1); renderMap(); });
  $("zoom-out").addEventListener("click", () => { state.zoom = Math.max(0.8, state.zoom - 0.1); renderMap(); });
  $("show-results").addEventListener("click", () => {
    document.querySelector(".map-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    document.querySelector(".map-panel").classList.add("attention");
    window.setTimeout(() => document.querySelector(".map-panel")?.classList.remove("attention"), 900);
  });
  $("mobile-menu").addEventListener("click", () => document.querySelector(".topbar nav").classList.toggle("open"));
}

async function init() {
  try {
    const response = await fetch("/api/life-fit");
    if (!response.ok) throw new Error("데이터 응답을 확인할 수 없습니다.");
    state.data = await response.json();
    $("facility-total").textContent = state.data.facilities.length.toLocaleString("ko-KR");
    $("area-total").textContent = state.data.meta.area_count || state.data.areas.length;
    $("condition-total").textContent = CATEGORIES.length;
    $("good-price-total").textContent = state.data.meta.good_price_total.toLocaleString("ko-KR");
    $("data-notice").textContent = state.data.meta.notice;
    $("updated-at").textContent = state.data.meta.updated_at;
    renderCriteria();
    bindControls();
    render();
    showPage(location.hash.slice(1) || "home", false);
  } catch (error) {
    document.body.innerHTML = `<main class="fatal"><h1>나혼자산다를 불러오지 못했습니다.</h1><p>${error.message}</p></main>`;
  }
}

init();
