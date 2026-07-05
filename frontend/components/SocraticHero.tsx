"use client";

import { useEffect, useState } from "react";

// Pulled from the real mentor prompts (backend/agents/mentor_agent.py) —
// this is what the product actually says, not marketing copy.
const QUESTIONS = [
  "What does this function return when the key doesn't exist?",
  "What happens when user_id isn't a key in the USERS dictionary?",
  "What does the client see when this crashes in production?",
];

const TYPE_SPEED_MS = 45;
const HOLD_MS = 2400;
const ERASE_SPEED_MS = 18;

function useTypewriter(words: string[]): string {
  const [text, setText] = useState(words[0] ?? "");

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    let wordIndex = 0;
    let charIndex = 0;
    let phase: "typing" | "holding" | "erasing" = "typing";
    let timeoutId: ReturnType<typeof setTimeout>;

    const tick = () => {
      const word = words[wordIndex];
      if (phase === "typing") {
        charIndex += 1;
        setText(word.slice(0, charIndex));
        if (charIndex >= word.length) {
          phase = "holding";
          timeoutId = setTimeout(tick, HOLD_MS);
          return;
        }
        timeoutId = setTimeout(tick, TYPE_SPEED_MS);
        return;
      }
      if (phase === "holding") {
        phase = "erasing";
        timeoutId = setTimeout(tick, ERASE_SPEED_MS);
        return;
      }
      charIndex -= 1;
      setText(word.slice(0, charIndex));
      if (charIndex <= 0) {
        wordIndex = (wordIndex + 1) % words.length;
        phase = "typing";
      }
      timeoutId = setTimeout(tick, ERASE_SPEED_MS);
    };

    timeoutId = setTimeout(tick, TYPE_SPEED_MS);
    return () => clearTimeout(timeoutId);
  }, [words]);

  return text;
}

export function SocraticHero() {
  const question = useTypewriter(QUESTIONS);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card-raised p-6 font-mono text-sm leading-relaxed">
        <div className="mb-4 flex items-center gap-2 text-xs text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-fail" />
          <span className="tracking-wide">broken_code / main.py</span>
        </div>
        <pre className="overflow-x-auto text-ink-dim">
          <code>
            <span className="text-muted">{"@app.get(\"/users/{user_id}\")\n"}</span>
            <span className="text-muted">{"def get_user(user_id: int):\n"}</span>
            <span className="-ml-3 block border-l-2 border-fail bg-fail/10 pl-3 text-ink">
              {"    return USERS[user_id]"}
            </span>
          </code>
        </pre>
      </div>

      <div className="card-raised flex flex-col justify-between p-6">
        <div className="mb-4 flex items-center gap-2 font-sans text-xs uppercase tracking-[0.2em] text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          the mentor
        </div>
        <p className="font-display text-xl italic leading-snug text-ink sm:text-2xl">
          {question}
          <span className="ml-0.5 inline-block h-6 w-[2px] translate-y-1 animate-pulse bg-accent align-middle" />
        </p>
        <p className="mt-6 font-sans text-sm text-muted">
          No answer is coming. That&rsquo;s the point.
        </p>
      </div>
    </div>
  );
}
