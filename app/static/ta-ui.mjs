import { categoryLabel, formatElapsed, statusBadge } from "./ui.mjs";

function setText(element, value) {
  if (element.textContent !== value) element.textContent = value;
}

export function createTaCard(request) {
  const root = document.getElementById("request-template").content.firstElementChild.cloneNode(true);
  const card = { root, statusKey: "" };
  for (const field of ["student", "number", "assignment", "category", "wait", "created", "description", "owner", "resolved", "status"]) {
    card[field] = root.querySelector(`[data-${field}]`);
  }
  root.dataset.requestId = String(request.id);
  for (const button of root.querySelectorAll("[data-action]")) button.hidden = true;
  return card;
}

export function updateTaCard(card, request, taName) {
  // Keep the same nodes across polls so open descriptions and text selection survive.
  setText(card.student, request.student_name);
  setText(card.number, `Request #${request.id}`);
  setText(card.assignment, request.assignment);
  setText(card.category, categoryLabel(request.issue_category));
  setText(card.description, request.description);
  const end = request.started_at ? Date.parse(request.started_at) : Date.now();
  setText(card.wait, `${request.status === "pending" ? "Waiting" : "Waited"} ${formatElapsed(request.created_at, end)}`);
  const dateOptions = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };
  setText(card.created, `Submitted ${new Date(request.created_at).toLocaleString([], dateOptions)}`);
  card.created.dateTime = request.created_at;
  card.resolved.hidden = !request.resolved_at;
  if (request.resolved_at) {
    setText(card.resolved, `Resolved ${new Date(request.resolved_at).toLocaleString([], dateOptions)}`);
    card.resolved.dateTime = request.resolved_at;
  }
  setText(card.owner, request.assigned_ta ?
    `${request.status === "resolved" ? "Resolved by" : "Assigned to"} ${request.assigned_ta}` : "Unassigned");
  card.root.classList.toggle("is-owned", Boolean(taName && request.assigned_ta === taName));
  const statusKey = `${request.status}:${request.assigned_ta || ""}`;
  if (card.statusKey !== statusKey) {
    card.status.replaceChildren(statusBadge(request));
    card.statusKey = statusKey;
  }
}
