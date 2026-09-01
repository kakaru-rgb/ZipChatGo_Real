(() => {
  const panel = document.getElementById("aiAgentPanel");
  const launcher = document.getElementById("aiAgentLauncher");
  const closeButton = document.getElementById("aiAgentClose");
  const messages = document.getElementById("aiAgentMessages");
  const suggestions = document.getElementById("aiAgentSuggestions");
  const form = document.getElementById("aiAgentForm");
  const input = document.getElementById("aiAgentInput");
  const sendButton = document.getElementById("aiAgentSend");

  if (!panel || !launcher || !closeButton || !messages || !form || !input || !sendButton) return;

  let waitingForResponse = false;

  function renderBrandIcons() {
    document.querySelectorAll("[data-ai-brand-icon]").forEach(icon => {
      icon.innerHTML = '<i class="ti ti-robot" aria-hidden="true"></i>';
    });
  }

  function setPanelOpen(open) {
    panel.classList.toggle("is-open", open);
    document.body.classList.toggle("ai-agent-open", open);
    panel.setAttribute("aria-hidden", String(!open));
    launcher.hidden = open;
    launcher.setAttribute("aria-expanded", String(open));

    if (open) window.setTimeout(() => input.focus(), 220);
    else launcher.focus();
  }

  function syncInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 112)}px`;
    sendButton.disabled = waitingForResponse || !input.value.trim();
  }

  function scrollToLatest() {
    messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
  }

  function appendUserMessage(text) {
    const message = document.createElement("div");
    message.className = "ai-agent-user-message";
    message.textContent = text;
    messages.appendChild(message);
  }

  function appendLoading() {
    const loading = document.createElement("div");
    loading.className = "ai-agent-answer ai-agent-loading";
    loading.id = "aiAgentLoading";
    loading.setAttribute("aria-label", "AI 에이전트가 답변을 작성하고 있습니다");
    loading.innerHTML = "<span></span><span></span><span></span>";
    messages.appendChild(loading);
  }

  function appendSampleAnswer() {
    document.getElementById("aiAgentLoading")?.remove();

    const answer = document.createElement("article");
    answer.className = "ai-agent-answer";
    answer.innerHTML = `
      <span class="ai-agent-brand-icon ai-agent-mark" data-ai-brand-icon aria-hidden="true"></span>
      <p>요청하신 조건을 확인했어요.</p>
      <p>현재는 채팅 화면을 확인하기 위한 예시 응답이며, 실제 매물 검색 기능은 AI 에이전트 연동 후 제공될 예정입니다.</p>
      <ul>
        <li><strong>지역과 출퇴근 조건</strong>을 기준으로 후보를 찾습니다.</li>
        <li><strong>예산, 면적, 세대수</strong> 등 상세 조건을 함께 비교합니다.</li>
        <li>추천 결과에는 매물 정보와 추천 이유가 문서 형태로 표시됩니다.</li>
      </ul>
    `;
    messages.appendChild(answer);
    renderBrandIcons();
  }

  function requestAgentResponse() {
    // FastAPI 연동 시 이 함수의 임시 응답을 Spring Boot API 호출로 교체합니다.
    appendLoading();
    scrollToLatest();

    window.setTimeout(() => {
      appendSampleAnswer();
      waitingForResponse = false;
      syncInput();
      scrollToLatest();
      input.focus();
    }, 700);
  }

  function sendMessage(rawText) {
    const text = rawText.trim();
    if (!text || waitingForResponse) return;

    suggestions?.remove();
    appendUserMessage(text);
    input.value = "";
    waitingForResponse = true;
    syncInput();
    requestAgentResponse();
  }

  launcher.addEventListener("click", () => setPanelOpen(true));
  closeButton.addEventListener("click", () => setPanelOpen(false));
  input.addEventListener("input", syncInput);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage(input.value);
    }
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    sendMessage(input.value);
  });
  suggestions?.addEventListener("click", event => {
    const button = event.target.closest("[data-ai-question]");
    if (button) sendMessage(button.dataset.aiQuestion || "");
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) setPanelOpen(false);
  });

  renderBrandIcons();
  syncInput();
})();
