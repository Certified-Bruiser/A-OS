import asyncio

audio_queue = asyncio.Queue()
transcript_queue = asyncio.Queue()
response_queue = asyncio.Queue()
tts_queue = asyncio.Queue()
playback_queue = asyncio.Queue()