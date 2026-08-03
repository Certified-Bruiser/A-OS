from app.providers import registry
from app.providers.factory import ProviderFactory

factory = ProviderFactory(registry)

stt = factory.create_stt("sarvam")

print(type(stt))

