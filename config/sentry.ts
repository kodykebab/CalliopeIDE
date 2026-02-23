/**
 * Sentry configuration for CalliopeIDE frontend
 */
import * as Sentry from "@sentry/nextjs";

export class SentryConfig {
  /**
   * Check if monitoring is enabled via environment variable
   */
  static isMonitoringEnabled(): boolean {
    return process.env.NEXT_PUBLIC_ENABLE_MONITORING === 'true';
  }

  /**
   * Get Sentry DSN from environment
   */
  static getDsn(): string {
    return process.env.NEXT_PUBLIC_SENTRY_DSN || '';
  }

  /**
   * Get deployment environment
   */
  static getEnvironment(): string {
    return process.env.NODE_ENV || 'development';
  }

  /**
   * Get release version
   */
  static getRelease(): string {
    return process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0';
  }

  /**
   * Filter sensitive data before sending to Sentry
   */
  static beforeSend(
    event: Sentry.Event,
    hint: Sentry.EventHint
  ): Sentry.Event | null {
    // Remove sensitive data from request data
    if (event.request) {
      const request = event.request;
      
      // Remove sensitive headers
      if (request.headers) {
        const sensitiveHeaders = ['authorization', 'cookie', 'x-api-key', 'x-auth-token'];
        sensitiveHeaders.forEach(header => {
          if (request.headers[header]) {
            request.headers[header] = '[Filtered]';
          }
          // Case-insensitive filtering
          Object.keys(request.headers).forEach(key => {
            if (sensitiveHeaders.includes(key.toLowerCase())) {
              request.headers[key] = '[Filtered]';
            }
          });
        });
      }

      // Remove sensitive form data and query parameters
      if (request.data && typeof request.data === 'object') {
        const sensitiveFields = ['password', 'token', 'secret', 'key', 'auth'];
        const data = request.data as Record<string, any>;
        
        sensitiveFields.forEach(field => {
          if (data[field]) {
            data[field] = '[Filtered]';
          }
        });
        
        // Case-insensitive filtering
        Object.keys(data).forEach(key => {
          if (sensitiveFields.some(sensitive => key.toLowerCase().includes(sensitive))) {
            data[key] = '[Filtered]';
          }
        });
      }

      // Filter sensitive query parameters
      if (request.query_string) {
        const sensitiveParams = ['password', 'token', 'secret', 'key', 'auth', 'api_key'];
        let queryString = request.query_string;
        
        sensitiveParams.forEach(param => {
          const regex = new RegExp(`(${param}=)[^&]*`, 'gi');
          queryString = queryString.replace(regex, `$1[Filtered]`);
        });
        
        request.query_string = queryString;
      }
    }

    // Remove sensitive user context
    if (event.user) {
      const user = event.user as Record<string, any>;
      // Keep essential user info but remove sensitive data
      const allowedFields = ['id', 'username', 'email'];
      const filteredUser: Record<string, any> = {};
      
      allowedFields.forEach(field => {
        if (user[field]) {
          filteredUser[field] = user[field];
        }
      });

      // Mask email partially for privacy
      if (filteredUser.email && typeof filteredUser.email === 'string') {
        const email = filteredUser.email;
        if (email.includes('@')) {
          const [local, domain] = email.split('@');
          if (local.length > 2) {
            filteredUser.email = `${local.substring(0, 2)}***@${domain}`;
          }
        }
      }

      event.user = filteredUser;
    }

    return event;
  }

  /**
   * Initialize Sentry for Next.js frontend
   */
  static initSentry(): boolean {
    if (!this.isMonitoringEnabled()) {
      console.warn('⚠️ Monitoring disabled - Sentry not initialized');
      return false;
    }

    const dsn = this.getDsn();
    if (!dsn) {
      console.warn('⚠️ NEXT_PUBLIC_SENTRY_DSN not provided - Sentry not initialized');
      return false;
    }

    try {
      Sentry.init({
        dsn,
        
        // Performance monitoring
        tracesSampleRate: 0.1, // Sample 10% of transactions for performance monitoring
        
        // Error sampling
        sampleRate: 1.0, // Send all errors
        
        // Environment and release
        environment: this.getEnvironment(),
        release: this.getRelease(),
        
        // Security and privacy
        beforeSend: this.beforeSend,
        sendDefaultPii: false, // Don't send personally identifiable information
        
        // Debug mode (only in development)
        debug: this.getEnvironment() === 'development',
        
        // Additional options
        attachStacktrace: true,
        
        // Next.js specific options
        tunnel: process.env.NEXT_PUBLIC_SENTRY_TUNNEL, // Optional tunnel for CSP
        
        // Integrations
        integrations: [
          new Sentry.BrowserTracing({
            // Performance monitoring for navigation
            tracePropagationTargets: ['localhost', /^\/api/],
          }),
        ],
      });

      console.log(`✅ Sentry initialized for environment: ${this.getEnvironment()}`);
      return true;
    } catch (error) {
      console.error('❌ Failed to initialize Sentry:', error);
      return false;
    }
  }
}

/**
 * Capture exception with additional context if Sentry is enabled
 */
export function captureExceptionWithContext(
  exception: Error,
  context: Record<string, any> = {}
): string {
  if (!SentryConfig.isMonitoringEnabled()) {
    return '';
  }

  try {
    return Sentry.withScope((scope) => {
      // Add context to the event
      Object.entries(context).forEach(([key, value]) => {
        scope.setContext(key, value);
      });
      
      return Sentry.captureException(exception);
    });
  } catch (error) {
    console.error('Failed to capture exception in Sentry:', error);
    return '';
  }
}

/**
 * Capture message with additional context if Sentry is enabled
 */
export function captureMessageWithContext(
  message: string,
  level: Sentry.SeverityLevel = 'info',
  context: Record<string, any> = {}
): string {
  if (!SentryConfig.isMonitoringEnabled()) {
    return '';
  }

  try {
    return Sentry.withScope((scope) => {
      // Add context to the event
      Object.entries(context).forEach(([key, value]) => {
        scope.setContext(key, value);
      });
      
      return Sentry.captureMessage(message, level);
    });
  } catch (error) {
    console.error('Failed to capture message in Sentry:', error);
    return '';
  }
}

/**
 * Set user context for Sentry
 */
export function setUserContext(user: { id?: string; username?: string; email?: string }): void {
  if (!SentryConfig.isMonitoringEnabled()) {
    return;
  }

  try {
    Sentry.setUser({
      id: user.id,
      username: user.username,
      email: user.email,
    });
  } catch (error) {
    console.error('Failed to set user context in Sentry:', error);
  }
}