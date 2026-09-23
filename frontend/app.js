const API = "/api";
const state = { documents: [], documentId: null, analysis: null, view: "overview", token: sessionStorage.getItem("lexi-token") || "", chatHistory: [], asking: false, selectionRequest: 0 };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}

function headers() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch { /* Keep the status message. */ }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message, type = "") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  $("#toast-region").append(node);
  setTimeout(() => node.remove(), 4200);
}

function dateLabel(value) {
  if (!value) return "Recently added";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Recently added" : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fileBadge(name) {
  const docx = String(name).toLowerCase().endsWith(".docx");
  return `<span class="file-type-icon ${docx ? "docx" : ""}">${docx ? "DOC" : "PDF"}</span>`;
}

function sourceLine(item) {
  const location = [item.document, item.page ? `page ${item.page}` : "", item.section || (item.clause ? `clause ${item.clause}` : "")].filter(Boolean).join(" · ");
  return `<div class="evidence-meta">${esc(location || "Source")}</div>`;
}

function evidenceCard(title, text, source, badge = "") {
  return `<article class="evidence-card">${badge ? `<span class="${badge.className}">${esc(badge.text)}</span>` : ""}<h3>${esc(title)}</h3>${text ? `<p class="evidence-quote">${esc(text)}</p>` : ""}${source ? sourceLine(source) : ""}</article>`;
}

function currentDocument() {
  return state.documents.find(doc => doc.id === state.documentId);
}

function setView(view) {
  state.view = view;
  $$(".view").forEach(element => element.classList.toggle("active", element.id === `view-${view}`));
  $$(".nav-item").forEach(element => element.classList.toggle("active", element.dataset.view === view));
  const labels = { overview: "Overview", clauses: "Clauses", dates: "Important dates", attention: "Attention areas", ask: "Ask document", compare: "Compare documents", history: "Document history" };
  $("#breadcrumb-current").textContent = labels[view] || "Overview";
  if (["clauses", "dates", "attention", "ask"].includes(view) && !state.documentId) toast("Upload or select a document first.");
}

function renderSidebar() {
  $("#stat-documents").textContent = state.documents.length;
  $("#recent-documents").innerHTML = state.documents.length ? state.documents.slice(0, 4).map(doc => `<button type="button" class="recent-item ${doc.id === state.documentId ? "selected" : ""}" data-doc="${esc(doc.id)}" aria-current="${doc.id === state.documentId ? "page" : "false"}">${fileBadge(doc.name)}<span class="recent-item-name">${esc(doc.name)}</span><span class="recent-item-date">${esc(dateLabel(doc.created_at))}</span></button>`).join("") : '<div class="empty-recent">No documents yet. Upload one to begin.</div>';
  $("#full-history").innerHTML = state.documents.length ? state.documents.map(doc => `<div class="recent-item ${doc.id === state.documentId ? "selected" : ""}" data-doc="${esc(doc.id)}" role="button" tabindex="0" aria-current="${doc.id === state.documentId ? "page" : "false"}">${fileBadge(doc.name)}<span class="recent-item-name">${esc(doc.name)}</span><span class="recent-item-date">${esc(dateLabel(doc.created_at))}</span><button class="row-delete" data-delete="${esc(doc.id)}" title="Delete document" aria-label="Delete ${esc(doc.name)}">×</button></div>`).join("") : '<div class="history-empty-full">No documents in this workspace yet.</div>';
}

function renderAnalysis() {
  const doc = currentDocument();
  const analysis = state.analysis;
  if (!doc) {
    $("#document-title").textContent = "Start with a document";
    $("#document-subtitle").textContent = "Upload a PDF or Word document to get started.";
    $("#document-content").innerHTML = '<div class="empty-upload" id="dropzone"><div class="upload-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v3h16v-3"/></svg></div><strong>Drop a document here</strong><span>or <button id="choose-file" class="text-button">browse files</button> to upload</span><small>PDF or DOCX · Up to 25 MB</small></div>';
    $("#stat-clauses").textContent = "—";
    $("#stat-dates").textContent = "—";
    $("#stat-attention").textContent = "—";
    $("#attention-count").textContent = "0";
    $("#attention-count").textContent = "0";
    $("#clauses-view").innerHTML = emptyPanel("Select a document to view detected clauses.");
    $("#dates-view").innerHTML = emptyPanel("Select a document to view extracted dates.");
    $("#attention-view").innerHTML = emptyPanel("Select a document to view review prompts.");
    return;
  }

  if (!analysis) {
    $("#document-title").textContent = doc.name;
    $("#document-subtitle").textContent = "Opening document analysis…";
    $("#document-content").innerHTML = '<div class="document-loading"><span class="loading-spinner"></span><span>Loading this document…</span></div>';
    $("#stat-clauses").textContent = "—";
    $("#stat-dates").textContent = "—";
    $("#stat-attention").textContent = "—";
    return;
  }

  $("#document-title").textContent = doc.name;
  $("#document-subtitle").textContent = `Added ${dateLabel(doc.created_at)} · Evidence-linked document overview`;
  $("#stat-clauses").textContent = Object.keys(analysis.clauses || {}).length;
  $("#stat-dates").textContent = (analysis.important_dates || []).length;
  $("#stat-attention").textContent = (analysis.attention_areas || []).length;
  $("#attention-count").textContent = (analysis.attention_areas || []).length;
  const summarySources = (analysis.summary_sources || []).map(sourceLine).join("");
  const clauses = analysis.clauses || {};
  const overviewClauses = Object.entries(clauses).map(([category, entries]) => `<article class="overview-clause"><h4>${esc(category)}</h4>${entries.map(entry => `<p class="evidence-quote">${esc(entry.text || "A matching clause reference was detected, but no source text was returned.")}</p>${sourceLine(entry)}`).join("")}</article>`).join("");
  $("#document-content").innerHTML = `<div class="document-summary"><div class="selected-document">${fileBadge(doc.name)}<div><h3>${esc(doc.name)}</h3><p>${esc(analysis.document_type_purpose || "Document analysis")}</p></div></div><button class="more-button" data-delete="${esc(doc.id)}" title="Delete document" aria-label="Delete document">×</button></div><p class="summary-text">${esc(analysis.summary || "No summary text could be extracted from this document.")}</p>${summarySources}<section class="overview-clauses"><h3>Detected clauses and source details</h3>${overviewClauses || '<span class="source-caption">No common clause types detected.</span>'}</section>`;

  const clauseHtml = Object.entries(clauses).flatMap(([category, entries]) => entries.map((entry, i) => evidenceCard(`${category}${entries.length > 1 ? ` · ${i + 1}` : ""}`, entry.text, entry))).join("");
  $("#clauses-view").innerHTML = clauseHtml || emptyPanel("No common clause patterns were detected. A missing match does not mean a clause is absent.");
  const dates = analysis.important_dates || [];
  $("#dates-view").innerHTML = dates.length ? dates.map(item => evidenceCard(`<span class="date-badge">${esc(item.date)}</span>`, item.text, item)).join("") : emptyPanel("No dates were extracted from the available document text.");
  const prompts = analysis.attention_areas || [];
  $("#attention-view").innerHTML = prompts.length ? prompts.map(item => evidenceCard(item.finding, item.text, item, { className: "review-badge", text: item.label || "Review recommended" })).join("") : emptyPanel("No automated review prompts were detected.");
}

function emptyPanel(message) {
  return `<article class="evidence-card"><div class="empty-state">${esc(message)}</div></article>`;
}

async function refreshHistory() {
  try {
    state.documents = await api("/documents");
    if (state.documentId && !state.documents.some(doc => doc.id === state.documentId)) state.documentId = null;
    if (!state.documentId && state.documents.length) state.documentId = state.documents[0].id;
    renderSidebar();
    if (state.documentId) await selectDocument(state.documentId, false);
    else renderAnalysis();
  } catch (error) {
    renderSidebar();
    if (error.status === 401) {
      state.documents = [];
      state.documentId = null;
      state.analysis = null;
      renderSidebar();
      renderAnalysis();
      $("#token-status").textContent = "Access required";
      toast("This workspace requires an access token.", "error");
      openTokenDialog();
    }
    else toast(error.message, "error");
  }
}

async function selectDocument(id, updateView = true) {
  const requestId = ++state.selectionRequest;
  if (state.documentId !== id) resetChat();
  state.documentId = id;
  renderSidebar();
  state.analysis = null;
  renderAnalysis();
  try {
    const record = await api(`/documents/${encodeURIComponent(id)}`);
    if (requestId !== state.selectionRequest) return;
    state.analysis = record.analysis;
    renderAnalysis();
    renderSidebar();
    if (updateView) setView("overview");
  } catch (error) {
    if (requestId !== state.selectionRequest) return;
    state.analysis = null;
    $("#document-subtitle").textContent = "We couldn’t open this document.";
    $("#document-content").innerHTML = `<div class="document-load-error"><strong>${esc(error.status === 401 ? "Access token required" : "Document failed to load")}</strong><span>${esc(error.status === 401 ? "Add your workspace token to open this document." : error.message)}</span><button type="button" class="text-button" data-retry-doc="${esc(id)}">Try again</button></div>`;
    toast(error.message, "error");
    if (error.status === 401) openTokenDialog();
  }
}

function openTokenDialog() {
  $("#token-input").value = state.token;
  if (!$("#token-dialog").open) $("#token-dialog").showModal();
}

async function uploadFile(file) {
  if (!file) return;
  if (!/\.(pdf|docx)$/i.test(file.name)) return toast("Choose a PDF or DOCX document.", "error");
  if (file.size > 25 * 1024 * 1024) return toast("This file is larger than the 25 MB upload limit.", "error");
  const body = new FormData();
  body.append("file", file);
  toast("Uploading and analyzing your document…");
  try {
    const record = await api("/documents", { method: "POST", body });
    await refreshHistory();
    await selectDocument(record.id);
    setView("overview");
    toast("Your document is ready to explore.", "success");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#file-input").value = "";
  }
}

const chatWelcomeHtml = `<div class="chat-welcome"><span class="chat-orb">✳</span><h2>What would you like to know?</h2><p>Ask about obligations, dates, or specific terms. Answers include source citations.</p><div class="suggestions"><button class="suggestion">What are the payment terms?</button><button class="suggestion">How can this agreement end?</button><button class="suggestion">Does it renew automatically?</button></div></div>`;

function resetChat() {
  state.chatHistory = [];
  $("#chat-messages").innerHTML = chatWelcomeHtml;
}

function appendMessage(role, text, citations = [], mode = "", notice = "") {
  const welcome = $(".chat-welcome");
  if (welcome) welcome.remove();
  const article = document.createElement("article");
  article.className = `chat-message ${role}`;
  const speaker = document.createElement("div");
  speaker.className = "speaker";
  speaker.textContent = role === "user" ? "YOU" : mode === "llm" ? "AI ANSWER · DOCUMENT-GROUNDED" : mode === "extractive" ? "SOURCE PASSAGES · MODEL UNAVAILABLE" : mode === "error" ? "REQUEST ERROR" : "DOCUMENT EVIDENCE CHECK";
  const body = document.createElement("div");
  body.className = "message-text";
  body.textContent = text;
  article.append(speaker, body);
  if (notice) {
    const note = document.createElement("div");
    note.className = "message-notice";
    note.textContent = notice;
    article.append(note);
  }
  if (citations.length) {
    const list = document.createElement("div");
    list.className = "citation-list";
    citations.forEach(citation => {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      chip.textContent = [citation.document, citation.page ? `p. ${citation.page}` : "", citation.section || citation.clause || ""].filter(Boolean).join(" · ");
      list.append(chip);
    });
    article.append(list);
  }
  $("#chat-messages").append(article);
  article.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function askQuestion(question) {
  if (!state.documentId) return toast("Upload or select a document first.", "error");
  if (state.asking) return;
  state.asking = true;
  const requestedDocumentId = state.documentId;
  const input = $("#question-input");
  const send = $("#ask-form .send-button");
  input.disabled = true;
  send.disabled = true;
  appendMessage("user", question);
  input.value = "";
  const typing = document.createElement("div");
  typing.className = "chat-message assistant typing-message";
  typing.id = "typing-indicator";
  typing.textContent = "Searching the document and preparing a cited answer…";
  $("#chat-messages").append(typing);
  const history = state.chatHistory.slice(-8).map(turn => ({ role: turn.role, content: turn.content.slice(-1800) }));
  try {
    const result = await api(`/documents/${encodeURIComponent(state.documentId)}/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, history }) });
    if (state.documentId !== requestedDocumentId) return;
    $("#typing-indicator")?.remove();
    appendMessage("assistant", result.answer, result.citations || [], result.mode, result.notice);
    state.chatHistory.push({ role: "user", content: question }, { role: "assistant", content: result.answer });
    state.chatHistory = state.chatHistory.slice(-12);
  } catch (error) {
    if (state.documentId !== requestedDocumentId) return;
    $("#typing-indicator")?.remove();
    appendMessage("assistant", error.message, [], "error");
  } finally {
    state.asking = false;
    input.disabled = false;
    send.disabled = false;
    input.focus();
  }
}

async function compareFiles() {
  const fileA = $("#compare-a").files[0];
  const fileB = $("#compare-b").files[0];
  if (!fileA || !fileB) return;
  const button = $("#compare-button");
  button.disabled = true;
  button.textContent = "Comparing…";
  const body = new FormData();
  body.append("file_a", fileA);
  body.append("file_b", fileB);
  try {
    const result = await api("/compare", { method: "POST", body });
    const target = $("#compare-results");
    target.innerHTML = result.changes.length ? result.changes.map(item => `<article class="change-card"><div class="change-heading"><span class="change-label">${esc(item.category)}</span>${esc(item.change)}</div><div class="change-columns"><div class="change-column"><strong>OLD · ${esc(item.source[0]?.document || fileA.name)}${item.source[0]?.page ? ` · PAGE ${esc(item.source[0].page)}` : ""}</strong><p>${esc(item.old || "No matching text")}</p></div><div class="change-column"><strong>NEW · ${esc(item.source[1]?.document || fileB.name)}${item.source[1]?.page ? ` · PAGE ${esc(item.source[1].page)}` : ""}</strong><p>${esc(item.new || "No matching text")}</p></div></div></article>`).join("") : emptyPanel("No text changes were detected.");
    toast(`${result.changes.length} text change${result.changes.length === 1 ? "" : "s"} found.`, "success");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.innerHTML = 'Compare versions <span>→</span>';
  }
}

document.addEventListener("click", async event => {
  const nav = event.target.closest("[data-view]");
  if (nav) return setView(nav.dataset.view);
  const jump = event.target.closest("[data-navigate]");
  if (jump) return setView(jump.dataset.navigate);
  const deleteButton = event.target.closest("[data-delete]");
  if (deleteButton) {
    event.stopPropagation();
    try {
      await api(`/documents/${encodeURIComponent(deleteButton.dataset.delete)}`, { method: "DELETE" });
      if (state.documentId === deleteButton.dataset.delete) {
        state.documentId = null;
        state.analysis = null;
      }
      await refreshHistory();
      toast("Document deleted from this workspace.", "success");
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  const retryButton = event.target.closest("[data-retry-doc]");
  if (retryButton) return selectDocument(retryButton.dataset.retryDoc);
  const documentRow = event.target.closest("[data-doc]");
  if (documentRow) return selectDocument(documentRow.dataset.doc);
  if (event.target.closest("#banner-upload, #choose-file, #history-upload")) return $("#file-input").click();
  if (event.target.closest("#dropzone")) return $("#file-input").click();
  if (event.target.closest("#workspace-picker, #token-button")) {
    $("#token-input").value = state.token;
    $("#token-dialog").showModal();
    return;
  }
  if (event.target.closest("#save-token")) {
    state.token = $("#token-input").value.trim();
    if (state.token) sessionStorage.setItem("lexi-token", state.token);
    else sessionStorage.removeItem("lexi-token");
    state.documentId = null;
    state.analysis = null;
    resetChat();
    $("#token-dialog").close();
    $("#token-status").textContent = state.token ? "Access token set" : "Local mode";
    $("#workspace-label").textContent = state.token ? "Connected workspace" : "Local workspace";
    await refreshHistory();
    return;
  }
  if (event.target.closest("#clear-token")) {
    state.token = "";
    sessionStorage.removeItem("lexi-token");
    $("#token-input").value = "";
    $("#token-status").textContent = "Local mode";
    $("#workspace-label").textContent = "Local workspace";
    $("#token-dialog").close();
    return refreshHistory();
  }
  const suggestion = event.target.closest(".suggestion");
  if (suggestion) {
    $("#question-input").value = suggestion.textContent;
    return $("#ask-form").requestSubmit();
  }
  if (event.target.closest("#compare-button")) return compareFiles();
});

document.addEventListener("keydown", event => {
  const row = event.target.closest('#full-history [data-doc][role="button"]');
  if (row && (event.key === "Enter" || event.key === " ") && !event.target.closest("[data-delete]")) {
    event.preventDefault();
    row.click();
  }
});

$("#file-input").addEventListener("change", event => uploadFile(event.target.files[0]));
$("#compare-a").addEventListener("change", event => { $("#compare-a-name").textContent = event.target.files[0]?.name || "Choose a PDF or DOCX"; $("#compare-button").disabled = !($("#compare-a").files[0] && $("#compare-b").files[0]); });
$("#compare-b").addEventListener("change", event => { $("#compare-b-name").textContent = event.target.files[0]?.name || "Choose a PDF or DOCX"; $("#compare-button").disabled = !($("#compare-a").files[0] && $("#compare-b").files[0]); });
$("#ask-form").addEventListener("submit", event => { event.preventDefault(); const question = $("#question-input").value.trim(); if (question) askQuestion(question); });

document.addEventListener("dragover", event => {
  const target = event.target.closest("#dropzone");
  if (target) { event.preventDefault(); target.classList.add("dragging"); }
});
document.addEventListener("dragleave", event => {
  const target = event.target.closest("#dropzone");
  if (target) target.classList.remove("dragging");
});
document.addEventListener("drop", event => {
  const target = event.target.closest("#dropzone");
  if (target) { event.preventDefault(); target.classList.remove("dragging"); uploadFile(event.dataTransfer.files[0]); }
});

$("#today-label").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }).toUpperCase();
if (state.token) {
  $("#token-status").textContent = "Access token set";
  $("#workspace-label").textContent = "Connected workspace";
}
renderSidebar();
refreshHistory();
