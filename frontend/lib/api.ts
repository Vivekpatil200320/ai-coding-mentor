import type {
  ChallengeMetadata,
  EvaluationReport,
  HealthResponse,
  StartSessionResponse,
  SubmitResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ReportNotReadyError extends Error {
  constructor() {
    super("Report not available yet — the session hasn't passed evaluation.");
    this.name = "ReportNotReadyError";
  }
}

export function getOrCreateUserId(): string {
  const key = "ai-coding-mentor:user-id";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const id = crypto.randomUUID();
  window.localStorage.setItem(key, id);
  return id;
}

export async function getChallenges(): Promise<ChallengeMetadata[]> {
  const res = await fetch(`${API_BASE}/challenges/`);
  if (!res.ok) throw new Error("Failed to load challenges.");
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Failed to reach the backend.");
  return res.json();
}

export async function startSession(
  challengeId: string,
  userId: string
): Promise<StartSessionResponse> {
  const res = await fetch(`${API_BASE}/sessions/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ challenge_id: challengeId, user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to start the session.");
  return res.json();
}

export async function submitCode(
  sessionId: string,
  userId: string,
  code: string
): Promise<SubmitResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, code }),
  });
  if (!res.ok) throw new Error("Failed to run your code.");
  return res.json();
}

export async function getReport(
  sessionId: string,
  userId: string
): Promise<EvaluationReport> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/report?user_id=${encodeURIComponent(userId)}`
  );
  if (res.status === 409) throw new ReportNotReadyError();
  if (!res.ok) throw new Error("Failed to load the report.");
  return res.json();
}

/**
 * The backend streams the mentor's reply as SSE (`data: {"token": "..."}`,
 * terminated by `data: [DONE]`). EventSource can't send a POST body, so
 * this reads the fetch response stream directly and parses the same
 * frame format the backend emits in api/routes.py.
 */
export async function* streamMessage(
  sessionId: string,
  userId: string,
  message: string
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message }),
  });
  if (!res.ok || !res.body) throw new Error("Failed to reach the mentor.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      if (!frame.startsWith("data: ")) continue;
      const payload = frame.slice("data: ".length);
      if (payload === "[DONE]") return;

      try {
        const parsed = JSON.parse(payload) as { token?: string; error?: string };
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.token) yield parsed.token;
      } catch {
        // Malformed frame — skip rather than break the whole stream.
      }
    }
  }
}
