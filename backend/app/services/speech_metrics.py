import re
from collections import Counter

from app.schemas.evaluation import FillerWordDetail, SpeechMetrics

_TOKEN_COUNT_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_+-]+")

# Ordered longest-first so multi-char fillers match cleanly
_ZH_FILLERS = [
    "就是说",
    "怎么说呢",
    "其实的话",
    "怎么讲",
    "那个",
    "然后",
    "呃",
    "嗯",
    "啊",
]
_EN_FILLER_RE = re.compile(
    r"\b(you\s+know|sort\s+of|kind\s+of|basically|actually|um+|uh+)\b",
    re.IGNORECASE,
)


def compute_speech_metrics(turns: list[dict]) -> SpeechMetrics:
    user_turns = [t for t in turns if t.get("speaker") == "user"]
    if not user_turns:
        return SpeechMetrics(
            total_user_turns=0,
            total_chars_and_words=0,
            total_speaking_duration_sec=0.0,
            chars_per_min=0.0,
            longest_silence_sec=0.0,
            total_filler_count=0,
            filler_breakdown=[],
            detected_fillers_by_turn={},
            estimation_note="无候选人作答轮次",
        )

    total_tokens = 0
    total_duration_ms = 0
    longest_silence_ms = 0
    filler_counter: Counter[str] = Counter()
    detected_by_turn: dict[str, list[str]] = {}
    used_estimated_duration = False

    for turn in user_turns:
        content = str(turn.get("content") or "")
        turn_tokens = len(_TOKEN_COUNT_RE.findall(content))
        total_tokens += turn_tokens

        start_ms = int(turn.get("timestamp_start_ms") or 0)
        end_ms = int(turn.get("timestamp_end_ms") or 0)
        dur_ms = max(0, end_ms - start_ms)
        is_text_paste_burst = (
            turn.get("stt_provider_used") == "text" and dur_ms < 2000 and turn_tokens > 15
        )
        if (dur_ms == 0 or is_text_paste_burst) and turn_tokens > 0:
            # Pure-text mode, pasted burst, or missing mic timestamps: estimate ~180 tokens/min
            dur_ms = max(3000, int((turn_tokens / 180.0) * 60_000))
            used_estimated_duration = True
        total_duration_ms += dur_ms

        pause_before = int(turn.get("pause_before_ms") or 0)
        if pause_before > longest_silence_ms:
            longest_silence_ms = pause_before

        word_ts = turn.get("word_timestamps") or []
        if isinstance(word_ts, list) and len(word_ts) >= 2:
            for prev_w, curr_w in zip(word_ts, word_ts[1:]):
                try:
                    gap = int(curr_w.get("start_ms", 0)) - int(prev_w.get("end_ms", 0))
                    if gap > longest_silence_ms:
                        longest_silence_ms = gap
                except (TypeError, ValueError):
                    continue

        turn_fillers: list[str] = []
        scan_text = content
        for zh_word in _ZH_FILLERS:
            hits = re.findall(re.escape(zh_word), scan_text)
            if hits:
                filler_counter[zh_word] += len(hits)
                turn_fillers.extend([zh_word] * len(hits))
                scan_text = scan_text.replace(zh_word, " ")

        for m in _EN_FILLER_RE.finditer(scan_text):
            norm = re.sub(r"\s+", " ", m.group(1).lower())
            filler_counter[norm] += 1
            turn_fillers.append(norm)

        if turn_fillers:
            detected_by_turn[str(turn.get("turn_index", 0))] = turn_fillers

    duration_sec = round(total_duration_ms / 1000.0, 2)
    duration_min = total_duration_ms / 60_000.0
    chars_per_min = round(total_tokens / duration_min, 1) if duration_min > 0 else 0.0
    longest_silence_sec = round(longest_silence_ms / 1000.0, 2)

    breakdown = [
        FillerWordDetail(word=w, count=c)
        for w, c in filler_counter.most_common()
    ]

    note = (
        "纯文本或无音频时长轮次已按标准语速估算发言耗时；停顿与填充词为纯确定性代码统计。"
        if used_estimated_duration
        else "语速、最长冷场停顿秒数与填充词均由纯确定性 Python 代码精确统计。"
    )

    return SpeechMetrics(
        total_user_turns=len(user_turns),
        total_chars_and_words=total_tokens,
        total_speaking_duration_sec=duration_sec,
        chars_per_min=chars_per_min,
        longest_silence_sec=longest_silence_sec,
        total_filler_count=sum(filler_counter.values()),
        filler_breakdown=breakdown,
        detected_fillers_by_turn=detected_by_turn,
        estimation_note=note,
    )
