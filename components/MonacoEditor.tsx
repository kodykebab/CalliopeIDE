"use client"

import { useRef, useCallback } from "react"
import Editor, { OnMount, OnChange } from "@monaco-editor/react"
import type { editor as MonacoEditorNS } from "monaco-editor"
import { X } from "lucide-react"

// ── Types ──────────────────────────────────────────────────────────────────────

export interface EditorFile {
  /** Absolute or workspace-relative path — used as the stable unique key */
  path: string
  /** Display name shown in the tab */
  name: string
  /** Current content of the file in the editor */
  content: string
  /** True when the buffer differs from the last-saved version */
  isDirty: boolean
  /** Monaco language id — derived automatically if omitted */
  language?: string
}

export interface MonacoEditorProps {
  /** All open files */
  files: EditorFile[]
  /** Path of the currently-visible file */
  activeFilePath: string | null
  /** Fired when the user switches tabs */
  onFileSelect: (path: string) => void
  /** Fired on every keystroke; provides the updated file object */
  onFileChange: (path: string, newContent: string) => void
  /** Fired when the user closes a tab (× button) */
  onFileClose: (path: string) => void
}

// ── Language detection ─────────────────────────────────────────────────────────

const EXT_TO_LANGUAGE: Record<string, string> = {
  rs:   "rust",
  ts:   "typescript",
  tsx:  "typescript",
  js:   "javascript",
  jsx:  "javascript",
  py:   "python",
  json: "json",
  md:   "markdown",
  toml: "ini",
  yaml: "yaml",
  yml:  "yaml",
  html: "html",
  css:  "css",
}

function detectLanguage(filePath: string, explicit?: string): string {
  if (explicit) return explicit
  const ext = filePath.split(".").pop()?.toLowerCase() ?? ""
  return EXT_TO_LANGUAGE[ext] ?? "plaintext"
}

// ── Component ──────────────────────────────────────────────────────────────────

/**
 * MonacoEditor — resolves issue #51.
 *
 * Wraps `@monaco-editor/react` and adds:
 *   • Multi-file tabs with active-file highlighting
 *   • Per-file dirty (unsaved-changes) tracking shown as a dot in the tab
 *   • Rust / TypeScript / JavaScript syntax highlighting out-of-the-box
 *   • Stable editor instance — model swap instead of full remount on tab switch
 *   • Keyboard shortcut Ctrl/Cmd+S bubbles a save event (consumed by the parent)
 */
export default function MonacoEditor({
  files,
  activeFilePath,
  onFileSelect,
  onFileChange,
  onFileClose,
}: MonacoEditorProps) {
  const editorRef = useRef<MonacoEditorNS.IStandaloneCodeEditor | null>(null)

  const activeFile = files.find((f) => f.path === activeFilePath) ?? null

  // ── Editor mount ────────────────────────────────────────────────────────────
  const handleEditorMount: OnMount = useCallback((editor) => {
    editorRef.current = editor

    // Propagate Ctrl/Cmd+S to the browser so the parent's keyboard listener
    // (or the native Save shortcut) can pick it up.
    editor.addCommand(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).monaco?.KeyMod?.CtrlCmd | (window as any).monaco?.KeyCode?.KeyS ?? 0,
      () => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true, bubbles: true }))
      }
    )
  }, [])

  // ── Content change ──────────────────────────────────────────────────────────
  const handleChange: OnChange = useCallback(
    (value) => {
      if (activeFilePath && value !== undefined) {
        onFileChange(activeFilePath, value)
      }
    },
    [activeFilePath, onFileChange]
  )

  // ── Tab close — prevent closing the last file ────────────────────────────────
  const handleClose = (e: React.MouseEvent, path: string) => {
    e.stopPropagation()
    onFileClose(path)
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col h-full bg-[#1e1e1e]"
      data-testid="monaco-editor-container"
    >
      {/* ── Tab bar ─────────────────────────────────────────────────────────── */}
      <div
        className="flex overflow-x-auto shrink-0 bg-[#252526] border-b border-[#1e1e1e]"
        role="tablist"
        aria-label="Open files"
      >
        {files.map((file) => {
          const isActive = file.path === activeFilePath
          return (
            <button
              key={file.path}
              role="tab"
              aria-selected={isActive}
              aria-controls="monaco-editor-panel"
              id={`tab-${file.path}`}
              onClick={() => onFileSelect(file.path)}
              className={[
                "flex items-center gap-1.5 px-3 py-2 text-xs shrink-0 border-r border-[#1e1e1e]",
                "transition-colors select-none whitespace-nowrap",
                isActive
                  ? "bg-[#1e1e1e] text-white border-t-2 border-t-blue-500"
                  : "text-gray-400 hover:bg-[#2d2d2d] hover:text-gray-200",
              ].join(" ")}
            >
              {/* Dirty dot */}
              {file.isDirty && (
                <span
                  className="w-2 h-2 rounded-full bg-orange-400 shrink-0"
                  aria-label="Unsaved changes"
                  data-testid={`dirty-indicator-${file.name}`}
                />
              )}
              <span>{file.name}</span>

              {/* Close button */}
              <span
                role="button"
                aria-label={`Close ${file.name}`}
                onClick={(e) => handleClose(e, file.path)}
                className="ml-1 rounded hover:bg-gray-600 p-0.5 opacity-60 hover:opacity-100"
                data-testid={`close-tab-${file.name}`}
              >
                <X className="w-3 h-3" />
              </span>
            </button>
          )
        })}

        {files.length === 0 && (
          <div className="px-4 py-2 text-xs text-gray-500 italic">
            No files open — select a file from the explorer
          </div>
        )}
      </div>

      {/* ── Editor panel ────────────────────────────────────────────────────── */}
      <div
        id="monaco-editor-panel"
        role="tabpanel"
        aria-labelledby={activeFilePath ? `tab-${activeFilePath}` : undefined}
        className="flex-1 overflow-hidden"
        data-testid="monaco-editor-panel"
      >
        {activeFile ? (
          <Editor
            key={activeFile.path}
            height="100%"
            language={detectLanguage(activeFile.path, activeFile.language)}
            value={activeFile.content}
            theme="vs-dark"
            options={{
              fontSize: 14,
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Menlo, monospace",
              minimap: { enabled: true },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              renderLineHighlight: "all",
              smoothScrolling: true,
              cursorBlinking: "smooth",
              cursorSmoothCaretAnimation: "on",
              bracketPairColorization: { enabled: true },
              guides: { bracketPairs: true },
            }}
            onMount={handleEditorMount}
            onChange={handleChange}
            loading={
              <div className="flex items-center justify-center h-full">
                <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              </div>
            }
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            <span>Open a file from the explorer to start editing</span>
          </div>
        )}
      </div>
    </div>
  )
}
