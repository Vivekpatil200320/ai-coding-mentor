"use client";

import Editor, { type BeforeMount } from "@monaco-editor/react";

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

// Matches the app's token system (app/globals.css) rather than Monaco's
// stock vs-dark, so the editor doesn't look like a different product
// bolted onto the page.
const beforeMount: BeforeMount = (monaco) => {
  monaco.editor.defineTheme("mentor-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "8f8571", fontStyle: "italic" },
      { token: "keyword", foreground: "e0a73a" },
      { token: "string", foreground: "74c98b" },
      { token: "number", foreground: "d9bb7a" },
    ],
    colors: {
      "editor.background": "#1c1811",
      "editor.foreground": "#ede6d8",
      "editorLineNumber.foreground": "#4a4437",
      "editorLineNumber.activeForeground": "#8f8571",
      "editor.selectionBackground": "#e0a73a2e",
      "editorCursor.foreground": "#e0a73a",
      "editor.lineHighlightBackground": "#241f16",
    },
  });
};

export function CodeEditor({ value, onChange, readOnly = false }: CodeEditorProps) {
  return (
    <div className="h-full overflow-hidden rounded-xl border border-border">
      <Editor
        height="100%"
        defaultLanguage="python"
        theme="mentor-dark"
        value={value}
        onChange={(next) => onChange(next ?? "")}
        beforeMount={beforeMount}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          padding: { top: 16 },
          scrollBeyondLastLine: false,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
