import { Button, Modal, useDisclosure, ModalContent, ModalHeader, ModalBody, Input, ModalFooter, Checkbox, Tooltip } from "@heroui/react";
import { CircleStop, CircleArrowUp, ArrowDown, ArrowRightToLine, AlertCircle } from "lucide-react"
import { useEffect, useState, useRef, useCallback } from "react";
import { streamGeminiResponse } from "../../scripts/streamer"
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'github-markdown-css'
import ClickSpark from "../../scripts/clickspark"
import { useRouter } from "next/router";
import 'katex/dist/katex.min.css'
// Import utilities with fallback for SSR
let apiClient, useApiCall, handleApiError, withErrorHandling, LoadingSpinner, InlineSpinner, ErrorAlert, useToast, ErrorBoundary;

try {
    const apiModule = require('@/utils/apiClient');
    apiClient = apiModule.apiClient;
    useApiCall = apiModule.useApiCall;
    
    const errorModule = require('@/utils/errorHandler');
    handleApiError = errorModule.handleApiError;
    withErrorHandling = errorModule.withErrorHandling;
    
    const loadingModule = require('@/components/LoadingSpinner');
    LoadingSpinner = loadingModule.LoadingSpinner || loadingModule.default;
    InlineSpinner = loadingModule.InlineSpinner;
    
    const alertModule = require('@/components/ErrorAlert');
    ErrorAlert = alertModule.ErrorAlert || alertModule.default;
    useToast = alertModule.useToast;
    
    const boundaryModule = require('@/components/ErrorBoundary');
    ErrorBoundary = boundaryModule.ErrorBoundary || boundaryModule.default;
} catch (e) {
    console.warn('Some utilities could not be loaded:', e);
    // Provide fallbacks
    LoadingSpinner = ({ children }) => children || null;
    InlineSpinner = () => null;
    ErrorAlert = () => null;
    ErrorBoundary = ({ children }) => children;
    useToast = () => ({ error: console.error, success: console.log, warning: console.warn });
    handleApiError = (err) => ({ message: err?.message || 'An error occurred' });
}

// Safe localStorage wrapper
const safeLocalStorage = {
    getItem: (key) => {
        try {
            return typeof window !== 'undefined' ? window.localStorage?.getItem(key) : null;
        } catch (e) {
            console.warn('localStorage access failed:', e);
            return null;
        }
    },
    setItem: (key, value) => {
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                window.localStorage.setItem(key, value);
            }
        } catch (e) {
            console.warn('localStorage write failed:', e);
        }
    },
    removeItem: (key) => {
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                window.localStorage.removeItem(key);
            }
        } catch (e) {
            console.warn('localStorage remove failed:', e);
        }
    }
};


const MarkdownComponent = (content) => {
    return (
        <>
            <div className="markdown-body" style={{ marginBottom: "14px" }}>
                <ReactMarkdown
                    children={content}
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                />
            </div>
        </>
    )
}

const UserMessage = (content, i, setInputContent, currentChat, setCurrentChat, setIsResponding) => {
    return (
        <>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <div style={{
                    width: "fit-content",
                    border: "1px solid rgba(255, 255, 255, 0.14)",
                    padding: "8px",
                    borderRadius: "5px",
                    backgroundColor: "#1c1c1c",
                    marginBottom: "14px"
                }}>
                    {content}
                </div>
            </div>
        </>
    )
}

const ModelMessage = MarkdownComponent

export default function Home() {
    var host = "http://127.0.0.1"
    const router = useRouter();
    const toast = useToast();
    const [inputContent, setInputContent] = useState("")
    const [serverURL, setServerURL] = useState("")
    const [codeServerURL, setCodeServerURL] = useState("")
    const [currentChat, setCurrentChat] = useState([])
    var [chatId, setChatId] = useState(null)
    const { isOpen, onOpen, onOpenChange } = useDisclosure()
    const { isOpen: ChatHistoryModalIsOpen, onOpen: ChatHistoryModalOnOpen, onOpenChange: ChatHistoryModalOnOpenChange, onClose: ChatHistoryModalOnClose } = useDisclosure()
    
    // Safe localStorage access
    const [modalAPIKeyValue, setModalAPIKeyValue] = useState(() => {
        try {
            return typeof window !== 'undefined' ? localStorage?.getItem("geminiAPIKey") || "" : "";
        } catch {
            return "";
        }
    });
    
    const [isResponding, setIsResponding] = useState(false)
    const [isSendingMessage, setIsSendingMessage] = useState(false)
    const [isLoadingServer, setIsLoadingServer] = useState(false)
    const [currentStream, setCurrentStream] = useState(null)
    const [serverError, setServerError] = useState(null)
    
    const [usingPro, setIsUsingPro] = useState(() => {
        try {
            return typeof window !== 'undefined' ? localStorage?.getItem("usingPro") === "true" : false;
        } catch {
            return false;
        }
    });

    // Additional state for chat history
    const [selectedItem, setSelectedItem] = useState(0);
    const [ChatHistoryQueryResults, setChatHistoryQueryResults] = useState([]);
    const [chatHistoryInputText, setChatHistoryInputText] = useState("");
    const prevScrollTop = useRef(0);
    
    // Mounted iframe state
    const [mountedIframe] = useState(() => {
        try {
            if (typeof document !== 'undefined') {
                const el = document.createElement("iframe");
                el.style.width = "100%";
                el.style.height = "100%";
                return el;
            }
        } catch {
            return null;
        }
        return null;
    });

    const chatboxRef = useRef(null);
    const [autoScroll, setAutoScroll] = useState(true);

    useEffect(() => {
        const el = chatboxRef.current;
        if (autoScroll && el) {
            el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
        }
    }, [currentChat, autoScroll]);

    useEffect(() => {
        setTimeout(() => {
            const textarea = document.querySelector("textarea");
            if (textarea) {
                textarea.focus();
            }
        }, 10);
    }, []);

    function generateUnsafeUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function HandleChat() {
        if (chatId == null) {
            const id = generateUnsafeUUID();
            setChatId(id);
            return id;
        }
        return chatId;
    }

    // Load chat from URL parameter with error handling
    useEffect(() => {
        const loadChatFromUrl = async () => {
            const id = router.query.id;
            if (!id) return;
            
            try {
                const storageChat = safeLocalStorage.getItem(id);
                if (storageChat) {
                    const parsedChat = JSON.parse(storageChat);
                    setChatId(id);
                    setCurrentChat(parsedChat);
                    
                    // Scroll to position after content loads
                    setTimeout(() => {
                        const el = document.getElementById("chatbox");
                        if (el) {
                            const here = el.scrollTop;
                            el.scrollTo({ top: here, behavior: "instant" });
                        }
                    }, 100);
                } else {
                    toast.warning('Chat not found. Starting a new conversation.');
                }
            } catch (error) {
                const errorInfo = handleApiError(error);
                toast.error('Failed to load chat: ' + errorInfo.message);
                console.error('Chat loading failed:', error);
            }
        };
        
        loadChatFromUrl();
    }, [router.query.id, toast]);

    // Safe localStorage operations
    const safeLocalStorage = {
        getItem: (key) => {
            try {
                return typeof window !== 'undefined' ? window.localStorage?.getItem(key) : null;
            } catch (error) {
                console.warn('localStorage access failed:', error);
                return null;
            }
        },
        setItem: (key, value) => {
            try {
                if (typeof window !== 'undefined') {
                    window.localStorage?.setItem(key, value);
                    return true;
                }
            } catch (error) {
                console.warn('localStorage write failed:', error);
                toast.error('Unable to save data locally. Some features may not work properly.');
            }
            return false;
        },
        removeItem: (key) => {
            try {
                if (typeof window !== 'undefined') {
                    window.localStorage?.removeItem(key);
                }
            } catch (error) {
                console.warn('localStorage removal failed:', error);
            }
        }
    };

    // Initialize server connection with error handling
    const initializeServer = useCallback(async () => {
        setIsLoadingServer(true);
        setServerError(null);
        
        try {
            const response = await apiClient.get(host + ":5000/");
            
            if (response.success && response.data) {
                setServerURL(host + ":" + response.data.port);
                setCodeServerURL(host + ":" + "8080/?folder=" + response.data.location);
                toast.success('Server connected successfully');
            } else {
                throw new Error(response.error || 'Failed to get server information');
            }
        } catch (error) {
            const errorInfo = handleApiError(error);
            setServerError(errorInfo.message);
            toast.error(errorInfo.message);
            console.error('Server initialization failed:', error);
        } finally {
            setIsLoadingServer(false);
        }
    }, [host, toast]);

    useEffect(() => {
        initializeServer();
    }, [initializeServer]);

    function ChatHistoryKeyboardHandler(event) {
        if (event.key == "ArrowUp") {
            if (selectedItem == 0) return;
            setSelectedItem(selectedItem - 1)
        }

        if (event.key == "ArrowDown") {
            if (selectedItem == ChatHistoryQueryResults.length - 1) {
                return
            }
            setSelectedItem(selectedItem + 1)
        }

        if (event.key == "Enter") {
            try { event.preventDefault() } catch { }

            if (ChatHistoryQueryResults.length == 0) {
                return;
            }

            setSelectedItem(0)
            setChatHistoryInputText("")

            if (ChatHistoryQueryResults[selectedItem].date == "Command") {
                commands[ChatHistoryQueryResults[selectedItem].title]()
                return
            }

            localStorage.setItem("readerId", "")
            setChatId(ChatHistoryQueryResults[selectedItem].id)
            ChatHistoryModalOnClose()
            setIsResponding(false)
            router.push("/?id=" + ChatHistoryQueryResults[selectedItem].id)
        }

        if (event.key == "Tab") {
            ChatHistoryModalOnClose()
        }
    }

    // Utility function for time formatting
    function getGithubTimeDelta(unixTimestampSec) {
        const seconds = Math.floor(Date.now() / 1000) - unixTimestampSec;

        if (seconds < 60) {
            return "just now";
        } else if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            return `${mins} minute${mins !== 1 ? 's' : ''} ago`;
        } else if (seconds < 86400) {
            const hours = Math.floor(seconds / 3600);
            return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
        } else if (seconds < 604800) {
            const days = Math.floor(seconds / 86400);
            return `${days} day${days !== 1 ? 's' : ''} ago`;
        } else if (seconds < 2592000) {
            const weeks = Math.floor(seconds / 604800);
            return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
        } else if (seconds < 31536000) {
            const months = Math.floor(seconds / 2592000);
            return `${months} month${months !== 1 ? 's' : ''} ago`;
        } else {
            const years = Math.floor(seconds / 31536000);
            return `${years} year${years !== 1 ? 's' : ''} ago`;
        }
    }

    // Chat history keyboard handler
    function ChatHistoryKeyboardHandler(event) {
        try {
            if (event.key === "ArrowUp") {
                if (selectedItem === 0) return;
                setSelectedItem(selectedItem - 1);
            }

            if (event.key === "ArrowDown") {
                if (selectedItem === ChatHistoryQueryResults.length - 1) {
                    return;
                }
                setSelectedItem(selectedItem + 1);
            }

            if (event.key === "Enter") {
                try { event.preventDefault() } catch { }

                if (ChatHistoryQueryResults.length === 0) {
                    return;
                }

                setSelectedItem(0);
                setChatHistoryInputText("");

                if (ChatHistoryQueryResults[selectedItem].date === "Command") {
                    commands[ChatHistoryQueryResults[selectedItem].title]();
                    return;
                }

                safeLocalStorage.setItem("readerId", "");
                setChatId(ChatHistoryQueryResults[selectedItem].id);
                ChatHistoryModalOnClose();
                setIsResponding(false);
                router.push("/app?id=" + ChatHistoryQueryResults[selectedItem].id);
            }

            if (event.key === "Tab") {
                ChatHistoryModalOnClose();
            }
        } catch (error) {
            console.error('Chat history keyboard error:', error);
        }
    }

    // Keyboard event handler with proper error handling
    function KeyboardListener(event) {
        try {
            if (ChatHistoryModalIsOpen) {
                ChatHistoryKeyboardHandler(event);
                return;
            }

            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
                return;
            }

            if (event.code === "Tab") {
                event.preventDefault();
                ChatHistoryModalOnOpen();
                return;
            }

            if (event.code === "Escape") {
                safeLocalStorage.setItem("readerId", "");
                setIsResponding(false);
                return;
            }

            if (event.key === "/") {
                const textarea = document.querySelector("textarea");
                if (document.activeElement !== textarea && textarea) {
                    event.preventDefault();
                    textarea.focus();
                }
            }
        } catch (error) {
            console.error('Keyboard event error:', error);
        }
    }

    // Add keyboard listeners
    useEffect(() => {
        document.addEventListener("keydown", KeyboardListener);
        return () => { document.removeEventListener("keydown", KeyboardListener) };
    }, [inputContent, ChatHistoryModalIsOpen, selectedItem, ChatHistoryQueryResults]);

    // Reset selected item when query changes
    useEffect(() => {
        setSelectedItem(0);
    }, [chatHistoryInputText]);

    // Update iframe source
    useEffect(() => {
        if (mountedIframe && codeServerURL) {
            mountedIframe.src = codeServerURL;
        }
    }, [codeServerURL, mountedIframe]);

    // Calculate query input width for modal
    let queryInputCurrentWidth = "";
    if (ChatHistoryModalIsOpen) {
        try {
            const queryInput = document.getElementById("queryInput");
            if (queryInput) {
                queryInputCurrentWidth = queryInput.clientWidth + "px";
            }
        } catch { }
    }

    // Send message with comprehensive error handling
    const sendMessage = useCallback(async () => {
                if (!inputContent.trim()) {
                    onOpen();
                    return;
                }
                
                if (isSendingMessage || isResponding) {
                    const toast = useToast();
                    toast.warning('Please wait for the current message to complete.');
                    return;
                }
                
                if (!serverURL) {
                    const toast = useToast();
                    toast.error('Server not connected. Please wait for server initialization.');
                    return;
                }
                
                const currentChatId = HandleChat();
                setIsSendingMessage(true);
                setIsResponding(true);
                const toast = useToast();
                
                try {
                    // Add user message to chat
                    const newUserMessage = { role: "user", parts: [{ text: inputContent }] };
                    const newAssistantMessage = { role: "model", parts: [{ text: "" }] };
                    const updatedChat = [...currentChat, newUserMessage, newAssistantMessage];
                    
                    setCurrentChat(updatedChat);
                    
                    // Save to localStorage safely
                    safeLocalStorage.setItem(currentChatId, JSON.stringify(updatedChat));
                    safeLocalStorage.setItem(currentChatId + "date", parseInt(Number(new Date()) / 1000).toString());
                    
                    // Clear input and set auto-scroll
                    setInputContent("");
                    setTimeout(() => setAutoScroll(true), 10);
                    
                    // Stream the response
                    await streamGeminiResponse(
                        serverURL,
                        [...currentChat, newUserMessage],
                        (chunk, id) => {
                            try {
                                const parsedChunk = JSON.parse(chunk);
                                if (parsedChunk.type !== "output") return;
                                
                                const responseText = parsedChunk.data + "\n\n";
                                
                                setCurrentChat((prevChat) => {
                                    if (safeLocalStorage.getItem("readerId") !== id) {
                                        return prevChat;
                                    }
                                    
                                    const updatedChat = [...prevChat];
                                    const lastMessage = { ...updatedChat[updatedChat.length - 1] };
                                    const lastPart = { ...lastMessage.parts[0] };
                                    
                                    lastPart.text += responseText;
                                    lastMessage.parts = [lastPart];
                                    updatedChat[updatedChat.length - 1] = lastMessage;
                                    
                                    // Save updated chat safely
                                    safeLocalStorage.setItem(currentChatId, JSON.stringify(updatedChat));
                                    safeLocalStorage.setItem(currentChatId + "date", parseInt(Number(new Date()) / 1000).toString());
                                    
                                    return updatedChat;
                                });
                            } catch (error) {
                                console.warn('Chunk parsing error:', error);
                                // Don't break the stream for parsing errors
                            }
                        },
                        () => {
                            setIsResponding(false);
                            toast.success('Message sent successfully');
                        },
                        (error) => {
                            // Handle streaming errors
                            const errorInfo = handleApiError(error.originalError || error);
                            toast.error('Streaming failed: ' + (error.message || errorInfo.message));
                            setIsResponding(false);
                        }
                    );
                } catch (error) {
                    const errorInfo = handleApiError(error);
                    toast.error('Failed to send message: ' + errorInfo.message);
                    
                    // Remove the failed assistant message
                    setCurrentChat(prevChat => {
                        if (prevChat.length >= 2) {
                            return prevChat.slice(0, -1);
                        }
                        return prevChat;
                    });
                    
                    setIsResponding(false);
                    console.error('Message sending failed:', error);
                } finally {
                    setIsSendingMessage(false);
                }
            }, [inputContent, isSendingMessage, isResponding, serverURL, currentChat, onOpen]);

    function getGithubTimeDelta(unixTimestampSec) {
        const seconds = Math.floor(Date.now() / 1000) - unixTimestampSec;

        if (seconds < 60) {
            return "just now";
        } else if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            return `${mins} minute${mins !== 1 ? 's' : ''} ago`;
        } else if (seconds < 86400) {
            const hours = Math.floor(seconds / 3600);
            return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
        } else if (seconds < 604800) {
            const days = Math.floor(seconds / 86400);
            return `${days} day${days !== 1 ? 's' : ''} ago`;
        } else if (seconds < 2592000) {
            const weeks = Math.floor(seconds / 604800);
            return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
        } else if (seconds < 31536000) {
            const months = Math.floor(seconds / 2592000);
            return `${months} month${months !== 1 ? 's' : ''} ago`;
        } else {
            const years = Math.floor(seconds / 31536000);
            return `${years} year${years !== 1 ? 's' : ''} ago`;
        }
    }

    // Start new chat with error handling
    function NewChat() {
        try {
            setCurrentChat([]);
            setChatId(null);
            ChatHistoryModalOnClose();
            safeLocalStorage.setItem("readerId", "");
            setIsResponding(false);
            router.push("/app");
            
            setTimeout(() => {
                const textarea = document.querySelector("textarea");
                if (textarea) {
                    textarea.focus();
                }
            }, 100);
        } catch (error) {
            console.error('New chat error:', error);
            toast.error('Failed to start new chat');
        }
    }

    var commands = {
        "Open VS Code": () => {
            onOpen()
        },
        "New Chat - Deletes the current chat": () => {
            try {
                safeLocalStorage.removeItem(chatId + "date");
                safeLocalStorage.removeItem(chatId);
                NewChat();
            } catch (error) {
                console.error('Delete chat error:', error);
                toast.error('Failed to delete chat');
            }
        }
    }

    // Search chat history with error handling
    function GetResults(query) {
        try {
            if (typeof window === 'undefined') return [];
            
            const results = {};
            const localStorage = window.localStorage;
            
            if (!localStorage) return [];
            
            for (let index = 0; index < localStorage.length; index++) {
                try {
                    const key = localStorage.key(index);
                    if (!key || !key.endsWith("date")) continue;
                    
                    const chatKey = key.split("date")[0];
                    const chatData = safeLocalStorage.getItem(chatKey);
                    
                    if (!chatData) continue;
                    
                    const chat = JSON.parse(chatData);
                    const searchText = chat[0]?.parts?.[0]?.text || '';
                    
                    if (!searchText.toLowerCase().includes(query.toLowerCase().trim())) {
                        continue;
                    }
                    
                    const date = parseInt(safeLocalStorage.getItem(key) || '0');
                    results[date] = {
                        date: getGithubTimeDelta(date),
                        title: searchText,
                        chat: chat,
                        id: chatKey
                    };
                } catch (error) {
                    console.warn('Error processing chat history item:', error);
                    continue;
                }
            }

            const sortedResults = Object.keys(results)
                .sort((a, b) => b - a)
                .map(key => results[key]);

            const filteredCommands = Object.keys(commands)
                .filter(command => command.toLowerCase().includes(query.toLowerCase()))
                .map(command => ({
                    date: "Command",
                    title: command,
                    id: ""
                }));

            return [...filteredCommands, ...sortedResults];
        } catch (error) {
            console.error('Search error:', error);
            toast.error('Failed to search chat history');
            return [];
        }
    }

    useEffect(() => {
        if (ChatHistoryModalIsOpen) {
            setChatHistoryQueryResults(GetResults(chatHistoryInputText))
        }
    }, [ChatHistoryModalIsOpen, chatHistoryInputText])

    useEffect(() => {
        setSelectedItem(0)
    }, [chatHistoryInputText])

    useEffect(() => {
        mountedIframe.src = codeServerURL;
    }, [codeServerURL]);

    return (
        <ErrorBoundary>
            <ClickSpark>
                <div style={{ minHeight: "100vh", width: "100vw", backgroundColor: "#111", overflowY: "auto", color: "white" }} ref={chatboxRef} id="chatbox" onScroll={(e) => {
                    if (!isResponding) {
                        return
                    }
                    const curr = e.target.scrollTop;
                    if (curr + 10 < prevScrollTop.current) {
                        console.log("scrolled up")
                        setAutoScroll(false);
                    }
                    prevScrollTop.current = curr;
                }}>
                    {/* Loading overlay for server initialization */}
                    {isLoadingServer && (
                        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                            <div className="bg-gray-800 rounded-lg p-6 shadow-lg border border-gray-600">
                                <LoadingSpinner size="lg" text="Connecting to server..." className="text-white" />
                            </div>
                        </div>
                    )}
                    
                    {/* Server error display */}
                    {serverError && (
                        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 max-w-md">
                            <ErrorAlert 
                                variant="error" 
                                title="Server Connection Failed" 
                                message={serverError}
                                closable={true}
                                onClose={() => setServerError(null)}
                            />
                            <div className="mt-2 text-center">
                                <Button 
                                    size="sm" 
                                    onClick={initializeServer}
                                    disabled={isLoadingServer}
                                    className="bg-blue-600 hover:bg-blue-700"
                                >
                                    {isLoadingServer ? <InlineSpinner className="mr-2" /> : null}
                                    Retry Connection
                                </Button>
                            </div>
                        </div>
                    )}
                    
                    <div style={{ height: "76vh", "width": "100%" }}>
                        <div style={{ height: "100%", width: "100%" }} className="flex justify-center items-center">
                            <div style={{ height: "100%", width: "60%", marginTop: "50px" }}>
                                {chatId == null ? (
                                    <div style={{ height: "100%", width: "100%" }} className="flex justify-center items-center">
                                        <div>
                                            <h1 className="text-4xl mt-10 text-center">What's on your mind today?</h1>
                                            <div className="flex justify-center items-center text-center" style={{ color: "#A1A1AA", marginTop: "14px" }}>
                                                {isLoadingServer ? "Connecting to server..." : "Press the Tab Key to open the Command Palette"}
                                            </div>
                                        </div>
                                    </div>
                                ) : null}
                                {currentChat.map((item, i) => {
                                    if (item.role == "user") {
                                        return UserMessage(item.parts[0].text, Number(i), setInputContent, currentChat, setCurrentChat, setIsResponding)
                                    } else {
                                        return ModelMessage(item.parts[0].text)
                                    }
                                })}
                                {isResponding && (
                                    <div className="flex items-center gap-3 mb-4">
                                        <LoadingSpinner size="sm" />
                                        <p className="shiny-text">Calliope is working for you!</p>
                                    </div>
                                )}
                                <div style={{ height: "28vh" }}></div>
                            </div>
                        </div>
                    </div>
                {!autoScroll && <div style={{ position: "absolute", bottom: "26vh", width: "100vw" }} className="flex justify-center items-center">
                    <Button style={{ backgroundColor: "rgb(28, 28, 28)", border: "1px solid rgba(255, 255, 255, 0.14)" }} isIconOnly
                        onPress={() => {
                            const el = chatboxRef.current;
                            const here = el.scrollTop;
                            el.scrollTo({ top: here, behavior: "instant" });
                            setAutoScroll(true)
                        }}
                    ><ArrowDown></ArrowDown></Button>
                </div>}
                    <div style={{ height: "24vh", "width": "100%", position: "fixed" }} className="flex justify-center items-center">
                        <div className="flex flex-col" style={{ height: "100%", width: "50%", border: "1px solid rgba(255, 255, 255, 0.14)", borderBottom: "none", borderTopLeftRadius: "14px", borderTopRightRadius: "14px", background: "#1c1c1c" }}>
                            <div style={{ height: "auto", padding: "8px" }} className="flex-1">
                                <textarea 
                                    style={{ 
                                        height: "90%", 
                                        width: "97.5%", 
                                        border: "none", 
                                        padding: "5px", 
                                        backgroundColor: "#1c1c1c",
                                        opacity: (isSendingMessage || isResponding || !serverURL) ? 0.6 : 1
                                    }}
                                    onInput={(x) => {
                                        setInputContent(x.target.value)
                                    }}
                                    value={inputContent}
                                    placeholder={isSendingMessage ? "Sending message..." : isResponding ? "Waiting for response..." : !serverURL ? "Connecting to server..." : "Write your message here"}
                                    autoFocus
                                    disabled={isSendingMessage || isResponding || !serverURL}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            if (!isSendingMessage && !isResponding && serverURL) {
                                                sendMessage();
                                            }
                                        }
                                    }}
                                >
                                </textarea>
                            </div>
                            <div style={{ height: "auto" }}>
                                <div style={{ float: "right", marginRight: "10px", marginBottom: "10px", cursor: "pointer" }} className="flex justify-center items-center gap-2">
                                    {(isSendingMessage || isResponding) && (
                                        <div className="flex items-center gap-2 text-sm text-gray-400">
                                            <InlineSpinner size="sm" />
                                            {isSendingMessage ? "Sending..." : "Waiting..."}
                                        </div>
                                    )}
                                    <Button 
                                        variant="faded" 
                                        size="sm" 
                                        style={{ marginRight: "10px" }} 
                                        onPress={() => onOpen()}
                                        disabled={isLoadingServer}
                                    >
                                        {isLoadingServer ? <InlineSpinner size="sm" className="mr-2" /> : null}
                                        Open VS Code
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>
            </div>
            <div
                style={{
                    display: isOpen ? "block" : "none",
                    position: "fixed",
                    top: 0,
                    left: 0,
                    width: "100vw",
                    height: "100vh",
                    backdropFilter: "blur(8px)",
                    zIndex: 10
                }}
                onClick={() => onOpenChange(false)}
            />

            <div
                style={{
                    display: isOpen ? "block" : "none",
                    position: "fixed",
                    top: "10vh",
                    left: "10vw",
                    width: "80vw",
                    height: "80vh",
                    zIndex: 20,
                    background: "#1c1c1c",
                    borderRadius: "8px",
                    overflow: "hidden"
                }}
            >
                <div style={{ width: "100%", height: "100%" }} ref={node => {
                    if (node && !node.contains(mountedIframe)) {
                        node.appendChild(mountedIframe);
                    }
                }} />
            </div>
            <Modal isOpen={ChatHistoryModalIsOpen} placement="top" onOpenChange={ChatHistoryModalOnOpenChange} backdrop="blur" hideCloseButton>
                <ModalContent style={{ padding: "10px", maxWidth: "100vw", width: "fit-content" }}>
                    {
                        (onClose) => (
                            <>
                                <textarea id="queryInput" style={{ padding: "14px", width: "60vw", fontSize: "20px", borderTopRightRadius: "10px", borderTopLeftRadius: "10px", borderBottomLeftRadius: ChatHistoryQueryResults.length == 0 ? "10px" : null, borderBottomRightRadius: ChatHistoryQueryResults.length == 0 ? "10px" : null }} rows={1} autoFocus
                                    value={chatHistoryInputText}
                                    placeholder="Write your query here"
                                    onInput={(e) => {
                                        setChatHistoryInputText(e.target.value)
                                    }}
                                ></textarea>
                                {ChatHistoryQueryResults.map((x, i) =>
                                    <>
                                        <div id={"selection_" + i} style={{ width: queryInputCurrentWidth, backgroundColor: selectedItem == i ? "#222" : "#111", padding: "8px", borderBottomRightRadius: i == ChatHistoryQueryResults.length - 1 ? "10px" : "", borderBottomLeftRadius: i == ChatHistoryQueryResults.length - 1 ? "10px" : "", cursor: "pointer" }}
                                            onClick={(event) => {
                                                if (event.target.id == "") {
                                                    event.target = event.target.parentElement
                                                }
                                                selectedItem = Number(event.target.id.split("selection_")[1])
                                                ChatHistoryKeyboardHandler({ "key": "Enter" })
                                            }}
                                            onMouseEnter={(e) => {
                                                if (e.target.id == "") {
                                                    e.target = e.target.parentElement
                                                }
                                                e.target.style.backgroundColor = "#222"
                                            }}
                                            onMouseLeave={(e) => {
                                                if (e.target.id == "") {
                                                    e.target = e.target.parentElement
                                                }
                                                e.target.style.backgroundColor = selectedItem == i ? "#222" : "#111"
                                            }}
                                        >
                                            <h1 style={{ overflow: "hidden", "whiteSpace": "nowrap", "textOverflow": "ellipsis", display: "block" }}>{x.title.replace(/\n/g, ' ')}</h1>
                                            <h2>{x.date}</h2>
                                        </div>
                                    </>
                                )}
                            </>
                        )
                    }
                </ModalContent>
            </Modal>
        </ClickSpark>
    </ErrorBoundary>
)
}