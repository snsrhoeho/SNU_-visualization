/* 법정동 기준의 주소 생활권·주거비·비교 기능. 기존 네이버 지도·챗봇 상태를 그대로 공유한다. */
(function () {
  function money(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toLocaleString()}만원` : "집계 없음";
  }

  function legalAreaName(area) {
    return area?.name || "선택한 법정동";
  }

  function compareRows() {
    return state.compareAreaIds.map((id) => areaById(id)).filter(Boolean);
  }

  function renderComparison() {
    const areas = compareRows();
    const count = document.getElementById("comparison-count");
    const picked = document.getElementById("comparison-picked");
    const button = document.getElementById("open-comparison");
    if (!count || !picked || !button) return;
    count.textContent = `${areas.length} / 2`;
    picked.innerHTML = areas.length
      ? areas.map((area) => `<button type="button" data-remove-compare="${area.id}">${legalAreaName(area)} <span>×</span></button>`).join("")
      : "<small>아직 고른 동네가 없어요.</small>";
    button.disabled = areas.length !== 2;
    picked.querySelectorAll("[data-remove-compare]").forEach((button) => {
      button.addEventListener("click", () => {
        state.compareAreaIds = state.compareAreaIds.filter((id) => id !== button.dataset.removeCompare);
        renderComparison();
      });
    });
  }

  function toggleComparison(areaId) {
    if (state.compareAreaIds.includes(areaId)) {
      state.compareAreaIds = state.compareAreaIds.filter((id) => id !== areaId);
    } else if (state.compareAreaIds.length < 2) {
      state.compareAreaIds = [...state.compareAreaIds, areaId];
    } else {
      state.compareAreaIds = [state.compareAreaIds[1], areaId];
    }
    renderComparison();
  }

  function renderComparisonDialog() {
    const areas = compareRows();
    if (areas.length !== 2) return;
    const ids = selectedPriority();
    document.getElementById("comparison-title").textContent = `${areas[0].name} · ${areas[1].name} 비교`;
    document.getElementById("comparison-summary").textContent = `현재 ${ids.length}개 생활 조건과 도보 ${state.minutes}분 기준으로 법정동별 시설 수를 비교했어.`;
    document.getElementById("comparison-rows").innerHTML = ids.map((id, index) => {
      const values = areas.map((area) => estimate(area, id));
      const max = Math.max(...values, 1);
      return `<section><header><span>${index + 1}순위</span><strong>${CATEGORY_META[id].icon} ${CATEGORY_META[id].label}</strong></header><div class="comparison-value-grid">${areas.map((area, areaIndex) => `<article><small>${area.name}</small><b>${values[areaIndex]}곳</b><i><em style="width:${Math.round(values[areaIndex] / max * 100)}%;background:${CATEGORY_META[id].color}"></em></i></article>`).join("")}</div></section>`;
    }).join("") || "<p>비교할 생활 조건을 먼저 선택해 주세요.</p>";
    document.getElementById("comparison-dialog").showModal();
  }

  async function loadHousingCosts() {
    const target = document.getElementById("budget-summary");
    if (!target) return;
    try {
      const response = await fetch("/api/housing-costs");
      if (!response.ok) throw new Error();
      state.housing = await response.json();
      const rent = state.housing.monthly?.median_rent;
      const deposit = state.housing.monthly?.median_deposit;
      target.textContent = `시흥시 월세 중위 ${money(rent)} · 보증금 중위 ${money(deposit)} (${state.housing.monthly?.sample_count || 0}건)`;
    } catch {
      target.textContent = "실거래가 요약을 불러오지 못했어요.";
    }
  }

  async function loadLegalDongRent() {
    const deposit = Number(document.getElementById("budget-deposit")?.value || 0);
    const rent = Number(document.getElementById("budget-rent")?.value || 0);
    const params = new URLSearchParams();
    if (deposit > 0) params.set("deposit_max", String(deposit));
    if (rent > 0) params.set("monthly_max", String(rent));
    try {
      const response = await fetch(`/api/legal-dong-rent?${params.toString()}`);
      if (!response.ok) throw new Error();
      state.rentData = await response.json();
      render();
    } catch {
      state.rentData = null;
    }
  }

  function applyBudgetHint() {
    const deposit = Number(document.getElementById("budget-deposit")?.value || 0);
    const rent = Number(document.getElementById("budget-rent")?.value || 0);
    const target = document.getElementById("budget-summary");
    if (!target || !state.housing) return;
    if (!deposit && !rent) {
      target.textContent = `시흥시 월세 중위 ${money(state.housing.monthly?.median_rent)} · 보증금 중위 ${money(state.housing.monthly?.median_deposit)} (${state.housing.monthly?.sample_count || 0}건)`;
      loadLegalDongRent();
      return;
    }
    const medianDeposit = Number(state.housing.monthly?.median_deposit || 0);
    const medianRent = Number(state.housing.monthly?.median_rent || 0);
    const depositOk = !deposit || medianDeposit <= deposit;
    const rentOk = !rent || medianRent <= rent;
    target.textContent = depositOk && rentOk
      ? `시흥시 월세 중위 거래는 설정 예산 안에 들어와요. 보증금 ${money(medianDeposit)} · 월세 ${money(medianRent)}`
      : `시흥시 전체 월세 중위는 보증금 ${money(medianDeposit)} · 월세 ${money(medianRent)}예요. 설정 예산과 차이가 있어요.`;
    loadLegalDongRent();
  }

  async function analyzeAddress(event) {
    event.preventDefault();
    const input = document.getElementById("address-input");
    const result = document.getElementById("address-result");
    const address = input.value.trim();
    if (!address) return;
    result.innerHTML = "<div class=\"address-loading\">주소와 주변 생활시설을 찾는 중…</div>";
    try {
      const geoResponse = await fetch(`/api/geocode?address=${encodeURIComponent(address)}`);
      const geo = await geoResponse.json();
      if (!geoResponse.ok) throw new Error(geo.detail || "주소를 찾지 못했습니다.");
      const categories = [...state.selected].join(",");
      const nearbyResponse = await fetch(`/api/nearby-facilities?lat=${geo.lat}&lng=${geo.lng}&radius=${walkRadius()}&categories=${encodeURIComponent(categories)}`);
      const nearby = await nearbyResponse.json();
      if (!nearbyResponse.ok) throw new Error(nearby.detail || "주변 시설을 찾지 못했습니다.");
      const grouped = (nearby.items || []).reduce((acc, item) => {
        (acc[item.category] ||= []).push(item);
        return acc;
      }, {});
      const categoriesToShow = selectedPriority().length ? selectedPriority() : Object.keys(grouped);
      result.innerHTML = `<header><span>주소 생활권</span><h2>${escapeHtml(geo.address)}</h2><p>직선거리 ${walkRadius().toLocaleString()}m 안에서 좌표가 확인된 시설을 보여줘.</p></header><div class="address-facility-groups">${categoriesToShow.map((id) => {
        const items = grouped[id] || [];
        const meta = CATEGORY_META[id] || { icon: "✦", label: id };
        return `<section><strong>${meta.icon} ${meta.label} <b>${items.length}곳</b></strong>${items.slice(0, 5).map((item) => `<p><span>${escapeHtml(item.name)}</span><small>${item.distance_m}m</small></p>`).join("") || "<p class=\"empty\">반경 안에 좌표가 확인된 시설이 없어요.</p>"}</section>`;
      }).join("") || "<p class=\"empty\">선택한 조건이 없어요. 동네 추천에서 먼저 조건을 골라 주세요.</p>"}</div>`;
      await drawAddressMap(geo, nearby.items || []);
    } catch (error) {
      result.innerHTML = `<div class="address-empty"><strong>분석하지 못했어요.</strong><p>${escapeHtml(error.message || "잠시 후 다시 시도해 주세요.")}</p></div>`;
    }
  }

  async function drawAddressMap(geo, facilities) {
    if (!state.naverKey) return;
    try {
      await loadNaverMaps(state.naverKey);
      if (!state.addressMap) state.addressMap = new naver.maps.Map("address-naver-map", { center: new naver.maps.LatLng(geo.lat, geo.lng), zoom: 15, zoomControl: true, mapDataControl: false });
      state.addressMarker?.setMap(null);
      state.addressMarkers.forEach((marker) => marker.setMap(null));
      state.addressMarkers = [];
      state.addressMap.setCenter(new naver.maps.LatLng(geo.lat, geo.lng));
      state.addressMarker = new naver.maps.Marker({ map: state.addressMap, position: new naver.maps.LatLng(geo.lat, geo.lng), title: geo.address });
      facilities.slice(0, 60).forEach((item) => {
        const meta = CATEGORY_META[item.category] || { color: "#257d57" };
        state.addressMarkers.push(new naver.maps.Marker({ map: state.addressMap, position: new naver.maps.LatLng(item.lat, item.lng), title: item.name, icon: { content: `<span class="facility-dot" style="--dot-color:${meta.color}"></span>`, size: new naver.maps.Size(12, 12), anchor: new naver.maps.Point(6, 6) } }));
      });
      document.getElementById("address-map-note").textContent = `${facilities.length}개 시설 · 주소 기준 직선거리 ${walkRadius().toLocaleString()}m`;
    } catch {
      document.getElementById("address-map-note").textContent = "네이버 지도를 불러오지 못했습니다.";
    }
  }

  function openAddressPage(updateHash = true) {
    state.page = "address";
    document.querySelectorAll(".app-page").forEach((item) => {
      const active = item.dataset.page === "address";
      item.hidden = !active;
      item.classList.toggle("active", active);
    });
    document.querySelectorAll("[data-page-link]").forEach((link) => link.classList.toggle("active", link.dataset.pageLink === "address"));
    if (updateHash && location.hash !== "#address") history.pushState(null, "", "#address");
    window.scrollTo({ top: 0, behavior: "smooth" });
    requestAnimationFrame(() => state.addressMap?.autoResize());
  }

  function installExperience() {
    const baseRender = render;
    render = function () {
      baseRender();
      renderComparison();
      document.querySelectorAll("[data-area-choice]").forEach((card) => {
        if (card.querySelector(".compare-toggle")) return;
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "compare-toggle";
        toggle.dataset.compareArea = card.dataset.areaChoice;
        toggle.textContent = state.compareAreaIds.includes(card.dataset.areaChoice) ? "비교 중" : "비교";
        toggle.addEventListener("click", (event) => { event.stopPropagation(); toggleComparison(card.dataset.areaChoice); toggle.textContent = state.compareAreaIds.includes(card.dataset.areaChoice) ? "비교 중" : "비교"; });
        card.append(toggle);
      });
    };
    document.querySelectorAll('[data-page-link="address"]').forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      openAddressPage();
    }, true));
    window.addEventListener("popstate", () => { if (location.hash === "#address") openAddressPage(false); });
    document.getElementById("open-comparison")?.addEventListener("click", renderComparisonDialog);
    document.querySelector("[data-close-comparison]")?.addEventListener("click", () => document.getElementById("comparison-dialog").close());
    document.getElementById("comparison-dialog")?.addEventListener("click", (event) => { if (event.target.id === "comparison-dialog") event.target.close(); });
    document.getElementById("address-form")?.addEventListener("submit", analyzeAddress);
    ["budget-deposit", "budget-rent"].forEach((id) => document.getElementById(id)?.addEventListener("input", applyBudgetHint));
    loadHousingCosts();
    loadLegalDongRent();
    render();
  }

  const timer = window.setInterval(() => {
    if (!window.state && typeof state === "undefined") return;
    if (!state.data) return;
    window.clearInterval(timer);
    installExperience();
  }, 80);
})();
