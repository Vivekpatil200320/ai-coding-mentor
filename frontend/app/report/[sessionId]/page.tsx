"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { EvalReport } from "@/components/EvalReport";
import { getOrCreateUserId, getReport, ReportNotReadyError } from "@/lib/api";
import type { EvaluationReport } from "@/lib/types";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; report: EvaluationReport };

const RETRY_DELAYS_MS = [500, 1000, 2000];

export default function ReportPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const searchParams = useSearchParams();
  const [load, setLoad] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    // Falls back to this browser's own id (e.g. direct navigation without
    // the query param) — the backend will 403 if it isn't the session owner.
    const userId = searchParams.get("user_id") ?? getOrCreateUserId();

    async function load_() {
      // Evaluation runs synchronously inside /submit before it returns,
      // so this should resolve on the first try — the retry only
      // covers the unlikely case of landing here before that write is
      // visible.
      for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt += 1) {
        try {
          const report = await getReport(sessionId, userId);
          if (!cancelled) setLoad({ status: "ready", report });
          return;
        } catch (error) {
          if (error instanceof ReportNotReadyError && attempt < RETRY_DELAYS_MS.length) {
            await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[attempt]));
            continue;
          }
          if (!cancelled) {
            setLoad({
              status: "error",
              message:
                error instanceof ReportNotReadyError
                  ? "Still evaluating — give it a moment and reload."
                  : "Couldn't load the report.",
            });
          }
          return;
        }
      }
    }

    void load_();
    return () => {
      cancelled = true;
    };
  }, [sessionId, searchParams]);

  return (
    <main className="mx-auto max-w-2xl px-6 py-20">
      <Link
        href="/"
        className="mb-10 inline-block font-sans text-xs uppercase tracking-[0.2em] text-muted transition-colors hover:text-accent"
      >
        &larr; all challenges
      </Link>

      <p className="mb-2 font-sans text-xs uppercase tracking-[0.25em] text-muted">
        Code review
      </p>
      <h1 className="mb-10 font-display text-4xl text-ink">The senior&rsquo;s notes</h1>

      {load.status === "loading" && (
        <p className="font-display text-lg italic text-muted">reading your submission…</p>
      )}
      {load.status === "error" && (
        <p className="rounded-xl border border-accent/30 bg-accent-soft px-6 py-4 font-sans text-sm text-accent">
          {load.message}
        </p>
      )}
      {load.status === "ready" && <EvalReport report={load.report} />}
    </main>
  );
}
