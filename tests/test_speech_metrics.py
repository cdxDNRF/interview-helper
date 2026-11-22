import json
from pathlib import Path

from app.services.speech_metrics import compute_speech_metrics

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_long_thinking_pause_and_fillers_deterministic():
    fixture = json.loads(
        (FIXTURES_DIR / "05_long_thinking_pause.json").read_text(encoding="utf-8")
    )
    metrics = compute_speech_metrics(fixture["turns"])

    # gap inside word_timestamps: 18000 - 12900 = 5100ms = 5.1s (also 12400 - 7200 = 5200ms = 5.2s!)
    assert metrics.longest_silence_sec >= 5.1
    assert metrics.total_filler_count >= 5
    filler_words = {item.word: item.count for item in metrics.filler_breakdown}
    assert filler_words.get("然后", 0) >= 1
    assert filler_words.get("那个", 0) >= 1
    assert filler_words.get("就是说", 0) >= 1
    assert filler_words.get("um", 0) >= 1
    assert metrics.chars_per_min > 0


def test_zh_en_mixed_word_rate_and_no_false_positive_like():
    turns = [
        {
            "turn_index": 1,
            "speaker": "user",
            "content": "It is likely that FastAPI and LangGraph handle WebSocket concurrency cleanly.",
            "timestamp_start_ms": 0,
            "timestamp_end_ms": 10000,  # 10s
            "pause_before_ms": 1500,
        }
    ]
    metrics = compute_speech_metrics(turns)
    # "likely" must not trigger English filler "like"
    assert metrics.total_filler_count == 0
    assert metrics.longest_silence_sec == 1.5
    assert metrics.total_chars_and_words == 11
    assert metrics.chars_per_min == 66.0


def test_text_paste_burst_uses_realistic_estimation():
    turns = [
        {
            "turn_index": 1,
            "speaker": "user",
            "content": "我们在 ws_manager 里使用 Redis Pub/Sub 和分布式的锁同步多实例连接状态，并且做了心跳兜底和 CAS 去重保障高并发可靠性。",
            "timestamp_start_ms": 0,
            "timestamp_end_ms": 500,  # 0.5s instant paste
            "pause_before_ms": 800,
            "stt_provider_used": "text",
        }
    ]
    metrics = compute_speech_metrics(turns)
    assert 150.0 <= metrics.chars_per_min <= 210.0
