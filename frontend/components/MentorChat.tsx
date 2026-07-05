"use client";

import { useEffect, useRef, useState } from "react";
import { streamMessage } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface MentorChatProps {
  sessionId: string;
  userId: string;
}

export function MentorChat({ sessionId, userId }: MentorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const hasKickedOff = useRef(false);

  // The mentor only speaks once /message is called (backend/api/orchestrator.py).
  // Kick off silently so the mentor opens the conversation.
  useEffect(() => {
    if (hasKickedOff.current) return;
    hasKickedOff.current = true;
    void send("I'm ready to start.", { silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string, opts: { silent?: boolean } = {}) {
    if (!text.trim() || isStreaming) return;
    setIsStreaming(true);

    if (!opts.silent) {
      setMessages((prev) => [...prev, { role: "user", content: text }]);
    }
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      for await (const token of streamMessage(sessionId, userId, text)) {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + token };
          return next;
        });
      }
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "Lost the connection to the mentor. Try sending that again.",
        };
        return next;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft;
    setDraft("");
    void send(text);
  }

  return (
    <div className="card-raised flex h-full flex-col p-0">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="font-sans text-xs uppercase tracking-[0.2em] text-muted">
          the mentor
        </span>
      </div>

      <div ref={listRef} className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        {messages.length === 0 && (
          <p className="font-sans text-sm text-muted">connecting…</p>
        )}
        {messages.map((message, i) =>
          message.role === "assistant" ? (
            // The mentor's voice: editorial serif, like a reviewer's note.
            <p
              key={i}
              className="font-display text-lg leading-relaxed text-ink"
            >
              {message.content || (isStreaming && i === messages.length - 1 ? "…" : "")}
            </p>
          ) : (
            <div key={i} className="text-right">
              <span className="inline-block max-w-[85%] rounded-2xl rounded-tr-sm bg-surface-raised px-4 py-2 text-left font-sans text-sm text-ink-dim">
                {message.content}
              </span>
            </div>
          )
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border p-3">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Talk through what you think is happening"
          disabled={isStreaming}
          className="flex-1 rounded-lg border border-border bg-bg px-4 py-2.5 font-sans text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !draft.trim()}
          className="rounded-lg bg-accent px-5 py-2.5 font-sans text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Send
        </button>
      </form>
    </div>
  );
}
