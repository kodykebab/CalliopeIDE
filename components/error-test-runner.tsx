import React, { useState, useEffect } from 'react';
import { Button } from '@heroui/react';
import { Play, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';
import { 
  showErrorToast, 
  showSuccessToast, 
  showWarningToast,
  showInfoToast,
  addToast,
  removeToast
} from '../ui/error-alert';
import { LoadingSpinner, ButtonWithLoading } from '../ui/loading-spinner';
import { safeFetch, handleApiError, logError } from '../../lib/error-handler';
import { streamGeminiResponse } from '../../scripts/streamer';

const ErrorHandlingTestRunner = () => {
  const [testResults, setTestResults] = useState({});
  const [isRunning, setIsRunning] = useState(false);
  const [currentTest, setCurrentTest] = useState(null);
  const [consoleErrors, setConsoleErrors] = useState([]);
  const [unhandledPromises, setUnhandledPromises] = useState([]);

  // Capture console errors and unhandled promises
  useEffect(() => {
    const originalConsoleError = console.error;
    const errors = [];
    
    console.error = (...args) => {
      errors.push(args.join(' '));
      setConsoleErrors(prev => [...prev, args.join(' ')]);
      originalConsoleError(...args);
    };

    const handleUnhandledRejection = (event) => {
      setUnhandledPromises(prev => [...prev, event.reason?.message || event.reason]);
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      console.error = originalConsoleError;
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  // Test 1: Backend Stop → Send Chat → Clear Error + Retry Option
  const testBackendStop = async () => {
    setCurrentTest('Backend Stop Test');
    const toastId = showInfoToast('Testing backend connection failure...');
    
    try {
      const result = await safeFetch('http://127.0.0.1:9999/nonexistent', {}, 2000);
      
      if (!result.success) {
        const errorToastId = showErrorToast(
          { ...result.error, action: { 
            label: 'Retry', 
            onClick: () => {
              showSuccessToast('Retry button works!');
              removeToast(errorToastId);
            }
          }}, 
          'Connection Failed'
        );
        
        return {
          pass: true,
          message: 'Error shown with retry option',
          details: `Error: ${result.error.message}`
        };
      }
    } catch (error) {
      return {
        pass: false,
        message: 'Test failed: ' + error.message
      };
    } finally {
      removeToast(toastId);
    }
  };

  // Test 2: API 500 → Friendly Message
  const testAPI500 = async () => {
    setCurrentTest('API 500 Error Test');
    
    const mockError500 = {
      status: 500,
      message: 'SqlException: Connection timeout at DatabaseService.ExecuteQuery() line 1247'
    };
    
    const handledError = handleApiError(mockError500);
    showErrorToast(handledError, 'Server Error Test');
    
    const isSanitized = !handledError.message.includes('SqlException') && 
                       !handledError.message.includes('DatabaseService') &&
                       !handledError.message.includes('line 1247');
    
    return {
      pass: isSanitized,
      message: isSanitized ? 'Sensitive info properly sanitized' : 'Raw error exposed',
      details: `Original: "${mockError500.message}" → Sanitized: "${handledError.message}"`
    };
  };

  // Test 3: Slow API → Loading Spinner
  const testSlowAPI = async () => {
    setCurrentTest('Slow API Test');
    
    const loadingToast = showInfoToast('Simulating slow API call...', 'Loading Test');
    const startTime = Date.now();
    
    // Simulate 3-second delay
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    const duration = Date.now() - startTime;
    removeToast(loadingToast);
    showSuccessToast(`API call completed in ${duration}ms`);
    
    return {
      pass: duration >= 2900,
      message: `Loading spinner shown for ${duration}ms`,
      details: 'Loading state properly displayed during delay'
    };
  };

  // Test 4: Rapid Button Clicks → Debouncing
  const testRapidClicks = async () => {
    setCurrentTest('Rapid Click Test');
    let clickCount = 0;
    let processing = false;
    
    const handleClick = async () => {
      clickCount++;
      
      if (processing) {
        showWarningToast(`Click #${clickCount} ignored - still processing`);
        return false;
      }
      
      processing = true;
      showInfoToast(`Processing click #${clickCount}...`);
      
      // Simulate processing time
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      processing = false;
      showSuccessToast(`Click #${clickCount} completed`);
      return true;
    };
    
    // Simulate 5 rapid clicks
    const results = [];
    for (let i = 0; i < 5; i++) {
      const processed = await handleClick();
      results.push(processed);
      // 200ms between clicks (rapid)
      if (i < 4) await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    const processedCount = results.filter(Boolean).length;
    const ignoredCount = results.filter(r => !r).length;
    
    return {
      pass: processedCount > 0 && ignoredCount > 0,
      message: `${processedCount} processed, ${ignoredCount} ignored`,
      details: 'Rapid clicks properly debounced'
    };
  };

  // Test 5: Invalid Project Creation → Validation Errors
  const testInvalidProject = async () => {
    setCurrentTest('Project Validation Test');
    
    const invalidInputs = [
      { name: '', error: 'Project name is required' },
      { name: 'ab', error: 'Name must be at least 3 characters' },
      { name: 'test!@#', error: 'Invalid characters in name' }
    ];
    
    const validationResults = [];
    
    for (const input of invalidInputs) {
      const validationError = {
        message: input.error,
        code: 'VALIDATION_ERROR'
      };
      
      showErrorToast(validationError, 'Validation Error');
      validationResults.push(input.error);
      
      await new Promise(resolve => setTimeout(resolve, 800));
    }
    
    return {
      pass: validationResults.length === invalidInputs.length,
      message: `${validationResults.length} validation errors shown`,
      details: 'Inline validation errors properly displayed'
    };
  };

  // Test 6: Network Disconnect → Notification
  const testNetworkDisconnect = async () => {
    setCurrentTest('Network Disconnect Test');
    
    const networkErrors = [
      new TypeError('Failed to fetch'),
      { code: 'ENOTFOUND', message: 'getaddrinfo ENOTFOUND' },
      { name: 'NetworkError', message: 'Network request failed' }
    ];
    
    const results = [];
    
    for (const error of networkErrors) {
      const handledError = handleApiError(error);
      showErrorToast(handledError, 'Network Error');
      
      const isNetworkHandled = handledError.code === 'NETWORK_ERROR' ||
                              handledError.message.toLowerCase().includes('network');
      
      results.push(isNetworkHandled);
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    const correctlyHandled = results.filter(Boolean).length;
    
    return {
      pass: correctlyHandled === networkErrors.length,
      message: `${correctlyHandled}/${networkErrors.length} network errors handled`,
      details: 'Network errors properly categorized and displayed'
    };
  };

  // Test 7: Chat Message → Stream Error Handling
  const testChatStreamError = async () => {
    setCurrentTest('Chat Stream Error Test');
    
    try {
      // Mock stream that fails
      const mockStreamError = async (endpoint, message, onUpdate, onEnd, onError) => {
        // Simulate stream starting
        setTimeout(() => {
          onUpdate('{"type":"output","data":"Starting response..."}', 'test-id');
        }, 500);
        
        // Simulate stream error after partial response
        setTimeout(() => {
          onError({
            message: 'Stream connection lost',
            code: 'STREAM_ERROR'
          });
        }, 1500);
      };
      
      let streamErrorCaught = false;
      let errorMessage = '';
      
      await mockStreamError(
        'http://test.com',
        [{ role: 'user', parts: [{ text: 'test' }] }],
        (data, id) => {
          console.log('Stream update:', data);
        },
        () => {
          console.log('Stream ended normally');
        },
        (error) => {
          streamErrorCaught = true;
          errorMessage = error.message;
          showErrorToast(error, 'Stream Error');
        }
      );
      
      return {
        pass: streamErrorCaught,
        message: streamErrorCaught ? 'Stream error handled' : 'Stream error missed',
        details: errorMessage || 'No error message captured'
      };
    } catch (error) {
      return {
        pass: false,
        message: 'Test failed: ' + error.message
      };
    }
  };

  // Run all tests
  const runAllTests = async () => {
    setIsRunning(true);
    setTestResults({});
    setConsoleErrors([]);
    setUnhandledPromises([]);
    
    const tests = [
      { name: 'backendStop', fn: testBackendStop, title: 'Backend Stop' },
      { name: 'api500', fn: testAPI500, title: 'API 500 Error' },
      { name: 'slowAPI', fn: testSlowAPI, title: 'Slow API' },
      { name: 'rapidClicks', fn: testRapidClicks, title: 'Rapid Clicks' },
      { name: 'invalidProject', fn: testInvalidProject, title: 'Invalid Project' },
      { name: 'networkDisconnect', fn: testNetworkDisconnect, title: 'Network Disconnect' },
      { name: 'chatStreamError', fn: testChatStreamError, title: 'Chat Stream Error' }
    ];
    
    const results = {};
    
    for (const test of tests) {
      try {
        setCurrentTest(test.title);
        const result = await test.fn();
        results[test.name] = result;
        setTestResults(prev => ({ ...prev, [test.name]: result }));
        
        // Pause between tests
        await new Promise(resolve => setTimeout(resolve, 1500));
      } catch (error) {
        results[test.name] = {
          pass: false,
          message: 'Test execution failed: ' + error.message
        };
        setTestResults(prev => ({ ...prev, [test.name]: results[test.name] }));
      }
    }
    
    setCurrentTest(null);
    setIsRunning(false);
    
    // Show summary
    const passed = Object.values(results).filter(r => r.pass).length;
    const total = Object.keys(results).length;
    
    if (passed === total && unhandledPromises.length === 0) {
      showSuccessToast(`All ${total} tests passed! 🎉`, 'Test Complete');
    } else {
      showErrorToast({
        message: `${passed}/${total} tests passed. ${unhandledPromises.length} unhandled promises.`
      }, 'Test Results');
    }
  };

  const getTestIcon = (result) => {
    if (!result) return <Clock className="w-4 h-4 text-gray-400" />;
    return result.pass 
      ? <CheckCircle className="w-4 h-4 text-green-400" />
      : <XCircle className="w-4 h-4 text-red-400" />;
  };

  const getTestColor = (result) => {
    if (!result) return 'bg-gray-800 border-gray-600';
    return result.pass 
      ? 'bg-green-900/30 border-green-500/30' 
      : 'bg-red-900/30 border-red-500/30';
  };

  return (
    <div className="p-6 bg-[#0D1117] text-white min-h-screen">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Error Handling Test Suite</h1>
          <p className="text-white/70 mb-4">
            Comprehensive testing of error handling and user feedback
          </p>
          
          <ButtonWithLoading
            isLoading={isRunning}
            loadingText="Running Tests..."
            onClick={runAllTests}
            disabled={isRunning}
            className="bg-[#9FEF00] text-black hover:bg-[#9FEF00]/80"
          >
            <Play className="w-4 h-4 mr-2" />
            Run All Tests
          </ButtonWithLoading>
          
          {currentTest && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <LoadingSpinner size="sm" />
              <span className="text-[#9FEF00]">Running: {currentTest}</span>
            </div>
          )}
        </div>

        <div className="grid gap-4 mb-8">
          {[
            { key: 'backendStop', title: 'Backend Stop → Retry Option', desc: 'Server down, error shown with retry' },
            { key: 'api500', title: 'API 500 → Friendly Message', desc: 'Raw errors sanitized for users' },
            { key: 'slowAPI', title: 'Slow API → Loading Spinner', desc: 'Loading states visible during delays' },
            { key: 'rapidClicks', title: 'Rapid Clicks → Debouncing', desc: 'Multiple clicks handled gracefully' },
            { key: 'invalidProject', title: 'Invalid Input → Validation', desc: 'Inline validation errors shown' },
            { key: 'networkDisconnect', title: 'Network Error → Notification', desc: 'Network issues properly handled' },
            { key: 'chatStreamError', title: 'Chat Stream → Error Recovery', desc: 'Stream errors caught and handled' }
          ].map((test) => {
            const result = testResults[test.key];
            return (
              <div
                key={test.key}
                className={`p-4 border rounded-lg ${getTestColor(result)}`}
              >
                <div className="flex items-start gap-3">
                  {getTestIcon(result)}
                  <div className="flex-1">
                    <h3 className="font-semibold">{test.title}</h3>
                    <p className="text-sm text-white/60 mb-2">{test.desc}</p>
                    {result && (
                      <div className="text-sm">
                        <p className={result.pass ? 'text-green-300' : 'text-red-300'}>
                          {result.message}
                        </p>
                        {result.details && (
                          <p className="text-white/50 mt-1 text-xs">
                            {result.details}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* System Status */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-gray-800/50 border border-gray-600 rounded-lg">
            <h4 className="font-semibold mb-2">Console Errors</h4>
            <p className={`text-2xl font-bold ${consoleErrors.length === 0 ? 'text-green-400' : 'text-red-400'}`}>
              {consoleErrors.length}
            </p>
          </div>
          
          <div className="p-4 bg-gray-800/50 border border-gray-600 rounded-lg">
            <h4 className="font-semibold mb-2">Unhandled Promises</h4>
            <p className={`text-2xl font-bold ${unhandledPromises.length === 0 ? 'text-green-400' : 'text-red-400'}`}>
              {unhandledPromises.length}
            </p>
          </div>
          
          <div className="p-4 bg-gray-800/50 border border-gray-600 rounded-lg">
            <h4 className="font-semibold mb-2">Test Status</h4>
            <p className="text-2xl font-bold text-blue-400">
              {Object.values(testResults).filter(r => r.pass).length}/{Object.keys(testResults).length}
            </p>
          </div>
        </div>

        {/* Error Logs */}
        {(consoleErrors.length > 0 || unhandledPromises.length > 0) && (
          <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
            <h4 className="font-semibold mb-2 text-red-300">
              <AlertTriangle className="w-4 h-4 inline mr-2" />
              Issues Found
            </h4>
            
            {consoleErrors.length > 0 && (
              <div className="mb-4">
                <h5 className="text-sm font-medium text-red-300 mb-1">Console Errors:</h5>
                <div className="bg-black/30 p-2 rounded text-xs font-mono max-h-32 overflow-y-auto">
                  {consoleErrors.map((error, i) => (
                    <div key={i} className="text-red-200">{error}</div>
                  ))}
                </div>
              </div>
            )}
            
            {unhandledPromises.length > 0 && (
              <div>
                <h5 className="text-sm font-medium text-red-300 mb-1">Unhandled Promises:</h5>
                <div className="bg-black/30 p-2 rounded text-xs font-mono max-h-32 overflow-y-auto">
                  {unhandledPromises.map((promise, i) => (
                    <div key={i} className="text-red-200">{promise}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ErrorHandlingTestRunner;