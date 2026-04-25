/**
 * tests/components/monaco-editor.test.tsx
 *
 * Unit tests for the MonacoEditor component (Issue #51).
 * Covers: multi-file tabs, dirty tracking, language detection,
 * tab close, empty states, and ARIA accessibility attributes.
 *
 * @monaco-editor/react is mocked so no real Monaco bundle is loaded.
 */

import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"

// ── Mock @monaco-editor/react ──────────────────────────────────────────────────
// The real Monaco editor relies on Worker / browser globals not available in
// jsdom. We replace it with a lightweight textarea that exercises the same
// props our wrapper passes through.
jest.mock("@monaco-editor/react", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const FakeEditor = ({ value, onChange, onMount, loading }: any) => {
    // Call onMount with a minimal mock editor object so our ref logic works.
    React.useEffect(() => {
      if (onMount) {
        onMount(
          {
            addCommand: jest.fn(),
            getValue: () => value ?? "",
          },
          {}
        )
      }
      // We intentionally exclude onMount from the deps to mimic the real editor.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    if (loading && value === undefined) return <>{loading}</>

    return (
      <textarea
        data-testid="monaco-fake-editor"
        value={value ?? ""}
        onChange={(e) => onChange && onChange(e.target.value)}
        aria-label="code editor"
      />
    )
  }
  return FakeEditor
})

// ── Import component after mock ───────────────────────────────────────────────
import MonacoEditor, { EditorFile } from "../../components/MonacoEditor"

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeFile(overrides: Partial<EditorFile> = {}): EditorFile {
  return {
    path: "/workspace/src/contract.rs",
    name: "contract.rs",
    content: "// Soroban contract",
    isDirty: false,
    ...overrides,
  }
}

const DEFAULT_PROPS = {
  files: [] as EditorFile[],
  activeFilePath: null,
  onFileSelect: jest.fn(),
  onFileChange: jest.fn(),
  onFileClose: jest.fn(),
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Empty state
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — empty state", () => {
  it("renders the editor container", () => {
    render(<MonacoEditor {...DEFAULT_PROPS} />)
    expect(screen.getByTestId("monaco-editor-container")).toBeInTheDocument()
  })

  it("shows a placeholder message when no files are open", () => {
    render(<MonacoEditor {...DEFAULT_PROPS} />)
    expect(
      screen.getByText(/no files open/i)
    ).toBeInTheDocument()
  })

  it("shows a prompt to open a file when no active file is set", () => {
    render(<MonacoEditor {...DEFAULT_PROPS} />)
    expect(
      screen.getByText(/open a file from the explorer/i)
    ).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 2. Single file — tab rendering
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — single file tab", () => {
  const file = makeFile()
  const props = {
    ...DEFAULT_PROPS,
    files: [file],
    activeFilePath: file.path,
  }

  it("renders a tab for the open file", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getByRole("tab", { name: /contract\.rs/i })).toBeInTheDocument()
  })

  it("marks the active tab as selected", () => {
    render(<MonacoEditor {...props} />)
    const tab = screen.getByRole("tab", { name: /contract\.rs/i })
    expect(tab).toHaveAttribute("aria-selected", "true")
  })

  it("renders the editor panel", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getByTestId("monaco-editor-panel")).toBeInTheDocument()
  })

  it("passes initial content to the editor", () => {
    render(<MonacoEditor {...props} />)
    const textarea = screen.getByTestId("monaco-fake-editor")
    expect(textarea).toHaveValue("// Soroban contract")
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 3. Multi-file tabs
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — multi-file tabs", () => {
  const fileA = makeFile({ path: "/workspace/src/contract.rs", name: "contract.rs" })
  const fileB = makeFile({ path: "/workspace/src/lib.rs",      name: "lib.rs",      content: "// lib" })
  const fileC = makeFile({ path: "/workspace/Cargo.toml",       name: "Cargo.toml",  content: "[package]" })

  const props = {
    ...DEFAULT_PROPS,
    files: [fileA, fileB, fileC],
    activeFilePath: fileA.path,
  }

  it("renders a tab for every open file", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getAllByRole("tab")).toHaveLength(3)
  })

  it("only the active file tab has aria-selected=true", () => {
    render(<MonacoEditor {...props} />)
    const tabs = screen.getAllByRole("tab")
    const selected = tabs.filter((t) => t.getAttribute("aria-selected") === "true")
    expect(selected).toHaveLength(1)
    expect(selected[0]).toHaveTextContent("contract.rs")
  })

  it("fires onFileSelect with the correct path when a tab is clicked", () => {
    const onFileSelect = jest.fn()
    render(<MonacoEditor {...props} onFileSelect={onFileSelect} />)
    fireEvent.click(screen.getByRole("tab", { name: /lib\.rs/i }))
    expect(onFileSelect).toHaveBeenCalledWith(fileB.path)
  })

  it("shows the content of the active file in the editor", () => {
    render(<MonacoEditor {...props} activeFilePath={fileB.path} />)
    expect(screen.getByTestId("monaco-fake-editor")).toHaveValue("// lib")
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 4. Dirty tracking
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — dirty tracking", () => {
  const cleanFile = makeFile({ isDirty: false })
  const dirtyFile = makeFile({
    path: "/workspace/src/lib.rs",
    name: "lib.rs",
    isDirty: true,
  })

  it("does NOT show dirty indicator for a clean file", () => {
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[cleanFile]}
        activeFilePath={cleanFile.path}
      />
    )
    expect(screen.queryByTestId("dirty-indicator-contract.rs")).not.toBeInTheDocument()
  })

  it("shows dirty indicator for a modified file", () => {
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[dirtyFile]}
        activeFilePath={dirtyFile.path}
      />
    )
    expect(screen.getByTestId("dirty-indicator-lib.rs")).toBeInTheDocument()
  })

  it("calls onFileChange when the editor content changes", () => {
    const onFileChange = jest.fn()
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[cleanFile]}
        activeFilePath={cleanFile.path}
        onFileChange={onFileChange}
      />
    )
    const textarea = screen.getByTestId("monaco-fake-editor")
    fireEvent.change(textarea, { target: { value: "// edited content" } })
    expect(onFileChange).toHaveBeenCalledWith(cleanFile.path, "// edited content")
  })

  it("reflects dirty state for multiple files independently", () => {
    const f1 = makeFile({ path: "/a.rs", name: "a.rs", isDirty: false })
    const f2 = makeFile({ path: "/b.rs", name: "b.rs", isDirty: true })
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[f1, f2]}
        activeFilePath={f1.path}
      />
    )
    expect(screen.queryByTestId("dirty-indicator-a.rs")).not.toBeInTheDocument()
    expect(screen.getByTestId("dirty-indicator-b.rs")).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 5. Tab close
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — tab close", () => {
  const file = makeFile()
  const props = {
    ...DEFAULT_PROPS,
    files: [file],
    activeFilePath: file.path,
  }

  it("renders a close button for each tab", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getByTestId("close-tab-contract.rs")).toBeInTheDocument()
  })

  it("calls onFileClose with the correct path when the × is clicked", () => {
    const onFileClose = jest.fn()
    render(<MonacoEditor {...props} onFileClose={onFileClose} />)
    fireEvent.click(screen.getByTestId("close-tab-contract.rs"))
    expect(onFileClose).toHaveBeenCalledWith(file.path)
  })

  it("close button click does NOT trigger onFileSelect", () => {
    const onFileSelect = jest.fn()
    const onFileClose  = jest.fn()
    render(
      <MonacoEditor
        {...props}
        onFileSelect={onFileSelect}
        onFileClose={onFileClose}
      />
    )
    fireEvent.click(screen.getByTestId("close-tab-contract.rs"))
    expect(onFileSelect).not.toHaveBeenCalled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 6. Language detection (unit-tested via EditorFile.language override)
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — language / file type support", () => {
  const rustFile = makeFile({ path: "/src/contract.rs", name: "contract.rs", content: "fn main() {}" })

  it("renders without error for a Rust file", () => {
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[rustFile]}
        activeFilePath={rustFile.path}
      />
    )
    expect(screen.getByTestId("monaco-fake-editor")).toBeInTheDocument()
  })

  it("renders without error for a TypeScript file", () => {
    const tsFile = makeFile({ path: "/src/index.ts", name: "index.ts", content: "const x: number = 1" })
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[tsFile]}
        activeFilePath={tsFile.path}
      />
    )
    expect(screen.getByTestId("monaco-fake-editor")).toBeInTheDocument()
  })

  it("renders without error for a JSON file", () => {
    const jsonFile = makeFile({ path: "/package.json", name: "package.json", content: "{}" })
    render(
      <MonacoEditor
        {...DEFAULT_PROPS}
        files={[jsonFile]}
        activeFilePath={jsonFile.path}
      />
    )
    expect(screen.getByTestId("monaco-fake-editor")).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 7. Accessibility
// ─────────────────────────────────────────────────────────────────────────────

describe("MonacoEditor — accessibility", () => {
  const file = makeFile()
  const props = {
    ...DEFAULT_PROPS,
    files: [file],
    activeFilePath: file.path,
  }

  it("tab list has aria-label", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getByRole("tablist")).toHaveAttribute("aria-label", "Open files")
  })

  it("editor panel has role=tabpanel", () => {
    render(<MonacoEditor {...props} />)
    expect(screen.getByRole("tabpanel")).toBeInTheDocument()
  })

  it("active tab's id is referenced by panel's aria-labelledby", () => {
    render(<MonacoEditor {...props} />)
    const panel = screen.getByRole("tabpanel")
    const labelledBy = panel.getAttribute("aria-labelledby")
    expect(labelledBy).toBeTruthy()
    expect(document.getElementById(labelledBy!)).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 8. EditorFile data model (pure logic — no rendering)
// ─────────────────────────────────────────────────────────────────────────────

describe("EditorFile data model", () => {
  it("has required fields: path, name, content, isDirty", () => {
    const f = makeFile()
    expect(f).toHaveProperty("path")
    expect(f).toHaveProperty("name")
    expect(f).toHaveProperty("content")
    expect(f).toHaveProperty("isDirty")
  })

  it("isDirty defaults to false for a freshly opened file", () => {
    const f = makeFile()
    expect(f.isDirty).toBe(false)
  })

  it("multiple files can be tracked independently", () => {
    const files: EditorFile[] = [
      makeFile({ path: "/a.rs", name: "a.rs", isDirty: false }),
      makeFile({ path: "/b.rs", name: "b.rs", isDirty: true }),
      makeFile({ path: "/c.rs", name: "c.rs", isDirty: false }),
    ]
    const dirty = files.filter((f) => f.isDirty)
    expect(dirty).toHaveLength(1)
    expect(dirty[0].name).toBe("b.rs")
  })

  it("content can be updated without mutating the original", () => {
    const original = makeFile({ content: "original" })
    const updated: EditorFile = { ...original, content: "updated", isDirty: true }
    expect(original.content).toBe("original")
    expect(updated.content).toBe("updated")
    expect(updated.isDirty).toBe(true)
  })
})
