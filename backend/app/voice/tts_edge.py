import asyncio
import edge_tts

from app.voice.interfaces import BaseTTSProvider, TTSResult


class EdgeTTSProvider(BaseTTSProvider):
    """
    edge-tts (>= 7.3.1) 默认实现：
    强制执行 0 字节音频检测与异常捕获；遇到 Sec-MS-GEC 403 / 超时 / 空音频时
    自动降级并通知前端启用浏览器 Web Speech API (speechSynthesis)。
    """

    name = "edge_tts"

    def __init__(self, default_voice: str = "zh-CN-XiaoxiaoNeural", default_rate: str = "+0%"):
        self.default_voice = default_voice
        self.default_rate = default_rate

    async def _collect_audio_bytes(self, text: str, voice: str, rate: str) -> bytes:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        return b"".join(chunks)

    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        clean = (text or "").strip()
        if not clean:
            return TTSResult(
                audio_bytes=b"",
                content_type="",
                provider_used="none",
                fallback_to_browser=False,
                fallback_reason="empty_text",
            )

        target_voice = voice or self.default_voice
        target_rate = rate or self.default_rate
        try:
            audio_bytes = await asyncio.wait_for(
                self._collect_audio_bytes(clean, target_voice, target_rate),
                timeout=12.0,
            )
        except Exception as exc:
            return TTSResult(
                audio_bytes=b"",
                content_type="",
                provider_used="web_speech_fallback",
                fallback_to_browser=True,
                fallback_reason=f"edge-tts 异常降级: {type(exc).__name__}: {str(exc)[:160]}",
            )

        # 0-byte audio guard (guards against Microsoft Sec-MS-GEC silent empty responses)
        if not audio_bytes or len(audio_bytes) == 0:
            return TTSResult(
                audio_bytes=b"",
                content_type="",
                provider_used="web_speech_fallback",
                fallback_to_browser=True,
                fallback_reason="edge-tts 返回 0 字节音频，已自动降级为浏览器 Web Speech 朗读。",
            )

        return TTSResult(
            audio_bytes=audio_bytes,
            content_type="audio/mpeg",
            provider_used=self.name,
            fallback_to_browser=False,
        )
