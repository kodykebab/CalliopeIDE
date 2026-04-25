/**
 * Tests for streaming responses (Issue #56)
 *
 * Covers:
 *   - useStream hook: initial state, successful streaming, error handling,
 *     input_required frames, POST body, abort on stop, multiple streams
 *   - StreamingMessage component: renders lines, shows/hides cursor,
 *     shows error badge, aria attributes, edge cases
 *
 * Note: jsdom lacks native ReadableStream/Response, so we provide
 * self-contained inline mocks that simulate SSE frame delivery.
 */

import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useStream } from '../../hooks/useStream';
import { StreamingMessage } from '../../components/StreamingMessage';

// ─── JSdom-compatible SSE mock helpers ───────────────────────────────────────

/**
 * Build a minimal ReadableStream-like object that delivers `chunks` one by
 * one then signals done.  Uses plain JavaScript so it works in jsdom.
 */
function makeFakeStream(chunks: string[]) {
  const enc = new TextEncoder();
  let idx = 0;
  return {
    getReader: () => ({
      read: jest.fn().mockImplementation(async () => {
        if (idx < chunks.length) {
          const value = enc.encode(chunks[idx++]);
          return { done: false, value };
        }
        return { done: true, value: undefined };
      }),
      releaseLock: jest.fn(),
    }),
  };
}

/** Encode a standard output SSE frame */
function outputFrame(data: string): string {
  return `data: ${JSON.stringify({ type: 'output', data })}\n\n`;
}

/** Encode an input_required SSE frame */
const inputRequiredFrame = `data: ${JSON.stringify({ type: 'input_required' })}\n\n`;

/** Encode an error SSE frame */
function errorFrame(message: string): string {
  return `data: ${JSON.stringify({ type: 'error', message })}\n\n`;
}

/**
 * Build a mock Response whose body is our fake stream.
 * `status` defaults to 200.
 */
function mockFetchOk(frames: string[]): Promise<Response> {
  const fakeBody = makeFakeStream(frames) as unknown as ReadableStream<Uint8Array>;
  return Promise.resolve({
    ok: true,
    status: 200,
    statusText: 'OK',
    body: fakeBody,
    text: async () => '',
  } as unknown as Response);
}

function mockFetchError(status: number, text = ''): Promise<Response> {
  return Promise.resolve({
    ok: false,
    status,
    statusText: 'Error',
    body: null,
    text: async () => text,
  } as unknown as Response);
}

// ─── useStream ────────────────────────────────────────────────────────────────

describe('useStream hook', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  // ── Initial state ──────────────────────────────────────────────────────────

  it('starts with correct initial state', () => {
    const { result } = renderHook(() => useStream());

    expect(result.current.lines).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.inputRequired).toBe(false);
    expect(result.current.error).toBeNull();
  });

  // ── Immediate streaming state ──────────────────────────────────────────────

  it('sets isStreaming true immediately after startStream is called', async () => {
    // Never-resolving fetch so we inspect transitional state
    global.fetch = jest.fn(
      () =>
        new Promise<Response>(() => {
          /* intentionally never resolves */
        })
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    expect(result.current.isStreaming).toBe(true);
    expect(result.current.lines).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  // ── Successful streaming ───────────────────────────────────────────────────

  it('accumulates lines from output frames', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([
        outputFrame('line one'),
        outputFrame('line two'),
        outputFrame('line three'),
      ])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));

    expect(result.current.lines).toEqual(['line one', 'line two', 'line three']);
    expect(result.current.error).toBeNull();
  });

  it('isStreaming becomes false when stream ends cleanly', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('done')])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    expect(result.current.lines).toEqual(['done']);
  });

  // ── input_required frame ──────────────────────────────────────────────────

  it('sets inputRequired=true and stops streaming on input_required frame', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('thinking...'), inputRequiredFrame])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.inputRequired).toBe(true));

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.lines).toContain('thinking...');
  });

  // ── Error frame ───────────────────────────────────────────────────────────

  it('captures error message on error frame', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('starting'), errorFrame('API key invalid')])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toBe('API key invalid');
    expect(result.current.isStreaming).toBe(false);
  });

  // ── HTTP errors ───────────────────────────────────────────────────────────

  it('sets error state on non-2xx HTTP status', async () => {
    global.fetch = jest.fn(() =>
      mockFetchError(401, 'Unauthorized')
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toMatch(/401/);
    expect(result.current.isStreaming).toBe(false);
  });

  it('sets error state on network failure', async () => {
    global.fetch = jest.fn(() =>
      Promise.reject(new TypeError('Failed to fetch'))
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toContain('Failed to fetch');
    expect(result.current.isStreaming).toBe(false);
  });

  it('sets error when response.body is null', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        body: null,
        text: async () => '',
      } as unknown as Response)
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toMatch(/null/i);
  });

  // ── stopStream ─────────────────────────────────────────────────────────────

  it('stopStream sets isStreaming=false', () => {
    global.fetch = jest.fn(
      () => new Promise<Response>(() => {
        /* never resolves */
      })
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      result.current.stopStream();
    });

    expect(result.current.isStreaming).toBe(false);
  });

  // ── reset ─────────────────────────────────────────────────────────────────

  it('reset clears all state', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('hello'), outputFrame('world')])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=hello');
    });

    await waitFor(() => expect(result.current.lines.length).toBeGreaterThan(0));

    act(() => {
      result.current.reset();
    });

    expect(result.current.lines).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.inputRequired).toBe(false);
  });

  // ── POST body ─────────────────────────────────────────────────────────────

  it('sends POST request when a body is provided', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('ok')])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/', {
        context_payload: { project_path: '/home/user/project' },
      });
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));

    const [fetchUrl, fetchOptions] = (global.fetch as jest.Mock).mock.calls[0];
    expect(fetchOptions.method).toBe('POST');
    expect(fetchOptions.headers?.['Content-Type']).toBe('application/json');
    expect(JSON.parse(fetchOptions.body).context_payload).toBeDefined();
  });

  it('uses GET request by default (no body)', async () => {
    global.fetch = jest.fn(() =>
      mockFetchOk([outputFrame('ok')])
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=test');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));

    const [, fetchOptions] = (global.fetch as jest.Mock).mock.calls[0];
    expect(fetchOptions.method).toBe('GET');
  });

  // ── Multiple consecutive streams ──────────────────────────────────────────

  it('handles multiple consecutive streams without state bleed', async () => {
    global.fetch = jest
      .fn()
      .mockImplementationOnce(() => mockFetchOk([outputFrame('first response')]))
      .mockImplementationOnce(() => mockFetchOk([outputFrame('second response')])) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=first');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    expect(result.current.lines).toEqual(['first response']);

    act(() => {
      result.current.startStream('http://localhost:9999/?data=second');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    // Lines reset for each new stream
    expect(result.current.lines).toEqual(['second response']);
  });

  // ── Malformed SSE frames ──────────────────────────────────────────────────

  it('silently skips malformed JSON in SSE frames', async () => {
    const enc = new TextEncoder();
    const badFrame = 'data: NOT_JSON\n\n';
    const goodFrame = outputFrame('good line');

    const bodyMock = {
      getReader: () => {
        const chunks = [badFrame, goodFrame];
        let idx = 0;
        return {
          read: jest.fn().mockImplementation(async () => {
            if (idx < chunks.length) {
              return { done: false, value: enc.encode(chunks[idx++]) };
            }
            return { done: true, value: undefined };
          }),
        };
      },
    };

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        body: bodyMock as unknown as ReadableStream<Uint8Array>,
        text: async () => '',
      } as unknown as Response)
    ) as jest.Mock;

    const { result } = renderHook(() => useStream());

    act(() => {
      result.current.startStream('http://localhost:9999/?data=test');
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));

    expect(result.current.lines).toEqual(['good line']);
    expect(result.current.error).toBeNull();
  });
});

// ─── StreamingMessage component ──────────────────────────────────────────────

describe('StreamingMessage component', () => {
  it('renders with data-testid="streaming-message"', () => {
    render(<StreamingMessage lines={[]} isStreaming={false} />);
    expect(screen.getByTestId('streaming-message')).toBeInTheDocument();
  });

  it('renders streamed lines as individual paragraphs', () => {
    render(
      <StreamingMessage
        lines={['Agent is working', 'CLI Output: hello']}
        isStreaming={false}
      />
    );

    expect(screen.getByText('Agent is working')).toBeInTheDocument();
    expect(screen.getByText('CLI Output: hello')).toBeInTheDocument();
  });

  it('shows blinking cursor while isStreaming=true', () => {
    render(<StreamingMessage lines={['partial...']} isStreaming={true} />);
    expect(screen.getByTestId('streaming-cursor')).toBeInTheDocument();
  });

  it('hides blinking cursor when isStreaming=false', () => {
    render(<StreamingMessage lines={['complete']} isStreaming={false} />);
    expect(screen.queryByTestId('streaming-cursor')).not.toBeInTheDocument();
  });

  it('does not show the error badge when error is null', () => {
    render(
      <StreamingMessage lines={['ok']} isStreaming={false} error={null} />
    );
    expect(screen.queryByTestId('streaming-error')).not.toBeInTheDocument();
  });

  it('shows error badge with message when error is set', () => {
    render(
      <StreamingMessage
        lines={[]}
        isStreaming={false}
        error="Connection reset by peer"
      />
    );

    const errorEl = screen.getByTestId('streaming-error');
    expect(errorEl).toBeInTheDocument();
    expect(errorEl).toHaveTextContent('Connection reset by peer');
  });

  it('has proper aria-live attribute for screen readers', () => {
    render(<StreamingMessage lines={[]} isStreaming={true} />);
    const container = screen.getByTestId('streaming-message');
    expect(container).toHaveAttribute('aria-live', 'polite');
    expect(container).toHaveAttribute('aria-atomic', 'false');
  });

  it('error badge has role="alert" for accessibility', () => {
    render(
      <StreamingMessage lines={[]} isStreaming={false} error="Something went wrong" />
    );
    const alertEl = screen.getByRole('alert');
    expect(alertEl).toBeInTheDocument();
  });

  it('renders with empty lines array without crashing', () => {
    expect(() =>
      render(<StreamingMessage lines={[]} isStreaming={false} />)
    ).not.toThrow();
  });

  it('applies custom className to wrapper, keeping base class', () => {
    render(
      <StreamingMessage
        lines={[]}
        isStreaming={false}
        className="chat-bubble"
      />
    );
    const wrapper = screen.getByTestId('streaming-message');
    expect(wrapper.className).toContain('chat-bubble');
    expect(wrapper.className).toContain('streaming-message');
  });

  it('renders many lines (long response) without crashing', () => {
    const lines = Array.from({ length: 200 }, (_, i) => `line ${i + 1}`);
    expect(() =>
      render(<StreamingMessage lines={lines} isStreaming={false} />)
    ).not.toThrow();

    expect(screen.getByText('line 1')).toBeInTheDocument();
    expect(screen.getByText('line 200')).toBeInTheDocument();
  });

  it('transitions from streaming to complete — cursor disappears', () => {
    const { rerender } = render(
      <StreamingMessage lines={['partial']} isStreaming={true} />
    );

    expect(screen.getByTestId('streaming-cursor')).toBeInTheDocument();

    rerender(
      <StreamingMessage lines={['partial', 'complete']} isStreaming={false} />
    );

    expect(screen.queryByTestId('streaming-cursor')).not.toBeInTheDocument();
    expect(screen.getByText('complete')).toBeInTheDocument();
  });

  it('renders data-testid="streaming-content" wrapper', () => {
    render(<StreamingMessage lines={['hello']} isStreaming={false} />);
    expect(screen.getByTestId('streaming-content')).toBeInTheDocument();
  });
});
