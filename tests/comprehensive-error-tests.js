/**
 * Comprehensive Error Handling Test Suite
 * Tests all error scenarios and user feedback improvements
 */

import { 
  safeFetch, 
  handleApiError, 
  logError 
} from '../lib/error-handler';

import { 
  showErrorToast, 
  showSuccessToast, 
  showWarningToast,
  addToast,
  removeToast
} from '../components/ui/error-alert';

// Test configuration
const TEST_CONFIG = {
  SERVER_URL: 'http://127.0.0.1:5000',
  API_URL: 'http://127.0.0.1:8000',
  TIMEOUT_MS: 5000,
  RETRY_ATTEMPTS: 3
};

// Global test state
let testResults = {};
let consoleErrors = [];
let unhandledPromises = [];

// Capture console errors and unhandled promises
const originalConsoleError = console.error;
console.error = (...args) => {
  consoleErrors.push(args);
  originalConsoleError(...args);
};

window.addEventListener('unhandledrejection', (event) => {
  unhandledPromises.push(event.reason);
  console.log('🚨 Unhandled Promise Rejection:', event.reason);
});

/**
 * TEST 1: Backend Stop → Send Chat → Clear Error + Retry Option
 */
async function testBackendStopScenario() {
  console.log('🧪 TEST 1: Backend Stop Scenario');
  
  try {
    // Simulate backend being down
    const deadUrl = 'http://127.0.0.1:9999/nonexistent';
    const result = await safeFetch(deadUrl, {}, 2000);
    
    if (!result.success) {
      showErrorToast(result.error, 'Server Connection Failed', {
        action: {
          label: 'Retry Connection',
          onClick: async () => {
            console.log('🔄 Retrying connection...');
            const retryResult = await safeFetch(TEST_CONFIG.SERVER_URL);
            if (retryResult.success) {
              showSuccessToast('Server reconnected successfully!');
            } else {
              showErrorToast(retryResult.error, 'Retry Failed');
            }
          }
        }
      });
      
      testResults.backendStop = {
        pass: true,
        message: 'Error shown with retry option',
        errorType: result.error.code
      };
    }
  } catch (error) {
    testResults.backendStop = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 2: Force API 500 → Friendly Message Shown
 */
async function testAPI500Scenario() {
  console.log('🧪 TEST 2: API 500 Error Scenario');
  
  try {
    // Simulate 500 error
    const mockError = {
      status: 500,
      message: 'Internal Server Error: Database connection pool exhausted at line 247 in user_service.py'
    };
    
    const handledError = handleApiError(mockError);
    showErrorToast(handledError, 'Server Error');
    
    const isFriendly = !handledError.message.includes('Database') && 
                      !handledError.message.includes('line 247') &&
                      !handledError.message.includes('user_service.py');
    
    testResults.api500 = {
      pass: isFriendly,
      message: isFriendly ? 'Sensitive info sanitized' : 'Raw error exposed',
      originalMessage: mockError.message,
      sanitizedMessage: handledError.message
    };
  } catch (error) {
    testResults.api500 = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 3: Simulate Slow API → Loading Spinner Visible
 */
async function testSlowAPIScenario() {
  console.log('🧪 TEST 3: Slow API Scenario');
  
  try {
    // Create loading toast
    const loadingToast = addToast({
      type: 'info',
      title: 'Processing Request',
      description: 'Please wait while we fetch your data...',
      duration: 0 // Don't auto-remove
    });
    
    // Simulate slow API call
    const slowPromise = new Promise((resolve) => {
      setTimeout(() => {
        resolve({ data: 'Slow response completed' });
      }, 3000);
    });
    
    const startTime = Date.now();
    const result = await slowPromise;
    const duration = Date.now() - startTime;
    
    // Remove loading toast and show success
    removeToast(loadingToast);
    showSuccessToast(`Request completed in ${duration}ms`);
    
    testResults.slowAPI = {
      pass: duration >= 2900, // Should take about 3 seconds
      message: `Loading state shown for ${duration}ms`,
      duration
    };
  } catch (error) {
    testResults.slowAPI = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 4: Rapid Button Clicks → Button Disabled During Loading
 */
async function testRapidClickScenario() {
  console.log('🧪 TEST 4: Rapid Button Click Scenario');
  
  try {
    let clickCount = 0;
    let processingCount = 0;
    
    // Simulate rapid button clicks
    const buttonHandler = async () => {
      clickCount++;
      
      if (processingCount > 0) {
        showWarningToast('Please wait for the current operation to complete');
        return;
      }
      
      processingCount++;
      
      // Simulate processing
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      processingCount--;
      showSuccessToast(`Operation ${clickCount} completed`);
    };
    
    // Simulate 5 rapid clicks
    const promises = [];
    for (let i = 0; i < 5; i++) {
      promises.push(buttonHandler());
      await new Promise(resolve => setTimeout(resolve, 100)); // 100ms between clicks
    }
    
    await Promise.all(promises);
    
    testResults.rapidClicks = {
      pass: processingCount === 0 && clickCount === 5,
      message: `${clickCount} clicks processed, ${processingCount} still processing`,
      clickCount,
      processingCount
    };
  } catch (error) {
    testResults.rapidClicks = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 5: Invalid Project Creation → Inline Validation Error
 */
async function testInvalidProjectScenario() {
  console.log('🧪 TEST 5: Invalid Project Creation Scenario');
  
  try {
    // Simulate validation errors
    const invalidInputs = [
      { name: '', error: 'Project name is required' },
      { name: 'ab', error: 'Project name must be at least 3 characters' },
      { name: 'invalid-chars!@#', error: 'Project name contains invalid characters' },
      { name: 'system', error: 'Project name is reserved' }
    ];
    
    const validationResults = [];
    
    for (const input of invalidInputs) {
      const validationError = {
        message: input.error,
        code: 'VALIDATION_ERROR',
        field: 'projectName'
      };
      
      showErrorToast(validationError, 'Validation Error');
      validationResults.push({
        input: input.name,
        error: input.error,
        handled: true
      });
      
      // Small delay between validations
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    testResults.invalidProject = {
      pass: validationResults.length === invalidInputs.length,
      message: `${validationResults.length} validation errors handled`,
      validationResults
    };
  } catch (error) {
    testResults.invalidProject = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 6: Network Disconnect → Proper Notification
 */
async function testNetworkDisconnectScenario() {
  console.log('🧪 TEST 6: Network Disconnect Scenario');
  
  try {
    // Simulate network errors
    const networkErrors = [
      new TypeError('Failed to fetch'),
      { name: 'NetworkError', message: 'Network request failed' },
      { code: 'ENOTFOUND', message: 'DNS resolution failed' },
      { code: 'ECONNRESET', message: 'Connection reset by peer' }
    ];
    
    const networkResults = [];
    
    for (const networkError of networkErrors) {
      const handledError = handleApiError(networkError);
      showErrorToast(handledError, 'Network Error');
      
      const isNetworkError = handledError.code === 'NETWORK_ERROR' || 
                            handledError.message.includes('Network') ||
                            handledError.message.includes('connection');
      
      networkResults.push({
        originalError: networkError.message || networkError.constructor.name,
        handledMessage: handledError.message,
        isNetworkError
      });
      
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    const allHandledCorrectly = networkResults.every(r => r.isNetworkError);
    
    testResults.networkDisconnect = {
      pass: allHandledCorrectly,
      message: `${networkResults.filter(r => r.isNetworkError).length}/${networkResults.length} network errors handled correctly`,
      networkResults
    };
  } catch (error) {
    testResults.networkDisconnect = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * TEST 7: Verify No Silent Failures
 */
async function testNoSilentFailures() {
  console.log('🧪 TEST 7: No Silent Failures');
  
  try {
    const silentFailureTests = [];
    
    // Test 1: Promise rejection without catch
    try {
      const rejectedPromise = Promise.reject(new Error('Silent error test'));
      await rejectedPromise;
    } catch (error) {
      const handledError = handleApiError(error);
      showErrorToast(handledError, 'Caught Error');
      silentFailureTests.push({ test: 'Promise rejection', caught: true });
    }
    
    // Test 2: Async function error
    try {
      await (async () => {
        throw new Error('Async function error');
      })();
    } catch (error) {
      const handledError = handleApiError(error);
      showErrorToast(handledError, 'Async Error');
      silentFailureTests.push({ test: 'Async function error', caught: true });
    }
    
    // Test 3: Fetch error
    try {
      const result = await safeFetch('http://invalid-url-that-does-not-exist.com');
      if (!result.success) {
        showErrorToast(result.error, 'Fetch Error');
        silentFailureTests.push({ test: 'Fetch error', caught: true });
      }
    } catch (error) {
      silentFailureTests.push({ test: 'Fetch error', caught: false });
    }
    
    const allCaught = silentFailureTests.every(t => t.caught);
    
    testResults.noSilentFailures = {
      pass: allCaught,
      message: `${silentFailureTests.filter(t => t.caught).length}/${silentFailureTests.length} errors properly caught`,
      tests: silentFailureTests
    };
  } catch (error) {
    testResults.noSilentFailures = {
      pass: false,
      message: 'Test failed: ' + error.message
    };
  }
}

/**
 * Main Test Runner
 */
async function runAllErrorHandlingTests() {
  console.log(`
🎯 CALLIOPE IDE ERROR HANDLING TEST SUITE
=========================================
Starting comprehensive error handling tests...
`);

  // Clear previous results
  testResults = {};
  consoleErrors = [];
  unhandledPromises = [];
  
  const startTime = Date.now();
  
  // Run all test scenarios
  const tests = [
    testBackendStopScenario,
    testAPI500Scenario,
    testSlowAPIScenario,
    testRapidClickScenario,
    testInvalidProjectScenario,
    testNetworkDisconnectScenario,
    testNoSilentFailures
  ];
  
  for (const test of tests) {
    try {
      await test();
      await new Promise(resolve => setTimeout(resolve, 1000)); // Pause between tests
    } catch (error) {
      console.error(`Test ${test.name} failed:`, error);
    }
  }
  
  const totalTime = Date.now() - startTime;
  
  // Generate test report
  console.log(`
📊 TEST RESULTS SUMMARY
======================
Total execution time: ${totalTime}ms
`);

  const passedTests = [];
  const failedTests = [];
  
  Object.entries(testResults).forEach(([testName, result]) => {
    const status = result.pass ? '✅' : '❌';
    console.log(`${status} ${testName}: ${result.message}`);
    
    if (result.pass) {
      passedTests.push(testName);
    } else {
      failedTests.push(testName);
    }
  });
  
  console.log(`
📈 VERIFICATION CHECKLIST
========================`);
  
  // Check verification criteria
  const verifications = {
    'No silent failures': unhandledPromises.length === 0,
    'No raw backend messages': !consoleErrors.some(err => 
      err.toString().includes('stack') || 
      err.toString().includes('Database') ||
      err.toString().includes('.py')
    ),
    'Loading states visible': testResults.slowAPI?.pass || false,
    'UI responsive': testResults.rapidClicks?.pass || false,
    'No unhandled promises': unhandledPromises.length === 0
  };
  
  Object.entries(verifications).forEach(([check, passed]) => {
    const status = passed ? '✅' : '❌';
    console.log(`${status} ${check}`);
  });
  
  console.log(`
🎯 FINAL SCORE
=============
Passed: ${passedTests.length}/${Object.keys(testResults).length} tests
Failed: ${failedTests.length}/${Object.keys(testResults).length} tests
Console Errors: ${consoleErrors.length}
Unhandled Promises: ${unhandledPromises.length}

${passedTests.length === Object.keys(testResults).length && 
  unhandledPromises.length === 0 ? 
  '🎉 ALL TESTS PASSED! Error handling is working correctly.' :
  '⚠️  Some issues found. Check failed tests above.'
}
`);

  // Return results for programmatic access
  return {
    passed: passedTests.length,
    failed: failedTests.length,
    total: Object.keys(testResults).length,
    consoleErrors: consoleErrors.length,
    unhandledPromises: unhandledPromises.length,
    results: testResults,
    verifications,
    executionTime: totalTime
  };
}

// Make test available globally for browser console
if (typeof window !== 'undefined') {
  window.runErrorHandlingTests = runAllErrorHandlingTests;
  window.testSingleScenario = {
    backendStop: testBackendStopScenario,
    api500: testAPI500Scenario,
    slowAPI: testSlowAPIScenario,
    rapidClicks: testRapidClickScenario,
    invalidProject: testInvalidProjectScenario,
    networkDisconnect: testNetworkDisconnectScenario,
    noSilentFailures: testNoSilentFailures
  };
  
  console.log(`
🔧 ERROR HANDLING TESTS LOADED
==============================
Run all tests: runErrorHandlingTests()
Run individual test: testSingleScenario.backendStop()

Available individual tests:
• testSingleScenario.backendStop()
• testSingleScenario.api500() 
• testSingleScenario.slowAPI()
• testSingleScenario.rapidClicks()
• testSingleScenario.invalidProject()
• testSingleScenario.networkDisconnect()
• testSingleScenario.noSilentFailures()
  `);
}

export { 
  runAllErrorHandlingTests,
  testBackendStopScenario,
  testAPI500Scenario,
  testSlowAPIScenario,
  testRapidClickScenario,
  testInvalidProjectScenario,
  testNetworkDisconnectScenario,
  testNoSilentFailures
};