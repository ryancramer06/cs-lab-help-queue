import { categoryLabel, formatElapsed, statusBadge } from "./ui.mjs";

function setText(element, value) {
  if (element.textContent !== value) element.textContent = value;
}

export function requestAction(request, taName) {
  if (request.status === "pending" && !request.assigned_ta) return "claim";
  if (!taName || request.assigned_ta !== taName) return null;
  if (request.status === "pending") return "start";
  if (request.status === "in_progress") return "resolve";
  return null;
}

export function createTaCard(request, onAction) {
  const root = document.getElementById("request-template").content.firstElementChild.cloneNode(true);
  const card = { root, statusKey: "", buttons: {} };
  for (const field of ["student", "number", "assignment", "category", "wait", "created", "description", "owner", "resolved", "status"]) {
    card[field] = root.querySelector(`[data-${field}]`);
  }
  root.dataset.requestId = String(request.id);
  for (const button of root.querySelectorAll("[data-action]")) {
    const action = button.dataset.action;
    card.buttons[action] = button;
    button.addEventListener("click", () => onAction(request.id, action));
  }
  return card;
}

export function updateTaCard(card, request, taName, { enabled = false, busy = null } = {}) {
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
    `${request.status === "resolved" ? "Resolved by" : "Assigned to"} ${request.assigned_ta}` :
    taName ? "Unassigned" : "Unassigned · Choose a TA name to claim");
  card.root.classList.toggle("is-owned", Boolean(taName && request.assigned_ta === taName));
  const statusKey = `${request.status}:${request.assigned_ta || ""}`;
  if (card.statusKey !== statusKey) {
    card.status.replaceChildren(statusBadge(request));
    card.statusKey = statusKey;
  }
  const action = busy?.id === request.id ? busy.action : requestAction(request, taName);
  const labels = { claim: "Claim", start: "Start work", resolve: "Resolve" };
  const progressLabels = { claim: "Claiming…", start: "Starting…", resolve: "Resolving…" };
  for (const [name, button] of Object.entries(card.buttons)) {
    button.hidden = name !== action;
    button.disabled = !enabled || !taName || Boolean(busy);
    const pending = busy?.id === request.id && busy.action === name;
    setText(button, pending ? progressLabels[name] : labels[name]);
    button.setAttribute("aria-label", `${pending ? progressLabels[name] : labels[name]} request #${request.id}`);
  }
}
