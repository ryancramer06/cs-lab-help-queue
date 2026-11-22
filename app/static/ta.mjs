import { apiRequest } from "./api.mjs";
import { categoryLabel, showMessage } from "./ui.mjs";
import { createTaCard, requestAction, updateTaCard } from "./ta-ui.mjs";

const element = (id) => document.getElementById(id);
const filterForm = element("filter-form");
const pageSize = 10;
const storageKey = "cs-lab-help-queue:ta-name";
const state = {
  taName: "", filters: {}, visibleFilters: {}, offset: 0, visibleOffset: 0,
  items: [], total: 0, hasLoaded: false, loading: false, stale: false, version: 0,
  busy: null,
};
const cards = new Map();
let refreshTimer;

function validName(name) {
  return name.length > 0 && name.length <= 100 && !name.includes("\0");
}

function updateIdentity() {
  element("identity-summary").textContent = state.taName || "Choose a name to manage requests.";
  updateControls();
}

function updateControls() {
  const blocked = state.loading || Boolean(state.busy);
  element("previous-page").disabled = blocked || state.offset === 0;
  element("next-page").disabled = blocked || state.offset + pageSize >= state.total;
  element("refresh-requests").disabled = blocked;
  element("identity-fields").disabled = Boolean(state.busy);
  element("filter-fields").disabled = Boolean(state.busy);
  for (const request of state.items) {
    updateTaCard(cards.get(request.id), request, state.taName, {
      enabled: !blocked && !state.stale, busy: state.busy,
    });
  }
}

function renderRequests() {
  const list = element("ta-request-list");
  const visibleIds = new Set(state.items.map((request) => request.id));
  state.items.forEach((request, index) => {
    let card = cards.get(request.id);
    if (!card) {
      card = createTaCard(request, runAction);
      cards.set(request.id, card);
    }
    updateTaCard(card, request, state.taName);
    if (list.children[index] !== card.root) list.insertBefore(card.root, list.children[index] || null);
  });
  for (const [id, card] of cards) {
    if (!visibleIds.has(id)) {
      card.root.remove();
      cards.delete(id);
    }
  }
  const filters = state.visibleFilters;
  const view = filters.status === "resolved" ? "Resolved requests" : filters.status === "pending" ?
    "Pending requests" : filters.status === "in_progress" ? "In-progress requests" : "Active requests";
  element("view-title").textContent = view;
  element("request-count").textContent = String(state.total);
  element("filter-summary").textContent = `${view} · ${filters.assignment || "All assignments"} · ${filters.issue_category ? categoryLabel(filters.issue_category) : "All categories"}`;
  element("page-summary").textContent = state.total === 0 ? "0 requests" :
    `Showing ${state.visibleOffset + 1}–${state.visibleOffset + state.items.length} of ${state.total}`;
  element("queue-empty").hidden = state.total !== 0;
  const filtered = Object.keys(filters).length > 0;
  element("empty-title").textContent = filtered ? "No matching requests" : "No active requests";
  element("empty-description").textContent = filtered ? "Try another assignment, category, or status." : "New student requests will appear here.";
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  if (!document.hidden && !state.busy) refreshTimer = setTimeout(refreshRequests, 15_000);
}

async function refreshRequests() {
  clearTimeout(refreshTimer);
  if (document.hidden || state.busy) return false;
  const version = ++state.version;
  state.loading = true;
  updateControls();
  const requestedFilters = { ...state.filters };
  try {
    const query = new URLSearchParams({ ...requestedFilters, limit: String(pageSize), offset: String(state.offset) });
    const page = await apiRequest(`/api/requests?${query}`);
    if (version !== state.version) return false;
    if (state.offset > 0 && state.offset >= page.total) {
      state.offset = Math.floor(Math.max(0, page.total - 1) / pageSize) * pageSize;
      return await refreshRequests();
    }
    state.items = page.items;
    state.total = page.total;
    state.visibleOffset = state.offset;
    state.visibleFilters = requestedFilters;
    state.hasLoaded = true;
    state.stale = false;
    renderRequests();
    showMessage(element("queue-message"));
    element("connection-state").classList.remove("offline");
    element("connection-state").textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    return true;
  } catch (error) {
    if (version !== state.version) return false;
    state.stale = true;
    state.offset = state.visibleOffset;
    const message = error.status === 422 ? "Check the filters and try again." : state.hasLoaded ?
      "Couldn’t update the requests. Showing the last results; use Refresh to try again." :
      "Requests are unavailable. Check your connection and use Refresh to try again.";
    showMessage(element("queue-message"), message, "error");
    element("connection-state").textContent = "Queue unavailable";
    element("connection-state").classList.add("offline");
    if (!state.hasLoaded) element("page-summary").textContent = "Requests unavailable";
    return false;
  } finally {
    if (version === state.version) {
      state.loading = false;
      element("queue-loading").hidden = true;
      updateControls();
      scheduleRefresh();
    }
  }
}

async function runAction(id, action) {
  const request = state.items.find((item) => item.id === id);
  if (state.busy || state.loading || state.stale || !state.taName || !request ||
      requestAction(request, state.taName) !== action) return;
  const button = cards.get(id).buttons[action];
  const hadFocus = document.activeElement === button;
  const taName = state.taName;
  state.busy = { id, action };
  clearTimeout(refreshTimer);
  updateControls();
  showMessage(element("action-message"));
  try {
    // A write is sent once. If its response is lost, read the queue before offering another action.
    await apiRequest(`/api/requests/${id}/${action}`, { method: "POST", body: { ta_name: taName } });
    const messages = {
      claim: `Request #${id} is assigned to ${taName}. Choose Start work when you begin helping.`,
      start: `Started work on request #${id}.`,
      resolve: `Request #${id} is resolved. You can find it in Resolved history.`,
    };
    showMessage(element("action-message"), messages[action], "success");
  } catch (error) {
    const message = error.status === 409 ?
      `Request #${id} changed before this action completed. Check its updated status and assignee below.` :
      error.status === 404 ? `Request #${id} is no longer available. Refreshing the list.` :
      error.status === 422 ? "The action was rejected. Check your TA name and refresh before trying again." :
      `Couldn’t confirm the action on request #${id}. Check its latest status before trying again.`;
    showMessage(element("action-message"), message, "error");
  } finally {
    state.busy = null;
    state.stale = true;
    updateControls();
    await refreshRequests();
    // Move focus only if the user stayed on the action while waiting for its response.
    if (hadFocus && (document.activeElement === button || document.activeElement === document.body)) {
      const nextButton = cards.get(id)?.root.querySelector("[data-action]:not([hidden]):not(:disabled)");
      (nextButton || element("requests-title")).focus();
    }
  }
}

element("identity-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = element("ta-name").value.trim();
  if (!validName(name)) {
    element("ta-name").setAttribute("aria-invalid", "true");
    showMessage(element("identity-message"), "Enter a TA name between 1 and 100 characters.", "error");
    return;
  }
  state.taName = name;
  element("ta-name").value = name;
  element("ta-name").removeAttribute("aria-invalid");
  try {
    sessionStorage.setItem(storageKey, name);
  } catch {
    // The workspace still works if the browser refuses to remember this tab's name.
  }
  updateIdentity();
  showMessage(element("identity-message"), `Using ${name} for this tab.`, "success");
});

filterForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.filters = Object.fromEntries([...new FormData(filterForm)]
    .map(([name, value]) => [name, String(value).trim()]).filter(([, value]) => value !== ""));
  state.offset = 0;
  showMessage(element("action-message"));
  void refreshRequests();
});
element("reset-filters").addEventListener("click", () => {
  filterForm.reset();
  state.filters = {};
  state.offset = 0;
  showMessage(element("action-message"));
  void refreshRequests();
});
element("refresh-requests").addEventListener("click", refreshRequests);
async function changePage(offset) {
  const button = document.activeElement;
  state.offset = offset;
  if (await refreshRequests()) {
    // Pagination sits below the cards; bring the new page into view for keyboard users too.
    if (document.activeElement === button || document.activeElement === document.body) {
      element("requests-title").focus();
    }
  }
}
element("previous-page").addEventListener("click", () => void changePage(Math.max(0, state.offset - pageSize)));
element("next-page").addEventListener("click", () => void changePage(state.offset + pageSize));
document.addEventListener("visibilitychange", () => {
  clearTimeout(refreshTimer);
  if (!document.hidden) void refreshRequests();
});
window.addEventListener("pagehide", () => clearTimeout(refreshTimer));
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void refreshRequests();
});

try {
  const name = sessionStorage.getItem(storageKey)?.trim() || "";
  if (validName(name)) {
    state.taName = name;
    element("ta-name").value = name;
  }
} catch {
  // A display name can be entered again when session storage is unavailable.
}
updateIdentity();
element("identity-fields").disabled = false;
element("filter-fields").disabled = false;
void refreshRequests();
