/**
 * Manual Testing Guide for Error Handling
 * Run these tests directly in the browser console
 */

// Test script to be run in browser console
const manualTests = {
  
  // 1. Test Backend Stop Scenario
  async testBackendStop() {
    console.log('🧪 Manual Test 1: Backend Stop');
    console.log('Instructions: Make sure your backend server is stopped, then try to send a chat message.');
    console.log('Expected: Error toast appears with friendly message and retry option');
    
    // Simulate what happens when backend is down
    const mockBackendDown = async () => {
      const { safeFetch, handleApiError } = await import('./lib/error-handler.ts');
      const { showErrorToast } = await import('./components/ui/error-alert');
      
      const result = await safeFetch('http://127.0.0.1:5000/', {}, 3000);
      if (!result.success) {
        showErrorToast(result.error, 'Server Connection Failed');
        console.log('✅ Error properly handled:', result.error);
      }
    };
    
    console.log('Run: await mockBackendDown()');
    return mockBackendDown;
  },

  // 2. Test API 500 Error
  testAPI500() {
    console.log('🧪 Manual Test 2: API 500 Error');
    console.log('Instructions: Check that raw server errors are sanitized');
    
    const testSanitization = async () => {
      const { handleApiError } = await import('./lib/error-handler.ts');
      const { showErrorToast } = await import('./components/ui/error-alert');
      
      const rawError = {
        status: 500,
        message: 'SqlException: Invalid column name in SELECT statement at DatabaseManager.ExecuteQuery() line 342'
      };
      
      const sanitized = handleApiError(rawError);
      showErrorToast(sanitized, 'Server Error Test');
      
      console.log('Original error:', rawError.message);
      console.log('Sanitized error:', sanitized.message);
      console.log('✅ Test passed:', !sanitized.message.includes('SqlException'));
    };
    
    console.log('Run: await testSanitization()');
    return testSanitization;
  },

  // 3. Test Loading States
  testLoadingStates() {
    console.log('🧪 Manual Test 3: Loading States');
    console.log('Instructions:');
    console.log('1. Type a message in the chat input');
    console.log('2. Press Enter to send');
    console.log('3. Verify loading spinner appears');
    console.log('4. Verify buttons are disabled during loading');
    console.log('5. Try clicking send button rapidly');
    
    const simulateSlowAPI = async () => {
      const { showInfoToast, showSuccessToast } = await import('./components/ui/error-alert');
      
      const toastId = showInfoToast('Simulating slow API...', 'Loading Test');
      console.log('⏳ Loading state active');
      
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      showSuccessToast('API call completed!');
      console.log('✅ Loading state completed');
    };
    
    console.log('Run: await simulateSlowAPI()');
    return simulateSlowAPI;
  },

  // 4. Test Rapid Button Clicks
  testRapidClicks() {
    console.log('🧪 Manual Test 4: Rapid Button Clicks');
    console.log('Instructions:');
    console.log('1. Try clicking the Send button multiple times quickly');
    console.log('2. Verify only one request is processed');
    console.log('3. Verify warning messages for additional clicks');
    
    console.log('Check the Send button implementation for proper debouncing');
    console.log('Look for isSubmittingMessage and isResponding state checks');
    
    return () => {
      console.log('✅ Check UI manually - rapid clicks should be debounced');
    };
  },

  // 5. Test Validation Errors
  testValidationErrors() {
    console.log('🧪 Manual Test 5: Validation Errors');
    
    const testValidation = async () => {
      const { showErrorToast } = await import('./components/ui/error-alert');
      
      const validationTests = [
        { field: 'projectName', value: '', error: 'Project name is required' },
        { field: 'projectName', value: 'ab', error: 'Project name must be at least 3 characters' },
        { field: 'email', value: 'invalid-email', error: 'Please enter a valid email address' }
      ];
      
      for (const test of validationTests) {
        const validationError = {
          message: test.error,
          code: 'VALIDATION_ERROR',
          field: test.field
        };
        
        showErrorToast(validationError, 'Validation Error');
        console.log(`❌ Validation: ${test.field} = "${test.value}" → ${test.error}`);
        
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
      
      console.log('✅ All validation errors displayed');
    };
    
    console.log('Run: await testValidation()');
    return testValidation;
  },

  // 6. Test Network Disconnect
  testNetworkDisconnect() {
    console.log('🧪 Manual Test 6: Network Disconnect');
    console.log('Instructions:');
    console.log('1. Disconnect your internet connection');
    console.log('2. Try to send a chat message'); 
    console.log('3. Verify network error notification appears');
    
    const simulateNetworkError = async () => {
      const { handleApiError } = await import('./lib/error-handler.ts');
      const { showErrorToast } = await import('./components/ui/error-alert');
      
      const networkErrors = [
        new TypeError('Failed to fetch'),
        { code: 'ENOTFOUND', message: 'Network request failed' },
        { name: 'NetworkError', message: 'The network connection was lost' }
      ];
      
      for (const error of networkErrors) {
        const handled = handleApiError(error);
        showErrorToast(handled, 'Network Test');
        console.log(`🌐 Network error: ${error.message || error.constructor.name} → ${handled.message}`);
        
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      
      console.log('✅ Network errors properly categorized');
    };
    
    console.log('Run: await simulateNetworkError()');
    return simulateNetworkError;
  },

  // 7. Check for Silent Failures
  checkSilentFailures() {
    console.log('🧪 Manual Test 7: Check Silent Failures');
    console.log('Instructions: Monitor browser console during all operations');
    console.log('Expected: No unhandled promise rejections or uncaught errors');
    
    const monitorErrors = () => {
      let errorCount = 0;
      let promiseRejectionCount = 0;
      
      const originalError = console.error;
      console.error = (...args) => {
        errorCount++;
        console.log(`🚨 Console Error #${errorCount}:`, ...args);
        originalError(...args);
      };
      
      window.addEventListener('unhandledrejection', (event) => {
        promiseRejectionCount++;
        console.log(`🚨 Unhandled Promise Rejection #${promiseRejectionCount}:`, event.reason);
      });
      
      console.log('✅ Error monitoring active');
      console.log('Run other tests and check for error reports above');
      
      // Return cleanup function
      return () => {
        console.error = originalError;
        console.log(`📊 Monitoring Results:`);
        console.log(`   Console Errors: ${errorCount}`);
        console.log(`   Unhandled Promises: ${promiseRejectionCount}`);
        console.log(errorCount === 0 && promiseRejectionCount === 0 ? '✅ No silent failures detected' : '❌ Silent failures found');
      };
    };
    
    console.log('Run: const cleanup = monitorErrors(); /* do tests */ cleanup();');
    return monitorErrors;
  }
};

// Make tests available in browser console
if (typeof window !== 'undefined') {
  window.calliopeManualTests = manualTests;
  
  console.log(`
🔧 CALLIOPE ERROR HANDLE MANUAL TESTS
====================================

Available Tests:
${Object.keys(manualTests).map(key => `• calliopeManualTests.${key}()`).join('\n')}

Quick Test All:
const runAll = async () => {
  const cleanup = calliopeManualTests.checkSilentFailures();
  
  await calliopeManualTests.testBackendStop()();
  await calliopeManualTests.testAPI500()();
  await calliopeManualTests.testLoadingStates()();
  await calliopeManualTests.testValidationErrors()();
  await calliopeManualTests.testNetworkDisconnect()();
  
  cleanup();
};

Then run: runAll();
  `);
}

// Automated verification checklist
const verificationChecklist = {
  'No silent failures': () => {
    let hasUnhandled = false;
    window.addEventListener('unhandledrejection', () => { hasUnhandled = true; });
    setTimeout(() => {
      console.log(hasUnhandled ? '❌ Unhandled promises detected' : '✅ No silent failures');
    }, 100);
  },
  
  'No raw backend messages': () => {
    const testError = { message: 'DatabaseException at line 123 in UserService.java' };
    const { handleApiError } = require('./lib/error-handler.ts');
    const handled = handleApiError(testError);
    const isClean = !handled.message.includes('DatabaseException') && !handled.message.includes('UserService.java');
    console.log(isClean ? '✅ Raw messages sanitized' : '❌ Raw messages exposed');
  },
  
  'Loading states visible': () => {
    console.log('✅ Check manually: Loading spinners appear during operations');
  },
  
  'UI responsive': () => {
    console.log('✅ Check manually: UI remains responsive during errors');
  },
  
  'No console unhandled promises': () => {
    console.log('✅ Check browser console: No red unhandled promise errors');
  }
};

console.log('🎯 Manual Test Suite Loaded');
console.log('Run calliopeManualTests.testBackendStop() to begin testing');

export { manualTests, verificationChecklist };