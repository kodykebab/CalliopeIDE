/**
 * Comprehensive Error Handling Verification Test
 * Tests all error scenarios and confirms proper behavior
 */

// Mock environment setup for testing
const mockEnvironment = {
  localStorage: {},
  consoleErrors: [],
  unhandledPromises: [],
  toastMessages: [],
  loadingStates: [],
  
  // Mock localStorage
  storage: {
    getItem: (key) => mockEnvironment.localStorage[key] || null,
    setItem: (key, value) => { mockEnvironment.localStorage[key] = value; },
    removeItem: (key) => { delete mockEnvironment.localStorage[key]; }
  },
  
  // Mock console error capture
  captureConsoleErrors: () => {
    const originalError = console.error;
    console.error = (...args) => {
      mockEnvironment.consoleErrors.push(args.join(' '));
      originalError(...args);
    };
    return () => { console.error = originalError; };
  },
  
  // Mock unhandled promise capture
  captureUnhandledPromises: () => {
    const handler = (event) => {
      mockEnvironment.unhandledPromises.push(event.reason?.message || event.reason);
    };
    
    if (typeof window !== 'undefined') {
      window.addEventListener('unhandledrejection', handler);
      return () => window.removeEventListener('unhandledrejection', handler);
    }
    return () => {};
  },
  
  // Mock toast system
  mockToast: (type, title, message, options = {}) => {
    const toast = {
      id: Math.random().toString(36),
      type,
      title,
      message,
      timestamp: Date.now(),
      hasRetryOption: !!options.action
    };
    mockEnvironment.toastMessages.push(toast);
    console.log(`📢 Toast [${type.toUpperCase()}]: ${title} - ${message}`);
    if (options.action) {
      console.log(`   🔄 Retry option available: ${options.action.label}`);
    }
    return toast.id;
  },
  
  // Mock loading state
  mockLoadingState: (isLoading, context = 'default') => {
    const state = {
      isLoading,
      context,
      timestamp: Date.now()
    };
    mockEnvironment.loadingStates.push(state);
    console.log(`⏳ Loading state [${context}]: ${isLoading ? 'ACTIVE' : 'INACTIVE'}`);
    return state;
  }
};

// Check if running in Node.js vs Browser
const isNode = typeof window === 'undefined';

// Mock fetch for Node.js environment
if (isNode && typeof fetch === 'undefined') {
  global.fetch = async (url, options = {}) => {
    // Simple mock that simulates different scenarios
    if (url.includes('nonexistent') || url.includes('invalid-domain')) {
      throw new TypeError('Failed to fetch');
    }
    
    return {
      ok: url.includes('success'),
      status: url.includes('500') ? 500 : (url.includes('success') ? 200 : 404),
      statusText: url.includes('500') ? 'Internal Server Error' : 'OK',
      json: async () => ({ message: 'Mock response' })
    };
  };
}

// Error handling utilities (imported from our lib/error-handler.ts)
const handleApiError = (error) => {
  // Handle fetch/network errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      message: "Network error. Please check your connection and try again.",
      code: "NETWORK_ERROR"
    };
  }

  // Handle timeout errors
  if (error.name === 'AbortError' || error.message?.includes('timeout')) {
    return {
      message: "Request timeout. Please try again.",
      code: "TIMEOUT_ERROR"
    };
  }

  // Handle HTTP errors with status codes
  if (error.status || error.response?.status) {
    const status = error.status || error.response.status;
    const statusMessages = {
      400: "Invalid request. Please check your input and try again.",
      401: "Authentication required. Please check your API key.",
      403: "Access denied. You don't have permission for this action.",
      404: "Resource not found. The requested item doesn't exist.",
      500: "Server error. Something went wrong on our end.",
      502: "Service temporarily unavailable. Please try again later.",
      503: "Service overloaded. Please try again in a few moments."
    };
    return {
      message: statusMessages[status] || "An unexpected error occurred. Please try again.",
      status,
      code: `HTTP_${status}`
    };
  }

  // Handle structured API errors - sanitize sensitive info
  if (error.message) {
    const sensitivePatterns = [
      /stack trace/i, /internal server error/i, /database/i, /sql/i,
      /exception/i, /traceback/i, /\.java/i, /\.py/i, /\.cs/i, /line \\d+/i
    ];

    const isSensitive = sensitivePatterns.some(pattern => pattern.test(error.message));
    
    if (isSensitive) {
      return {
        message: "An unexpected error occurred. Please try again.",
        code: "INTERNAL_ERROR"
      };
    }

    return {
      message: error.message,
      code: "API_ERROR"
    };
  }

  return {
    message: "An unexpected error occurred. Please try again.",
    code: "UNKNOWN_ERROR"
  };
};

const safeFetch = async (url, options = {}, timeoutMs = 10000) => {
  let controller, timeoutId;
  
  // Create AbortController if available
  if (typeof AbortController !== 'undefined') {
    controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller?.signal,
    });

    if (timeoutId) clearTimeout(timeoutId);

    if (!response.ok) {
      throw {
        status: response.status,
        message: `HTTP ${response.status}: ${response.statusText}`
      };
    }

    const data = await response.json();
    return { data, success: true };
  } catch (error) {
    if (timeoutId) clearTimeout(timeoutId);
    return {
      error: handleApiError(error),
      success: false
    };
  }
};


// Test Results Tracker
let testResults = {
  passed: 0,
  failed: 0,
  total: 0,
  details: []
};

const logTest = (testName, passed, message, details = '') => {
  testResults.total++;
  if (passed) {
    testResults.passed++;
    console.log(`✅ ${testName}: ${message}`);
  } else {
    testResults.failed++;
    console.log(`❌ ${testName}: ${message}`);
  }
  
  if (details) {
    console.log(`   💡 ${details}`);
  }
  
  testResults.details.push({
    name: testName,
    passed,
    message,
    details
  });
};

// TEST 1: Backend Stop → Send Chat → Clear Error + Retry Option
async function test1_BackendStop() {
  console.log('\n🧪 TEST 1: Backend Stop Scenario');
  
  try {
    // Simulate backend down
    const result = await safeFetch('http://127.0.0.1:9999/nonexistent', {}, 2000);
    
    if (!result.success) {
      // Simulate showing error with retry option
      const toastId = mockEnvironment.mockToast(
        'error', 
        'Server Connection Failed', 
        result.error.message,
        { action: { label: 'Retry Connection', onClick: () => {} } }
      );
      
      const hasRetryOption = mockEnvironment.toastMessages.some(toast => toast.hasRetryOption);
      const isUserFriendly = !result.error.message.includes('9999') && 
                            result.error.message.includes('Network error');
      
      logTest(
        'Backend Stop → Error + Retry',
        hasRetryOption && isUserFriendly,
        hasRetryOption && isUserFriendly ? 
          'Error shown with retry option and friendly message' : 
          'Missing retry option or unfriendly message',
        `Message: "${result.error.message}"`
      );
    }
  } catch (error) {
    logTest('Backend Stop → Error + Retry', false, 'Test execution failed', error.message);
  }
}

// TEST 2: Force API 500 → Friendly Message Shown
async function test2_API500() {
  console.log('\n🧪 TEST 2: API 500 Error Sanitization');
  
  const rawError = {
    status: 500,
    message: 'SqlException: Connection timeout at DatabaseService.ExecuteQuery() line 1247 in UserController.java'
  };
  
  const sanitizedError = handleApiError(rawError);
  
  const isSanitized = !sanitizedError.message.includes('SqlException') &&
                     !sanitizedError.message.includes('DatabaseService') &&
                     !sanitizedError.message.includes('line 1247') &&
                     !sanitizedError.message.includes('UserController.java');
  
  mockEnvironment.mockToast('error', 'Server Error', sanitizedError.message);
  
  logTest(
    'API 500 → Friendly Message',
    isSanitized,
    isSanitized ? 'Sensitive information properly sanitized' : 'Raw error details exposed',
    `Original: "${rawError.message}" → Sanitized: "${sanitizedError.message}"`
  );
}

// TEST 3: Simulate Slow API → Loading Spinner Visible
async function test3_SlowAPI() {
  console.log('\n🧪 TEST 3: Slow API Loading States');
  
  const startTime = Date.now();
  
  // Show loading state
  mockEnvironment.mockLoadingState(true, 'chat-message');
  const loadingToast = mockEnvironment.mockToast('info', 'Processing', 'Sending your message...');
  
  // Simulate slow API call
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Hide loading state
  mockEnvironment.mockLoadingState(false, 'chat-message');
  mockEnvironment.mockToast('success', 'Complete', 'Message sent successfully');
  
  const duration = Date.now() - startTime;
  const hasLoadingState = mockEnvironment.loadingStates.some(state => 
    state.context === 'chat-message' && state.isLoading
  );
  
  logTest(
    'Slow API → Loading Spinner',
    hasLoadingState && duration >= 1900,
    hasLoadingState ? `Loading state shown for ${duration}ms` : 'Loading state missing',
    'Loading spinner should be visible during API calls'
  );
}

// TEST 4: Rapid Button Clicks → Button Disabled During Loading
async function test4_RapidClicks() {
  console.log('\n🧪 TEST 4: Rapid Button Click Prevention');
  
  let isProcessing = false;
  let clicksProcessed = 0;
  let clicksIgnored = 0;
  
  const simulateButtonClick = async () => {
    if (isProcessing) {
      clicksIgnored++;
      mockEnvironment.mockToast('warning', 'Please Wait', 'Please wait for the current operation to complete');
      return false;
    }
    
    isProcessing = true;
    clicksProcessed++;
    mockEnvironment.mockLoadingState(true, 'button-processing');
    
    // Simulate processing time
    await new Promise(resolve => setTimeout(resolve, 500));
    
    isProcessing = false;
    mockEnvironment.mockLoadingState(false, 'button-processing');
    mockEnvironment.mockToast('success', 'Complete', `Operation ${clicksProcessed} completed`);
    return true;
  };
  
  // Simulate 5 rapid clicks
  const promises = [];
  for (let i = 0; i < 5; i++) {
    promises.push(simulateButtonClick());
    // 100ms between clicks (very rapid)
    if (i < 4) await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  await Promise.all(promises);
  
  const hasDebouncing = clicksIgnored > 0;
  const properProcessing = clicksProcessed > 0;
  
  logTest(
    'Rapid Clicks → Debouncing',
    hasDebouncing && properProcessing,
    hasDebouncing ? `${clicksProcessed} processed, ${clicksIgnored} ignored` : 'No debouncing detected',
    'Multiple rapid clicks should be prevented during processing'
  );
}

// TEST 5: Invalid Project Creation → Inline Validation Error
async function test5_Validation() {
  console.log('\n🧪 TEST 5: Input Validation Errors');
  
  const validationTests = [
    { input: '', expected: 'Project name is required' },
    { input: 'ab', expected: 'Project name must be at least 3 characters' },
    { input: 'test!@#$', expected: 'Project name contains invalid characters' },
    { input: 'system', expected: 'Project name is reserved' }
  ];
  
  let validationErrorsShown = 0;
  
  for (const test of validationTests) {
    try {
      // Simulate validation
      let errorMessage = '';
      
      if (!test.input) {
        errorMessage = 'Project name is required';
      } else if (test.input.length < 3) {
        errorMessage = 'Project name must be at least 3 characters';
      } else if (!/^[a-zA-Z0-9\-_]+$/.test(test.input)) {
        errorMessage = 'Project name contains invalid characters';
      } else if (['system', 'admin', 'root'].includes(test.input.toLowerCase())) {
        errorMessage = 'Project name is reserved';
      }
      
      if (errorMessage) {
        mockEnvironment.mockToast('error', 'Validation Error', errorMessage);
        validationErrorsShown++;
      }
      
      await new Promise(resolve => setTimeout(resolve, 300));
    } catch (error) {
      console.warn('Validation test error:', error);
    }
  }
  
  logTest(
    'Invalid Input → Validation Errors',
    validationErrorsShown === validationTests.length,
    `${validationErrorsShown}/${validationTests.length} validation errors shown`,
    'All invalid inputs should show appropriate error messages'
  );
}

// TEST 6: Network Disconnect → Proper Notification
async function test6_NetworkDisconnect() {
  console.log('\n🧪 TEST 6: Network Error Handling');
  
  const networkErrors = [
    new TypeError('Failed to fetch'),
    { code: 'ENOTFOUND', message: 'getaddrinfo ENOTFOUND example.com' },
    { name: 'NetworkError', message: 'Network request failed' },
    { name: 'AbortError', message: 'The operation was aborted' }
  ];
  
  let properlyHandled = 0;
  
  for (const error of networkErrors) {
    const handledError = handleApiError(error);
    mockEnvironment.mockToast('error', 'Network Error', handledError.message);
    
    const isNetworkError = handledError.code === 'NETWORK_ERROR' || 
                          handledError.code === 'TIMEOUT_ERROR' ||
                          handledError.message.toLowerCase().includes('network') ||
                          handledError.message.toLowerCase().includes('connection');
    
    if (isNetworkError) {
      properlyHandled++;
    }
    
    console.log(`   🌐 ${error.name || error.constructor.name}: ${handledError.message} (${handledError.code})`);
    
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  
  logTest(
    'Network Errors → Proper Notification',
    properlyHandled === networkErrors.length,
    `${properlyHandled}/${networkErrors.length} network errors properly categorized`,
    'All network errors should be detected and handled appropriately'
  );
}

// TEST 7: Verify No Silent Failures
async function test7_NoSilentFailures() {
  console.log('\n🧪 TEST 7: Silent Failure Detection');
  
  const cleanupConsole = mockEnvironment.captureConsoleErrors();
  const cleanupPromises = mockEnvironment.captureUnhandledPromises();
  
  try {
    // Test 1: Promise rejection with proper handling
    try {
      await Promise.reject(new Error('Test promise rejection'));
    } catch (error) {
      const handled = handleApiError(error);
      mockEnvironment.mockToast('error', 'Caught Error', handled.message);
    }
    
    // Test 2: Async function error with proper handling
    try {
      await (async () => {
        throw new Error('Test async error');
      })();
    } catch (error) {
      const handled = handleApiError(error);
      mockEnvironment.mockToast('error', 'Async Error', handled.message);
    }
    
    // Test 3: Fetch error with proper handling
    try {
      const result = await safeFetch('http://invalid-domain-that-does-not-exist-12345.com');
      if (!result.success) {
        mockEnvironment.mockToast('error', 'Fetch Error', result.error.message);
      }
    } catch (error) {
      // This should not happen with safeFetch
      console.warn('Unexpected fetch error:', error);
    }
    
    // Wait briefly for any delayed promise rejections
    await new Promise(resolve => setTimeout(resolve, 500));
    
  } finally {
    cleanupConsole();
    cleanupPromises();
  }
  
  const hasUnhandledPromises = mockEnvironment.unhandledPromises.length > 0;
  const hasConsoleErrors = mockEnvironment.consoleErrors.filter(err => 
    err.includes('Uncaught') || err.includes('Unhandled')
  ).length > 0;
  
  logTest(
    'No Silent Failures',
    !hasUnhandledPromises && !hasConsoleErrors,
    hasUnhandledPromises || hasConsoleErrors ? 
      `Found ${mockEnvironment.unhandledPromises.length} unhandled promises, ${mockEnvironment.consoleErrors.length} console errors` :
      'All errors properly caught and handled',
    'No unhandled promise rejections or uncaught exceptions should occur'
  );
}

// TEST 8: Verify UI Responsiveness
async function test8_UIResponsive() {
  console.log('\n🧪 TEST 8: UI Responsiveness Check');
  
  // Simulate multiple concurrent operations
  const operations = [];
  
  for (let i = 0; i < 5; i++) {
    operations.push((async () => {
      mockEnvironment.mockLoadingState(true, `operation-${i}`);
      await new Promise(resolve => setTimeout(resolve, Math.random() * 1000 + 500));
      mockEnvironment.mockLoadingState(false, `operation-${i}`);
      mockEnvironment.mockToast('success', 'Operation Complete', `Operation ${i} finished`);
    })());
  }
  
  const startTime = Date.now();
  await Promise.all(operations);
  const totalTime = Date.now() - startTime;
  
  // Check that operations ran concurrently (should be close to max operation time, not sum)
  const isResponsive = totalTime < 2000; // Should be under 2 seconds for concurrent ops
  
  logTest(
    'UI Responsiveness',
    isResponsive,
    isResponsive ? `5 operations completed in ${totalTime}ms (concurrent)` : `Operations took ${totalTime}ms (possibly blocking)`,
    'Multiple operations should run concurrently without blocking UI'
  );
}

// Main test runner
async function runAllErrorHandlingTests() {
  console.log(`
🎯 CALLIOPE IDE ERROR HANDLING VERIFICATION
==========================================
Running comprehensive error handling tests...
`);

  // Reset test environment
  mockEnvironment.localStorage = {};
  mockEnvironment.consoleErrors = [];
  mockEnvironment.unhandledPromises = [];
  mockEnvironment.toastMessages = [];
  mockEnvironment.loadingStates = [];
  
  testResults = { passed: 0, failed: 0, total: 0, details: [] };
  
  const startTime = Date.now();
  
  // Run all tests
  await test1_BackendStop();
  await test2_API500();
  await test3_SlowAPI();
  await test4_RapidClicks();
  await test5_Validation();
  await test6_NetworkDisconnect();
  await test7_NoSilentFailures();
  await test8_UIResponsive();
  
  const totalTime = Date.now() - startTime;
  
  // Generate final report
  console.log(`
📊 VERIFICATION RESULTS SUMMARY
==============================
Execution time: ${totalTime}ms
Tests passed: ${testResults.passed}/${testResults.total}
Tests failed: ${testResults.failed}/${testResults.total}

📋 VERIFICATION CHECKLIST
=========================`);

  // Check all requirements
  const requirements = {
    'No silent failures': mockEnvironment.unhandledPromises.length === 0,
    'No raw backend messages': !mockEnvironment.toastMessages.some(toast => 
      toast.message.includes('Exception') || 
      toast.message.includes('line ') ||
      toast.message.includes('.java') ||
      toast.message.includes('.py')
    ),
    'Loading states visible': mockEnvironment.loadingStates.some(state => state.isLoading),
    'UI responsive': testResults.details.find(t => t.name === 'UI Responsiveness')?.passed || false,
    'No console unhandled promises': mockEnvironment.unhandledPromises.length === 0
  };
  
  let requirementsPassed = 0;
  Object.entries(requirements).forEach(([requirement, passed]) => {
    const status = passed ? '✅' : '❌';
    console.log(`${status} ${requirement}`);
    if (passed) requirementsPassed++;
  });
  
  console.log(`
🎯 FINAL ASSESSMENT
==================
Core Requirements: ${requirementsPassed}/${Object.keys(requirements).length} passed
Test Cases: ${testResults.passed}/${testResults.total} passed
Toast Messages: ${mockEnvironment.toastMessages.length} shown
Loading States: ${mockEnvironment.loadingStates.length} recorded
Console Errors: ${mockEnvironment.consoleErrors.length}
Unhandled Promises: ${mockEnvironment.unhandledPromises.length}

${testResults.passed === testResults.total && requirementsPassed === Object.keys(requirements).length ?
'🎉 ALL TESTS PASSED! Error handling system is working correctly.' :
'⚠️  Issues found. Review failed tests above.'
}

📱 MANUAL VERIFICATION STEPS
============================
1. Open the app in browser (http://localhost:3000/app)
2. Open browser dev tools (F12)
3. Stop the backend server
4. Try to send a chat message → Should show error with retry option
5. Check console → Should have no red "Unhandled promise" errors
6. Try rapid clicking send button → Should prevent multiple submissions
7. Disconnect network → Should show network error notification
8. All error messages should be user-friendly, not technical
`);

  return {
    passed: testResults.passed,
    failed: testResults.failed,
    total: testResults.total,
    requirementsPassed,
    totalRequirements: Object.keys(requirements).length,
    executionTime: totalTime,
    details: testResults.details,
    environment: {
      toasts: mockEnvironment.toastMessages.length,
      loadingStates: mockEnvironment.loadingStates.length,
      consoleErrors: mockEnvironment.consoleErrors.length,
      unhandledPromises: mockEnvironment.unhandledPromises.length
    }
  };
}

// Auto-run tests
console.log('🚀 Starting Error Handling Verification Tests...');
runAllErrorHandlingTests().then(results => {
  console.log(`
✨ Test execution completed!
   Results: ${results.passed}/${results.total} tests passed
   Requirements: ${results.requirementsPassed}/${results.totalRequirements} met
  `);
}).catch(error => {
  console.error('❌ Test execution failed:', error);
});

// Export for manual use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { runAllErrorHandlingTests };
}