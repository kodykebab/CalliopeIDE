"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FolderClosed,
  FolderOpen,
  Menu,
  MessageSquare,
  Play,
  Plus,
  Save,
  Send,
  Settings,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"

const STORAGE_KEY = "calliope.workspace.v1"
const AUTOSAVE_DELAY_MS = 700

const defaultWorkspace = {
  id: "root",
  name: "stellar-token-starter",
  type: "folder",
  children: [
    {
      id: "src",
      name: "src",
      type: "folder",
      children: [
        {
          id: "contract",
          name: "contract.rs",
          type: "file",
          language: "rust",
          content: `#![no_std]
use soroban_sdk::{contract, contractimpl, Env, String};

#[contract]
pub struct GreetingContract;

#[contractimpl]
impl GreetingContract {
    pub fn hello(env: Env, name: String) -> String {
        let mut response = String::from_str(&env, "Hello, ");
        response.push_str(&name);
        response
    }
}
`,
        },
        {
          id: "lib",
          name: "lib.rs",
          type: "file",
          language: "rust",
          content: `mod contract;

pub use crate::contract::GreetingContract;
`,
        },
      ],
    },
    {
      id: "tests",
      name: "tests",
      type: "folder",
      children: [
        {
          id: "contract-test",
          name: "contract.test.ts",
          type: "file",
          language: "typescript",
          content: `describe("GreetingContract", () => {
  it("returns a greeting", () => {
    expect("Hello, Soroban").toContain("Soroban");
  });
});
`,
        },
      ],
    },
    {
      id: "cargo",
      name: "Cargo.toml",
      type: "file",
      language: "toml",
      content: `[package]
name = "stellar-token-starter"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
soroban-sdk = "22.0.0"
`,
    },
    {
      id: "readme",
      name: "README.md",
      type: "file",
      language: "markdown",
      content: `# Stellar Token Starter

Browser-persistent starter workspace for Soroban contract experiments.
`,
    },
  ],
}

function collectFileIds(node, ids = []) {
  if (node.type === "file") {
    ids.push(node.id)
    return ids
  }

  ;(node.children || []).forEach((child) => collectFileIds(child, ids))
  return ids
}

function findNodeById(node, id) {
  if (!node) return null
  if (node.id === id) return node
  if (node.type !== "folder") return null

  for (const child of node.children || []) {
    const found = findNodeById(child, id)
    if (found) return found
  }

  return null
}

function updateNodeById(node, id, updater) {
  if (node.id === id) {
    return updater(node)
  }

  if (node.type !== "folder") {
    return node
  }

  return {
    ...node,
    children: (node.children || []).map((child) => updateNodeById(child, id, updater)),
  }
}

function insertNode(parent, parentId, newNode) {
  if (parent.id === parentId && parent.type === "folder") {
    return {
      ...parent,
      children: [...(parent.children || []), newNode],
    }
  }

  if (parent.type !== "folder") {
    return parent
  }

  return {
    ...parent,
    children: (parent.children || []).map((child) => insertNode(child, parentId, newNode)),
  }
}

function getLineNumbers(content) {
  return Array.from({ length: Math.max(content.split("\n").length, 1) }, (_, index) => index + 1)
}

function createNodeId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function buildDefaultExpandedFolders() {
  return ["root", "src", "tests"]
}

function renderStatusLabel(status, unsavedChanges) {
  if (unsavedChanges) return "Unsaved changes"
  return status
}

function WorkspaceTree({
  node,
  expandedFolders,
  activeFileId,
  onToggleFolder,
  onSelectFile,
  depth = 0,
}) {
  const isFolder = node.type === "folder"
  const isExpanded = expandedFolders.includes(node.id)

  if (isFolder) {
    return (
      <div>
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-gray-300 transition hover:bg-gray-800"
          style={{ paddingLeft: `${depth * 14 + 8}px` }}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
          {isExpanded ? (
            <FolderOpen className="h-4 w-4 text-amber-300" />
          ) : (
            <FolderClosed className="h-4 w-4 text-amber-300" />
          )}
          <span>{node.name}</span>
        </button>

        {isExpanded &&
          (node.children || []).map((child) => (
            <WorkspaceTree
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedFolders={expandedFolders}
              activeFileId={activeFileId}
              onToggleFolder={onToggleFolder}
              onSelectFile={onSelectFile}
            />
          ))}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onSelectFile(node.id)}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition ${
        activeFileId === node.id
          ? "bg-blue-500/20 text-white"
          : "text-gray-300 hover:bg-gray-800"
      }`}
      style={{ paddingLeft: `${depth * 14 + 28}px` }}
    >
      <FileCode2 className="h-4 w-4 text-cyan-300" />
      <span>{node.name}</span>
    </button>
  )
}

export default function IDEApp() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [chatOpen, setChatOpen] = useState(true)
  const [message, setMessage] = useState("")
  const [isMobile, setIsMobile] = useState(false)
  const [workspace, setWorkspace] = useState(defaultWorkspace)
  const [expandedFolders, setExpandedFolders] = useState(buildDefaultExpandedFolders())
  const [activeFileId, setActiveFileId] = useState("contract")
  const [editorValue, setEditorValue] = useState("")
  const [saveStatus, setSaveStatus] = useState("All changes saved")
  const [isHydrated, setIsHydrated] = useState(false)
  const autosaveTimerRef = useRef(null)

  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)

      if (mobile) {
        setSidebarOpen(false)
        setChatOpen(false)
      } else if (window.innerWidth >= 1024) {
        setSidebarOpen(true)
        setChatOpen(true)
      }
    }

    const storedWorkspace = window.localStorage.getItem(STORAGE_KEY)
    if (storedWorkspace) {
      try {
        const parsed = JSON.parse(storedWorkspace)
        setWorkspace(parsed.workspace || defaultWorkspace)
        setExpandedFolders(parsed.expandedFolders || buildDefaultExpandedFolders())
        setActiveFileId(parsed.activeFileId || "contract")
      } catch {
        window.localStorage.removeItem(STORAGE_KEY)
      }
    }

    setIsHydrated(true)
    checkMobile()
    window.addEventListener("resize", checkMobile)
    return () => window.removeEventListener("resize", checkMobile)
  }, [])

  const activeFile = useMemo(() => findNodeById(workspace, activeFileId), [workspace, activeFileId])
  const activeFileContent = activeFile?.type === "file" ? activeFile.content : ""
  const unsavedChanges = editorValue !== activeFileContent

  useEffect(() => {
    if (activeFile?.type === "file") {
      setEditorValue(activeFile.content)
    }
  }, [activeFileId, activeFile])

  useEffect(() => {
    if (!isHydrated) return

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ workspace, expandedFolders, activeFileId })
    )
  }, [workspace, expandedFolders, activeFileId, isHydrated])

  useEffect(() => {
    if (!isHydrated || !activeFile || activeFile.type !== "file") {
      return undefined
    }

    if (!unsavedChanges) {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current)
      }
      return undefined
    }

    setSaveStatus("Autosaving...")
    autosaveTimerRef.current = window.setTimeout(() => {
      setWorkspace((current) =>
        updateNodeById(current, activeFileId, (node) => ({
          ...node,
          content: editorValue,
        }))
      )
      setSaveStatus("All changes saved")
    }, AUTOSAVE_DELAY_MS)

    return () => {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current)
      }
    }
  }, [activeFile, activeFileId, editorValue, isHydrated, unsavedChanges])

  const fileCount = collectFileIds(workspace).length
  const lineNumbers = getLineNumbers(editorValue)

  const toggleFolder = (folderId) => {
    setExpandedFolders((current) =>
      current.includes(folderId)
        ? current.filter((id) => id !== folderId)
        : [...current, folderId]
    )
  }

  const handleManualSave = () => {
    if (!activeFile || activeFile.type !== "file") return

    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current)
    }

    setWorkspace((current) =>
      updateNodeById(current, activeFileId, (node) => ({
        ...node,
        content: editorValue,
      }))
    )
    setSaveStatus("All changes saved")
  }

  const createWorkspaceItem = (type) => {
    const input = window.prompt(type === "file" ? "New file name" : "New folder name")
    const name = input?.trim()

    if (!name) return

    const newNode =
      type === "file"
        ? {
            id: createNodeId("file"),
            name,
            type: "file",
            language: name.split(".").pop() || "text",
            content: "",
          }
        : {
            id: createNodeId("folder"),
            name,
            type: "folder",
            children: [],
          }

    setWorkspace((current) => insertNode(current, "root", newNode))

    if (type === "file") {
      setActiveFileId(newNode.id)
    } else {
      setExpandedFolders((current) => [...new Set([...current, "root", newNode.id])])
    }
  }

  const sidebarVariants = {
    open: { x: 0, opacity: 1 },
    closed: { x: "-100%", opacity: 0 },
  }

  const chatVariants = {
    open: { x: 0, opacity: 1 },
    closed: { x: "100%", opacity: 0 },
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0D1117] text-white">
      {isMobile && (sidebarOpen || chatOpen) && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => {
            setSidebarOpen(false)
            setChatOpen(false)
          }}
        />
      )}

      <AnimatePresence>
        {(sidebarOpen || !isMobile) && (
          <motion.aside
            initial={isMobile ? "closed" : "open"}
            animate="open"
            exit="closed"
            variants={sidebarVariants}
            transition={{ duration: 0.25 }}
            className={`${
              isMobile ? "fixed left-0 top-0 z-40 h-full w-80 max-w-[86vw]" : "relative"
            } ${!isMobile && !sidebarOpen ? "w-0" : ""} ${
              !isMobile && sidebarOpen ? "w-72 xl:w-80" : ""
            } flex flex-col border-r border-gray-800 bg-[#161B22]`}
          >
            <div className="flex items-center justify-between border-b border-gray-800 p-4">
              <div>
                <h2 className="text-lg font-semibold">Workspace</h2>
                <p className="text-xs text-gray-400">{fileCount} files tracked</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(false)}
                className="p-1 text-gray-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="border-b border-gray-800 p-3">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => createWorkspaceItem("file")}
                  className="justify-start text-gray-300 hover:text-white"
                >
                  <Plus className="mr-1 h-4 w-4" />
                  New File
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => createWorkspaceItem("folder")}
                  className="justify-start text-gray-300 hover:text-white"
                >
                  <FolderOpen className="mr-1 h-4 w-4" />
                  New Folder
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              <WorkspaceTree
                node={workspace}
                expandedFolders={expandedFolders}
                activeFileId={activeFileId}
                onToggleFolder={toggleFolder}
                onSelectFile={setActiveFileId}
              />
            </div>

            <div className="border-t border-gray-800 p-4">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start text-gray-400 hover:text-white"
              >
                <Settings className="mr-2 h-4 w-4" />
                Workspace Settings
              </Button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-12 items-center gap-4 border-b border-gray-800 bg-[#161B22] px-4">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1 text-gray-400 hover:text-white"
            >
              <Menu className="h-4 w-4" />
            </Button>
            <div>
              <p className="text-sm text-white">{activeFile?.name || "No file selected"}</p>
              <p className="text-xs text-gray-500">{renderStatusLabel(saveStatus, unsavedChanges)}</p>
            </div>
          </div>

          <div className="flex-1" />

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleManualSave}
              className="hidden p-1 text-gray-400 hover:text-white sm:flex"
            >
              <Save className="mr-1 h-4 w-4" />
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="hidden p-1 text-gray-400 hover:text-white sm:flex"
            >
              <Play className="mr-1 h-4 w-4" />
              Run
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setChatOpen(!chatOpen)}
              className="p-1 text-gray-400 hover:text-white"
            >
              <MessageSquare className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          <div className={`flex min-w-0 flex-1 flex-col ${!isMobile && chatOpen ? "lg:flex-1" : "flex-1"}`}>
            <div className="border-b border-gray-800 bg-[#11161D] px-4 py-2 text-xs text-gray-400">
              {workspace.name} / {activeFile?.name || "untitled"}
            </div>

            <div className="flex flex-1 overflow-hidden bg-[#0D1117]">
              <div className="hidden select-none border-r border-gray-800 bg-[#11161D] px-3 py-4 text-right font-mono text-xs text-gray-500 sm:block">
                {lineNumbers.map((lineNumber) => (
                  <div key={lineNumber} className="leading-6">
                    {lineNumber}
                  </div>
                ))}
              </div>

              <textarea
                aria-label="Code editor"
                value={editorValue}
                onChange={(event) => setEditorValue(event.target.value)}
                spellCheck="false"
                className="flex-1 resize-none bg-transparent px-4 py-4 font-mono text-sm leading-6 text-gray-100 outline-none"
              />
            </div>
          </div>

          <AnimatePresence>
            {(chatOpen || !isMobile) && (
              <motion.div
                initial={isMobile ? "closed" : "open"}
                animate="open"
                exit="closed"
                variants={chatVariants}
                transition={{ duration: 0.25 }}
                className={`${
                  isMobile ? "fixed right-0 top-0 z-40 h-full w-80 max-w-[86vw]" : "relative"
                } ${!isMobile && !chatOpen ? "w-0" : ""} ${
                  !isMobile && chatOpen ? "w-80 xl:w-96" : ""
                } flex flex-col border-l border-gray-800 bg-[#161B22]`}
              >
                <div className="flex h-12 items-center justify-between border-b border-gray-800 px-4">
                  <div>
                    <h3 className="text-sm font-semibold">AI Assistant</h3>
                    <p className="text-xs text-gray-500">Workspace-aware draft guidance</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setChatOpen(false)}
                    className="p-1 text-gray-400 hover:text-white"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="flex-1 space-y-4 overflow-y-auto p-4">
                  <div className="rounded-lg bg-[#0D1117] p-3">
                    <p className="text-sm text-gray-200">
                      Open file: <span className="font-medium text-white">{activeFile?.name || "None"}</span>
                    </p>
                    <p className="mt-2 text-sm text-gray-400">
                      I can help refine the active contract, propose tests, or scaffold missing files.
                    </p>
                  </div>

                  <div className="ml-8 rounded-lg bg-blue-600 p-3">
                    <p className="text-sm">Add storage-backed token balances and tests.</p>
                  </div>

                  <div className="rounded-lg bg-[#0D1117] p-3">
                    <p className="text-sm text-gray-300">
                      Start by extending the contract state, then add a focused test file for mint and transfer flows.
                    </p>
                  </div>
                </div>

                <div className="border-t border-gray-800 p-4">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder="Ask about the active file..."
                      className="min-h-[40px] flex-1 rounded border border-gray-700 bg-[#0D1117] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault()
                          setMessage("")
                        }
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-[40px] w-[40px] p-2 text-gray-400 hover:text-white"
                      onClick={() => setMessage("")}
                    >
                      <Send className="h-4 w-4" />
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
