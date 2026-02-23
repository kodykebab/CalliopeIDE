// Test file to verify error handling implementation
import { apiClient } from '@/utils/apiClient';
import { handleApiError } from '@/utils/errorHandler';
import { useToast } from '@/components/ErrorAlert';

// Test the API client error handling
async function testApiErrorHandling() {
    console.log('Testing API error handling...');
    
    // Test network error
    try {
        const result = await apiClient.get('http://nonexistent-server.com/api/test');
        console.log('Should not reach here');
    } catch (error) {
        const errorInfo = handleApiError(error);
        console.log('Network error handled:', errorInfo.message);
    }
    
    // Test timeout
    try {
        const result = await apiClient.get('http://httpstat.us/500?sleep=15000', { timeout: 2000 });
        console.log('Should not reach here');
    } catch (error) {
        const errorInfo = handleApiError(error);
        console.log('Timeout error handled:', errorInfo.message);
    }
    
    console.log('API error handling tests completed');
}

// Test toast notifications
function testToastNotifications() {
    console.log('Testing toast notifications...');
    
    const toast = useToast();
    
    toast.success('Success message test');
    toast.error('Error message test');
    toast.warning('Warning message test');
    toast.info('Info message test');
    
    console.log('Toast notification tests completed');
}

// Export for testing
export { testApiErrorHandling, testToastNotifications };