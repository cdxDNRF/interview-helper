import re
from typing import AsyncGenerator

from app.schemas.evaluation import (
    ChecklistOutcome,
    DimensionEvaluation,
    EvidenceQuote,
    FourDimensionsSchema,
    JudgeLLMOutput,
    TranscriptAnnotation,
)
from app.schemas.prep import GapPoint, PrepPlan, PrepTopic


_FILE_PATH_RE = re.compile(
    r"(?:^|\s|`|#)([A-Za-z0-9_./-]+\.(?:py|ts|tsx|js|go|rs|java|sql|yaml|yml))\b"
)
_HOTWORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_.-]{2,24}\b")

_TECHNICAL_SIGNALS = [
    "qps", "tps", "p99", "latency", "延迟", "吞吐", "并发", "锁", "cas",
    "幂等", "超时", "熔断", "降级", "背压", "队列", "redis", "sqlite", "wal",
    "索引", "事务", "mvcc", "分片", "缓存", "穿透", "雪崩", "一致性",
    "源码", "函数", "异步", "协程", "连接池", "心跳", "重连", "测试", "压测",
    "fallback", "retry", "circuit", "deadlock", "mutex", "webrtc", "sse",
]

_EVASION_SIGNALS = [
    "不知道", "不清楚", "忘了", "没用过", "记不得", "答不上", "跳过",
    "换一题", "天气", "吃饭", "无关", "随便", "没做过", "不太懂",
]

_ROTE_SIGNALS = [
    "八股", "背一下", "概念就是", "一般来说就是", "大概就是这样", "网上说",
    "书上写", "优点是", "缺点是", "具体没看过", "只是调包", "封装好的",
]


def _extract_repo_files(repo_digest: str) -> list[str]:
    found: list[str] = []
    for match in _FILE_PATH_RE.findall(repo_digest or ""):
        if match not in found and not match.endswith(".json"):
            found.append(match)
        if len(found) >= 5:
            break
    return found


def mock_prep_plan(
    resume_markdown: str,
    job_description: str,
    repo_digest_markdown: str,
    interviewer_style: str,
) -> PrepPlan:
    repo_files = _extract_repo_files(repo_digest_markdown)
    f0 = repo_files[0] if len(repo_files) > 0 else "src/service/ws_manager.py"
    f1 = repo_files[1] if len(repo_files) > 1 else "src/db/session_store.py"

    raw_terms = _HOTWORD_RE.findall(f"{resume_markdown}\n{job_description}\n{repo_digest_markdown}")
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "https", "github", "com"}
    hotwords: list[str] = []
    for term in raw_terms:
        if term.lower() not in stopwords and term not in hotwords:
            hotwords.append(term)
        if len(hotwords) >= 16:
            break
    for default_hw in ["FastAPI", "LangGraph", "SQLite", "WAL", "WebRTC", "Redis", "PromptCaching"]:
        if default_hw not in hotwords:
            hotwords.append(default_hw)

    tone_prefix = "直接切入硬核细节：" if interviewer_style == "pressure" else "我们先从你的核心项目聊起："

    topics = [
        PrepTopic(
            topic_id="topic_1",
            title="核心模块源码架构与并发状态同步",
            source_entrypoint=f0,
            target_dimensions=["technical_depth", "code_and_testing"],
            atomic_checklist=[
                "是否阐明该模块核心职责与状态存储方式",
                "是否指出单机内存状态在多实例部署时的同步缺陷",
                "是否给出具体一致性兜底或锁/消息队列方案",
            ],
            l1_seed_question=f"{tone_prefix}看到你仓库里的 `{f0}`，先讲讲这个模块的核心设计思路，以及如果多进程部署它的状态该如何同步？",
        ),
        PrepTopic(
            topic_id="topic_2",
            title="高并发链路下的持久化、缓存与故障降级",
            source_entrypoint=f1,
            target_dimensions=["engineering_tradeoffs", "technical_depth"],
            atomic_checklist=[
                "是否对比不同存储/缓存方案的读写延迟与一致性权衡",
                "是否给出具体的超时、重试退避或熔断降级阈值",
                "是否说明异常或宕机重启后的数据恢复路径",
            ],
            l1_seed_question=f"顺着 `{f1}` 往下问：在高峰请求或上游依赖超时抖动时，你是怎么设计持久化一致性与降级兜底的？",
        ),
        PrepTopic(
            topic_id="topic_3",
            title="端到端延迟优化与异常排查复盘",
            source_entrypoint="简历核心项目经验",
            target_dimensions=["problem_structuring", "engineering_tradeoffs"],
            atomic_checklist=[
                "是否能按监控指标（P95/P99/缓存命中率）定位瓶颈",
                "是否用量化数据证明优化前后收益",
                "是否体现排查思路的结构化拆解能力",
            ],
            l1_seed_question="结合你简历上的主力项目，讲一次你解决过的最棘手的性能抖动或线上故障，当时指标怎么变化、怎么一步步排查的？",
        ),
        PrepTopic(
            topic_id="topic_4",
            title="测试覆盖、边界防护与工程可观测性",
            source_entrypoint="自动化测试与监控链路",
            target_dimensions=["code_and_testing", "problem_structuring"],
            atomic_checklist=[
                "是否说明核心状态机或关键路径的回归测试策略",
                "是否覆盖极端空输入、并发竞态与外部服务返回异常",
            ],
            l1_seed_question="最后一个主题：对于这种带外部模型或复杂状态的系统，你怎么设计自动化测试和线上可观测性来防止静默故障？",
        ),
    ]

    gaps = [
        GapPoint(
            area="高并发与多实例一致性证明",
            observation="简历与代码摘要偏重单机功能闭环，缺少跨进程锁、幂等校验与压力测试量化数据。",
            risk_level="high",
        ),
        GapPoint(
            area="极端故障降级与边界覆盖",
            observation="对上游超时、空载荷或网络抖动的熔断恢复细节在材料中未体现，需要 L3/L4 深挖核验。",
            risk_level="medium",
        ),
        GapPoint(
            area="岗位匹配度与架构权衡深度",
            observation=f"JD 强调线上稳定性与成本控制，需考察对 `{f0}` 选型背后的取舍而非单纯背诵概念。",
            risk_level="medium",
        ),
    ]

    return PrepPlan(
        candidate_summary="（离线 Mock 预规划）已结合简历、JD 与仓库文件骨架生成 4 个递进考点与核查清单。",
        resume_jd_gaps=gaps,
        topics=topics,
        hotwords=hotwords[:20],
    )


def mock_evaluate_turn(topic_title: str, ladder_level: int, user_text: str) -> dict:
    lower = user_text.lower()
    char_len = len(user_text.strip())

    evasion_hits = sum(1 for kw in _EVASION_SIGNALS if kw in lower)
    rote_hits = sum(1 for kw in _ROTE_SIGNALS if kw in lower)
    tech_hits = sum(1 for kw in _TECHNICAL_SIGNALS if kw in lower)
    has_numbers = bool(re.search(r"\d+(?:\.\d+)?\s*(?:ms|s|秒|%|qps|tps|mb|kb|万|千|倍|次)", lower))

    if evasion_hits >= 1 or char_len < 18:
        return {
            "score": 0.25,
            "is_rote_memorization": False,
            "is_off_topic": True,
            "covered_points": [],
            "missing_points": [f"未给出关于「{topic_title}」在 L{ladder_level} 层级的有效技术回答"],
            "brief_diagnosis": "候选人回避或答非所问/过短，未切中当前问题核心。",
        }

    if rote_hits >= 1 and tech_hits <= 2 and not has_numbers:
        return {
            "score": 0.48,
            "is_rote_memorization": True,
            "is_off_topic": False,
            "covered_points": ["提及了基础概念名称"],
            "missing_points": ["缺少具体项目实战细节、代码实现路径或量化权衡"],
            "brief_diagnosis": "回答偏背八股/泛泛而谈，缺少结合自身代码与真实边界的深度论证。",
        }

    base = 0.42 + min(0.32, tech_hits * 0.08) + (0.12 if has_numbers else 0.0) + (0.10 if char_len >= 90 else 0.0)
    if ladder_level >= 3 and tech_hits < 3 and not has_numbers:
        base = min(base, 0.58)
    score = round(min(0.95, max(0.30, base)), 2)

    return {
        "score": score,
        "is_rote_memorization": rote_hits > 0 and score < 0.65,
        "is_off_topic": False,
        "covered_points": [f"覆盖了 L{ladder_level} 阶段 {tech_hits} 个关键工程要素"] if tech_hits else [],
        "missing_points": [] if score >= 0.65 else ["需补充底层实现细节或异常边界处理"],
        "brief_diagnosis": "达到当前深度门槛，可继续加压。" if score >= 0.65 else "深度略浅，建议同层反问核实。",
    }


def mock_interviewer_reply(
    interviewer_style: str,
    action: str,
    topic_title: str,
    source_entrypoint: str,
    next_ladder_level: int,
    next_seed_question: str,
    eval_result: dict,
) -> str:
    pressure = interviewer_style == "pressure"
    missing = (eval_result.get("missing_points") or ["具体落地边界"])[0]

    if action == "end_interview":
        if pressure:
            return "好，今天的技术深挖先到这里。你把几个关键取舍和边界再复盘一下，稍后看复盘台的具体批注和重构建议。"
        return "好的，今天预设的几个核心考点我们已经过完了，辛苦了！接下来系统会基于逐字稿生成证据锚定复盘报告，请稍候。"

    if action == "next_topic":
        prefix = (
            "这一块先停一下，追问两轮都没给到底层闭环，我记一个待补短板。切下一题："
            if (pressure and eval_result.get("score", 0) < 0.65)
            else "这一题的链路基本过清楚了，我们切到下一个考点："
        )
        return f"{prefix}{next_seed_question}"

    if action == "reprobe_same_level":
        if eval_result.get("is_off_topic"):
            return (
                f"你刚刚有点跑偏了，我没有问泛泛的背景，而是聚焦在 `{source_entrypoint}` 的 `{topic_title}`。直接回答：{missing} 是怎么落地的？"
                if pressure
                else f"我们拉回当前考点「{topic_title}」本身：能不能先不展开外围内容，具体说说你在这块是怎么解决「{missing}」的？"
            )
        return (
            f"听起来还是偏概念背诵，没看到你在 `{source_entrypoint}` 里的真刀真枪。给我具体代码级做法，而不是教科书定义。"
            if pressure
            else f"概念方向是对的，不过我还想听听你自己在项目里的真实做法，尤其是「{missing}」这块，能举个具体例子吗？"
        )

    # upgrade_level
    level_prompts = {
        2: (
            f"原理说得通，现在看实战：在 `{source_entrypoint}` 里，你当时具体怎么选型落地的？如果重来一次会改哪里？"
            if not pressure
            else f"原理我默认你清楚了，别停在纸面上。结合 `{source_entrypoint}`，你线上真实吞吐、延迟和折中代价是什么？"
        ),
        3: (
            f"再往底层代码走一层：如果让你手写/重构 `{topic_title}` 的关键路径，数据结构、锁粒度或状态流转具体怎么控制？"
            if not pressure
            else f"继续往下抠实现细节：并发竞争、内存状态和回调时序怎么防脏写和死锁？直接讲函数边界。"
        ),
        4: (
            f"最后看一档极端边界：如果流量突发 10 倍、或下游依赖返回 0 字节/超时雪崩，你这套设计哪里会先崩，怎么保命？"
            if not pressure
            else f"加压到 L4 故障边界：假设网络分区加下游连续 429/超时，你的重试风暴把系统打挂了怎么排查止血？"
        ),
    }
    return level_prompts.get(next_ladder_level, next_seed_question)


async def mock_stream_text(text: str) -> AsyncGenerator[str, None]:
    chunk_size = 6
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def mock_judge_report(
    prep_plan: PrepPlan,
    turns: list[dict],
    state_snapshot: dict,
) -> JudgeLLMOutput:
    user_turns = [t for t in turns if t.get("speaker") == "user"]
    quotes: list[EvidenceQuote] = []
    annotations: list[TranscriptAnnotation] = []

    topic_map = {idx: t.title for idx, t in enumerate(prep_plan.topics)}

    scores_seen: list[float] = []
    tested_dims: set[str] = set()
    for t in user_turns:
        ev = t.get("turn_eval") or {}
        score_val = float(ev.get("score", 0.5))
        scores_seen.append(score_val)
        t_idx = int(t.get("topic_index", 0))
        if t_idx < len(prep_plan.topics):
            tested_dims.update(prep_plan.topics[t_idx].target_dimensions)

        snippet = str(t.get("content", "")).strip()
        if len(snippet) > 90:
            snippet = snippet[:90] + "..."
        turn_idx = int(t.get("turn_index", 0))
        ts_ms = int(t.get("timestamp_start_ms", 0))

        quotes.append(
            EvidenceQuote(
                quote=snippet,
                turn_index=turn_idx,
                timestamp_ms=ts_ms,
                relevance=ev.get("brief_diagnosis", "候选人关键技术表达"),
            )
        )

        if score_val < 0.72 or len(annotations) < 3:
            topic_title = topic_map.get(t_idx, "核心技术考点")
            critique = (
                f"本轮处于 L{t.get('ladder_level', 1)} 追问（得分 {score_val:.2f}）："
                + (
                    "存在明显偏题或回避细节。"
                    if ev.get("is_off_topic")
                    else "偏概念复述，缺少具体量化指标、代码路径与边界兜底说明。"
                    if score_val < 0.65
                    else "切中要点并具备工程思路，可进一步补充极端故障下的量化监控与降级参数。"
                )
            )
            annotations.append(
                TranscriptAnnotation(
                    turn_index=turn_idx,
                    topic_title=topic_title,
                    ladder_level=int(t.get("ladder_level", 1)),
                    critique=critique,
                    original_utterance=str(t.get("content", "")),
                    ideal_rewrite=(
                        f"在「{topic_title}」中，我会先明确现状边界（例如单机内存字典无法跨 worker 同步），"
                        "随后给出具体选型权衡（引入带 TTL 的 Redis Pub/Sub + 本地版本号校验，P99 控制在 15ms 内），"
                        "并补充异常降级策略（Redis 不可用时切换只读降级并触发熔断告警，通过单元测试覆盖断连重连竞态）。"
                    ),
                )
            )

    if not user_turns:
        empty_dim = DimensionEvaluation(
            evidence_quotes=[],
            reasoning="本场对话无候选人有效作答记录，证据不足，按规则标记为 N/A (null)。",
            score=None,
        )
        return JudgeLLMOutput(
            evidence_quotes=[],
            reasoning="无候选人作答逐字稿，无法进行有效技术评估。",
            dimensions=FourDimensionsSchema(
                technical_depth=empty_dim,
                engineering_tradeoffs=empty_dim,
                problem_structuring=empty_dim,
                code_and_testing=empty_dim,
            ),
            checklist_results=[
                ChecklistOutcome(
                    topic_title=topic.title,
                    criterion=c,
                    status="not_tested",
                    evidence_quote="",
                    turn_index=None,
                )
                for topic in prep_plan.topics
                for c in topic.atomic_checklist
            ],
            transcript_annotations=[],
            summary_markdown="本场尚未记录有效作答，建议至少完成一轮问答后再生成复盘报告。",
            overall_score=None,
        )

    avg_01 = sum(scores_seen) / len(scores_seen)
    max_level = max([int(t.get("ladder_level", 1)) for t in user_turns] + [1])

    def build_dim(dim_key: str, label: str, offset: int) -> DimensionEvaluation:
        if dim_key not in tested_dims and len(user_turns) < 3:
            return DimensionEvaluation(
                evidence_quotes=[],
                reasoning=f"本场对话结束较早，未充分考察「{label}」维度，依据可观测性铁律标为 N/A (null)。",
                score=None,
            )
        dim_quotes = quotes[:2]
        raw_score = int(round(min(96, max(22, avg_01 * 92 + (max_level - 1) * 4 + offset))))
        return DimensionEvaluation(
            evidence_quotes=dim_quotes,
            reasoning=f"基于 {len(user_turns)} 轮作答原话（最高触及 L{max_level} 阶梯），「{label}」表现出均分 {avg_01:.2f} 对应的实操与表达水准。",
            score=raw_score,
        )

    dim_td = build_dim("technical_depth", "技术原理深度", 2)
    dim_et = build_dim("engineering_tradeoffs", "工程权衡与边界意识", 0)
    dim_ps = build_dim("problem_structuring", "问题拆解与表达结构", 1)
    dim_ct = build_dim("code_and_testing", "代码实现与自测意识", -2)

    valid_scores = [
        d.score for d in (dim_td, dim_et, dim_ps, dim_ct) if d.score is not None
    ]
    overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None

    topic_records = {
        r.get("topic_id"): r for r in (state_snapshot.get("topic_records") or [])
    }
    checklist_outcomes: list[ChecklistOutcome] = []
    for idx, topic in enumerate(prep_plan.topics):
        t_turns = [t for t in user_turns if int(t.get("topic_index", -1)) == idx]
        rec = topic_records.get(topic.topic_id, {})
        for c_idx, crit in enumerate(topic.atomic_checklist):
            if not t_turns:
                checklist_outcomes.append(
                    ChecklistOutcome(
                        topic_title=topic.title,
                        criterion=crit,
                        status="not_tested",
                        evidence_quote="",
                        turn_index=None,
                    )
                )
            else:
                best_turn = max(t_turns, key=lambda x: float((x.get("turn_eval") or {}).get("score", 0)))
                best_score = float((best_turn.get("turn_eval") or {}).get("score", 0))
                passed = best_score >= 0.65 and (c_idx == 0 or rec.get("max_level_reached", 1) >= c_idx + 1)
                checklist_outcomes.append(
                    ChecklistOutcome(
                        topic_title=topic.title,
                        criterion=crit,
                        status="passed" if passed else "missed",
                        evidence_quote=str(best_turn.get("content", ""))[:80],
                        turn_index=int(best_turn.get("turn_index", 0)),
                    )
                )

    return JudgeLLMOutput(
        evidence_quotes=quotes[:5],
        reasoning=(
            f"（离线 Mock 证据锚定裁判）共核验 {len(user_turns)} 轮候选人发言，"
            f"最高追问达到 L{max_level}，加权回答质量分均值 {avg_01:.2f}。"
            "未充分触发的维度已诚实标为 null，不生成虚高分数。"
        ),
        dimensions=FourDimensionsSchema(
            technical_depth=dim_td,
            engineering_tradeoffs=dim_et,
            problem_structuring=dim_ps,
            code_and_testing=dim_ct,
        ),
        checklist_results=checklist_outcomes,
        transcript_annotations=annotations,
        summary_markdown=(
            f"### 离线 Mock 复盘诊断\n"
            f"- **表现亮点**：共完成 {len(user_turns)} 轮技术作答，最高推进至 L{max_level} 追问阶梯。\n"
            f"- **核心短板**：建议重点对照中栏 Diff 重构版，补齐关键模块的并发锁/熔断阈值与压测指标。\n"
        ),
        overall_score=overall,
    )
