from abc import ABC, abstractmethod

from app.integrations.ai.schemas import AIGenerationRequest, AIGenerationResponse

class AIProvider(ABC):
    name: str
    model: str
    @abstractmethod
    def generate(self, request: AIGenerationRequest, *, repair: bool = False, repair_context: dict | None = None) -> AIGenerationResponse:
        raise NotImplementedError
