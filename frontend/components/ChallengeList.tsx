import Link from "next/link";
import type { ChallengeMetadata } from "@/lib/types";

const TYPE_LABEL: Record<ChallengeMetadata["type"], string> = {
  bug_fix: "bug fix",
  feature_extension: "feature",
  refactor: "refactor",
};

const TYPE_COLOR: Record<ChallengeMetadata["type"], string> = {
  bug_fix: "text-fail border-fail/30 bg-fail/10",
  feature_extension: "text-pass border-pass/30 bg-pass/10",
  refactor: "text-accent border-accent/30 bg-accent-soft",
};

export function ChallengeList({ challenges }: { challenges: ChallengeMetadata[] }) {
  return (
    <ul className="card-raised divide-y divide-[color:var(--color-border)] overflow-hidden p-0">
      {challenges.map((challenge) => (
        <li key={challenge.id}>
          <Link
            href={`/challenge/${challenge.id}`}
            className="group flex flex-col gap-3 px-6 py-5 transition-colors hover:bg-surface-raised focus-visible:bg-surface-raised focus-visible:outline-none sm:flex-row sm:items-center sm:gap-6"
          >
            <span
              className={`inline-flex w-fit items-center rounded-full border px-2.5 py-0.5 font-sans text-[11px] uppercase tracking-wide ${TYPE_COLOR[challenge.type]}`}
            >
              {TYPE_LABEL[challenge.type]}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-3">
                <h3 className="font-display text-lg text-ink transition-colors group-hover:text-accent">
                  {challenge.title}
                </h3>
                <span className="font-sans text-xs uppercase tracking-wide text-muted">
                  {challenge.difficulty}
                </span>
              </div>
              <p className="mt-1 truncate font-sans text-sm text-muted">
                {challenge.learning_objective}
              </p>
            </div>

            <span
              aria-hidden
              className="shrink-0 font-sans text-sm text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent"
            >
              open &rarr;
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
