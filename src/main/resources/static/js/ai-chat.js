(() => {
  const panel = document.getElementById("aiAgentPanel");
  const launcher = document.getElementById("aiAgentLauncher");
  const closeButton = document.getElementById("aiAgentClose");
  const resetButton = document.getElementById("aiAgentReset");
  const messages = document.getElementById("aiAgentMessages");
  const suggestions = document.getElementById("aiAgentSuggestions");
  const form = document.getElementById("aiAgentForm");
  const input = document.getElementById("aiAgentInput");
  const sendButton = document.getElementById("aiAgentSend");

  if (!panel || !launcher || !closeButton || !resetButton || !messages || !form || !input || !sendButton) return;

  let waitingForResponse = false;
  const HISTORY_MAX_MESSAGES = 8;
  const HISTORY_MAX_CHARACTERS = 8000;
  let conversationHistory = [];
  let recentContext = {
    recent_property_ids: [],
    last_referenced_property_id: null,
    recent_properties: []
  };

  function addHistoryMessage(role, content) {
    const normalized = String(content || "").trim().slice(0, 4000);
    if (!normalized) return;
    conversationHistory.push({ role, content: normalized });
    conversationHistory = conversationHistory.slice(-HISTORY_MAX_MESSAGES);
    while (
      conversationHistory.length > 1 &&
      conversationHistory.reduce((total, item) => total + item.content.length, 0) > HISTORY_MAX_CHARACTERS
    ) {
      conversationHistory.shift();
    }
  }

  function resetConversation() {
    if (waitingForResponse) return;
    conversationHistory = [];
    recentContext = { recent_property_ids: [], last_referenced_property_id: null, recent_properties: [] };
    messages.innerHTML = `
      <article class="ai-agent-answer ai-agent-welcome">
        <span class="ai-agent-brand-icon ai-agent-mark" data-ai-brand-icon aria-hidden="true"></span>
        <p>새 대화를 시작했어요.</p>
        <h2>어떤 집을 찾고 계신가요?</h2>
      </article>`;
    renderBrandIcons();
    input.focus();
  }

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
          "blockquote", "code", "pre", "h1", "h2", "h3", "hr", "a"
        ],
        ALLOWED_ATTR: ["href"],
        ALLOW_ARIA_ATTR: false,
        ALLOW_DATA_ATTR: false
      });
      content.querySelectorAll("a[href]").forEach(link => {
        try {
          const url = new URL(link.getAttribute("href"), window.location.origin);
          const isOfficialLawLink = url.protocol === "https:"
            && (url.hostname === "law.go.kr" || url.hostname.endsWith(".law.go.kr"));

          if (!isOfficialLawLink) {
            link.replaceWith(document.createTextNode(link.textContent || "외부 링크"));
            return;
          }

          link.href = url.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        } catch (error) {
          link.replaceWith(document.createTextNode(link.textContent || "잘못된 링크"));
        }
      });
    } catch (error) {
      console.error("AI 답변의 Markdown을 표시하지 못했습니다.", error);
      content.classList.add("is-plain-text");
      content.textContent = text;
    }

    return content;
  }

  function appendAgentAnswer(text, actions = [], responseContext = null) {
    document.getElementById("aiAgentLoading")?.remove();

    const answer = document.createElement("article");
    answer.className = "ai-agent-answer";

    const icon = document.createElement("span");
    icon.className = "ai-agent-brand-icon ai-agent-mark";
    icon.dataset.aiBrandIcon = "";
    icon.setAttribute("aria-hidden", "true");

    const content = renderSafeMarkdown(text);
    bindPropertyTitleLinks(content, actions, responseContext);
    answer.append(icon, content);

    messages.appendChild(answer);
    renderBrandIcons();
  }

  function bindPropertyTitleLinks(content, actions, responseContext) {
    if (!content || !Array.isArray(actions) || !responseContext) return;

    const highlightedIds = new Set(actions
      .filter(action => action?.type === "HIGHLIGHT_PROPERTIES")
      .flatMap(action => Array.isArray(action.property_ids) ? action.property_ids : [])
      .map(String)
      .filter(Boolean));
    if (!highlightedIds.size) return;

    const propertyIds = (responseContext.recent_property_ids || [])
      .map(String)
      .filter(propertyId => highlightedIds.has(propertyId));
    if (!propertyIds.length) return;

    const orderedList = Array.from(content.querySelectorAll("ol")).find(list => (
      Array.from(list.children).filter(child => child.tagName === "LI").length >= propertyIds.length
    ));
    if (!orderedList) return;

    const listItems = Array.from(orderedList.children)
      .filter(child => child.tagName === "LI")
      .slice(0, propertyIds.length);

    listItems.forEach((item, index) => {
      const title = item.querySelector(":scope > strong, :scope > p > strong");
      if (!title) return;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "ai-property-title-link";
      button.dataset.propertyId = propertyIds[index];
      button.textContent = title.textContent;
      button.addEventListener("click", () => openPropertyFromAiChat(propertyIds[index]));
      title.replaceWith(button);
    });
  }

  function openPropertyFromAiChat(propertyId) {
    const normalizedId = Number(propertyId);
    if (!Number.isInteger(normalizedId) || normalizedId < 1) return;

    recentContext.last_referenced_property_id = normalizedId;
    window.zipchatgoMapActions?.execute?.([
      { type: "OPEN_PROPERTY", property_id: String(normalizedId) }
    ]);
  }

  function normalizeRecentContext(value) {
    if (!value || typeof value !== "object") {
      return { recent_property_ids: [], last_referenced_property_id: null, recent_properties: [] };
    }

    return {
      recent_property_ids: Array.isArray(value.recent_property_ids)
        ? value.recent_property_ids.map(Number).filter(Number.isInteger).slice(0, 10)
        : [],
      last_referenced_property_id: value.last_referenced_property_id != null
        && Number.isInteger(Number(value.last_referenced_property_id))
        ? Number(value.last_referenced_property_id)
        : null,
      recent_properties: Array.isArray(value.recent_properties)
        ? value.recent_properties.slice(0, 10)
        : []
    };
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
          appState: getAppState(),
          history: conversationHistory,
          recentContext
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
      const responseContext = data.recent_context && typeof data.recent_context === "object"
        ? normalizeRecentContext(data.recent_context)
        : recentContext;
      appendAgentAnswer(data.message, actions, responseContext);
      recentContext = responseContext;
      addHistoryMessage("user", text);
      addHistoryMessage("assistant", data.message);

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
  resetButton.addEventListener("click", resetConversation);
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
