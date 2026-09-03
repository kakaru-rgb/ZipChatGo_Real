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

  function renderSafeMarkdown(text) {
    const content = document.createElement("div");
    content.className = "ai-agent-markdown";

    if (!window.marked?.parse || !window.DOMPurify?.sanitize) {
      content.classList.add("is-plain-text");
      content.textContent = text;
      return content;
    }

    try {
      const html = window.marked.parse(text, {
        breaks: true,
        gfm: true
      });
      content.innerHTML = window.DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
          "p", "br", "strong", "em", "ul", "ol", "li",
          "blockquote", "code", "pre", "h1", "h2", "h3", "hr"
        ],
        ALLOWED_ATTR: [],
        ALLOW_ARIA_ATTR: false,
        ALLOW_DATA_ATTR: false
      });
    } catch (error) {
      console.error("AI 답변의 Markdown을 표시하지 못했습니다.", error);
      content.classList.add("is-plain-text");
      content.textContent = text;
    }

    return content;
  }

  function appendAgentAnswer(text, actions = []) {
    document.getElementById("aiAgentLoading")?.remove();

    const answer = document.createElement("article");
    answer.className = "ai-agent-answer";

    const icon = document.createElement("span");
    icon.className = "ai-agent-brand-icon ai-agent-mark";
    icon.dataset.aiBrandIcon = "";
    icon.setAttribute("aria-hidden", "true");

    answer.append(icon, renderSafeMarkdown(text));

    const propertyActions = renderPropertyActionButtons(actions);
    if (propertyActions) answer.appendChild(propertyActions);

    messages.appendChild(answer);
    renderBrandIcons();
  }

  function renderPropertyActionButtons(actions) {
    if (!Array.isArray(actions)) return null;

    const propertyIds = actions
      .filter(action => action?.type === "HIGHLIGHT_PROPERTIES")
      .flatMap(action => Array.isArray(action.property_ids) ? action.property_ids : [])
      .map(String)
      .filter((propertyId, index, ids) => ids.indexOf(propertyId) === index)
      .slice(0, 5);

    if (!propertyIds.length) return null;

    const container = document.createElement("div");
    container.className = "ai-agent-property-actions";

    propertyIds.forEach((propertyId, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `매물 ${index + 1} 상세보기`;
      button.addEventListener("click", () => {
        window.zipchatgoMapActions?.execute?.([
          { type: "OPEN_PROPERTY", property_id: propertyId }
        ]);
      });
      container.appendChild(button);
    });

    return container;
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

      const actions = Array.isArray(data.actions) ? data.actions : [];
      appendAgentAnswer(data.message, actions);

      try {
        await window.zipchatgoMapActions?.execute?.(actions);
      } catch (actionError) {
        console.error("AI 지도 Action을 실행하지 못했습니다.", actionError);
      }
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
