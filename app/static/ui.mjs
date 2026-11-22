const categories = {
  syntax: "Syntax", debugging: "Debugging", conceptual: "Concepts",
  environment: "Environment", other: "Other",
};

export function formatElapsed(createdAt, end = Date.now()) {
  const start = Date.parse(createdAt);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "—";
  const minutes = Math.max(0, Math.floor((end - start) / 60_000));
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hr${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
}

export function statusBadge(request) {
  const badge = document.createElement("span");
  const status = ["pending", "in_progress", "resolved"].includes(request.status) ? request.status : "pending";
  badge.className = `status ${status}`;
  badge.textContent = status === "resolved" ? "Resolved" : status === "in_progress" ? "In progress" : request.assigned_ta ? "TA assigned" : "Waiting";
  return badge;
}

function cell(label, value) {
  const container = document.createElement("div");
  const title = document.createElement("span");
  title.className = "cell-label";
  title.textContent = label;
  const content = document.createElement("span");
  content.textContent = value;
  container.append(title, content);
  return container;
}

export function queueItem(request, trackedId) {
  const row = document.createElement("li");
  row.className = `queue-row${request.id === trackedId ? " is-tracked" : ""}`;
  const student = document.createElement("div");
  const name = document.createElement("h3");
  // Student-entered text stays text. Never treat names or descriptions as HTML.
  name.textContent = request.student_name;
  const number = document.createElement("span");
  number.className = "request-number";
  number.textContent = `#${request.id}${request.id === trackedId ? " · Tracking" : ""}`;
  student.append(name, number);
  const waitEnd = request.started_at ? Date.parse(request.started_at) : Date.now();
  const status = cell("Status", "");
  status.lastElementChild.replaceWith(statusBadge(request));
  row.append(
    student, cell("Assignment", request.assignment),
    cell("Issue", categories[request.issue_category] || "Other"),
    cell("Wait time", formatElapsed(request.created_at, waitEnd)), status,
  );
  return row;
}

export function showMessage(element, message = "", tone = "") {
  element.hidden = !message;
  element.className = `notice${tone ? ` ${tone}` : ""}`;
  if (element.textContent !== message) element.textContent = message;
}
