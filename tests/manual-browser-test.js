/**
 * Manual Error Handling Test - Run this in browser console
 * Open app in browser → F12 (dev tools) → Console tab → paste this code
 */

console.log('🧪 Starting Manual Error Handling Test...');

// Test 1: Simulate backend down error
async function testBackendDown() {
  console.log('\n1️⃣ Testing Backend Down...');
  try {
    const response = await fetch('/api/nonexistent');
    console.log('Response:', response);
  } catch (error) {
    console.log('✅ Caught fetch error:', error.message);
  }
}

// Test 2: Test the error handler directly
function testErrorHandler() {
  console.log('\n2️⃣ Testing Error Handler...');
  
  // Simulate 500 Error with sensitive info
  const sensitiveError = {
    status: 500,
    message: 'SQLException: Connection failed at line 1247 in DatabaseController.java'
  };
  
  // This should be available if your error handler is loaded
  if (typeof window.handleApiError === 'function') {
    const sanitized = window.handleApiError(sensitiveError);
    console.log('Raw error:', sensitiveError.message);
    console.log('✅ Sanitized:', sanitized.message);
  } else {
    console.log('⚠️  Error handler not found on window object');
  }
}

// Test 3: Check for toast system
function testToastSystem() {
  console.log('\n3️⃣ Testing Toast System...');
  
  // Look for toast container
  const toastContainer = document.querySelector('[data-testid="toast-container"]') || 
                        document.querySelector('.toast-container') ||
                        document.querySelector('#toast-root');
  
  if (toastContainer) {
    console.log('✅ Toast container found:', toastContainer);
  } else {
    console.log('⚠️  Toast container not found - check if ErrorAlert component is rendered');
  }
}

// Test 4: Check ErrorBoundary
function testErrorBoundary() {
  console.log('\n4️⃣ Testing Error Boundary...');
  
  // Look for error boundary
  const errorBoundary = document.querySelector('[data-error-boundary]');
  if (errorBoundary) {
    console.log('✅ Error boundary found');
  } else {
    console.log('ℹ️  Error boundary not visible (good - no errors caught)');
  }
}

// Test 5: Simulate chat error
async function testChatError() {
  console.log('\n5️⃣ Testing Chat Error...');
  
  // Find send button
  const sendButton = document.querySelector('button[type="submit"]') ||
                    document.querySelector('button:contains("Send")') ||
                    document.querySelector('.send-button');
  
  if (sendButton) {
    console.log('✅ Send button found:', sendButton);
    console.log('💡 Try clicking send without backend running to test error handling');
  } else {
    console.log('ℹ️  Send button not found - may need to navigate to chat interface');
  }
}

// Test 6: Check loading states
function testLoadingStates() {
  console.log('\n6️⃣ Checking Loading States...');
  
  const loadingElements = document.querySelectorAll('[data-loading], .loading, .spinner');
  if (loadingElements.length > 0) {
    console.log('✅ Loading elements found:', loadingElements.length);
  } else {
    console.log('ℹ️  No loading states currently visible');
  }
}

// Run all tests
async function runManualTests() {
  console.log('🎯 MANUAL ERROR HANDLING VERIFICATION');
  console.log('====================================');
  
  testToastSystem();
  testErrorBoundary();
  testErrorHandler();
  testLoadingStates();
  testChatError();
  await testBackendDown();
  
  console.log('\n✅ Manual verification complete!');
  console.log('\n📋 CHECKLIST - Verify these manually:');
  console.log('1. Stop backend server (if running)');
  console.log('2. Try to send a chat message');
  console.log('3. Should see user-friendly error with retry button');
  console.log('4. No raw error messages in console'); 
  console.log('5. Loading spinner shows during requests');
  console.log('6. Rapid button clicks are prevented');
  
  console.log('\n🔍 Check browser console for any red errors!');
}

// Auto-run
runManualTests();

// Export functions for individual testing
window.testErrorHandling = {
  runAll: runManualTests,
  testBackendDown,
  testErrorHandler, 
  testToastSystem,
  testErrorBoundary,
  testChatError,
  testLoadingStates
};

console.log('\n💡 Functions available: window.testErrorHandling');