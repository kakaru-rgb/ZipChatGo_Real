document.querySelectorAll(".faq-item > button").forEach(button => {
  button.addEventListener("click", () => {
    const item = button.closest(".faq-item");
    const isOpen = item.classList.toggle("open");
    button.setAttribute("aria-expanded", String(isOpen));
  });
});

const faqSearch = document.getElementById("faqSearch");
const faqTabs = document.querySelectorAll(".faq-tabs button");
const faqItems = document.querySelectorAll(".faq-item");
const faqEmpty = document.querySelector(".faq-empty");
let activeCategory = "all";

function filterFaq() {
  const keyword = faqSearch.value.trim().toLowerCase();
  let visibleCount = 0;

  faqItems.forEach(item => {
    const matchesCategory = activeCategory === "all" || item.dataset.category === activeCategory;
    const matchesKeyword = !keyword || item.textContent.toLowerCase().includes(keyword);
    const isVisible = matchesCategory && matchesKeyword;
    item.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });

  faqEmpty.hidden = visibleCount !== 0;
}

faqSearch.addEventListener("input", filterFaq);
faqTabs.forEach(tab => {
  tab.addEventListener("click", () => {
    activeCategory = tab.dataset.category;
    faqTabs.forEach(item => item.classList.toggle("active", item === tab));
    filterFaq();
  });
});

document.getElementById("inquiryForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const result = document.getElementById("formResult");
  const submitButton = form.querySelector("button[type='submit']");
  submitButton.disabled = true;
  result.textContent = "문의 내용을 접수하고 있습니다.";

  try {
    const response = await fetch(form.action, {
      method: form.method,
      body: new FormData(form),
      headers: { Accept: "application/json" }
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || "문의 접수에 실패했습니다.");
    result.textContent = `${payload.message} 빠르게 확인해 드릴게요.`;
    form.reset();
  } catch (error) {
    result.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});
