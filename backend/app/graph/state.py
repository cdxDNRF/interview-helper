from typing import Any, TypedDict

from app.schemas.interview import InterviewStateSnapshot
from app.schemas.prep import PrepPlan


class LiveTurnGraphState(TypedDict, total=False):
    session_id: str
    interviewer_style: str
    resume_markdown: str
    job_description: str
    repo_digest_markdown: str
    prep_plan: PrepPlan
    state_snapshot: InterviewStateSnapshot
    history_messages: list[dict[str, str]]
    latest_user_message: str
    mock_mode: bool

    # Outputs computed inside the graph
    eval_result: dict[str, Any]
    eval_usage: Any
    next_state: InterviewStateSnapshot
    eval_action: str  # upgrade_level | reprobe_same_level | next_topic | end_interview
    static_prefix_sha256: str
    interviewer_messages: list[dict[str, str]]
    interviewer_reply: str
    reply_usage: Any
