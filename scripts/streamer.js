export async function streamGeminiResponse(endpoint, message, onUpdate, onEnd, onError) {
    let reader = null;
    let id = Math.random().toString();
    
    try {
        // Validate inputs
        if (!endpoint || !message) {
            throw new Error("Missing required parameters: endpoint and message");
        }

        if (!Array.isArray(message) || message.length === 0 || !message[message.length - 1]?.parts?.[0]?.text) {
            throw new Error("Invalid message format");
        }

        const messageText = message[message.length - 1].parts[0].text;
        window.localStorage.setItem("readerId", id);

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

        // Check if response is ok
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        if (!response.body) {
            throw new Error("Readable stream not supported in this environment");
        }
        
        reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        function splitByNewlineAndEveryN(str) {
            return str
                .split(/(\n)/)
                .flatMap(part => {
                    if (part === '\n') return [part];
                    return part.match(/.{1,50}/g) || [''];
                });
        }

        // Add reading timeout
        let lastUpdateTime = Date.now();
        const readTimeout = 15000; // 15 seconds between updates

        while (true) {
            // Check for timeout
            if (Date.now() - lastUpdateTime > readTimeout) {
                throw new Error("Stream read timeout - no data received");
            }

            try {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                lastUpdateTime = Date.now();
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n').filter(line => line.trim().startsWith('data: '));
            
                for (const line of lines) {
                    try {
                        const text = String(line.split("data: ")[1]);
                        if (text && text !== "undefined") {
                            onUpdate(text, id);
                        }
                    } catch (parseError) {
                        console.warn("Failed to parse line:", line, parseError);
                        // Continue processing other lines
                    }
                }
            } catch (readError) {
                if (readError.name === 'AbortError') {
                    throw new Error("Request was cancelled");
                }
                throw readError;
            }
        }
        
        onEnd();
        
    } catch (error) {
        console.error("Streaming error:", error);
        
        // Clean up reader if it exists
        if (reader) {
            try {
                reader.cancel();
            } catch (cancelError) {
                console.warn("Failed to cancel reader:", cancelError);
            }
        }

        // Clean up localStorage
        if (id) {
            window.localStorage.removeItem("readerId");
        }

        // Call error handler if provided
        if (onError) {
            let errorMessage = "Failed to stream response";
            
            if (error.name === 'AbortError') {
                errorMessage = "Request timeout - please try again";
            } else if (error.message?.includes('fetch')) {
                errorMessage = "Network error - please check your connection";
            } else if (error.message) {
                errorMessage = error.message;
            }

            onError({
                message: errorMessage,
                code: error.name || 'STREAM_ERROR',
                status: error.status
            });
        } else {
            // Fallback if no error handler provided
            throw error;
        }
    }
}