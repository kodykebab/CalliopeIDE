/**
 * StreamingMessage — renders a single AI assistant message that arrives via
 * streaming.
 *
 * Props:
 *   - lines        List of output strings received from the stream
 *   - isStreaming  Whether more tokens are expected
 *   - error        Non-null string when the stream errored
 *
 * The component renders each line in order with a blinking cursor appended
 * while `isStreaming` is true, so the user can see tokens arrive in real-time.
 */

import React from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface StreamingMessageProps {
  /** Output lines received from the SSE stream */
  lines: string[];
  /** Whether the stream is still open */
  isStreaming: boolean;
  /** Error message — if provided, shows an error badge below the content */
  error?: string | null;
  /** Optional CSS class applied to the wrapper div */
  className?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * StreamingMessage
 *
 * @example
 * ```tsx
 * const { lines, isStreaming, error } = useStream();
 *
 * return (
 *   <StreamingMessage
 *     lines={lines}
 *     isStreaming={isStreaming}
 *     error={error}
 *   />
 * );
 * ```
 */
export function StreamingMessage({
  lines,
  isStreaming,
  error = null,
  className = '',
}: StreamingMessageProps): React.ReactElement {
  return (
    <div
      className={`streaming-message ${className}`.trim()}
      data-testid="streaming-message"
      aria-live="polite"
      aria-atomic="false"
    >
      {/* Render each streamed line as its own paragraph */}
      <div
        className="streaming-message__content"
        data-testid="streaming-content"
      >
        {lines.map((line, index) => (
          <p key={index} className="streaming-message__line">
            {line}
          </p>
        ))}

        {/* Blinking cursor shown only while streaming */}
        {isStreaming && (
          <span
            className="streaming-message__cursor"
            data-testid="streaming-cursor"
            aria-hidden="true"
          >
            ▋
          </span>
        )}
      </div>

      {/* Error badge shown when the stream errors */}
      {error && (
        <div
          className="streaming-message__error"
          data-testid="streaming-error"
          role="alert"
        >
          <span className="streaming-message__error-icon" aria-hidden="true">
            ⚠
          </span>
          <span className="streaming-message__error-text">{error}</span>
        </div>
      )}
    </div>
  );
}

export default StreamingMessage;
