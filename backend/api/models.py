from typing import Literal, Optional

from pydantic import BaseModel, Field

MAX_MESSAGE_LENGTH = 4000
MAX_CODE_LENGTH = 20_000


class StartSessionRequest(BaseModel):
    challenge_id: str
    user_id: str


class ChallengeMetadata(BaseModel):
    id: str
    title: str
    description: str
    difficulty: str
    type: str
    learning_objective: str


class StartSessionResponse(BaseModel):
    session_id: str
    challenge: ChallengeMetadata
    codebase: str


class MessageRequest(BaseModel):
    user_id: str
    message: str = Field(..., max_length=MAX_MESSAGE_LENGTH)


class SubmitRequest(BaseModel):
    user_id: str
    code: str = Field(..., max_length=MAX_CODE_LENGTH)


class ExecutionResult(BaseModel):
    passed: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    test_results: str
    refused: bool = False
    violations: list[str] = []


class SubmitResponse(BaseModel):
    execution_result: ExecutionResult
    next_action: Literal["mentor", "evaluation"]


class EvaluationReport(BaseModel):
    scores: dict = {}
    what_you_did_well: Optional[str] = None
    what_you_missed: Optional[str] = None
    pattern: Optional[str] = None
    what_a_real_reviewer_would_flag: Optional[str] = None
    suggested_next_challenge: Optional[str] = None
    parse_error: Optional[bool] = None
    raw_response: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    sandbox: str
    langfuse: str
