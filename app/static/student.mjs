import { apiRequest } from "./api.mjs";
import { formatElapsed, queueItem, showMessage, statusBadge } from "./ui.mjs";

const element = (id) => document.getElementById(id);
const form = element("request-form");
const fields = element("request-fields");
const submitButton = element("submit-request");
const pageSize = 10;
const storageKey = "cs-lab-help-queue:request-id";
const state = {
  offset: 0, visibleOffset: 0, total: 0, queue: [], hasLoaded: false,
  queueLoading: false, queueVersion: 0, submitting: false, trackedId: null,
  trackedRequest: null, trackingLoading: false, trackingVersion: 0,
};
let refreshTimer;
let lastAnnouncement = "";

function updatePageButtons() {
  element("previous-page").disabled = state.queueLoading || state.offset === 0;
  element("next-page").disabled = state.queueLoading || state.offset + pageSize >= state.total;
  element("refresh-queue").disabled = state.queueLoading;
}

function renderQueue() {
  element("queue-list").replaceChildren(...state.queue.map((request) => queueItem(request, state.trackedId)));
  element("queue-count").textContent = String(state.total);
  element("queue-labels").hidden = state.total === 0;
  element("queue-empty").hidden = state.total !== 0;
  element("page-summary").textContent = state.total === 0 ? "0 requests" :
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
  await Promise.allSettled([refreshQueue(), refreshTracking()]);
  scheduleRefresh();
}

function parseRequestId(value) {
  if (!/^[1-9]\d*$/.test(value)) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id <= 2147483647 ? id : null;
}

function rememberTracking(id) {
  try {
    if (id === null) sessionStorage.removeItem(storageKey);
    else sessionStorage.setItem(storageKey, String(id));
  } catch {
    // Some browsers block storage. The ID on screen still works for manual tracking.
  }
}

function updateFormState() {
  const active = state.trackedRequest && state.trackedRequest.status !== "resolved";
  const restoring = state.trackedId !== null && state.trackedRequest === null;
  fields.disabled = state.submitting || Boolean(active) || restoring;
  submitButton.textContent = state.submitting ? "Submitting…" : restoring ? "Loading request…" : active ? "Request active" : "Submit request";
  element("form-footnote").textContent = restoring ?
    "Restoring your request. You can stop tracking it to start a new one." : active ?
    "You’re tracking an active request. Follow it here, or stop tracking to submit another." :
    "Keep this page open to follow your request. Your queue position updates automatically.";
}

function adoptRequest(request) {
  const changed = state.trackedId !== request.id;
  state.trackedId = request.id;
  state.trackedRequest = request;
  rememberTracking(request.id);
  // Background refreshes should not overwrite an ID the student is typing.
  if (changed) element("request-id").value = String(request.id);
  element("tracking-empty").hidden = true;
  element("tracked-request").hidden = false;
  element("stop-tracking").hidden = false;
  if (request.status === "resolved" && element("form-message").classList.contains("success")) {
    showMessage(element("form-message"));
  }
  if (state.hasLoaded) renderQueue();
  updateFormState();
}

function renderTracking(request, position) {
  element("tracked-summary").textContent = `${request.student_name} · ${request.assignment} · #${request.id}`;
  element("tracked-status").replaceChildren(statusBadge(request));
  element("tracked-position").textContent = request.status === "pending" ?
    (position === null ? "Updating…" : `#${position}`) : "—";
  element("tracked-wait").textContent = formatElapsed(
    request.created_at, request.started_at ? Date.parse(request.started_at) : Date.now(),
  );
  const ta = request.assigned_ta || "A teaching assistant";
  element("tracked-guidance").textContent = request.status === "resolved" ?
    "Resolved. You can submit another request if you need more help." :
    request.status === "in_progress" ? `${ta} is helping you. Keep your code ready.` :
    request.assigned_ta ? `${ta} has claimed your request and will start shortly.` :
    "You’re in the queue. Keep working while you wait.";
  const announcement = `Request #${request.id}: ${element("tracked-status").textContent}.${
    request.status === "pending" && position !== null ? ` Queue position ${position}.` : ""
  }`;
  // Announce meaningful changes, rather than reading out the waiting clock every poll.
  if (announcement !== lastAnnouncement) {
    element("tracking-announcement").textContent = announcement;
    lastAnnouncement = announcement;
  }
}

function clearTracking() {
  state.trackingVersion += 1;
  state.trackedId = null;
  state.trackedRequest = null;
  state.trackingLoading = false;
  rememberTracking(null);
  element("tracked-request").hidden = true;
  element("tracking-empty").hidden = false;
  element("tracking-empty").textContent = "After you join, your status and queue position will appear here.";
  element("stop-tracking").hidden = true;
  element("track-button").disabled = false;
  element("track-button").textContent = "Track";
  element("tracking-announcement").textContent = "";
  lastAnnouncement = "";
  element("request-id").value = "";
  if (state.hasLoaded) renderQueue();
  updateFormState();
}

async function refreshTracking(id = state.trackedId, manual = false) {
  if (!id || (!manual && state.trackingLoading)) return;
  const version = ++state.trackingVersion;
  state.trackingLoading = true;
  element("track-button").disabled = true;
  if (manual || !state.trackedRequest) element("track-button").textContent = "Loading…";
  try {
    const request = await apiRequest(`/api/requests/${id}`);
    let position = null;
    let positionFailed = false;
    if (request.status === "pending") {
      try {
        position = (await apiRequest(`/api/requests/${id}/position`)).position;
      } catch {
        positionFailed = true;
      }
    }
    if (version !== state.trackingVersion) return;
    adoptRequest(request);
    renderTracking(request, position);
    showMessage(element("tracking-message"), positionFailed ?
      "Status updated, but the queue position couldn’t load. Use Refresh to try again." : "", "error");
  } catch (error) {
    if (version !== state.trackingVersion) return;
    if (error.status === 404) {
      if (id === state.trackedId) clearTracking();
      showMessage(element("tracking-message"), `Request #${id} wasn’t found. Check the ID and try again.`, "error");
    } else {
      showMessage(element("tracking-message"), state.trackedRequest ?
        "Couldn’t update the request. Showing its last known status; use Refresh to try again." :
        "Couldn’t load the request. Check your connection and try again.", "error");
    }
  } finally {
    if (version === state.trackingVersion) {
      state.trackingLoading = false;
      element("track-button").disabled = false;
      element("track-button").textContent = "Track";
    }
  }
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
  if (state.submitting || fields.disabled || !form.reportValidity()) return;
  clearFieldErrors();
  showMessage(element("form-message"));
  const payload = Object.fromEntries([...new FormData(form)].map(([name, value]) => [name, String(value).trim()]));
  state.submitting = true;
  fields.disabled = true;
  submitButton.textContent = "Submitting…";
  let firstInvalid;
  try {
    const request = await apiRequest("/api/requests", { method: "POST", body: payload });
    state.trackingVersion += 1;
    state.trackingLoading = false;
    adoptRequest(request);
    renderTracking(request, null);
    form.reset();
    element("description-count").textContent = "0 / 1000";
    showMessage(element("form-message"), `Request #${request.id} submitted. You’re in the queue.`, "success");
    state.offset = 0;
    await refreshAll();
    element("tracking-title").focus({ preventScroll: true });
    element("tracking").scrollIntoView({ block: "nearest" });
  } catch (error) {
    firstInvalid = displayFieldErrors(error.details || []);
    showMessage(element("form-message"), error.status === 0 ?
      "Couldn’t confirm the submission. Your form is kept; check the queue before trying again." : error.message, "error");
  } finally {
    state.submitting = false;
    updateFormState();
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
element("track-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.trackingLoading) return;
  const id = parseRequestId(element("request-id").value);
  if (id === null) {
    showMessage(element("tracking-message"), "Enter a whole request ID between 1 and 2147483647.", "error");
    return;
  }
  void refreshTracking(id, true);
});
element("stop-tracking").addEventListener("click", () => {
  const id = state.trackedId;
  clearTracking();
  showMessage(element("tracking-message"), `Stopped tracking #${id} on this tab. The server request is unchanged.`);
  showMessage(element("form-message"));
});
document.addEventListener("visibilitychange", () => {
  clearTimeout(refreshTimer);
  if (!document.hidden) void refreshAll();
});
window.addEventListener("pagehide", () => clearTimeout(refreshTimer));
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void refreshAll();
});

try {
  const stored = sessionStorage.getItem(storageKey);
  state.trackedId = stored ? parseRequestId(stored) : null;
  if (stored && state.trackedId === null) rememberTracking(null);
} catch {
  // Manual request-ID lookup remains available when browser storage is blocked.
}
if (state.trackedId) {
  element("request-id").value = String(state.trackedId);
  element("tracking-empty").textContent = `Loading request #${state.trackedId}…`;
  element("stop-tracking").hidden = false;
}
updateFormState();
element("track-button").disabled = false;
void refreshAll();
