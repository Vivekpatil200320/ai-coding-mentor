from typing import Literal, TypedDict


class MentorState(TypedDict):
    session_id: str
    challenge_id: str
    user_code: str
    task_type: Literal["bug_fix", "feature_extension", "refactor"]
    codebase_analysis: str  # output of analysis agent
    conversation_history: list[dict]  # mentor chat history
    hint_level: int  # 0=no hint, 1=gentle, 2=direct, 3=answer
    execution_result: dict  # sandbox output
    evaluation_report: dict  # final rubric scores
    current_agent: str  # which agent is active
    is_complete: bool
