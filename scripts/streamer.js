/**
 * Enhanced streaming function with comprehensive error handling
 */
export async function streamGeminiResponse(endpoint, message, onUpdate, onEnd, onError) {
    const messageText = message[message.length - 1].parts[0].text;
    const id = Math.random().toString();
    
    // Store reader ID safely
    try {
        if (typeof window !== 'undefined' && window.localStorage) {
            window.localStorage.setItem("readerId", id);
        }
    } catch (error) {
        console.warn('Failed to store reader ID:', error);
    }
    
    let reader = null;
    let isStreamCancelled = false;
    
    try {
        // Validate inputs
        if (!endpoint) {
            throw new Error('Streaming endpoint is required');
        }
        
        if (!messageText || !messageText.trim()) {
            throw new Error('Message content is required');
        }
        
        // Add timeout to fetch request
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            controller.abort();
        }, 30000); // 30 second timeout
        
        const response = await fetch(endpoint + "/?data=" + encodeURIComponent(messageText), {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            },
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        // Check response status
        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}: ${response.statusText}`);
        }
        
        if (!response.body) {
            throw new Error("Streaming is not supported in this environment");
        }
        
        reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        
        while (!isStreamCancelled) {
            try {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n').filter(line => line.trim().startsWith('data: '));
                
                for (const line of lines) {
                    try {
                        const text = String(line.split("data: ")[1]);
                        
                        // Validate that callback is still valid
                        if (typeof onUpdate === 'function') {
                            onUpdate(text, id);
                        }
                    } catch (parseError) {
                        console.warn('Failed to parse streaming chunk:', parseError);
                        // Continue processing other chunks
                        continue;
                    }
                }
            } catch (readError) {
                if (readError.name === 'AbortError') {
                    throw new Error('Streaming request was cancelled or timed out');
                }
                throw readError;
            }
        }
        
        // Successfully completed
        if (typeof onEnd === 'function') {
            onEnd();
        }
        
    } catch (error) {
        console.error('Streaming error:', error);
        
        // Clean up reader if it exists
        if (reader) {
            try {
                reader.cancel();
            } catch (cleanupError) {
                console.warn('Failed to cancel reader:', cleanupError);
            }
        }
        
        // Clear reader ID on error
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                window.localStorage.setItem("readerId", "");
            }
        } catch (storageError) {
            console.warn('Failed to clear reader ID:', storageError);
        }
        
        // Determine user-friendly error message
        let userMessage = 'An error occurred while streaming the response.';
        
        if (error.name === 'AbortError') {
            userMessage = 'The request timed out. Please try again.';
        } else if (error.message.includes('fetch')) {
            userMessage = 'Unable to connect to the server. Please check your connection.';
        } else if (error.message.includes('status')) {
            userMessage = 'Server error. Please try again later.';
        } else if (error.message.includes('stream')) {
            userMessage = 'Streaming is not supported. Please try a different browser.';
        }
        
        // Call error callback if provided
        if (typeof onError === 'function') {
            onError({
                message: userMessage,
                originalError: error,
                timestamp: new Date().toISOString()
            });
        } else {
            // Fallback: call onEnd to ensure UI cleanup
            if (typeof onEnd === 'function') {
                onEnd();
            }
            
            // Re-throw if no error handler provided
            throw error;
        }
    }
}

/**
 * Cancel active streaming session
 */
export function cancelStream() {
    try {
        if (typeof window !== 'undefined' && window.localStorage) {
            window.localStorage.setItem("readerId", "");
        }
        return true;
    } catch (error) {
        console.warn('Failed to cancel stream:', error);
        return false;
    }
}