from app.integrations.ai.base import AIProvider
from app.integrations.ai.exceptions import AIConfigurationError
from app.integrations.ai.gemini_provider import GeminiProvider
from app.integrations.ai.settings import AISettings

class AIProviderFactory:
    @staticmethod
    def create() -> AIProvider:
        provider = AISettings().ai_provider.strip().lower()
        if provider == "gemini":
            return GeminiProvider()
        if provider == "openai":
            raise AIConfigurationError("Provider OpenAI belum dikonfigurasi.")
        raise AIConfigurationError("AI_PROVIDER tidak didukung.")
