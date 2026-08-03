const state = { data: null, area: "all", housing: "all", rate: 0.05, tableFiltered: false };
const $ = (id) => document.getElementById(id);
const won = (value) => `${Math.round(value).toLocaleString("ko-KR")}만원`;
const convertedRent = (deposit, monthly) => monthly + (deposit * state.rate / 12);

function privateRent(area) { return convertedRent(area.private_deposit, area.private_monthly); }
function publicRent(area) { return convertedRent(area.public_deposit, area.public_monthly); }
function activeAreas() { return state.area === "all" ? state.data.areas : state.data.areas.filter((area) => area.id === state.area); }
function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const i = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[i] : (sorted[i - 1] + sorted[i]) / 2;
}
function rentColor(value, min, max) {
  const t = max === min ? 0.5 : (value - min) / (max - min);
  const start = [254, 229, 216], end = [241, 102, 67];
  return `rgb(${start.map((v, i) => Math.round(v + (end[i] - v) * t)).join(",")})`;
}

function renderMetrics() {
  const areas = activeAreas();
  const privateMedian = median(areas.map(privateRent));
  const publicMedian = median(areas.map(publicRent));
  const units = areas.reduce((sum, area) => sum + area.supply_units, 0);
  const records = areas.reduce((sum, area) => sum + area.deals + area.notices, 0);
  $("private-rent").textContent = won(privateMedian);
  $("public-supply").textContent = `${units.toLocaleString("ko-KR")}호`;
  $("saving-rate").textContent = `${Math.max(0, (1 - publicMedian / privateMedian) * 100).toFixed(1)}%`;
  $("record-count").textContent = `${records.toLocaleString("ko-KR")}건`;
}

function selectArea(id) {
  state.area = state.area === id ? "all" : id;
  $("area-filter").value = state.area;
  render();
}

function renderMap() {
  const map = $("area-map");
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
  const low = [...areas].sort((a, b) => a.supply_units - b.supply_units)[0];
  const gap = [...areas].sort((a, b) => (privateRent(b) - publicRent(b)) - (privateRent(a) - publicRent(a)))[0];
  $("insight-panel").innerHTML = `<p class="eyebrow">READ THE PATTERN</p><h3>${state.area === "all" ? "시흥시 핵심 관찰" : `${areas[0].name} 관찰`}</h3>
    <div class="insight"><div class="insight-label">HIGH RENT</div><p><strong>${high.name}</strong>의 민간 환산월세는 <strong>${won(privateRent(high))}</strong>으로 선택 범위에서 가장 높습니다.</p></div>
    <div class="insight"><div class="insight-label">LOW SUPPLY</div><p><strong>${low.name}</strong>은 확인된 청년 공공임대 공급이 <strong>${low.supply_units}호</strong>로 가장 적습니다.</p></div>
    <div class="insight"><div class="insight-label">LARGEST GAP</div><p><strong>${gap.name}</strong>은 민간과 공공의 환산월세 차이가 <strong>${won(privateRent(gap) - publicRent(gap))}</strong>입니다.</p></div>`;
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
  const areas = state.data.areas, width = 560, height = 245, left = 40, right = 18, top = 19, bottom = 34;
  const maxX = Math.max(...areas.map((a) => a.supply_units)) + 4, maxY = Math.ceil(Math.max(...areas.map(privateRent)) / 10) * 10 + 5;
  const x = (value) => left + value * (width - left - right) / maxX;
  const y = (value) => top + (maxY - value) * (height - top - bottom) / (maxY - 35);
  const grids = [40, 50, 60].map((value) => `<line class="grid-line" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text class="axis-label" x="3" y="${y(value) + 3}">${value}</text>`).join("");
  $("scatter-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${grids}<line class="axis" x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}"/><line class="axis" x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}"/>${areas.map((area) => `<circle class="scatter-dot ${state.area === area.id ? "selected" : ""}" data-area="${area.id}" cx="${x(area.supply_units)}" cy="${y(privateRent(area))}" r="${4 + Math.sqrt(area.deals) * .65}"><title>${area.name}: 공급 ${area.supply_units}호, 민간 ${won(privateRent(area))}</title></circle><text class="scatter-label" x="${x(area.supply_units) + 7}" y="${y(privateRent(area)) + 3}">${area.name}</text>`).join("")}<text class="axis-label" x="${width - right}" y="${height - 8}" text-anchor="end">공급 호수 →</text><text class="axis-label" x="${left}" y="12">민간 환산월세</text></svg>`;
  $("scatter-chart").querySelectorAll(".scatter-dot").forEach((node) => node.addEventListener("click", () => selectArea(node.dataset.area)));
}

function renderBars() {
  const areas = state.data.areas, max = Math.max(...areas.flatMap((area) => [privateRent(area), publicRent(area)]));
  $("bar-chart").innerHTML = `<div class="bar-key"><span><i class="private"></i>민간</span><span><i class="public"></i>공공</span></div>${areas.map((area) => `<div class="bar-row" data-area="${area.id}" role="button" tabindex="0"><strong class="bar-name">${area.name}</strong><div class="bar-track"><div class="bar private" style="width:${privateRent(area) / max * 100}%"></div></div><div class="bar-track"><div class="bar public" style="width:${publicRent(area) / max * 100}%"></div></div><span class="bar-value">${won(privateRent(area))}</span></div>`).join("")}`;
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
  $("source-list").innerHTML = state.data.sources.map((source) => `<li><a href="${source.url}" target="_blank" rel="noopener noreferrer">${source.name} ↗</a><br/><span>${source.organization} · ${source.description}</span></li>`).join("");
}

function render() { renderMetrics(); renderMap(); renderInsights(); renderTrend(); renderScatter(); renderBars(); renderTable(); }

function bindControls() {
  $("area-filter").addEventListener("change", (event) => { state.area = event.target.value; render(); });
  $("housing-filter").addEventListener("change", (event) => { state.housing = event.target.value; renderTable(); });
  $("rate-filter").addEventListener("change", (event) => { state.rate = Number(event.target.value); render(); });
  $("reset-filters").addEventListener("click", () => { state.area = "all"; state.housing = "all"; state.rate = 0.05; $("area-filter").value = "all"; $("housing-filter").value = "all"; $("rate-filter").value = "0.05"; render(); });
  $("table-filter").addEventListener("click", () => { state.tableFiltered = !state.tableFiltered; renderTable(); });
}

async function init() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) throw new Error("데이터를 불러오지 못했습니다.");
    state.data = await response.json();
    const meta = state.data.meta;
    $("period-label").textContent = meta.period;
    $("updated-label").textContent = meta.updated_at;
    $("footer-updated").textContent = meta.updated_at;
    if (meta.data_mode === "demo") { const banner = $("demo-banner"); banner.textContent = `시연 모드 — ${meta.notice}`; banner.classList.add("show"); }
    state.data.areas.forEach((area) => $("area-filter").insertAdjacentHTML("beforeend", `<option value="${area.id}">${area.name}</option>`));
    renderSources(); bindControls(); render();
  } catch (error) {
    document.body.innerHTML = `<main class="fatal"><h1>데이터를 불러오지 못했습니다.</h1><p>${error.message}</p><p>서버의 <code>/health</code> 주소와 배포 로그를 확인하세요.</p></main>`;
  }
}

init();
