from app.providers.registry import ProviderRegistry


class ProviderFactory:

    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    def create_stt(self, provider_id):
        provider = self.registry.get_stt(provider_id)

        if provider is None:
            raise ValueError(f"Unknown STT provider: {provider_id}")

        return provider()

    def create_llm(self, provider_id):
        provider = self.registry.get_llm(provider_id)

        if provider is None:
            raise ValueError(f"Unknown LLM provider: {provider_id}")

        return provider()

    def create_tts(self, provider_id):
        provider = self.registry.get_tts(provider_id)

        if provider is None:
            raise ValueError(f"Unknown TTS provider: {provider_id}")

        return provider()

