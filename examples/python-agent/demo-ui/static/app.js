const composer = document.querySelector("#composer");
const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send-button");
const messagesElement = document.querySelector("#messages");
const suggestions = document.querySelector("#suggestions");
const resetButton = document.querySelector("#reset-button");
const statusDot = document.querySelector("#status-dot");
const statusText = document.querySelector("#status-text");

const conversation = [];

function setConnection(online) {
  statusDot.className = `status-dot ${online ? "online" : "offline"}`;
  statusText.textContent = online ? "Agent online" : "Agent offline";
}

async function checkReadiness() {
  try {
    const response = await fetch("/api/readiness", { cache: "no-store" });
    setConnection(response.ok);
  } catch {
    setConnection(false);
  }
}

function appendMessage(role, text, options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}-message${options.error ? " message-error" : ""}${options.pending ? " pending" : ""}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Citadel";

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;
  article.append(label, body);

  if (options.tools?.length) {
    const trace = document.createElement("div");
    trace.className = "tool-trace";
    trace.textContent = `Tool activity: ${options.tools.join(", ")}`;
    article.append(trace);
  }

  messagesElement.append(article);
  messagesElement.scrollTop = messagesElement.scrollHeight;
  return { article, body };
}

function extractResponse(payload) {
  if (payload.error) {
    throw new Error(payload.error.message || payload.error);
  }

  const texts = [];
  const tools = [];
  for (const item of payload.output || []) {
    if (["mcp_call", "function_call", "web_search_call", "file_search_call"].includes(item.type)) {
      tools.push(item.name || item.server_label || item.type.replaceAll("_", " "));
    }
    if (item.type !== "message") continue;
    for (const content of item.content || []) {
      if (content.text) texts.push(content.text);
      if (content.refusal) texts.push(content.refusal);
    }
  }

  if (!texts.length) throw new Error("The agent completed without returning a text response.");
  return { text: texts.join("\n\n"), tools: [...new Set(tools)] };
}

async function sendMessage(text) {
  suggestions.hidden = true;
  appendMessage("user", text);
  conversation.push({ role: "user", content: text });
  const pending = appendMessage("assistant", "Working through the governed toolbox...", { pending: true });
  sendButton.disabled = true;
  promptInput.disabled = true;

  try {
    const response = await fetch("/api/responses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: conversation, stream: false, store: false }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.message || payload.error || `Request failed (${response.status}).`);

    const result = extractResponse(payload);
    conversation.push({ role: "assistant", content: result.text });
    pending.article.remove();
    appendMessage("assistant", result.text, { tools: result.tools });
    setConnection(true);
  } catch (error) {
    pending.article.remove();
    appendMessage("assistant", error.message, { error: true });
    setConnection(false);
  } finally {
    sendButton.disabled = false;
    promptInput.disabled = false;
    promptInput.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text) return;
  promptInput.value = "";
  promptInput.style.height = "auto";
  sendMessage(text);
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 150)}px`;
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

suggestions.addEventListener("click", (event) => {
  if (event.target instanceof HTMLButtonElement) sendMessage(event.target.textContent);
});

resetButton.addEventListener("click", () => {
  conversation.length = 0;
  for (const message of messagesElement.querySelectorAll(".message:not(:first-child)")) message.remove();
  suggestions.hidden = false;
  promptInput.value = "";
  promptInput.focus();
});

checkReadiness();
setInterval(checkReadiness, 30_000);