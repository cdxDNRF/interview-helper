from app.voice.interfaces import BaseTTSProvider, TTSResult


class WebSpeechFallbackProvider(BaseTTSProvider):
    name = "web_speech"

    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        return TTSResult(
            audio_bytes=b"",
            content_type="",
            provider_used="web_speech",
            fallback_to_browser=True,
            fallback_reason="使用浏览器原生 Web Speech API (speechSynthesis) 朗读。",
        )


class NullTTSProvider(BaseTTSProvider):
    name = "none"

    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        return TTSResult(
            audio_bytes=b"",
            content_type="",
            provider_used="none",
            fallback_to_browser=False,
            fallback_reason="纯文本静默模式",
        )


class KokoroTTSProvider(BaseTTSProvider):
    """预留扩展位：本地 CPU 开源 Kokoro-82M TTS 服务。"""

    name = "kokoro"

    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        return TTSResult(
            audio_bytes=b"",
            content_type="",
            provider_used="web_speech_fallback",
            fallback_to_browser=True,
            fallback_reason="Kokoro-82M 扩展位尚未挂载本地推理服务，已自动降级至浏览器 Web Speech。",
        )


class OpenAICompatTTSProvider(BaseTTSProvider):
    """预留扩展位：OpenAI /audio/speech 或商业 TTS（CosyVoice / Cartesia）网关。"""

    name = "openai_tts"

    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        return TTSResult(
            audio_bytes=b"",
            content_type="",
            provider_used="web_speech_fallback",
            fallback_to_browser=True,
            fallback_reason="商业/OpenAI TTS 扩展位未配置端点，已自动降级至浏览器 Web Speech。",
        )
