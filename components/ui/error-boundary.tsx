/**
 * Error Boundary Component
 * Catches JavaScript errors anywhere in the component tree and displays a fallback UI
 */
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { captureException } from '@/lib/monitoring';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    this.setState({
      error,
      errorInfo
    });

    // Send to error tracking service (Sentry)
    captureException(error, { 
      componentStack: errorInfo.componentStack,
      errorBoundary: true,
      errorType: error.constructor.name
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div
          className="flex min-h-screen items-center justify-center bg-background p-4"
          role="alert"
          aria-live="assertive"
        >
          <div className="w-full max-w-md rounded-lg border border-destructive bg-card p-6 shadow-lg">
            <h2 className="mb-4 text-2xl font-bold text-destructive">
              Something went wrong
            </h2>
            <p className="mb-4 text-muted-foreground">
              We're sorry, but something unexpected happened. The error has been logged
              and we'll look into it.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mb-4 rounded bg-muted p-3 text-sm">
                <summary className="cursor-pointer font-semibold">
                  Error Details (Development Only)
                </summary>
                <pre className="mt-2 overflow-auto text-xs">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <div className="flex gap-2">
              <button
                onClick={this.handleReset}
                className="rounded bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
              >
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="rounded border border-input bg-background px-4 py-2 hover:bg-accent hover:text-accent-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
