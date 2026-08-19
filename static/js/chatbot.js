/* 현재 추천 결과를 읽는 AI 도우미. 추천 화면의 계산 로직은 app.js를 그대로 사용한다. */
(() => {
  const $ = (id) => document.getElementById(id);
  const pageToken = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const storageKey = "siheung-life-ai-chat-v2";
  const defaultMessage = "안녕! 코드를 입력하면 지금 고른 조건과 추천 결과를 바탕으로 같이 살펴볼게.";
  const chat = { authenticated: false, messages: [], suggestions: [], loading: false };

  function loadMessages() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
      return Array.isArray(saved) ? saved.filter((item) => item && typeof item.text === "string").slice(-16) : [];
    } catch { return []; }
  }
  function saveMessages() {
    try { localStorage.setItem(storageKey, JSON.stringify(chat.messages.filter((item) => !item.pending).slice(-16))); } catch {}
  }
  function context() {
    const ids = selectedPriority();
    const rows = ranking().slice(0, 3);
    return {
      selected_conditions: ids.map((id, index) => ({
        priority: index + 1,
        label: CATEGORY_META[id]?.label || id,
        count: estimate(activeArea(), id),
      })),
      top_recommendations: rows.map((row, index) => ({
        rank: index + 1,
        area: row.area.name,
        conditions_met: `${row.met}/${row.total}`,
        facility_count: row.totalFacilities,
      })),
      note: "추천은 등록된 시설 좌표와 선택 조건의 법정동별 비교값을 기반으로 한 탐색용 결과입니다.",
    };
  }
  function render() {
    const launcher = $("ai-launcher-image");
    const character = $("ai-character-image");
    const speaking = chat.messages.some((item) => item.role === "assistant" && !item.pending);
    const image = speaking ? "guide-speaking.png" : "guide-thinking.png";
    if (launcher) launcher.src = `/static/assets/chatbot/${image}`;
    if (character) character.src = `/static/assets/chatbot/${image}`;
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
      if (message.pending) return '<div class="ai-message-row assistant"><img src="/static/assets/chatbot/guide-thinking.png" alt="" /><article class="ai-message assistant"><span class="ai-message-label">AI GUIDE</span><i class="ai-typing"><b></b><b></b><b></b></i></article></div>';
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
      chat.messages = [{ role: "assistant", text: "인증됐어! 지금 화면에서 궁금한 점을 편하게 물어봐." }];
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
      chat.messages = [{ role: "assistant", text: chat.authenticated ? "새로 시작할게. 지금 결과에서 무엇이 궁금해?" : defaultMessage }];
      saveMessages();
      render();
    });
    checkAuth();
  }
  init();
})();
