/**
 * Error Utilities for Calliope IDE
 * Provides error handling and recovery strategies
 */

export class AppError extends Error {
  constructor(
    public message: string,
    public code: string = 'UNKNOWN_ERROR',
    public statusCode: number = 500,
    public userMessage: string = message,
    public context?: Record<string, any>,
  ) {
    super(message)
    this.name = 'AppError'
    Object.setPrototypeOf(this, AppError.prototype)
  }

  toJSON() {
    return {
      message: this.message,
      code: this.code,
      statusCode: this.statusCode,
      userMessage: this.userMessage,
      context: this.context,
    }
  }
}

export class ValidationError extends AppError {
  constructor(message: string, userMessage?: string, context?: Record<string, any>) {
    super(
      message,
      'VALIDATION_ERROR',
      400,
      userMessage || 'The provided information is invalid. Please check and try again.',
      context,
    )
    this.name = 'ValidationError'
    Object.setPrototypeOf(this, ValidationError.prototype)
  }
}

export class AuthenticationError extends AppError {
  constructor(message: string = 'Authentication failed', context?: Record<string, any>) {
    super(
      message,
      'AUTHENTICATION_ERROR',
      401,
      'Your session has expired. Please sign in again.',
      context,
    )
    this.name = 'AuthenticationError'
    Object.setPrototypeOf(this, AuthenticationError.prototype)
  }
}

export class AuthorizationError extends AppError {
  constructor(message: string = 'Access denied', context?: Record<string, any>) {
    super(
      message,
      'AUTHORIZATION_ERROR',
      403,
      'You do not have permission to perform this action.',
      context,
    )
    this.name = 'AuthorizationError'
    Object.setPrototypeOf(this, AuthorizationError.prototype)
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, context?: Record<string, any>) {
    super(
      `${resource} not found`,
      'NOT_FOUND_ERROR',
      404,
      `The requested ${resource} could not be found.`,
      context,
    )
    this.name = 'NotFoundError'
    Object.setPrototypeOf(this, NotFoundError.prototype)
  }
}

export class ConflictError extends AppError {
  constructor(message: string, context?: Record<string, any>) {
    super(
      message,
      'CONFLICT_ERROR',
      409,
      'This action cannot be completed due to conflicting data.',
      context,
    )
    this.name = 'ConflictError'
    Object.setPrototypeOf(this, ConflictError.prototype)
  }
}

export class RateLimitError extends AppError {
  constructor(retryAfter?: number, context?: Record<string, any>) {
    super(
      'Rate limit exceeded',
      'RATE_LIMIT_ERROR',
      429,
      `Too many requests. Please try again${retryAfter ? ` in ${retryAfter} seconds` : ' later'}.`,
      context,
    )
    this.name = 'RateLimitError'
    Object.setPrototypeOf(this, RateLimitError.prototype)
  }
}

export class ServerError extends AppError {
  constructor(message: string = 'Server error', context?: Record<string, any>) {
    super(
      message,
      'SERVER_ERROR',
      500,
      'The server encountered an error. Our team has been notified. Please try again later.',
      context,
    )
    this.name = 'ServerError'
    Object.setPrototypeOf(this, ServerError.prototype)
  }
}

export class NetworkError extends AppError {
  constructor(message: string = 'Network error', context?: Record<string, any>) {
    super(
      message,
      'NETWORK_ERROR',
      0,
      'Unable to connect to the server. Please check your internet connection and try again.',
      context,
    )
    this.name = 'NetworkError'
    Object.setPrototypeOf(this, NetworkError.prototype)
  }
}

/**
 * Determine error type from HTTP status code
 */
export function getErrorTypeFromStatus(
  status: number,
  message: string = 'An error occurred',
): AppError {
  const context = { originalStatus: status }

  switch (status) {
    case 400:
      return new ValidationError(message, undefined, context)
    case 401:
      return new AuthenticationError(message, context)
    case 403:
      return new AuthorizationError(message, context)
    case 404:
      return new NotFoundError('Resource', context)
    case 409:
      return new ConflictError(message, context)
    case 429:
      return new RateLimitError(undefined, context)
    case 500:
    case 502:
    case 503:
    case 504:
      return new ServerError(message, context)
    default:
      if (status >= 500) {
        return new ServerError(message, context)
      }
      return new AppError(message, 'UNKNOWN_ERROR', status, message, context)
  }
}

/**
 * Check if error is retryable
 */
export function isRetryableError(error: Error): boolean {
  if (error instanceof RateLimitError) return true
  if (error instanceof NetworkError) return true

  if (error instanceof AppError) {
    const retryableStatuses = [408, 429, 500, 502, 503, 504]
    return retryableStatuses.includes(error.statusCode)
  }

  return false
}

/**
 * Get user-friendly error message
 */
export function getUserErrorMessage(error: unknown): string {
  if (error instanceof AppError) {
    return error.userMessage
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unexpected error occurred. Please try again.'
}

/**
 * Extract error context for logging
 */
export function getErrorContext(error: unknown): Record<string, any> {
  if (error instanceof AppError) {
    return {
      type: error.name,
      message: error.message,
      code: error.code,
      statusCode: error.statusCode,
      context: error.context,
    }
  }

  if (error instanceof Error) {
    return {
      type: error.name,
      message: error.message,
      stack: error.stack,
    }
  }

  return { error }
}
