/**
 * Interactive Error Handling Demo
 * Demonstrates all error handling features in Calliope IDE
 */

import { 
  safeFetch, 
  handleApiError, 
  safeAsync, 
  logError 
} from '../lib/error-handler.ts';

import { 
  showErrorToast, 
  showSuccessToast, 
  showWarningToast, 
  showInfoToast 
} from '../components/ui/error-alert';

// Demo scenarios for testing error handling
const DEMO_SCENARIOS = {
  // Network failures
  networkError: () => {
    console.log('🔥 Testing Network Error...');
    const networkError = new TypeError('Failed to fetch: net::ERR_INTERNET_DISCONNECTED');
    const handled = handleApiError(networkError);
    showErrorToast(handled, 'Network Test');
    return handled;
  },

  // Server errors  
  serverError: async () => {
    console.log('🔥 Testing Server Error...');
    const result = await safeFetch('http://localhost:9999/nonexistent');
    if (!result.success) {
      showErrorToast(result.error, 'Server Connection Test');
    }
    return result;
  },

  // Timeout scenarios
  timeoutError: async () => {
    console.log('🔥 Testing Timeout...');
    const slowEndpoint = 'https://httpbin.org/delay/10'; // 10 second delay
    const result = await safeFetch(slowEndpoint, {}, 2000); // 2 second timeout
    if (!result.success) {
      showErrorToast(result.error, 'Timeout Test');
    }
    return result;
  },

  // API validation errors
  validationError: () => {
    console.log('🔥 Testing Validation Error...');
    const apiError = {
      message: 'Validation failed: Invalid email format',
      status: 422,
      code: 'VALIDATION_ERROR'
    };
    const handled = handleApiError(apiError);
    showErrorToast(handled, 'Validation Test');
    return handled;
  },

  // Authentication failures
  authError: () => {
    console.log('🔥 Testing Auth Error...');
    const authError = {
      message: 'Authentication required',
      status: 401,
      code: 'AUTH_REQUIRED'
    };
    const handled = handleApiError(authError);
    showErrorToast(handled, 'Authentication Test');
    return handled;
  },

  // Rate limiting
  rateLimitError: () => {
    console.log('🔥 Testing Rate Limit...');
    const rateLimitError = {
      message: 'Too many requests',
      status: 429,
      code: 'RATE_LIMITED'
    };
    const handled = handleApiError(rateLimitError);
    showErrorToast(handled, 'Rate Limit Test');
    return handled;
  },

  // Sensitive error sanitization
  sensitiveError: () => {
    console.log('🔥 Testing Sensitive Error Sanitization...');
    const sensitiveError = {
      message: 'Internal server error: Database connection failed at mysql://user:password@localhost:3306/app with stack trace: Error: Connection timeout...'
    };
    const handled = handleApiError(sensitiveError);
    showErrorToast(handled, 'Security Test');
    console.log('Original:', sensitiveError.message);
    console.log('Sanitized:', handled.message);
    return handled;
  },

  // Success scenarios
  successScenario: async () => {
    console.log('✅ Testing Success Flow...');
    const result = await safeAsync(async () => {
      // Simulate successful operation
      await new Promise(resolve => setTimeout(resolve, 500));
      return { message: 'Operation completed successfully', data: { id: 123 } };
    });
    
    if (result.success) {
      showSuccessToast(result.data.message, 'Success Test');
    }
    return result;
  },

  // Warning scenarios
  warningScenario: () => {
    console.log('⚠️ Testing Warning...');
    showWarningToast('Your session will expire in 5 minutes', 'Session Warning');
    return { type: 'warning', message: 'Session warning displayed' };
  },

  // Info scenarios  
  infoScenario: () => {
    console.log('ℹ️ Testing Info...');
    showInfoToast('New features available in this update', 'Update Info');
    return { type: 'info', message: 'Info notification displayed' };
  },

  // LocalStorage errors
  storageError: () => {
    console.log('🔥 Testing Storage Error...');
    try {
      // Simulate quota exceeded error
      throw new Error('QuotaExceededError: localStorage quota exceeded');
    } catch (error) {
      logError(error, 'localStorage operation');
      const handled = handleApiError(error);
      showErrorToast(handled, 'Storage Test');
      return handled;
    }
  },

  // Stream processing errors
  streamError: async () => {
    console.log('🔥 Testing Stream Error...');
    const mockStreamError = {
      message: 'Stream was aborted',
      name: 'AbortError'
    };
    const handled = handleApiError(mockStreamError);
    showErrorToast(handled, 'Stream Test');
    return handled;
  }
};

// Demo runner function
export async function runErrorHandlingDemo(scenario = 'all') {
  console.log(`
🎭 Calliope IDE Error Handling Demo
==================================
Testing comprehensive error handling and user feedback system...
`);

  const results = {};

  if (scenario === 'all') {
    // Run all scenarios
    for (const [name, testFn] of Object.entries(DEMO_SCENARIOS)) {
      try {
        console.log(`\n--- Running ${name} ---`);
        results[name] = await testFn();
        await new Promise(resolve => setTimeout(resolve, 1000)); // Pause between tests
      } catch (error) {
        console.error(`Failed to run ${name}:`, error);
        results[name] = { error: error.message };
      }
    }
  } else if (DEMO_SCENARIOS[scenario]) {
    // Run specific scenario
    console.log(`\n--- Running ${scenario} ---`);
    results[scenario] = await DEMO_SCENARIOS[scenario]();
  } else {
    console.error(`Unknown scenario: ${scenario}`);
    console.log('Available scenarios:', Object.keys(DEMO_SCENARIOS).join(', '));
    return;
  }

  console.log(`
📊 Demo Results Summary
======================`);
  Object.entries(results).forEach(([name, result]) => {
    const status = result?.error ? '❌' : result?.success === false ? '⚠️' : '✅';
    console.log(`${status} ${name}: ${result?.message || result?.error || 'Completed'}`);
  });

  console.log(`
🎯 Error Handling Features Demonstrated:
========================================
✅ Network error detection and user-friendly messages
✅ Timeout handling with automatic retry suggestions  
✅ HTTP status code mapping to meaningful messages
✅ Sensitive information sanitization for security
✅ Toast notifications for different message types
✅ Graceful fallback behaviors
✅ Comprehensive error logging for debugging
✅ Loading states and user feedback
✅ LocalStorage error resilience
✅ Stream processing error recovery

The error handling system ensures:
• No silent failures - all errors are visible to users
• Clean, professional error messages - no raw stack traces
• Consistent UX across all error scenarios
• Proper error categorization and response
• Actionable feedback when possible
• Security through error message sanitization
`);

  return results;
}

// Browser console integration for testing
if (typeof window !== 'undefined') {
  // Make demo available in browser console
  window.calliopeDemoError = runErrorHandlingDemo;
  
  console.log(`
🔧 Interactive Demo Available!
==============================
Open browser console and run:

// Test all error scenarios
calliopeDemoError('all')

// Test specific scenarios  
calliopeDemoError('networkError')
calliopeDemoError('serverError')
calliopeDemoError('timeoutError')
calliopeDemoError('sensitiveError')
calliopeDemoError('successScenario')

Available scenarios:
${Object.keys(DEMO_SCENARIOS).map(key => `• ${key}`).join('\n')}
  `);
}

// Node.js integration for CLI testing
if (typeof process !== 'undefined') {
  const args = process.argv.slice(2);
  if (args.length > 0) {
    runErrorHandlingDemo(args[0]);
  }
}

export { DEMO_SCENARIOS };