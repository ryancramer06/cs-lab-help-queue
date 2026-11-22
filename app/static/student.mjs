import { apiRequest } from "./api.mjs";
import { queueItem, showMessage } from "./ui.mjs";

const element = (id) => document.getElementById(id);
const form = element("request-form");
const fields = element("request-fields");
const submitButton = element("submit-request");
const pageSize = 10;
const state = {
  offset: 0, visibleOffset: 0, total: 0, queue: [], hasLoaded: false,
  queueLoading: false, queueVersion: 0, submitting: false, trackedId: null,
};
let refreshTimer;

function updatePageButtons() {
  element("previous-page").disabled = state.queueLoading || state.offset === 0;
  element("next-page").disabled = state.queueLoading || state.offset + pageSize >= state.total;
  element("refresh-queue").disabled = state.queueLoading;
}

function renderQueue() {
  element("queue-list").replaceChildren(...state.queue.map((request) => queueItem(request, state.trackedId)));
  element("queue-count").textContent = String(state.total);
  element("queue-empty").hidden = state.total !== 0;
  element("page-summary").textContent = state.total === 0 ? "No active requests" :
    `Showing ${state.visibleOffset + 1}–${state.visibleOffset + state.queue.length} of ${state.total}`;
}

async function refreshQueue() {
  const version = ++state.queueVersion;
  state.queueLoading = true;
  updatePageButtons();
  try {
    const query = new URLSearchParams({ limit: String(pageSize), offset: String(state.offset) });
    const page = await apiRequest(`/api/requests?${query}`);
    // A newer page request may finish first. Don't replace it with an older response.
    if (version !== state.queueVersion) return;
    if (state.offset > 0 && state.offset >= page.total) {
      state.offset = Math.floor(Math.max(0, page.total - 1) / pageSize) * pageSize;
      return await refreshQueue();
    }
    state.queue = page.items;
    state.total = page.total;
    state.visibleOffset = state.offset;
    state.hasLoaded = true;
    renderQueue();
    showMessage(element("queue-message"));
    element("connection-state").classList.remove("offline");
    element("connection-state").textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  } catch (error) {
    if (version !== state.queueVersion) return;
    state.offset = state.visibleOffset;
    showMessage(element("queue-message"), state.hasLoaded ?
      "The queue couldn’t update. Showing the last results; use Refresh to try again." :
      "The queue is unavailable. Check your connection and use Refresh to try again.", "error");
    element("connection-state").textContent = "Queue unavailable";
    element("connection-state").classList.add("offline");
    if (!state.hasLoaded) element("page-summary").textContent = "Queue unavailable";
  } finally {
    if (version === state.queueVersion) {
      state.queueLoading = false;
      element("queue-loading").hidden = true;
      updatePageButtons();
    }
  }
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  if (!document.hidden) refreshTimer = setTimeout(refreshAll, 15_000);
}

async function refreshAll() {
  clearTimeout(refreshTimer);
  if (document.hidden) return;
  await refreshQueue();
  scheduleRefresh();
}

function clearFieldErrors() {
  for (const input of form.querySelectorAll("[aria-invalid]")) input.removeAttribute("aria-invalid");
  for (const message of form.querySelectorAll(".field-error")) message.hidden = true;
}

function displayFieldErrors(details) {
  let firstInvalid;
  for (const detail of details) {
    const name = detail.loc?.[0] === "body" ? detail.loc[1] : null;
    if (typeof name !== "string") continue;
    const input = form.elements.namedItem(name);
    const message = element(`${name.replaceAll("_", "-")}-error`);
    if (!input || !message) continue;
    input.setAttribute("aria-invalid", "true");
    message.textContent = detail.msg;
    message.hidden = false;
    firstInvalid ||= input;
  }
  return firstInvalid;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.submitting || !form.reportValidity()) return;
  clearFieldErrors();
  showMessage(element("form-message"));
  const payload = Object.fromEntries([...new FormData(form)].map(([name, value]) => [name, String(value).trim()]));
  state.submitting = true;
  fields.disabled = true;
  submitButton.textContent = "Submitting…";
  let firstInvalid;
  try {
    const request = await apiRequest("/api/requests", { method: "POST", body: payload });
    state.trackedId = request.id;
    element("request-id").value = String(request.id);
    form.reset();
    element("description-count").textContent = "0 / 1000";
    showMessage(element("form-message"), `Request #${request.id} submitted. You’re in the queue.`, "success");
    state.offset = 0;
    await refreshAll();
  } catch (error) {
    firstInvalid = displayFieldErrors(error.details || []);
    showMessage(element("form-message"), error.status === 0 ?
      "Couldn’t confirm the submission. Your form is kept; check the queue before trying again." : error.message, "error");
  } finally {
    state.submitting = false;
    fields.disabled = false;
    submitButton.textContent = "Submit request";
    firstInvalid?.focus();
  }
});

element("description").addEventListener("input", (event) => {
  element("description-count").textContent = `${event.target.value.length} / 1000`;
});
element("refresh-queue").addEventListener("click", refreshAll);
element("previous-page").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - pageSize);
  void refreshQueue();
});
element("next-page").addEventListener("click", () => {
  state.offset += pageSize;
  void refreshQueue();
});
document.addEventListener("visibilitychange", () => {
  clearTimeout(refreshTimer);
  if (!document.hidden) void refreshAll();
});
window.addEventListener("pagehide", () => clearTimeout(refreshTimer));

fields.disabled = false;
void refreshAll();
