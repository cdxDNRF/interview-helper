import json
from pathlib import Path

import pytest

from app.config import AppRuntimeConfig
from app.llm.client import LLMCallResult
from app.llm.mock_adapter import mock_evaluate_turn
from app.schemas.evaluation import JudgeLLMOutput
from app.schemas.prep import PrepPlan
from app.services.judge_service import run_post_interview_judge
from app.services.speech_metrics import compute_speech_metrics

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _run_fixture_through_mock(filename: str):
    data = json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))
    prep = PrepPlan.model_validate(data["prep_plan"])
    turns = data["turns"]
    enriched_turns = []
    for t in turns:
        t_copy = dict(t)
        if t_copy["speaker"] == "user":
            t_idx = min(int(t_copy.get("topic_index", 0)), len(prep.topics) - 1)
            t_copy["turn_eval"] = mock_evaluate_turn(
                prep.topics[t_idx].title, int(t_copy.get("ladder_level", 1)), t_copy["content"]
            )
        enriched_turns.append(t_copy)
    return data, prep, enriched_turns


@pytest.mark.asyncio
async def test_five_regression_fixtures_scoring_and_null_honesty():
    cfg = AppRuntimeConfig(mock_mode=True)
    scores: dict[str, float | None] = {}

    # 1. High score deep dive
    d1, p1, t1 = _run_fixture_through_mock("01_high_score_deep_dive.json")
    r1 = await run_post_interview_judge(
        cfg, p1, t1, {"topic_records": []}, "resume", "jd", force_mock=True
    )
    scores["high"] = r1.report.overall_score
    assert r1.report.overall_score is not None and r1.report.overall_score >= 70
    assert len(r1.report.evidence_quotes) >= 2

    # 2. Rote memorization
    d2, p2, t2 = _run_fixture_through_mock("02_rote_memorization.json")
    r2 = await run_post_interview_judge(
        cfg, p2, t2, {"topic_records": []}, "resume", "jd", force_mock=True
    )
    scores["rote"] = r2.report.overall_score
    assert r2.report.overall_score is not None
    assert scores["high"] - scores["rote"] >= 20

    # 3. Off-topic evasion -> untested dimensions must honestly be None (N/A)
    d3, p3, t3 = _run_fixture_through_mock("03_off_topic_evasion.json")
    r3 = await run_post_interview_judge(
        cfg, p3, t3, {"topic_records": []}, "resume", "jd", force_mock=True
    )
    scores["off_topic"] = r3.report.overall_score
    assert r3.report.dimensions.engineering_tradeoffs.score is None
    assert r3.report.dimensions.code_and_testing.score is None
    assert scores["rote"] > (scores["off_topic"] or 0)

    # 4. Zh-En code mixed
    d4, p4, t4 = _run_fixture_through_mock("04_zh_en_code_mixed.json")
    m4 = compute_speech_metrics(t4)
    r4 = await run_post_interview_judge(
        cfg, p4, t4, {"topic_records": []}, "resume", "jd", force_mock=True
    )
    assert m4.chars_per_min > 0
    assert r4.report.overall_score is not None and r4.report.overall_score >= 65

    # 5. Long thinking pause
    d5, p5, t5 = _run_fixture_through_mock("05_long_thinking_pause.json")
    m5 = compute_speech_metrics(t5)
    r5 = await run_post_interview_judge(
        cfg, p5, t5, {"topic_records": []}, "resume", "jd", force_mock=True
    )
    assert m5.longest_silence_sec >= 4.8
    assert m5.total_filler_count >= 4
    assert r5.report.evidence_quotes


@pytest.mark.asyncio
async def test_judge_pydantic_validation_auto_retries_up_to_two_times(monkeypatch):
    _, prep, turns = _run_fixture_through_mock("04_zh_en_code_mixed.json")
    cfg = AppRuntimeConfig(mock_mode=False)

    valid_payload = JudgeLLMOutput.model_validate(
        {
            "evidence_quotes": [
                {
                    "quote": "把 system persona 和 sorted tools JSON 锁在 prefix 头部",
                    "turn_index": 1,
                    "timestamp_ms": 3000,
                    "relevance": "掌握 Prompt Caching 核心工程规则",
                }
            ],
            "reasoning": "先引用原话，再给出各维度评分；代码自测未展开故标记 null。",
            "dimensions": {
                "technical_depth": {
                    "evidence_quotes": [
                        {
                            "quote": "命中率从 10% 提到 88%",
                            "turn_index": 1,
                            "timestamp_ms": 3000,
                            "relevance": "有量化指标",
                        }
                    ],
                    "reasoning": "机制清晰",
                    "score": 84,
                },
                "engineering_tradeoffs": {
                    "evidence_quotes": [],
                    "reasoning": "说明了延迟收益",
                    "score": 78,
                },
                "problem_structuring": {
                    "evidence_quotes": [],
                    "reasoning": "表述完整",
                    "score": 80,
                },
                "code_and_testing": {
                    "evidence_quotes": [],
                    "reasoning": "未考到代码与单测细节",
                    "score": None,
                },
            },
            "checklist_results": [],
            "transcript_annotations": [],
            "summary_markdown": "整体扎实。",
            "overall_score": 80.7,
        }
    ).model_dump_json()

    attempts = {"n": 0}

    async def fake_chat_completion(*_args, **_kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            content = "{not valid json"
        elif attempts["n"] == 2:
            content = '{"evidence_quotes": [], "reasoning": "missing dimensions"}'
        else:
            content = valid_payload
        return LLMCallResult(
            content=content,
            model="test-judge",
            prompt_tokens=100,
            cached_tokens=0,
            completion_tokens=50,
            latency_ms=10,
            estimated_cost_cny=0.001,
            raw_usage={},
        )

    monkeypatch.setattr("app.services.judge_service.chat_completion", fake_chat_completion)
    outcome = await run_post_interview_judge(
        cfg, prep, turns, {"topic_records": []}, "resume", "jd", force_mock=False
    )

    assert attempts["n"] == 3
    assert outcome.retry_count == 2
    assert outcome.report.overall_score == 80.7
    assert outcome.report.dimensions.code_and_testing.score is None
