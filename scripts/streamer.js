/** User-facing messages for common failure modes. */
const STREAM_ERRORS = {
    noBody: "Streaming is not supported in this browser. Please try a different browser.",
    networkFailure: "Unable to connect to the server. Please check your internet connection.",
    timeout: "The request timed out. Please try again.",
    serverError: (status) => `The server returned an error (${status}). Please try again later.`,
    unexpectedEnd: "The connection closed unexpectedly. Please try again.",
    default: "Something went wrong while receiving the response. Please try again.",
};

/**
 * Stream a response from the Gemini endpoint.
 *
 * @param {string} endpoint - Base URL of the streaming endpoint.
 * @param {Array<{parts: Array<{text: string}>}>} message - Message history array.
 * @param {(text: string, id: string) => void} onUpdate - Called for each streamed chunk.
 * @param {() => void} onEnd - Called when the stream completes successfully.
 * @param {(friendlyMessage: string) => void} [onError] - Called with a user-friendly
 *   error message if the stream fails. If omitted the error is re-thrown.
 * @param {AbortSignal} [signal] - Optional external AbortSignal to cancel the stream.
 * @returns {Promise<void>}
 */
export async function streamGeminiResponse(endpoint, message, onUpdate, onEnd, onError, signal) {
    const text = message[message.length - 1].parts[0].text;
    const id = Math.random().toString(36).slice(2);
    window.localStorage.setItem("readerId", id);

    // Internal abort controller for timeout; can be cancelled by the external signal too.
    const controller = new AbortController();
    const TIMEOUT_MS = 60_000;
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    if (signal) {
        signal.addEventListener("abort", () => controller.abort());
    }

    const mapToFriendlyError = (err) => {
        let friendly = STREAM_ERRORS.default;

        if (err && err.name === "AbortError") {
            friendly = STREAM_ERRORS.timeout;
        } else if (err && err.message) {
            if (
                err.message.includes("Failed to fetch") ||
                err.message.includes("NetworkError") ||
                err.message.includes("network")
            ) {
                friendly = STREAM_ERRORS.networkFailure;
            } else if (err.message.startsWith("SERVER_")) {
                // Internal sentinel set below
                friendly = err.message.replace("SERVER_", "");
            }
        }

        return friendly;
    };

    const notifyOrThrow = (friendly) => {
        if (typeof onError === "function") {
            onError(friendly);
        } else {
            throw new Error(friendly);
        }
    };

    try {
        // Encode the prompt safely instead of embedding raw text in the URL query.
        const url = `${endpoint}/?data=${encodeURIComponent(text)}`;

        let response;
        try {
            response = await fetch(url, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                signal: controller.signal,
            });
        } catch (fetchErr) {
            const friendly = mapToFriendlyError(fetchErr);
            notifyOrThrow(friendly);
            return;
        }

        if (!response.ok) {
            const sentinelErr = new Error(`SERVER_${STREAM_ERRORS.serverError(response.status)}`);
            const friendly = mapToFriendlyError(sentinelErr);
            notifyOrThrow(friendly);
            return;
        }

        if (!response.body) {
            const friendly = mapToFriendlyError(new Error(STREAM_ERRORS.noBody));
            notifyOrThrow(friendly);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        try {
            while (true) {
                let done, value;
                try {
                    ({ done, value } = await reader.read());
                } catch (readErr) {
                    const friendly = mapToFriendlyError(readErr);
                    notifyOrThrow(friendly);
                    return;
                }

                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk
                    .split("\n\n")
                    .filter((line) => line.trim().startsWith("data: "));

                for (const line of lines) {
                    const chunkText = String(line.split("data: ")[1] ?? "");
                    onUpdate(chunkText, id);
                }
            }
        } finally {
            // Always release the reader lock so the stream can be GC'd.
            reader.releaseLock();
        }

        onEnd();
    } catch (unexpectedErr) {
        const friendly = mapToFriendlyError(unexpectedErr);
        notifyOrThrow(friendly);
    } finally {
        clearTimeout(timeoutId);
    }
}