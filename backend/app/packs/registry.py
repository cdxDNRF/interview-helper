import json
from functools import lru_cache
from pathlib import Path

from app.packs.schemas import (
    GeneralPackPreset,
    KnowledgePackPreset,
    PresetsCatalogResponse,
    PresetTopicSeed,
    RoleTrackPreset,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def load_presets_catalog() -> PresetsCatalogResponse:
    roles_raw = json.loads((_DATA_DIR / "roles.json").read_text(encoding="utf-8"))
    fund_raw = json.loads((_DATA_DIR / "fundamentals.json").read_text(encoding="utf-8"))
    gen_raw = json.loads((_DATA_DIR / "general.json").read_text(encoding="utf-8"))
    return PresetsCatalogResponse(
        roles=[RoleTrackPreset.model_validate(r) for r in roles_raw],
        fundamentals=[KnowledgePackPreset.model_validate(f) for f in fund_raw],
        general_packs=[GeneralPackPreset.model_validate(g) for g in gen_raw],
    )


def get_role_track(role_id: str | None) -> RoleTrackPreset | None:
    if not role_id:
        return None
    for role in load_presets_catalog().roles:
        if role.id == role_id:
            return role
    return None


def get_knowledge_packs(pack_ids: list[str] | None) -> list[KnowledgePackPreset]:
    if not pack_ids:
        return []
    by_id = {p.id: p for p in load_presets_catalog().fundamentals}
    return [by_id[pid] for pid in pack_ids if pid in by_id]


def get_general_packs(pack_ids: list[str] | None) -> list[GeneralPackPreset]:
    all_packs = load_presets_catalog().general_packs
    if not pack_ids:
        return list(all_packs)
    by_id = {p.id: p for p in all_packs}
    matched = [by_id[pid] for pid in pack_ids if pid in by_id]
    return matched or list(all_packs)


def collect_seed_topics_and_hotwords(
    interview_type: str,
    role_track_id: str | None,
    knowledge_pack_ids: list[str] | None,
) -> tuple[str, list[PresetTopicSeed], list[str]]:
    """
    根据面试模式与选择的预设包，生成：
    (默认合成标题/JD说明, 种子考点列表, 领域热词列表)
    """
    topics: list[PresetTopicSeed] = []
    hotwords: list[str] = []
    desc_parts: list[str] = []

    if interview_type == "cs_role_track":
        role = get_role_track(role_track_id) or load_presets_catalog().roles[0]
        desc_parts.append(f"【职业专项：{role.name}】{role.default_jd}")
        topics.extend(role.core_topics)
        hotwords.extend(role.hotwords)

    elif interview_type == "bagu_fundamentals":
        packs = get_knowledge_packs(knowledge_pack_ids)
        if not packs:
            packs = load_presets_catalog().fundamentals[:3]
        names = " + ".join(p.name for p in packs)
        desc_parts.append(
            f"【重要八股深度突击：{names}】"
            + "；".join(f"{p.name}({p.summary})" for p in packs)
        )
        # Round-robin pick up to 5 topics across chosen packs for balanced coverage
        max_len = max(len(p.core_topics) for p in packs)
        for i in range(max_len):
            for p in packs:
                if i < len(p.core_topics):
                    topics.append(p.core_topics[i])
                if len(topics) >= 5:
                    break
            if len(topics) >= 5:
                break
        for p in packs:
            hotwords.extend(p.hotwords)

    elif interview_type == "general_behavioral":
        packs = get_general_packs(knowledge_pack_ids)
        names = "、".join(p.name for p in packs)
        desc_parts.append(
            f"【通用综合与 STAR 行为面试：{names}】考察个人真实项目担当、跨团队沟通分歧解决、高压事故复盘及反问洞察力。"
        )
        for p in packs:
            topics.extend(p.core_topics)
        topics = topics[:5]
        hotwords.extend(["STAR", "Ownership", "Postmortem", "ROI", "KPI"])

    dedup_hotwords: list[str] = []
    for hw in hotwords:
        if hw not in dedup_hotwords:
            dedup_hotwords.append(hw)

    return "\n".join(desc_parts), topics, dedup_hotwords[:25]
