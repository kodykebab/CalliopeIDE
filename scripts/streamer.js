export async function streamGeminiResponse(endpoint, message, onUpdate, onEnd) {
    message = message[message.length - 1].parts[0].text
    var id=Math.random().toString()
    window.localStorage.setItem("readerId", id)
    const response = await fetch(endpoint+"/?data="+message, {
        method: "GET",
        headers: {
            "Content-Type": "application/json"
        },
    });
    
    if (!response.body) {
        throw new Error("Readable stream not supported in this environment");
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');

    function splitByNewlineAndEveryN(str) {
        return str
            .split(/(\n)/)
            .flatMap(part => {
                if (part === '\n') return [part];
                return part.match(/.{1,50}/g) || [''];
            });
    }
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
    
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n\n').filter(line => line.trim().startsWith('data: '));
    
        for (const line of lines) {
            const text = String(line.split("data: ")[1]);
            onUpdate(text, id)
        }
    }
    onEnd()
}