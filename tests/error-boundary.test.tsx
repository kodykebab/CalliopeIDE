import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ErrorBoundary } from '@/lib/error-boundary'
import React from 'react'

// Mock the monitoring module
jest.mock('@/lib/monitoring', () => ({
  captureException: jest.fn(),
}))

describe('ErrorBoundary', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test Content</div>
      </ErrorBoundary>,
    )
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('renders error UI when child component throws', () => {
    // Component that throws an error
    const ThrowComponent = () => {
      throw new Error('Test error')
    }

    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

    render(
      <ErrorBoundary>
        <ThrowComponent />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(
      screen.getByText(/An unexpected error occurred/),
    ).toBeInTheDocument()

    consoleSpy.mockRestore()
  })

  it('renders custom fallback when provided', () => {
    const ThrowComponent = () => {
      throw new Error('Custom error')
    }

    const customFallback = (error: Error) => (
      <div>Custom Error: {error.message}</div>
    )

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowComponent />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Custom Error: Custom error')).toBeInTheDocument()

    consoleSpy.mockRestore()
  })

  it('calls onError callback when error occurs', () => {
    const ThrowComponent = () => {
      throw new Error('Test error')
    }

    const onError = jest.fn()
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

    render(
      <ErrorBoundary onError={onError}>
        <ThrowComponent />
      </ErrorBoundary>,
    )

    expect(onError).toHaveBeenCalled()
    const [error, info] = onError.mock.calls[0]
    expect(error.message).toBe('Test error')
    expect(info.componentStack).toBeDefined()

    consoleSpy.mockRestore()
  })

  it('allows retry after error', async () => {
    const user = userEvent.setup()
    let shouldThrow = true

    const ToggleComponent = () => {
      if (shouldThrow) {
        throw new Error('Temporary error')
      }
      return <div>Success!</div>
    }

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()

    const { rerender } = render(
      <ErrorBoundary>
        <ToggleComponent />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    shouldThrow = false

    const retryButton = screen.getByText('Try Again')
    await user.click(retryButton)

    // After retry button click, component should recover if state is reset
    expect(screen.getByText('Success!')).toBeInTheDocument()

    consoleSpy.mockRestore()
  })

  it('shows error details in development mode', () => {
    const ThrowComponent = () => {
      throw new Error('Development error')
    }

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()
    const nodeEnv = process.env.NODE_ENV
    process.env.NODE_ENV = 'development'

    render(
      <ErrorBoundary>
        <ThrowComponent />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Error Details')).toBeInTheDocument()

    process.env.NODE_ENV = nodeEnv
    consoleSpy.mockRestore()
  })
})
