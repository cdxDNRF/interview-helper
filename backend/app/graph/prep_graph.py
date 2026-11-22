import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.config import AppRuntimeConfig
from app.llm.client import LLMCallResult, chat_completion, strip_json_fences
from app.llm.mock_adapter import mock_prep_plan
from app.llm.prompts import PREP_SYSTEM_PROMPT
from app.packs.registry import collect_seed_topics_and_hotwords
from app.schemas.prep import PrepPlan


@dataclass
class PrepOutcome:
    plan: PrepPlan
    usage_records: list[LLMCallResult]


async def run_prep_pipeline(
    runtime_cfg: AppRuntimeConfig,
    resume_markdown: str,
    job_description: str,
    repo_digest_markdown: str,
    interviewer_style: str,
    interview_type: str = "project_deep_dive",
    role_track_id: str | None = None,
    knowledge_pack_ids: list[str] | None = None,
    *,
    force_mock: bool = False,
) -> PrepOutcome:
    if force_mock or runtime_cfg.mock_mode:
        return PrepOutcome(
            plan=mock_prep_plan(
                resume_markdown,
                job_description,
                repo_digest_markdown,
                interviewer_style,
                interview_type=interview_type,
                role_track_id=role_track_id,
                knowledge_pack_ids=knowledge_pack_ids,
            ),
            usage_records=[],
        )

    preset_guide = ""
    if interview_type != "project_deep_dive":
        desc, seeds, hotwords = collect_seed_topics_and_hotwords(
            interview_type, role_track_id, knowledge_pack_ids
        )
        seed_preview = json.dumps(
            [s.model_dump(mode="json") for s in seeds],
            ensure_ascii=False,
        )
        preset_guide = (
            f"\n### 选定专项考纲与参考种子题库（请围绕此范围出题并适配候选人背景）\n"
            f"{desc}\n推荐热词：{', '.join(hotwords)}\n种子考点参考：{seed_preview[:3500]}\n"
        )

    user_prompt = (
        f"面试模式：{interview_type} | 面试官风格：{interviewer_style}\n\n"
        f"### 候选人简历\n{resume_markdown.strip()}\n\n"
        f"### 目标岗位 JD / 考核说明\n{job_description.strip()}\n"
        f"{preset_guide}\n"
        f"### GitHub 仓库 Repomix AST 摘要\n"
        f"{repo_digest_markdown.strip() or '(未提供 GitHub 仓库)'}"
    )

    messages: list[dict] = [
        {"role": "system", "content": PREP_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "interview_prep_plan",
            "strict": False,
            "schema": PrepPlan.model_json_schema(),
        },
    }

    usage_records: list[LLMCallResult] = []
    last_err = ""
    for attempt in range(3):
        call_res = await chat_completion(
            runtime_cfg.prep_llm,
            runtime_cfg,
            messages,
            response_format=response_format,
        )
        usage_records.append(call_res)
        cleaned = strip_json_fences(call_res.content)
        try:
            plan = PrepPlan.model_validate_json(cleaned)
            return PrepOutcome(plan=plan, usage_records=usage_records)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_err = str(exc)
            if attempt < 2:
                messages.append({"role": "assistant", "content": call_res.content})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Prep JSON 校验失败：{last_err[:600]}。请仅输出合法 JSON。",
                    }
                )

    raise ValueError(f"Prep 预规划输出解析失败: {last_err[:300]}")
