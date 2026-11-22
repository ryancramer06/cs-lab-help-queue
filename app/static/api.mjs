export class ApiError extends Error {
  constructor(message, status = 0, details = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

export async function apiRequest(path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      method,
      signal: controller.signal,
      cache: "no-store",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const details = Array.isArray(data?.detail) ? data.detail : [];
      const message = typeof data?.detail === "string" ? data.detail : "Please check the request details and try again.";
      throw new ApiError(message, response.status, details);
    }
    if (data === null) throw new ApiError("The server returned an unreadable response.");
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Could not connect to the lab server.");
  } finally {
    clearTimeout(timeout);
  }
}
