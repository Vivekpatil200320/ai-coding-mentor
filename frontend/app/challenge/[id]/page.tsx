"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CodeEditor } from "@/components/CodeEditor";
import { MentorChat } from "@/components/MentorChat";
import { Terminal } from "@/components/Terminal";
import { getOrCreateUserId, startSession, submitCode } from "@/lib/api";
import type { ChallengeMetadata, ExecutionResult } from "@/lib/types";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; sessionId: string; userId: string; challenge: ChallengeMetadata };

export default function ChallengeWorkspace({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: challengeId } = use(params);
  const router = useRouter();

  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [code, setCode] = useState("");
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [justPassed, setJustPassed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const userId = getOrCreateUserId();
        const session = await startSession(challengeId, userId);
        if (cancelled) return;
        setCode(session.codebase);
        setLoad({
          status: "ready",
          sessionId: session.session_id,
          userId,
          challenge: session.challenge,
        });
      } catch {
        if (!cancelled) {
          setLoad({
            status: "error",
            message: "Couldn't start a session. Check that the backend is running.",
          });
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [challengeId]);

  async function handleSubmit() {
    if (load.status !== "ready" || isRunning) return;
    setIsRunning(true);
    setResult(null);
    try {
      const response = await submitCode(load.sessionId, load.userId, code);
      setResult(response.execution_result);
      if (response.next_action === "evaluation") {
        setJustPassed(true);
      }
    } catch {
      setResult({
        passed: false,
        stdout: "",
        stderr: "Couldn't reach the sandbox. Try submitting again.",
        exit_code: -1,
        timed_out: false,
        test_results: "",
        refused: false,
        violations: [],
      });
    } finally {
      setIsRunning(false);
    }
  }

  if (load.status === "loading") {
    return (
      <main className="flex h-screen items-center justify-center bg-bg">
        <p className="font-display text-lg italic text-muted">starting session…</p>
      </main>
    );
  }

  if (load.status === "error") {
    return (
      <main className="flex h-screen items-center justify-center bg-bg px-6">
        <p className="max-w-md rounded-xl border border-fail/30 bg-fail/10 px-6 py-4 font-sans text-sm text-fail">
          {load.message}
        </p>
      </main>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-bg">
      <header className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
        <div>
          <p className="font-sans text-xs uppercase tracking-[0.2em] text-muted">
            {load.challenge.difficulty} · {load.challenge.type.replace("_", " ")}
          </p>
          <h1 className="font-display text-xl text-ink">{load.challenge.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          {justPassed && (
            <button
              onClick={() => router.push(`/report/${load.sessionId}?user_id=${encodeURIComponent(load.userId)}`)}
              className="rounded-lg border border-pass/40 bg-pass/10 px-4 py-2 font-sans text-sm font-medium text-pass transition-colors hover:bg-pass/20"
            >
              View report &rarr;
            </button>
          )}
          <button
            onClick={handleSubmit}
            disabled={isRunning}
            className="rounded-lg bg-accent px-5 py-2 font-sans text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
          >
            {isRunning ? "Running…" : "Run tests"}
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        <div className="min-h-0">
          <CodeEditor value={code} onChange={setCode} />
        </div>
        <div className="grid min-h-0 grid-rows-[3fr_2fr] gap-3">
          <MentorChat sessionId={load.sessionId} userId={load.userId} />
          <Terminal result={result} isRunning={isRunning} />
        </div>
      </div>
    </div>
  );
}
