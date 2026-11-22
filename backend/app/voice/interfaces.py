from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TTSResult:
    audio_bytes: bytes
    content_type: str
    provider_used: str
    fallback_to_browser: bool = False
    fallback_reason: str = ""


@dataclass
class STTResult:
    text: str
    provider_used: str
    word_timestamps: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0


class BaseTTSProvider(ABC):
    name: str

    @abstractmethod
    async def synthesize(
        self, text: str, *, voice: str | None = None, rate: str | None = None
    ) -> TTSResult:
        """Convert text to audio bytes or return explicit browser fallback signal."""


class BaseSTTProvider(ABC):
    name: str

    @abstractmethod
    async def transcribe(
        self, audio_bytes: bytes, filename: str, *, hotwords: list[str] | None = None
    ) -> STTResult:
        """Transcribe audio bytes into text with optional word timestamps."""


class TurnDetectorProtocol(Protocol):
    """P1 extension slot for Smart Turn v3.2 prosodic turn completion scoring."""

    async def predict_turn_complete(self, pcm_16khz: bytes) -> tuple[bool, float]:
        ...


class RealtimeTransportProtocol(Protocol):
    """P1 extension slot for LiveKit WebRTC room + Data Channel transport."""

    async def create_room_token(self, session_id: str, participant_name: str) -> dict[str, str]:
        ...
