"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X, FolderOpen, Settings, Play, Save, Download, MessageSquare, Send, ChevronLeft, ChevronRight, Rocket } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getPublicKey, signTransaction, isConnected } from "@stellar/freighter-api"

export default function IDEApp() {
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const [chatOpen, setChatOpen] = useState(true)
    const [message, setMessage] = useState("")
    const [isMobile, setIsMobile] = useState(false)
    const [isDeploying, setIsDeploying] = useState(false)
    const [contractId, setContractId] = useState(null)

    // Check if we're on mobile
    useEffect(() => {
        const checkMobile = () => {
            setIsMobile(window.innerWidth < 768)
            // Auto-collapse sidebar and chat on mobile
            if (window.innerWidth < 768) {
                setSidebarOpen(false)
                setChatOpen(false)
            } else if (window.innerWidth >= 1024) {
                // Auto-open on desktop
                setSidebarOpen(true)
                setChatOpen(true)
            }
        }
        
        checkMobile()
        window.addEventListener("resize", checkMobile)
        return () => window.removeEventListener("resize", checkMobile)
    }, [])

    const handleDeploy = async () => {
        try {
            setIsDeploying(true);
            const connected = await isConnected();
            if (!connected) {
                alert("Please install and unlock Freighter extension.");
                return;
            }

            const publicKey = await getPublicKey();
            if (!publicKey) return;

            // 1. Prepare Upload
            const uploadPrep = await fetch("/api/soroban/prepare-upload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: 1, // Mock session ID for now
                    wasm_path: "target/wasm32-unknown-unknown/release/contract.wasm", 
                    public_key: publicKey
                })
            }).then(r => r.json());

            if (!uploadPrep.success) throw new Error(uploadPrep.error);

            // 2. Sign Upload
            const signedUpload = await signTransaction(uploadPrep.unsigned_xdr, { network: "TESTNET" });
            
            // 3. Submit Upload
            const uploadResult = await fetch("/api/soroban/submit-tx", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ signed_xdr: signedUpload })
            }).then(r => r.json());

            if (!uploadResult.success) throw new Error(uploadResult.error);
            const wasmHash = uploadResult.wasm_hash;

            // 4. Prepare Create
            const createPrep = await fetch("/api/soroban/prepare-create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: 1,
                    wasm_hash: wasmHash,
                    public_key: publicKey
                })
            }).then(r => r.json());

            if (!createPrep.success) throw new Error(createPrep.error);

            // 5. Sign Create
            const signedCreate = await signTransaction(createPrep.unsigned_xdr, { network: "TESTNET" });

            // 6. Submit Create
            const createResult = await fetch("/api/soroban/submit-tx", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ signed_xdr: signedCreate })
            }).then(r => r.json());

            if (!createResult.success) throw new Error(createResult.error);
            
            setContractId(createResult.contract_id);
            alert(`Contract deployed successfully! ID: ${createResult.contract_id}`);

        } catch (error) {
            console.error("Deployment failed:", error);
            alert(`Deployment failed: ${error.message}`);
        } finally {
            setIsDeploying(false);
        }
    };

    const sidebarVariants = {
        open: { x: 0, opacity: 1 },
        closed: { x: "-100%", opacity: 0 }
    }

    const chatVariants = {
        open: { x: 0, opacity: 1 },
        closed: { x: "100%", opacity: 0 }
    }

    return (
        <div className="flex h-screen bg-[#0D1117] text-white overflow-hidden">
            {/* Mobile Backdrop */}
            {isMobile && (sidebarOpen || chatOpen) && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/50 z-30 md:hidden"
                    onClick={() => {
                        setSidebarOpen(false)
                        setChatOpen(false)
                    }}
                />
            )}

            {/* Sidebar */}
            <AnimatePresence>
                {(sidebarOpen || !isMobile) && (
                    <motion.aside
                        initial={isMobile ? "closed" : "open"}
                        animate="open"
                        exit="closed"
                        variants={sidebarVariants}
                        transition={{ duration: 0.3 }}
                        className={`
                            ${isMobile 
                                ? "fixed left-0 top-0 h-full z-40 w-80 max-w-[80vw]" 
                                : "relative"
                            }
                            ${!isMobile && !sidebarOpen ? "w-0" : ""}
                            ${!isMobile && sidebarOpen ? "w-64 lg:w-80" : ""}
                            bg-[#161B22] border-r border-gray-700 flex flex-col
                        `}
                    >
                        {/* Sidebar Header */}
                        <div className="flex items-center justify-between p-4 border-b border-gray-700">
                            <h2 className="text-lg font-semibold">Explorer</h2>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSidebarOpen(false)}
                                className="p-1 h-auto text-gray-400 hover:text-white"
                            >
                                <X className="w-4 h-4" />
                            </Button>
                        </div>

                        {/* File Explorer */}
                        <div className="flex-1 overflow-y-auto p-4">
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 p-2 hover:bg-gray-700 rounded cursor-pointer">
                                    <FolderOpen className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm">src/</span>
                                </div>
                                <div className="flex items-center gap-2 p-2 ml-4 hover:bg-gray-700 rounded cursor-pointer">
                                    <span className="w-4 h-4 text-center text-xs">📄</span>
                                    <span className="text-sm">contract.rs</span>
                                </div>
                                <div className="flex items-center gap-2 p-2 ml-4 hover:bg-gray-700 rounded cursor-pointer">
                                    <span className="w-4 h-4 text-center text-xs">📄</span>
                                    <span className="text-sm">lib.rs</span>
                                </div>
                                <div className="flex items-center gap-2 p-2 hover:bg-gray-700 rounded cursor-pointer">
                                    <FolderOpen className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm">tests/</span>
                                </div>
                                <div className="flex items-center gap-2 p-2 hover:bg-gray-700 rounded cursor-pointer">
                                    <span className="w-4 h-4 text-center text-xs">📄</span>
                                    <span className="text-sm">Cargo.toml</span>
                                </div>
                            </div>
                        </div>

                        {/* Sidebar Footer */}
                        <div className="p-4 border-t border-gray-700">
                            <Button 
                                variant="ghost" 
                                size="sm" 
                                className="w-full justify-start text-gray-400 hover:text-white"
                            >
                                <Settings className="w-4 h-4 mr-2" />
                                Settings
                            </Button>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Top Toolbar */}
                <div className="h-12 bg-[#161B22] border-b border-gray-700 flex items-center px-4 gap-4">
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            className="p-1 h-auto text-gray-400 hover:text-white"
                        >
                            <Menu className="w-4 h-4" />
                        </Button>
                        <span className="text-sm text-gray-400">contract.rs</span>
                    </div>
                    
                    <div className="flex-1" />
                    
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="hidden sm:flex p-1 h-auto text-gray-400 hover:text-white"
                        >
                            <Save className="w-4 h-4 mr-1" />
                            Save
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="hidden sm:flex p-1 h-auto text-gray-400 hover:text-white"
                        >
                            <Play className="w-4 h-4 mr-1" />
                            Run
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleDeploy}
                            disabled={isDeploying}
                            className={`hidden sm:flex p-1 h-auto ${isDeploying ? "text-blue-500 animate-pulse" : "text-gray-400 hover:text-white"}`}
                        >
                            <Rocket className="w-4 h-4 mr-1" />
                            {isDeploying ? "Deploying..." : "Deploy"}
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setChatOpen(!chatOpen)}
                            className="p-1 h-auto text-gray-400 hover:text-white"
                        >
                            <MessageSquare className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Editor and Chat Container */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Code Editor */}
                    <div className={`
                        flex-1 flex flex-col min-w-0
                        ${!isMobile && chatOpen ? "lg:flex-1" : "flex-1"}
                    `}>
                        <div className="flex-1 bg-[#0D1117] p-4 overflow-auto">
                            <div className="font-mono text-sm space-y-1">
                                <div className="text-gray-500">1</div>
                                <div className="text-gray-500">2</div>
                                <div className="text-gray-500">3</div>
                                <div className="text-gray-500">4</div>
                                <div className="text-gray-500">5</div>
                                <div className="text-gray-500">6</div>
                                <div className="text-gray-500">7</div>
                                <div className="text-gray-500">8</div>
                                <div className="text-gray-500">9</div>
                                <div className="text-gray-500">10</div>
                                <div className="text-gray-500">11</div>
                                <div className="text-gray-500">12</div>
                                <div className="text-gray-500">13</div>
                                <div className="text-gray-500">14</div>
                                <div className="text-gray-500">15</div>
                            </div>
                        </div>
                    </div>

                    {/* Chat Panel */}
                    <AnimatePresence>
                        {(chatOpen || !isMobile) && (
                            <motion.div
                                initial={isMobile ? "closed" : "open"}
                                animate="open"
                                exit="closed"
                                variants={chatVariants}
                                transition={{ duration: 0.3 }}
                                className={`
                                    ${isMobile 
                                        ? "fixed right-0 top-0 h-full z-40 w-80 max-w-[80vw]" 
                                        : "relative"
                                    }
                                    ${!isMobile && !chatOpen ? "w-0" : ""}
                                    ${!isMobile && chatOpen ? "w-80 lg:w-96" : ""}
                                    bg-[#161B22] border-l border-gray-700 flex flex-col
                                `}
                            >
                                {/* Chat Header */}
                                <div className="h-12 border-b border-gray-700 flex items-center justify-between px-4">
                                    <h3 className="text-sm font-semibold">AI Assistant</h3>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setChatOpen(false)}
                                        className="p-1 h-auto text-gray-400 hover:text-white"
                                    >
                                        <X className="w-4 h-4" />
                                    </Button>
                                </div>

                                {/* Chat Messages */}
                                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                    <div className="bg-[#0D1117] p-3 rounded-lg">
                                        <p className="text-sm">Hello! I'm your AI assistant for Soroban smart contract development. How can I help you today?</p>
                                    </div>
                                    
                                    <div className="bg-blue-600 p-3 rounded-lg ml-8">
                                        <p className="text-sm">Can you help me write a token contract?</p>
                                    </div>

                                    <div className="bg-[#0D1117] p-3 rounded-lg">
                                        <p className="text-sm">Absolutely! I'll help you create a basic Soroban token contract. Let me start with the basic structure...</p>
                                    </div>
                                </div>

                                {/* Chat Input */}
                                <div className="p-4 border-t border-gray-700">
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={message}
                                            onChange={(e) => setMessage(e.target.value)}
                                            placeholder="Ask about your code..."
                                            className="flex-1 bg-[#0D1117] border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px]"
                                            onKeyPress={(e) => {
                                                if (e.key === 'Enter' && !e.shiftKey) {
                                                    e.preventDefault()
                                                    // Handle send message
                                                    setMessage("")
                                                }
                                            }}
                                        />
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="p-2 h-[40px] w-[40px] text-gray-400 hover:text-white"
                                            onClick={() => setMessage("")}
                                        >
                                            <Send className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    )
}