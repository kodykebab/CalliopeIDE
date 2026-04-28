import {
  AppError,
  ValidationError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  ServerError,
  NetworkError,
  getErrorTypeFromStatus,
  isRetryableError,
  getUserErrorMessage,
  getErrorContext,
} from '@/lib/error-utils'

describe('Error Classes', () => {
  describe('AppError', () => {
    it('creates error with all properties', () => {
      const error = new AppError(
        'Test message',
        'TEST_ERROR',
        400,
        'User message',
        { field: 'value' },
      )

      expect(error.message).toBe('Test message')
      expect(error.code).toBe('TEST_ERROR')
      expect(error.statusCode).toBe(400)
      expect(error.userMessage).toBe('User message')
      expect(error.context).toEqual({ field: 'value' })
    })

    it('serializes to JSON', () => {
      const error = new AppError('Test', 'CODE', 500, 'User msg')
      const json = error.toJSON()

      expect(json.message).toBe('Test')
      expect(json.code).toBe('CODE')
      expect(json.statusCode).toBe(500)
    })
  })

  describe('ValidationError', () => {
    it('creates validation error with correct defaults', () => {
      const error = new ValidationError('Invalid input')

      expect(error.code).toBe('VALIDATION_ERROR')
      expect(error.statusCode).toBe(400)
      expect(error.userMessage).toContain('invalid')
    })

    it('uses custom user message if provided', () => {
      const error = new ValidationError('Bad format', 'Custom message')
      expect(error.userMessage).toBe('Custom message')
    })
  })

  describe('AuthenticationError', () => {
    it('creates authentication error with correct defaults', () => {
      const error = new AuthenticationError()

      expect(error.code).toBe('AUTHENTICATION_ERROR')
      expect(error.statusCode).toBe(401)
      expect(error.userMessage).toContain('expired')
    })
  })

  describe('AuthorizationError', () => {
    it('creates authorization error with correct defaults', () => {
      const error = new AuthorizationError()

      expect(error.code).toBe('AUTHORIZATION_ERROR')
      expect(error.statusCode).toBe(403)
      expect(error.userMessage).toContain('permission')
    })
  })

  describe('NotFoundError', () => {
    it('creates not found error for resource', () => {
      const error = new NotFoundError('User')

      expect(error.code).toBe('NOT_FOUND_ERROR')
      expect(error.statusCode).toBe(404)
      expect(error.userMessage).toContain('User')
    })
  })

  describe('ConflictError', () => {
    it('creates conflict error', () => {
      const error = new ConflictError('Duplicate entry')

      expect(error.code).toBe('CONFLICT_ERROR')
      expect(error.statusCode).toBe(409)
      expect(error.userMessage).toContain('conflicting')
    })
  })

  describe('RateLimitError', () => {
    it('creates rate limit error', () => {
      const error = new RateLimitError(60)

      expect(error.code).toBe('RATE_LIMIT_ERROR')
      expect(error.statusCode).toBe(429)
      expect(error.userMessage).toContain('60 seconds')
    })
  })

  describe('ServerError', () => {
    it('creates server error', () => {
      const error = new ServerError('Internal error')

      expect(error.code).toBe('SERVER_ERROR')
      expect(error.statusCode).toBe(500)
      expect(error.userMessage).toContain('team has been notified')
    })
  })

  describe('NetworkError', () => {
    it('creates network error with correct defaults', () => {
      const error = new NetworkError()

      expect(error.code).toBe('NETWORK_ERROR')
      expect(error.statusCode).toBe(0)
      expect(error.userMessage).toContain('internet connection')
    })
  })
})

describe('Error Utilities', () => {
  describe('getErrorTypeFromStatus', () => {
    it('returns ValidationError for 400', () => {
      const error = getErrorTypeFromStatus(400)
      expect(error).toBeInstanceOf(ValidationError)
    })

    it('returns AuthenticationError for 401', () => {
      const error = getErrorTypeFromStatus(401)
      expect(error).toBeInstanceOf(AuthenticationError)
    })

    it('returns AuthorizationError for 403', () => {
      const error = getErrorTypeFromStatus(403)
      expect(error).toBeInstanceOf(AuthorizationError)
    })

    it('returns NotFoundError for 404', () => {
      const error = getErrorTypeFromStatus(404)
      expect(error).toBeInstanceOf(NotFoundError)
    })

    it('returns ConflictError for 409', () => {
      const error = getErrorTypeFromStatus(409)
      expect(error).toBeInstanceOf(ConflictError)
    })

    it('returns RateLimitError for 429', () => {
      const error = getErrorTypeFromStatus(429)
      expect(error).toBeInstanceOf(RateLimitError)
    })

    it('returns ServerError for 5xx status codes', () => {
      const error500 = getErrorTypeFromStatus(500)
      const error502 = getErrorTypeFromStatus(502)

      expect(error500).toBeInstanceOf(ServerError)
      expect(error502).toBeInstanceOf(ServerError)
    })

    it('returns AppError for unknown status', () => {
      const error = getErrorTypeFromStatus(418)
      expect(error).toBeInstanceOf(AppError)
    })
  })

  describe('isRetryableError', () => {
    it('returns true for RateLimitError', () => {
      const error = new RateLimitError()
      expect(isRetryableError(error)).toBe(true)
    })

    it('returns true for NetworkError', () => {
      const error = new NetworkError()
      expect(isRetryableError(error)).toBe(true)
    })

    it('returns true for server errors', () => {
      const error = new ServerError()
      expect(isRetryableError(error)).toBe(true)
    })

    it('returns true for AppError with retryable status', () => {
      const error = new AppError('Timeout', 'TIMEOUT_ERROR', 408)
      expect(isRetryableError(error)).toBe(true)
    })

    it('returns false for validation errors', () => {
      const error = new ValidationError('Bad input')
      expect(isRetryableError(error)).toBe(false)
    })

    it('returns false for authentication errors', () => {
      const error = new AuthenticationError()
      expect(isRetryableError(error)).toBe(false)
    })
  })

  describe('getUserErrorMessage', () => {
    it('returns userMessage from AppError', () => {
      const error = new ValidationError('Invalid', 'Please check input')
      const message = getUserErrorMessage(error)
      expect(message).toBe('Please check input')
    })

    it('returns message from generic Error', () => {
      const error = new Error('Generic error')
      const message = getUserErrorMessage(error)
      expect(message).toBe('Generic error')
    })

    it('returns default message for unknown error type', () => {
      const message = getUserErrorMessage({ something: 'else' })
      expect(message).toContain('unexpected')
    })
  })

  describe('getErrorContext', () => {
    it('extracts context from AppError', () => {
      const error = new AppError('Test', 'CODE', 500, 'msg', { field: 'value' })
      const context = getErrorContext(error)

      expect(context.type).toBe('AppError')
      expect(context.code).toBe('CODE')
      expect(context.statusCode).toBe(500)
      expect(context.context).toEqual({ field: 'value' })
    })

    it('extracts context from generic Error', () => {
      const error = new Error('Test error')
      const context = getErrorContext(error)

      expect(context.type).toBe('Error')
      expect(context.message).toBe('Test error')
      expect(context.stack).toBeDefined()
    })

    it('handles unknown error objects', () => {
      const context = getErrorContext({ unknown: 'object' })
      expect(context.error).toBeDefined()
    })
  })
})
