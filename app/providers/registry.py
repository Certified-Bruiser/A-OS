class ProviderRegistry:

    def __init__(self):
        self.stt = {}
        self.llm = {}
        self.tts = {}

    def register_stt(self, provider):
        self.stt[provider.id] = provider

    def register_llm(self, provider):
        self.llm[provider.id] = provider

    def register_tts(self, provider):
        self.tts[provider.id] = provider

    def get_stt(self, provider_id):
        return self.stt.get(provider_id)

    def get_llm(self, provider_id):
        return self.llm.get(provider_id)

    def get_tts(self, provider_id):
        return self.tts.get(provider_id)

    def available(self):
        return {
            "stt": list(self.stt.keys()),
            "llm": list(self.llm.keys()),
            "tts": list(self.tts.keys()),
        }
