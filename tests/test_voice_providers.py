import pytest

from app.voice.tts_edge import EdgeTTSProvider


@pytest.mark.asyncio
async def test_edge_tts_zero_byte_triggers_browser_fallback(monkeypatch):
    provider = EdgeTTSProvider()

    async def fake_collect(_self, _text: str, _voice: str, _rate: str) -> bytes:
        return b""

    monkeypatch.setattr(EdgeTTSProvider, "_collect_audio_bytes", fake_collect)
    res = await provider.synthesize("你好，请讲一下你的并发模型。")

    assert res.fallback_to_browser is True
    assert res.audio_bytes == b""
    assert res.provider_used == "web_speech_fallback"
    assert "0 字节" in res.fallback_reason


@pytest.mark.asyncio
async def test_edge_tts_403_exception_triggers_browser_fallback(monkeypatch):
    provider = EdgeTTSProvider()

    async def fake_collect(_self, _text: str, _voice: str, _rate: str) -> bytes:
        raise RuntimeError("403 Forbidden Sec-MS-GEC")

    monkeypatch.setattr(EdgeTTSProvider, "_collect_audio_bytes", fake_collect)
    res = await provider.synthesize("请问如何避免缓存击穿？")

    assert res.fallback_to_browser is True
    assert res.provider_used == "web_speech_fallback"
    assert "403" in res.fallback_reason


@pytest.mark.asyncio
async def test_edge_tts_valid_audio_passes(monkeypatch):
    provider = EdgeTTSProvider()

    async def fake_collect(_self, _text: str, _voice: str, _rate: str) -> bytes:
        return b"ID3\x04\x00\x00\x00\x00\x00\x00FAKE_MP3_PAYLOAD"

    monkeypatch.setattr(EdgeTTSProvider, "_collect_audio_bytes", fake_collect)
    res = await provider.synthesize("正常音频合成测试。")

    assert res.fallback_to_browser is False
    assert res.content_type == "audio/mpeg"
    assert len(res.audio_bytes) > 0
