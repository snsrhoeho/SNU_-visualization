/* 현재 추천 결과를 읽는 AI 도우미. 추천 화면의 계산 로직은 app.js를 그대로 사용한다. */
(() => {
  const $ = (id) => document.getElementById(id);
  const pageToken = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const storageKey = "siheung-life-ai-chat-v3";
  const defaultMessage = "안녕! 코드를 입력하면 지금 고른 조건과 추천 결과를 바탕으로 같이 살펴볼게.";
  const welcomeMessage = "어디서부터 물어봐야 할지 모르겠어? 내가 도와줄게!\n\n• 왜 이 동네를 추천했는지 물어봐\n• 어떤 동네가 내 조건에 더 잘 맞는지 비교해봐\n• 이 주소에서 가까운 시설이나 교통을 찾아봐\n• 전월세까지 고려하면 어디가 더 좋은지 물어봐\n\n지금 보고 있는 화면을 기준으로 편하게 질문해줘.";
  const chat = { authenticated: false, messages: [], suggestions: [], loading: false };

  function loadMessages() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
      return Array.isArray(saved) ? saved.filter((item) => item && typeof item.text === "string").slice(-16) : [];
    } catch { return []; }
  }
  function saveMessages() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(chat.messages.filter((item) => !item.pending).slice(-16))); } catch {}
  }
  function rentSummary(area) {
    if (!area || !state.legalDongRent) return null;
    const row = state.legalDongRent.areas?.find((item) => item.id === area.id || item.name === area.name);
    if (!row) return null;
    const type = state.housingType === "monthly" ? "monthly" : "jeonse";
    const data = row[type] || {};
    return {
      area: area.name,
      transaction_type: state.housingType === "monthly" ? "월세" : "전세",
      transaction_count: Number(data.count || 0),
      median_deposit_manwon: data.median_deposit ?? null,
      median_monthly_rent_manwon: data.median_rent ?? null,
      median_converted_monthly_rent_manwon: data.median_converted_rent ?? null,
      converted_monthly_rent_middle_50_percent_manwon: data.p25_converted_rent != null && data.p75_converted_rent != null
        ? `${data.p25_converted_rent}~${data.p75_converted_rent}` : null,
      latest_transaction_date: data.latest_date || null,
      budget_matched_transactions: Number(row.budget?.matched_count || 0),
      budget_eligible_transactions: Number(row.budget?.eligible_count || 0),
      budget_match_rate_percent: row.budget?.match_rate ?? null,
    };
  }
  function visiblePageText() {
    const page = document.querySelector(".app-page:not([hidden])");
    // 화면에 실제로 보이는 문구를 함께 보내, 이전 페이지의 추천 결과로 답하는 일을 막는다.
    return (page?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 4500);
  }
  function context() {
    const ids = selectedPriority();
    const rows = ranking().slice(0, 3);
    const focusArea = activeArea();
    const comparedAreas = selectedAreas();
    const nearby = state.origin ? recommendationNearbyFacilities() : [];
    const currentPage = document.querySelector(".app-page:not([hidden])")?.id?.replace("page-", "") || "home";
    const rentMeta = state.legalDongRent?.meta || {};
    return {
      captured_at: new Date().toISOString(),
      current_page: currentPage,
      recommendation_step: state.recommendationStep,
      focused_area: focusArea ? focusArea.name : null,
      selected_comparison_areas: comparedAreas.map((area) => ({
        area: area.name,
        selected_facility_counts: ids.map((id) => ({ label: CATEGORY_META[id]?.label || id, count: estimate(area, id) })),
      })),
      selected_conditions: ids.map((id, index) => ({
        priority: index + 1,
        label: CATEGORY_META[id]?.label || id,
        focused_area_count: focusArea ? estimate(focusArea, id) : null,
      })),
      top_recommendations: rows.map((row, index) => ({
        rank: index + 1,
        area: row.area.name,
        conditions_met: `${row.met}/${row.total}`,
        facility_count: row.totalFacilities,
      })),
      housing_condition: {
        type: state.housingType,
        monthly_rent_range: state.housingType === "monthly" ? `${state.budgetMin}~${state.budgetMax}만원` : null,
        deposit_range: `${state.depositMin}~${state.depositMax}만원`,
      },
      housing_market: {
        source: rentMeta.source || null,
        period: rentMeta.period || null,
        scope: rentMeta.scope || null,
        conversion_rate: rentMeta.conversion_rate ?? null,
        conversion_formula: "환산 월세 = 월세 + 보증금 × 전월세전환율 ÷ 12",
        focused_area: rentSummary(focusArea),
        compared_areas: comparedAreas.map(rentSummary).filter(Boolean),
      },
      visible_page_text: visiblePageText(),
      address_analysis: state.origin ? {
        address: state.origin.address,
        walk_minutes: state.addressMinutes,
        selected_facility_count: nearby.length,
      } : null,
      note: "이 데이터는 사용자가 지금 보고 있는 페이지에서 질문을 누른 순간 생성된 최신 화면 요약입니다. visible_page_text와 current_page를 최우선으로 해석하고, 이전 대화·다른 페이지·추정 수치로 답하지 마세요.",
    };
  }
  function render() {
    const launcher = $("ai-launcher-image");
    const character = $("ai-character-image");
    const speaking = chat.messages.some((item) => item.role === "assistant" && !item.pending);
    const image = chat.loading ? "guide-reply.png" : (speaking ? "guide-speaking.png" : "guide-thinking.png");
    if (launcher) launcher.src = `/static/assets/chatbot/${image}`;
    if (character) {
      character.src = `/static/assets/chatbot/${image}`;
      character.classList.toggle("is-responding", chat.loading);
    }
    const loginGate = $("ai-login-gate");
    // 일부 배포 브라우저에서 .ai-login-gate의 display:grid 규칙이 hidden 속성을 덮어썼다.
    // 속성과 인라인 표시 상태를 함께 바꿔 인증 후 안내막이 남지 않게 한다.
    loginGate.hidden = chat.authenticated;
    loginGate.style.display = chat.authenticated ? "none" : "grid";
    $("ai-chat-input").disabled = !chat.authenticated || chat.loading;
    $("ai-chat-form").querySelector("button").disabled = !chat.authenticated || chat.loading;
    $("ai-quick-actions").innerHTML = chat.authenticated
      ? (chat.suggestions.length
        ? chat.suggestions.map((item) => `<button type="button" data-ai-suggestion="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")
        : (chat.loading ? "<small>질문을 준비하는 중…</small>" : ""))
      : "";
    document.querySelectorAll("[data-ai-suggestion]").forEach((button) => button.addEventListener("click", () => ask(button.dataset.aiSuggestion)));
    $("ai-chat-messages").innerHTML = chat.messages.map((message) => {
      if (message.pending) return '<div class="ai-message-row assistant"><img class="is-responding" src="/static/assets/chatbot/guide-reply.png" alt="" /><article class="ai-message assistant"><span class="ai-message-label">AI GUIDE</span><i class="ai-typing"><b></b><b></b><b></b></i></article></div>';
      const klass = message.role === "user" ? "user" : "assistant";
      const avatar = message.role === "assistant" ? '<img src="/static/assets/chatbot/guide-speaking.png" alt="" />' : "";
      return `<div class="ai-message-row ${klass}">${avatar}<article class="ai-message ${klass}"><span class="ai-message-label">${klass === "user" ? "YOU" : "AI GUIDE"}</span>${escapeHtml(message.text).replace(/\n/g, "<br>")}</article></div>`;
    }).join("");
    const box = $("ai-chat-messages");
    box.scrollTop = box.scrollHeight;
  }
  async function suggest() {
    if (!chat.authenticated || chat.loading) return;
    try {
      const response = await fetch("/api/chat/suggestions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Chat-Page-Token": pageToken },
        body: JSON.stringify({ message: "현재 추천 결과에서 물어볼 만한 질문을 3개 제안해줘.", context: context() }),
      });
      const payload = await response.json();
      chat.suggestions = response.ok ? (payload.suggestions || []).slice(0, 3) : [];
    } catch { chat.suggestions = []; }
    render();
  }
  async function ask(question) {
    if (!question?.trim() || !chat.authenticated || chat.loading) return;
    chat.messages.push({ role: "user", text: question.trim() }, { role: "assistant", text: "", pending: true });
    chat.loading = true;
    render();
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Chat-Page-Token": pageToken },
        body: JSON.stringify({ message: question.trim(), context: context() }),
      });
      const payload = await response.json();
      chat.messages = chat.messages.filter((item) => !item.pending);
      if (!response.ok) throw new Error(payload.detail || "AI 응답을 불러오지 못했습니다.");
      chat.messages.push({ role: "assistant", text: payload.answer });
    } catch (error) {
      chat.messages = chat.messages.filter((item) => !item.pending);
      chat.messages.push({ role: "assistant", text: error.message || "AI 응답을 불러오지 못했습니다." });
    } finally {
      chat.loading = false;
      saveMessages();
      render();
    }
  }
  async function verifyCode(code) {
    const message = $("ai-login-message");
    message.textContent = "확인 중…";
    try {
      const response = await fetch("/api/auth/team-code", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Chat-Page-Token": pageToken },
        body: JSON.stringify({ code }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "팀 코드가 맞지 않습니다.");
      chat.authenticated = true;
      chat.messages = [{ role: "assistant", text: welcomeMessage }];
      saveMessages();
      render();
      suggest();
    } catch (error) {
      message.textContent = error.message || "팀 코드가 맞지 않습니다.";
    }
  }
  async function checkAuth() {
    try {
      const response = await fetch("/api/auth/status", { headers: { "X-Chat-Page-Token": pageToken } });
      const payload = await response.json();
    chat.authenticated = Boolean(payload.authenticated);
    } catch { chat.authenticated = false; }
    if (chat.authenticated && chat.messages.length === 1 && chat.messages[0].text === defaultMessage) {
      chat.messages = [{ role: "assistant", text: welcomeMessage }];
      saveMessages();
    }
    render();
    if (chat.authenticated) suggest();
  }
  function init() {
    chat.messages = loadMessages();
    if (!chat.messages.length) chat.messages = [{ role: "assistant", text: defaultMessage }];
    $("ai-analysis-launcher").addEventListener("click", () => {
      const dialog = $("ai-analysis-dialog");
      if (!dialog.open) dialog.showModal();
      render();
      suggest();
    });
    $("ai-dialog-close").addEventListener("click", () => $("ai-analysis-dialog").close());
    $("ai-analysis-dialog").addEventListener("click", (event) => { if (event.target === $("ai-analysis-dialog")) event.target.close(); });
    $("ai-team-code-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const input = $("ai-team-code");
      const code = input.value.trim();
      if (!code) return;
      input.value = "";
      verifyCode(code);
    });
    $("ai-chat-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const input = $("ai-chat-input");
      const question = input.value.trim();
      if (!question) return;
      input.value = "";
      ask(question);
    });
    $("ai-chat-reset").addEventListener("click", () => {
      chat.messages = [{ role: "assistant", text: chat.authenticated ? welcomeMessage : defaultMessage }];
      saveMessages();
      render();
    });
    checkAuth();
  }
  init();
})();
