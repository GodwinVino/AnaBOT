const API_BASE = "http://localhost:8000/api";

let currentApp = "";
let kbLoaded = false;
let isLoading = false;

// Configure marked — safe, no HTML passthrough from untrusted sources
if (typeof marked !== "undefined") {
  marked.setOptions({
    breaks: true,       // single newline → <br>
    gfm: true,          // GitHub-flavoured Markdown (tables, strikethrough)
    pedantic: false,
  });
}

function renderMarkdown(text) {
  if (typeof marked === "undefined") return escapeHtml(text);
  return marked.parse(text);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Safe DOM helpers ──────────────────────────────────────────────────────────
function safeSetText(id, text) {
  const el = document.getElementById(id);
  if (!el) { console.warn("[DOM] Element not found:", id); return; }
  el.textContent = text;
}

function safeSetHTML(id, html) {
  const el = document.getElementById(id);
  if (!el) { console.warn("[DOM] Element not found:", id); return; }
  el.innerHTML = html;
}

function safeAddClass(id, cls) {
  const el = document.getElementById(id);
  if (el) el.classList.add(cls);
}

function safeRemoveClass(id, cls) {
  const el = document.getElementById(id);
  if (el) el.classList.remove(cls);
}

// ── DOM refs (resolved after DOMContentLoaded via init) ───────────────────────
let appSelect, btnLoad, btnReset, btnRefresh, btnTest;
let chatMessages, chatInput, btnSend, statusBar, activeAppLabel;
let testModal;

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  // Resolve all DOM refs here — guaranteed to exist
  appSelect      = document.getElementById("app-select");
  btnLoad        = document.getElementById("btn-load");
  btnReset       = document.getElementById("btn-reset");
  btnRefresh     = document.getElementById("btn-refresh");
  btnTest        = document.getElementById("btn-test");
  chatMessages   = document.getElementById("chat-messages");
  chatInput      = document.getElementById("chat-input");
  btnSend        = document.getElementById("btn-send");
  statusBar      = document.getElementById("status-bar");
  activeAppLabel = document.getElementById("active-app-label");
  testModal      = document.getElementById("test-modal");

  await loadApplications();
  appSelect.addEventListener("change", onAppChange);
  btnLoad.addEventListener("click", onLoadKB);
  btnReset.addEventListener("click", onReset);
  btnRefresh.addEventListener("click", onRefresh);
  btnTest.addEventListener("click", onTestKnowledge);
  btnSend.addEventListener("click", onSend);
  document.getElementById("test-modal-close") && document.getElementById("test-modal-close").addEventListener("click", () =>
    testModal.classList.remove("open")
  );
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
  });
  chatInput.addEventListener("input", autoResize);
  initQuizListeners();
}

function autoResize() {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 110) + "px";
}

// ── Applications ──────────────────────────────────────────────────────────────
async function loadApplications() {
  try {
    const res = await fetch(`${API_BASE}/applications`);
    const data = await res.json();
    const apps = data.applications || [];
    appSelect.innerHTML = '<option value="">Select an application</option>';
    apps.forEach(app => {
      const opt = document.createElement("option");
      opt.value = app;
      opt.textContent = app;
      appSelect.appendChild(opt);
    });
    if (apps.length === 0)
      showStatus("No applications found. Add folders to data/applications/", "error");
  } catch {
    showStatus("Cannot connect to backend. Make sure the server is running.", "error");
  }
}

function onAppChange() {
  btnLoad.disabled = !appSelect.value;
}

// ── Load KB ───────────────────────────────────────────────────────────────────
async function onLoadKB() {
  const app = appSelect.value;
  if (!app) return;

  btnLoad.disabled = true;
  btnLoad.innerHTML = '<span class="spinner"></span>';
  showStatus(`Loading knowledge base for ${app}...`, "info");

  try {
    const statusRes = await fetch(`${API_BASE}/status/${app}`);
    const statusData = await statusRes.json();

    if (!statusData.vectorstore_ready) {
      showStatus(`No vectorstore found for "${app}". Running ingestion...`, "info");
      const ingestRes = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application: app }),
      });
      if (!ingestRes.ok) {
        const err = await ingestRes.json();
        throw new Error(err.detail || "Ingestion failed");
      }
      const ingestData = await ingestRes.json();
      showStatus(
        `Ingested ${ingestData.chunks_indexed} chunks from ${ingestData.documents_loaded} documents. Loading...`,
        "info"
      );
    }

    const loadRes = await fetch(`${API_BASE}/load/${app}`, { method: "POST" });
    if (!loadRes.ok) {
      const err = await loadRes.json();
      throw new Error(err.detail || "Failed to load KB");
    }
    const loadData = await loadRes.json();
    const vectorCount = loadData.vectors || loadData.chunks || 0;

    currentApp = app;
    kbLoaded = true;
    setKBLoaded(true, vectorCount);
    showStatus(`✓ KB Loaded Successfully — ${vectorCount} vectors from FAISS DB`, "success");
    safeSetText("active-app-label", `— ${app}`);
    clearChat();
  } catch (e) {
    showStatus(`Error: ${e.message}`, "error");
    setKBLoaded(false, 0);
  } finally {
    btnLoad.innerHTML = "Load KB";
    btnLoad.disabled = false;
  }
}

function setKBLoaded(loaded, vectorCount = 0) {
  kbLoaded = loaded;
  if (chatInput)  chatInput.disabled  = !loaded;
  if (btnSend)    btnSend.disabled    = !loaded;
  if (btnRefresh) btnRefresh.disabled = !loaded;
  if (btnTest)    btnTest.disabled    = !loaded;
  if (btnReset)   btnReset.disabled   = !loaded;
  if (chatInput)  chatInput.placeholder = loaded
    ? "Type your question... (Enter to send)"
    : "Load KB to start chatting...";

  const sidebarInfo = document.getElementById("sidebar-info");
  if (sidebarInfo) {
    if (loaded && vectorCount > 0) {
      sidebarInfo.innerHTML = `✅ <strong>${vectorCount}</strong> vectors loaded`;
      sidebarInfo.style.color = "#1a7a1a";
    } else {
      sidebarInfo.textContent = "Until the KB is successfully loaded, all other buttons remain disabled.";
      sidebarInfo.style.color = "#999";
    }
  }

  // update empty state text only if elements exist
  if (loaded) {
    const emptyMsg  = document.getElementById("empty-msg");
    const emptyHint = document.getElementById("empty-hint");
    if (emptyMsg)  emptyMsg.textContent  = "No messages yet";
    if (emptyHint) emptyHint.textContent = "Type your question below";
  }
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function onReset() {
  currentApp = "";
  kbLoaded = false;
  if (appSelect) appSelect.value = "";
  safeSetText("active-app-label", "");
  setKBLoaded(false, 0);
  clearChat();
  if (btnLoad)  btnLoad.disabled  = true;
  if (btnReset) btnReset.disabled = true;
  showStatus("Application reset.", "info");
  setTimeout(() => {
    const bar = document.getElementById("status-bar");
    if (bar) bar.classList.add("hidden");
  }, 2000);
}

// ── Refresh ───────────────────────────────────────────────────────────────────
async function onRefresh() {
  if (!currentApp) return;
  btnRefresh.disabled = true;
  btnRefresh.textContent = "⏳ Refreshing...";
  showStatus(`Re-ingesting ALL documents for ${currentApp}...`, "info");
  try {
    const res = await fetch(`${API_BASE}/refresh/${currentApp}`, { method: "POST" });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
    const data = await res.json();
    const count = data.vectors || data.chunks_indexed || 0;
    setKBLoaded(true, count);
    showStatus(
      `✓ Refreshed — ${data.documents_loaded} docs, ${data.chunks_indexed} chunks indexed`,
      "success"
    );
  } catch (e) {
    showStatus(`Refresh failed: ${e.message}`, "error");
  } finally {
    btnRefresh.disabled = false;
    btnRefresh.textContent = "🔄 Refresh document";
  }
}

// ── Test Knowledge — opens difficulty picker ──────────────────────────────────
function onTestKnowledge() {
  if (!kbLoaded) return;
  testModal.classList.add("open");
}

// ── Quiz state ────────────────────────────────────────────────────────────────
let quizQuestions  = [];
let quizCurrent    = 0;
let quizAnswers    = [];   // user's selected answer per question
let quizLevel      = "";

function initQuizListeners() {
  // Difficulty cards
  document.querySelectorAll(".level-card").forEach(card => {
    card.addEventListener("click", () => {
      const level = card.dataset.level;
      testModal.classList.remove("open");
      startQuiz(level);
    });
  });

  document.getElementById("test-modal-cancel").addEventListener("click", () =>
    testModal.classList.remove("open")
  );

  document.getElementById("btn-quiz-next").addEventListener("click", onQuizNext);
  document.getElementById("btn-quiz-retry").addEventListener("click", () => {
    closeQuizModal();
    testModal.classList.add("open");
  });
  document.getElementById("btn-quiz-close").addEventListener("click", closeQuizModal);
}

async function startQuiz(level) {
  quizLevel = level;
  quizQuestions = [];
  quizCurrent = 0;
  quizAnswers = [];

  const quizModal  = document.getElementById("quiz-modal");
  const quizBody   = document.getElementById("quiz-body");
  const quizFooter = document.getElementById("quiz-footer");
  const quizResults = document.getElementById("quiz-results");
  const quizResultsFooter = document.getElementById("quiz-results-footer");

  // Reset view
  quizBody.style.display = "block";
  quizFooter.style.display = "flex";
  quizResults.classList.remove("show");
  quizResultsFooter.style.display = "none";

  // Show loading state
  document.getElementById("quiz-title").textContent = `🧪 Generating ${level} Quiz...`;
  document.getElementById("quiz-meta").textContent = `Application: ${currentApp}`;
  document.getElementById("quiz-q-num").textContent = "";
  document.getElementById("quiz-question").textContent = "Please wait while questions are being generated...";
  document.getElementById("quiz-options").innerHTML = `
    <div style="text-align:center;padding:20px;color:#888">
      <div class="typing-dots" style="justify-content:center">
        <span></span><span></span><span></span>
      </div>
      <p style="margin-top:10px;font-size:13px">Generating questions from knowledge base...</p>
    </div>`;
  document.getElementById("quiz-explanation").classList.remove("show");
  document.getElementById("btn-quiz-next").disabled = true;
  document.getElementById("quiz-progress-bar").style.width = "0%";
  quizModal.classList.add("open");

  try {
    const res = await fetch(`${API_BASE}/quiz/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application: currentApp, level }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to generate quiz");

    quizQuestions = data.questions || [];
    if (quizQuestions.length === 0) throw new Error("No questions returned");

    document.getElementById("quiz-title").textContent = `🧪 ${level} Quiz`;
    renderQuizQuestion();
  } catch (e) {
    document.getElementById("quiz-question").textContent = `⚠️ Error: ${e.message}`;
    document.getElementById("quiz-options").innerHTML = "";
    showStatus(`Quiz error: ${e.message}`, "error");
  }
}

function renderQuizQuestion() {
  const q = quizQuestions[quizCurrent];
  const total = quizQuestions.length;

  document.getElementById("quiz-q-num").textContent = `Question ${quizCurrent + 1} of ${total}`;
  document.getElementById("quiz-question").textContent = q.question;
  document.getElementById("quiz-q-counter").textContent = `${quizCurrent + 1} / ${total}`;
  document.getElementById("quiz-explanation").classList.remove("show");
  document.getElementById("btn-quiz-next").disabled = true;
  document.getElementById("quiz-progress-bar").style.width =
    `${((quizCurrent) / total) * 100}%`;

  const optionsEl = document.getElementById("quiz-options");
  optionsEl.innerHTML = "";

  q.options.forEach((optText) => {
    const label = optText.charAt(0);   // "A", "B", "C", "D"
    const text  = optText.slice(2).trim(); // strip "A. "

    const div = document.createElement("div");
    div.className = "quiz-option";
    div.dataset.label = label;
    div.innerHTML = `<span class="opt-label">${label}</span><span>${escapeHtml(text)}</span>`;
    div.addEventListener("click", () => onSelectOption(div, label));
    optionsEl.appendChild(div);
  });
}

function onSelectOption(selectedDiv, label) {
  // Ignore if already answered
  if (document.querySelector(".quiz-option.correct, .quiz-option.wrong")) return;

  const q = quizQuestions[quizCurrent];
  quizAnswers[quizCurrent] = label;

  document.querySelectorAll(".quiz-option").forEach(opt => {
    opt.classList.add("disabled");
    const optLabel = opt.dataset.label;
    if (optLabel === q.answer) {
      opt.classList.add("correct");
    } else if (optLabel === label && label !== q.answer) {
      opt.classList.add("wrong");
    }
  });

  // Show explanation
  const explEl = document.getElementById("quiz-explanation");
  explEl.innerHTML = `<strong>💡 Explanation:</strong> ${escapeHtml(q.explanation)}`;
  explEl.classList.add("show");

  // Enable next / finish
  const btnNext = document.getElementById("btn-quiz-next");
  btnNext.disabled = false;
  btnNext.textContent = quizCurrent < quizQuestions.length - 1 ? "Next →" : "See Results";
}

function onQuizNext() {
  if (quizCurrent < quizQuestions.length - 1) {
    quizCurrent++;
    renderQuizQuestion();
  } else {
    showQuizResults();
  }
}

function showQuizResults() {
  const total   = quizQuestions.length;
  const correct = quizQuestions.filter((q, i) => quizAnswers[i] === q.answer).length;
  const pct     = Math.round((correct / total) * 100);

  // Hide question view, show results
  document.getElementById("quiz-body").style.display = "none";
  document.getElementById("quiz-footer").style.display = "none";
  document.getElementById("quiz-progress-bar").style.width = "100%";

  const resultsEl = document.getElementById("quiz-results");
  resultsEl.classList.add("show");
  document.getElementById("quiz-results-footer").style.display = "flex";

  // Score circle
  const circle = document.getElementById("score-circle");
  circle.className = "score-circle" + (pct >= 80 ? "" : pct >= 50 ? " mid" : " low");
  document.getElementById("score-fraction").textContent = `${correct}/${total}`;
  document.getElementById("score-pct").textContent = `${pct}%`;

  // Label
  const labels = [
    [80, "🏆 Excellent!", "Great job — you really know this material."],
    [50, "👍 Good Effort", "You're on the right track. Review the explanations below."],
    [0,  "📚 Keep Learning", "Review the knowledge base and try again."],
  ];
  const [, lbl, sub] = labels.find(([min]) => pct >= min);
  document.getElementById("result-label").textContent = lbl;
  document.getElementById("result-sublabel").textContent = sub;

  // Per-question review
  const reviewEl = document.getElementById("result-review");
  reviewEl.innerHTML = "";
  quizQuestions.forEach((q, i) => {
    const userAns    = quizAnswers[i] || "—";
    const isCorrect  = userAns === q.answer;
    const correctOpt = q.options.find(o => o.startsWith(q.answer + ".")) || q.answer;
    const userOpt    = q.options.find(o => o.startsWith(userAns + ".")) || userAns;

    const item = document.createElement("div");
    item.className = "result-item";
    item.innerHTML = `
      <div class="result-item-header">
        <span class="ri-icon">${isCorrect ? "✅" : "❌"}</span>
        <span>Q${i + 1}: ${escapeHtml(q.question)}</span>
      </div>
      ${!isCorrect ? `
      <div class="result-item-body">
        <div class="your-ans">Your answer: ${escapeHtml(userOpt)}</div>
        <div class="correct-ans">Correct answer: ${escapeHtml(correctOpt)}</div>
        <div class="expl">💡 ${escapeHtml(q.explanation)}</div>
      </div>` : ""}
    `;
    reviewEl.appendChild(item);
  });
}

function closeQuizModal() {
  const quizModal = document.getElementById("quiz-modal");
  quizModal.classList.remove("open");
  quizQuestions = [];
  quizCurrent = 0;
  quizAnswers = [];
}

// ── Chat ──────────────────────────────────────────────────────────────────────
async function onSend() {
  const question = chatInput.value.trim();
  if (!question || !kbLoaded || isLoading) return;

  isLoading = true;
  chatInput.value = "";
  chatInput.style.height = "auto";
  btnSend.disabled = true;

  hideChatEmpty();
  appendUserMessage(question);
  const typingEl = appendTyping();

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application: currentApp, question }),
    });
    const data = await res.json();
    removeTyping(typingEl);

    if (!res.ok) throw new Error(data.detail || "Chat failed");

    appendAssistantMessage(data.answer, data.sources, data.chunks_used);
  } catch (e) {
    removeTyping(typingEl);
    appendAssistantMessage(`⚠️ **Error:** ${e.message}`, [], 0);
  } finally {
    isLoading = false;
    btnSend.disabled = false;
    chatInput.focus();
  }
}

// ── Message builders ──────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "msg user";

  const avatar = makeAvatar("U", "user");
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
}

function appendAssistantMessage(markdownText, sources, chunksUsed) {
  const isNotAvailable = /not available in knowledge base/i.test(markdownText);

  const row = document.createElement("div");
  row.className = "msg assistant";

  const avatar = makeAvatar("A", "assistant");
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble" + (isNotAvailable ? " not-available" : "");

  // Render Markdown → HTML
  bubble.innerHTML = renderMarkdown(markdownText);

  // Footer: sources + chunk count
  if ((sources && sources.length > 0) || chunksUsed > 0) {
    const footer = document.createElement("div");
    footer.className = "msg-footer";

    if (sources && sources.length > 0) {
      const label = document.createElement("span");
      label.className = "msg-footer-label";
      label.textContent = "📄 Sources:";
      footer.appendChild(label);

      sources.forEach(s => {
        const tag = document.createElement("span");
        tag.className = "src-tag";
        tag.textContent = s;
        footer.appendChild(tag);
      });
    }

    if (chunksUsed > 0) {
      const badge = document.createElement("span");
      badge.className = "chunks-badge";
      badge.textContent = `🔍 ${chunksUsed} chunk${chunksUsed !== 1 ? "s" : ""} retrieved`;
      footer.appendChild(badge);
    }

    bubble.appendChild(footer);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
}

function appendTyping() {
  const row = document.createElement("div");
  row.className = "msg assistant";
  row.id = "typing-indicator";

  const avatar = makeAvatar("A", "assistant");
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = `
    <div style="font-size:12px;color:#94a3b8;font-style:italic;margin-bottom:4px">Thinking...</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>`;

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
  return row;
}

function makeAvatar(letter, role) {
  const el = document.createElement("div");
  el.className = "msg-avatar";
  el.textContent = letter;
  return el;
}

function removeTyping(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

function hideChatEmpty() {
  const el = document.getElementById("chat-empty");
  if (el) el.style.display = "none";
}

function clearChat() {
  chatMessages.innerHTML = "";
  const empty = document.createElement("div");
  empty.id = "chat-empty";
  empty.innerHTML = `
    <div class="empty-icon">💬</div>
    <p id="empty-msg">No messages yet</p>
    <p class="empty-sub" id="empty-hint">Type your question below</p>
  `;
  chatMessages.appendChild(empty);
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Status bar ────────────────────────────────────────────────────────────────
function showStatus(msg, type = "info") {
  const bar = document.getElementById("status-bar");
  if (!bar) return;
  bar.textContent = msg;
  bar.className = type === "error" ? "error" : type === "success" ? "success" : "";
  bar.classList.remove("hidden");
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", init);
