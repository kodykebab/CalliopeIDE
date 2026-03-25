import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import IDEApp from "@/pages/app/index";

jest.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    aside: ({ children, ...props }: any) => <aside {...props}>{children}</aside>,
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

describe("IDE workspace app", () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.restoreAllMocks();
  });

  it("loads the default workspace and switches active files from the explorer", () => {
    render(<IDEApp />);

    expect(screen.getByText("stellar-token-starter / contract.rs")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "README.md" }));

    expect(screen.getByText("stellar-token-starter / README.md")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Browser-persistent starter workspace/)).toBeInTheDocument();
  });

  it("autosaves editor content into local storage", async () => {
    jest.useFakeTimers();

    render(<IDEApp />);

    const editor = screen.getByLabelText("Code editor");
    fireEvent.change(editor, { target: { value: "fn main() {}\n" } });

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(750);
    });

    await waitFor(() => {
      const stored = JSON.parse(window.localStorage.getItem("calliope.workspace.v1") || "{}");
      expect(stored.workspace.children[0].children[0].content).toBe("fn main() {}\n");
    });

    jest.useRealTimers();
  });

  it("creates a new file from the workspace actions", () => {
    jest.spyOn(window, "prompt").mockReturnValue("notes.md");

    render(<IDEApp />);

    fireEvent.click(screen.getByRole("button", { name: /New File/i }));

    expect(screen.getByRole("button", { name: "notes.md" })).toBeInTheDocument();
    expect(screen.getByText("stellar-token-starter / notes.md")).toBeInTheDocument();
  });
});
