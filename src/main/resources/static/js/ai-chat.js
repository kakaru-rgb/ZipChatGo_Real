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

  function appendAgentAnswer(text) {
    document.getElementById("aiAgentLoading")?.remove();

    const answer = document.createElement("article");
    answer.className = "ai-agent-answer";

    const icon = document.createElement("span");
    icon.className = "ai-agent-brand-icon ai-agent-mark";
    icon.dataset.aiBrandIcon = "";
    icon.setAttribute("aria-hidden", "true");

    const paragraph = document.createElement("p");
    paragraph.textContent = text;

    answer.append(icon, paragraph);
    messages.appendChild(answer);
    renderBrandIcons();
  }

  function getAppState() {
    return window.zipchatgoMapState?.getSnapshot?.() || {
      current_page: "map"
    };
  }

  async function requestAgentResponse(text) {
    appendLoading();
    scrollToLatest();

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: text,
          appState: getAppState()
        })
      });

      if (!response.ok) {
        throw new Error(`AI request failed with status ${response.status}`);
      }

      const data = await response.json();
      if (!data?.message || typeof data.message !== "string") {
        throw new Error("AI response did not contain a message");
      }

      appendAgentAnswer(data.message);
    } catch (error) {
      console.error("AI 에이전트 응답을 불러오지 못했습니다.", error);
      appendAgentAnswer("죄송합니다. 현재 AI 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      waitingForResponse = false;
      syncInput();
      scrollToLatest();
      input.focus();
    }
  }

  function sendMessage(rawText) {
    const text = rawText.trim();
    if (!text || waitingForResponse) return;

    suggestions?.remove();
    appendUserMessage(text);
    input.value = "";
    waitingForResponse = true;
    syncInput();
    requestAgentResponse(text);
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
