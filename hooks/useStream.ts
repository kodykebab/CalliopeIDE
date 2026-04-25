/**
 * useStream — Custom hook for consuming Server-Sent Events (SSE) from the
 * Calliope backend agent endpoint.
 *
 * The backend (server/agent.py) already emits `text/event-stream` frames in
 * the shape:
 *   data: {"type": "output", "data": "<line>"}
 *   data: {"type": "input_required"}
 *
 * This hook opens the stream, parses each frame, and exposes:
 *   - lines        — accumulated output lines received so far
 *   - isStreaming  — true while the stream is open
 *   - error        — non-null if the stream errored or the server returned a
 *                    non-2xx status
 *   - startStream  — call this with (url, body?) to begin a new stream
 *   - stopStream   — abort the current stream
 *   - reset        — clear all state back to initial values
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export type SseFrameType = 'output' | 'input_required' | 'error';

export interface SseFrame {
  type: SseFrameType;
  data?: string;
  message?: string;
}

export interface StreamState {
  /** All output lines received from the stream so far */
  lines: string[];
  /** Whether the stream is currently open and receiving data */
  isStreaming: boolean;
  /** Whether the backend has requested interactive user input */
  inputRequired: boolean;
  /** Error message, null when there is no error */
  error: string | null;
}

export interface UseStreamReturn extends StreamState {
  /** Open a new SSE stream to `url`, optionally with a POST `body` */
  startStream: (url: string, body?: Record<string, unknown>) => void;
  /** Abort the running stream */
  stopStream: () => void;
  /** Reset state back to initial values */
  reset: () => void;
}

// ─── Initial state ────────────────────────────────────────────────────────────

const INITIAL_STATE: StreamState = {
  lines: [],
  isStreaming: false,
  inputRequired: false,
  error: null,
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * useStream
 *
 * @example
 * ```tsx
 * const { lines, isStreaming, error, startStream, stopStream } = useStream();
 *
 * const handleSend = () => {
 *   startStream(`http://localhost:${port}/?data=${encodeURIComponent(query)}`);
 * };
 * ```
 */
export function useStream(): UseStreamReturn {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);

  // Keep a ref to the AbortController so we can cancel from stopStream/unmount
  const abortRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  const startStream = useCallback(
    (url: string, body?: Record<string, unknown>) => {
      // Abort any previous stream first
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Reset to fresh streaming state
      setState({ lines: [], isStreaming: true, inputRequired: false, error: null });

      const run = async () => {
        try {
          const fetchOptions: RequestInit = {
            signal: controller.signal,
          };

          if (body !== undefined) {
            fetchOptions.method = 'POST';
            fetchOptions.headers = { 'Content-Type': 'application/json' };
            fetchOptions.body = JSON.stringify(body);
          } else {
            fetchOptions.method = 'GET';
          }

          const response = await fetch(url, fetchOptions);

          if (!response.ok) {
            const text = await response.text().catch(() => '');
            throw new Error(
              `Server responded with ${response.status}: ${text || response.statusText}`
            );
          }

          if (!response.body) {
            throw new Error('Response body is null — streaming not supported');
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE frames are separated by double newlines
            const parts = buffer.split('\n\n');
            // The last element may be a partial frame — keep it in the buffer
            buffer = parts.pop() ?? '';

            for (const part of parts) {
              const trimmed = part.trim();
              if (!trimmed) continue;

              // Extract the "data: ..." line
              const dataLine = trimmed
                .split('\n')
                .find((l) => l.startsWith('data:'));

              if (!dataLine) continue;

              const jsonStr = dataLine.slice('data:'.length).trim();

              let frame: SseFrame;
              try {
                frame = JSON.parse(jsonStr) as SseFrame;
              } catch {
                // Malformed JSON — skip
                continue;
              }

              if (frame.type === 'output' && frame.data !== undefined) {
                setState((prev) => ({
                  ...prev,
                  lines: [...prev.lines, frame.data as string],
                }));
              } else if (frame.type === 'input_required') {
                setState((prev) => ({
                  ...prev,
                  inputRequired: true,
                  isStreaming: false,
                }));
                return; // Pause; caller should handle user input
              } else if (frame.type === 'error') {
                throw new Error(frame.message ?? 'Unknown streaming error');
              }
            }
          }

          // Stream finished cleanly
          setState((prev) => ({ ...prev, isStreaming: false }));
        } catch (err) {
          if ((err as { name?: string }).name === 'AbortError') {
            // User intentionally aborted — not an error
            setState((prev) => ({ ...prev, isStreaming: false }));
            return;
          }

          const message =
            err instanceof Error ? err.message : 'Unexpected streaming error';
          setState((prev) => ({
            ...prev,
            isStreaming: false,
            error: message,
          }));
        }
      };

      run();
    },
    []
  );

  return {
    ...state,
    startStream,
    stopStream,
    reset,
  };
}
