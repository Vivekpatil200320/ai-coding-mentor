export interface ChallengeMetadata {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  type: "bug_fix" | "feature_extension" | "refactor";
  learning_objective: string;
}

export interface StartSessionResponse {
  session_id: string;
  challenge: ChallengeMetadata;
  codebase: string;
}

export interface ExecutionResult {
  passed: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  test_results: string;
  refused: boolean;
  violations: string[];
}

export interface SubmitResponse {
  execution_result: ExecutionResult;
  next_action: "mentor" | "evaluation";
}

export interface DimensionScore {
  score: number;
  comment: string;
}

export interface EvaluationReport {
  scores: Record<string, DimensionScore>;
  what_you_did_well?: string;
  what_you_missed?: string;
  pattern?: string;
  what_a_real_reviewer_would_flag?: string;
  suggested_next_challenge?: string;
  parse_error?: boolean;
  raw_response?: string;
}

export interface HealthResponse {
  status: string;
  sandbox: string;
  langfuse: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
