import type { EvaluationReport } from "@/lib/types";

const DIMENSION_LABEL: Record<string, string> = {
  correctness: "correctness",
  edge_case_handling: "edge case handling",
  code_readability: "code readability",
  pattern_recognition: "pattern recognition",
  what_senior_would_catch: "what a senior would catch",
};

function scoreColor(score: number): string {
  if (score >= 8) return "text-pass border-pass/30 bg-pass/10";
  if (score >= 5) return "text-accent border-accent/30 bg-accent-soft";
  return "text-fail border-fail/30 bg-fail/10";
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div>
      <p className="mb-2 font-sans text-xs uppercase tracking-[0.2em] text-muted">
        {label}
      </p>
      <p className="font-display text-lg leading-relaxed text-ink-dim">{children}</p>
    </div>
  );
}

export function EvalReport({ report }: { report: EvaluationReport }) {
  if (report.parse_error) {
    return (
      <div className="rounded-xl border border-accent/30 bg-accent-soft p-6">
        <p className="mb-2 font-sans text-xs uppercase tracking-[0.2em] text-accent">
          couldn&rsquo;t parse the review
        </p>
        <pre className="whitespace-pre-wrap font-mono text-xs text-ink-dim">
          {report.raw_response}
        </pre>
      </div>
    );
  }

  const dimensions = Object.entries(report.scores ?? {});

  return (
    <div className="space-y-10">
      {dimensions.length > 0 && (
        <div>
          <p className="mb-4 font-sans text-xs uppercase tracking-[0.2em] text-muted">
            Rubric
          </p>
          <div className="space-y-3">
            {dimensions.map(([key, { score, comment }]) => (
              <div key={key} className="card-raised flex items-start gap-4 p-4">
                <span
                  className={`shrink-0 rounded-lg border px-2.5 py-1 font-mono text-xs ${scoreColor(score)}`}
                >
                  {score}/10
                </span>
                <div>
                  <p className="font-sans text-sm font-medium text-ink">
                    {DIMENSION_LABEL[key] ?? key}
                  </p>
                  <p className="mt-1 font-sans text-sm leading-relaxed text-muted">
                    {comment}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card-raised space-y-7 p-7">
        <Section label="what you did well">{report.what_you_did_well}</Section>
        <Section label="what you missed">{report.what_you_missed}</Section>
        <Section label="the pattern">{report.pattern}</Section>
        <Section label="what a real reviewer would flag">
          {report.what_a_real_reviewer_would_flag}
        </Section>
        <Section label="next up">{report.suggested_next_challenge}</Section>
      </div>
    </div>
  );
}
