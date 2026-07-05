import type { ExecutionResult } from "@/lib/types";

interface TerminalProps {
  result: ExecutionResult | null;
  isRunning: boolean;
}

export function Terminal({ result, isRunning }: TerminalProps) {
  const dotClass = isRunning
    ? "animate-pulse bg-accent"
    : result === null
      ? "bg-muted/50"
      : result.passed
        ? "bg-pass"
        : "bg-fail";

  return (
    <div className="card-raised flex h-full flex-col p-0">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
          <span className="font-sans text-xs uppercase tracking-[0.2em] text-muted">
            test run
          </span>
        </div>
        {result && (
          <span
            className={`font-sans text-xs font-medium uppercase tracking-wide ${result.passed ? "text-pass" : "text-fail"}`}
          >
            {result.passed
              ? "passed"
              : result.timed_out
                ? "timed out"
                : result.refused
                  ? "refused"
                  : "failed"}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-5 font-mono text-xs leading-relaxed">
        {isRunning && <p className="text-muted">running tests…</p>}
        {!isRunning && result === null && (
          <p className="font-sans text-sm text-muted">
            Submit your code to run the test suite.
          </p>
        )}
        {!isRunning && result?.refused && (
          <div className="text-fail">
            <p>Execution refused — security check failed:</p>
            <ul className="mt-1 list-inside list-disc">
              {result.violations.map((violation) => (
                <li key={violation}>{violation}</li>
              ))}
            </ul>
          </div>
        )}
        {!isRunning && result && !result.refused && (
          <pre className="whitespace-pre-wrap text-ink-dim">
            {result.test_results || result.stdout}
            {result.stderr && <span className="text-fail">{"\n" + result.stderr}</span>}
          </pre>
        )}
      </div>
    </div>
  );
}
