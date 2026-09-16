from app.providers.registry import ProviderRegistry

from app.providers.stt.sarvam.provider import SarvamSTT
from app.providers.llm.deepseek.provider import DeepSeekLLM
from app.providers.llm.gemini.provider import GeminiLLM
from app.providers.llm.perplexity.provider import PerplexityLLM
from app.providers.tts.piper.provider import PiperTTS
from app.providers.tts.sarvam.provider import SarvamTTS
registry = ProviderRegistry()


registry.register_stt(SarvamSTT)
registry.register_llm(DeepSeekLLM)
registry.register_llm(GeminiLLM)
registry.register_llm(PerplexityLLM)
registry.register_tts(PiperTTS)
registry.register_tts(SarvamTTS)

