import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.config import AppRuntimeConfig
from app.llm.client import LLMCallResult, chat_completion, strip_json_fences
from app.llm.mock_adapter import mock_judge_report
from app.llm.prompts import JUDGE_SYSTEM_PROMPT
from app.schemas.evaluation import JudgeLLMOutput
from app.schemas.prep import PrepPlan


@dataclass
class JudgeEvaluationOutcome:
    report: JudgeLLMOutput
    model_used: str
    retry_count: int
    usage_records: list[LLMCallResult]


async def run_post_interview_judge(
    runtime_cfg: AppRuntimeConfig,
    prep_plan: PrepPlan,
    turns: list[dict],
    state_snapshot: dict,
    resume_markdown: str,
    job_description: str,
    *,
    force_mock: bool = False,
) -> JudgeEvaluationOutcome:
    if force_mock or runtime_cfg.mock_mode:
        report = mock_judge_report(prep_plan, turns, state_snapshot)
        return JudgeEvaluationOutcome(
            report=report,
            model_used="mock-judge-v1",
            retry_count=0,
            usage_records=[],
        )

    transcript_lines = []
    for t in turns:
        speaker_label = "面试官" if t.get("speaker") == "ai" else "候选人"
        transcript_lines.append(
            f"[Turn {t.get('turn_index')} | Topic {t.get('topic_index')} | "
            f"L{t.get('ladder_level')} | t={t.get('timestamp_start_ms')}ms | "
            f"pause={t.get('pause_before_ms')}ms] {speaker_label}: {t.get('content')}"
        )

    user_payload = (
        f"### 目标岗位 JD\n{job_description[:3000]}\n\n"
        f"### 简历摘要\n{resume_markdown[:3000]}\n\n"
        f"### 冻结的 Prep 题纲与原子核查清单\n"
        f"{json.dumps(prep_plan.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
        f"### 状态机终态快照\n{json.dumps(state_snapshot, ensure_ascii=False)}\n\n"
        f"### 完整面试逐字稿\n" + "\n".join(transcript_lines)
    )

    messages: list[dict] = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]

    schema = JudgeLLMOutput.model_json_schema()
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "interview_judge_report",
            "strict": False,
            "schema": schema,
        },
    }

    usage_records: list[LLMCallResult] = []
    last_error_text = ""

    # Initial attempt + up to 2 automatic Pydantic validation retries
    for retry_idx in range(3):
        call_res = await chat_completion(
            runtime_cfg.judge_llm,
            runtime_cfg,
            messages,
            response_format=response_format,
        )
        usage_records.append(call_res)
        cleaned = strip_json_fences(call_res.content)
        try:
            parsed = JudgeLLMOutput.model_validate_json(cleaned)
            return JudgeEvaluationOutcome(
                report=parsed,
                model_used=call_res.model,
                retry_count=retry_idx,
                usage_records=usage_records,
            )
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error_text = str(exc)
            if retry_idx < 2:
                messages.append({"role": "assistant", "content": call_res.content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"你刚才输出的 JSON 未通过 Pydantic v2 Schema 校验，错误如下：\n"
                            f"{last_error_text[:800]}\n\n"
                            "请严格修复上述字段与类型问题，并确保先输出 evidence_quotes 和 reasoning，最后输出可空 score，只返回纯 JSON。"
                        ),
                    }
                )

    raise ValueError(f"赛后裁判连续 3 次未通过结构化校验: {last_error_text[:400]}")
