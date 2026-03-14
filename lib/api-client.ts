/** Human-readable messages for common error conditions. */
const FRIENDLY_ERRORS: Record<string, string> = {
  "Failed to fetch":
    "Unable to connect to the server. Please check your internet connection.",
  NetworkError: "Network error. Please check your connection and try again.",
  "500": "The server encountered an error. Please try again later.",
  "502": "The server is temporarily unreachable. Please try again later.",
  "503": "The service is temporarily unavailable. Please try again later.",
  "504": "The server took too long to respond. Please try again.",
  "404": "The requested resource was not found.",
  "401": "You are not authorized. Please sign in and try again.",
  "403": "Access denied. You do not have permission for this action.",
  timeout: "The request timed out. Please try again.",
};

const DEFAULT_ERROR = "Something went wrong. Please try again.";
const SAFE_CLIENT_ERRORS = new Set<string>([
  "Received an unexpected response from the server.",
]);

/**
 * Maps an unknown thrown value to a user-friendly string.
 * Raw backend messages (e.g. Python tracebacks) are never surfaced.
 */
export function getFriendlyError(error: unknown): string {
  if (error instanceof Error) {
    // Abort = timeout
    if (error.name === "AbortError") return FRIENDLY_ERRORS["timeout"];

    for (const [key, msg] of Object.entries(FRIENDLY_ERRORS)) {
      if (error.message.includes(key)) return msg;
    }
  }
  if (typeof error === "string") {
    for (const [key, msg] of Object.entries(FRIENDLY_ERRORS)) {
      if (error.includes(key)) return msg;
    }
  }
  return DEFAULT_ERROR;
}

export interface ApiFetchOptions extends RequestInit {
  /** Milliseconds before the request is aborted. Default 30 000. */
  timeoutMs?: number;
  /** When true, non-JSON 2xx responses are returned as text instead of throwing. */
  acceptText?: boolean;
}

/**
 * Fetch wrapper with:
 *  - automatic timeout / AbortController
 *  - HTTP-error detection (throws friendly Error on non-2xx)
 *  - invalid-response detection
 *  - no raw server messages exposed to callers
 */
export async function apiFetch<T = unknown>(
  url: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { timeoutMs = 30_000, acceptText = false, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });

    if (!response.ok) {
      const friendlyMsg =
        FRIENDLY_ERRORS[String(response.status)] ??
        `Request failed (${response.status}). Please try again.`;
      throw new Error(friendlyMsg);
    }

    if (acceptText) {
      return (await response.text()) as unknown as T;
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      throw new Error("Received an unexpected response from the server.");
    }

    return (await response.json()) as T;
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new Error(FRIENDLY_ERRORS["timeout"]);
    }
    // Re-throw already-friendly and known safe client messages unchanged
    if (
      err instanceof Error &&
      (Object.values(FRIENDLY_ERRORS).includes(err.message) ||
        SAFE_CLIENT_ERRORS.has(err.message) ||
        err.message.startsWith("Request failed ("))
    ) {
      throw err;
    }
    // Map anything else (TypeError: Failed to fetch, etc.) to friendly form
    throw new Error(getFriendlyError(err));
  } finally {
    clearTimeout(timeoutId);
  }
}
