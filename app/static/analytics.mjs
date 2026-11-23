import { apiRequest } from "./api.mjs";
import { categoryLabel, showMessage } from "./ui.mjs";

const element = (id) => document.getElementById(id);
const number = new Intl.NumberFormat();
const shortNumber = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });
const utcDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
let hasLoaded = false;
let loading = false;
let refreshTimer;

function duration(seconds) {
  if (seconds === null) return "—";
  const rounded = Math.round(seconds);
  if (rounded < 60) return `${rounded} sec`;
  if (rounded < 3600) return `${(seconds / 60).toLocaleString(undefined, { maximumFractionDigits: 1 })} min`;
  const minutes = Math.round(seconds / 60);
  return `${Math.floor(minutes / 60)} hr${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
}

function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

function renderBreakdown(id, items, label) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  const rows = items.map((item) => {
    const row = node("li", "breakdown-row");
    const heading = node("div", "breakdown-heading");
    // Assignment names are user-entered text; never insert them as HTML.
    heading.append(node("span", "breakdown-label", label(item)), node("strong", "", number.format(item.count)));
    const track = node("div", "breakdown-track");
    track.setAttribute("aria-hidden", "true");
    const bar = node("span", "breakdown-bar");
    bar.style.width = `${item.count / maximum * 100}%`;
    track.append(bar);
    row.append(heading, track);
    return row;
  });
  element(id).replaceChildren(...(rows.length ? rows : [node("li", "chart-empty", "No requests to display yet.")]));
}

function renderActivity(activity) {
  const maximum = Math.max(1, ...activity.map((day) => day.count));
  const tableRows = [];
  const columns = activity.map((day) => {
    const date = new Date(`${day.date}T00:00:00Z`);
    const label = utcDate.format(date);
    const column = node("div", "activity-day");
    column.title = `${label}: ${number.format(day.count)} requests`;
    const track = node("div", "activity-track");
    const bar = node("span", "activity-bar");
    bar.style.height = `${day.count / maximum * 100}%`;
    track.append(bar);
    column.append(node("span", "activity-value", shortNumber.format(day.count)), track,
      node("span", "activity-label", String(date.getUTCDate())));
    const row = node("tr");
    const dateCell = node("th", "", day.date);
    dateCell.scope = "row";
    row.append(dateCell, node("td", "", number.format(day.count)));
    tableRows.push(row);
    return column;
  });
  element("activity-chart").replaceChildren(...columns);
  element("activity-table").replaceChildren(...tableRows);
  const total = activity.reduce((sum, day) => sum + day.count, 0);
  element("activity-summary").textContent = `${number.format(total)} requests submitted during this period. Days with no submissions are shown as zero.`;
  element("activity-range").textContent = `${utcDate.format(new Date(`${activity[0].date}T00:00:00Z`))} – ${utcDate.format(new Date(`${activity.at(-1).date}T00:00:00Z`))} · Daily submissions`;
}

function renderAnalytics(data) {
  for (const [id, key] of Object.entries({
    "total-requests": "total_requests", "pending-requests": "pending_requests",
    "in-progress-requests": "in_progress_requests", "resolved-requests": "resolved_requests",
  })) element(id).textContent = number.format(data[key]);
  element("average-wait").textContent = duration(data.average_wait_seconds);
  element("average-resolution").textContent = duration(data.average_resolution_seconds);
  element("wait-sample").textContent = data.wait_sample_size ?
    `Based on ${number.format(data.wait_sample_size)} started request${data.wait_sample_size === 1 ? "" : "s"}` : "No valid wait intervals yet";
  element("resolution-sample").textContent = data.resolution_sample_size ?
    `Based on ${number.format(data.resolution_sample_size)} resolved request${data.resolution_sample_size === 1 ? "" : "s"}` : "No valid resolution intervals yet";
  renderBreakdown("category-chart", data.by_category, (item) => categoryLabel(item.issue_category));
  renderBreakdown("assignment-chart", data.by_assignment, (item) => item.assignment);
  element("assignment-scope").textContent = data.total_assignments > 10 ?
    `Top 10 of ${number.format(data.total_assignments)} assignments · All requests` : "All assignments · Ordered by request count";
  renderActivity(data.activity);
  element("analytics-empty").hidden = data.total_requests !== 0;
  element("analytics-results").hidden = false;
  element("connection-state").textContent = `Updated ${new Date(data.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  element("connection-state").classList.remove("offline");
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  if (!document.hidden) refreshTimer = setTimeout(refreshAnalytics, 30_000);
}

async function refreshAnalytics() {
  clearTimeout(refreshTimer);
  if (document.hidden || loading) return;
  loading = true;
  element("refresh-analytics").disabled = true;
  element("analytics-results").setAttribute("aria-busy", "true");
  try {
    const data = await apiRequest("/api/analytics");
    renderAnalytics(data);
    hasLoaded = true;
    showMessage(element("analytics-message"));
  } catch {
    showMessage(element("analytics-message"), hasLoaded ?
      "Couldn’t update analytics. Showing the last results; use Refresh to try again." :
      "Analytics are unavailable. Check your connection and use Refresh to try again.", "error");
    element("connection-state").textContent = "Analytics unavailable";
    element("connection-state").classList.add("offline");
  } finally {
    loading = false;
    element("refresh-analytics").disabled = false;
    element("analytics-loading").hidden = true;
    element("analytics-results").setAttribute("aria-busy", "false");
    scheduleRefresh();
  }
}

element("refresh-analytics").addEventListener("click", refreshAnalytics);
document.addEventListener("visibilitychange", () => {
  clearTimeout(refreshTimer);
  if (!document.hidden) void refreshAnalytics();
});
window.addEventListener("pagehide", () => clearTimeout(refreshTimer));
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void refreshAnalytics();
});
void refreshAnalytics();
