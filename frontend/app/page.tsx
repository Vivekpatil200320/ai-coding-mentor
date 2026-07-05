import { ChallengeList } from "@/components/ChallengeList";
import { SocraticHero } from "@/components/SocraticHero";
import type { ChallengeMetadata } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function loadChallenges(): Promise<
  { ok: true; challenges: ChallengeMetadata[] } | { ok: false }
> {
  try {
    const res = await fetch(`${API_BASE}/challenges/`, { cache: "no-store" });
    if (!res.ok) return { ok: false };
    return { ok: true, challenges: await res.json() };
  } catch {
    return { ok: false };
  }
}

export default async function Home() {
  const result = await loadChallenges();

  return (
    <main className="mx-auto max-w-3xl px-6 py-20 sm:py-28">
      <header className="mb-14">
        <p className="mb-5 font-sans text-xs uppercase tracking-[0.25em] text-muted">
          AI Coding Mentor
        </p>
        <h1 className="font-display text-4xl leading-[1.1] text-ink sm:text-5xl">
          You get dropped into broken code.
          <br />
          <span className="italic text-accent">It asks.</span> It doesn&rsquo;t tell.
        </h1>
        <p className="mt-6 max-w-xl font-sans text-base leading-relaxed text-muted">
          A senior engineer reads your fix and guides you with questions —
          the way a real code review feels, not a tutorial.
        </p>
      </header>

      <section className="mb-16" aria-label="How a session actually looks">
        <SocraticHero />
      </section>

      <section aria-label="Available challenges">
        <h2 className="mb-4 font-sans text-xs uppercase tracking-[0.25em] text-muted">
          Challenges
        </h2>
        {result.ok ? (
          result.challenges.length > 0 ? (
            <ChallengeList challenges={result.challenges} />
          ) : (
            <p className="card-raised px-6 py-6 font-sans text-sm text-muted">
              No challenges yet.
            </p>
          )
        ) : (
          <p className="rounded-xl border border-fail/30 bg-fail/10 px-6 py-4 font-sans text-sm text-fail">
            Can&rsquo;t reach the backend at {API_BASE}. Start it, then reload.
          </p>
        )}
      </section>
    </main>
  );
}
