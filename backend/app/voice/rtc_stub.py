from app.voice.interfaces import RealtimeTransportProtocol, TurnDetectorProtocol


class LiveKitSmartTurnStub(RealtimeTransportProtocol, TurnDetectorProtocol):
    """
    P1 预留接口占位：
    - RealtimeTransportProtocol -> LiveKit Cloud / Self-hosted WebRTC SFU Room + Data Channel
    - TurnDetectorProtocol -> Pipecat Smart Turn v3.2 (8MB int8 ONNX 韵律停顿检测)
    """

    async def predict_turn_complete(self, pcm_16khz: bytes) -> tuple[bool, float]:
        raise NotImplementedError("Smart Turn v3.2 将在 P1 WebRTC 阶段接入")

    async def create_room_token(self, session_id: str, participant_name: str) -> dict[str, str]:
        raise NotImplementedError("LiveKit WebRTC 房间调度将在 P1 阶段接入")
