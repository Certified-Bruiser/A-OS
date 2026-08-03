import asyncio

from app.audio.engine import AudioEngine

from app.stt.service import STTService
from app.tts.service import TTSService
from app.llm.service import LLMService
from app.memory.service import MemoryService

from app.core.state_manager import StateManager


class JarvisRuntime:

    def __init__(self):

        self.audio = AudioEngine()

        self.stt = STTService()
        self.tts = TTSService()
        self.llm = LLMService()

        self.memory = MemoryService()

        self.state = StateManager()

        self.running = True

        self.is_speaking = False

        self.response_queue = asyncio.Queue()

    async def run(self):

        print("\n🚀 Starting Jarvis Runtime...")

        await self.stt.connect()

        self.audio.microphone.start()

        await asyncio.gather(

            self.audio_loop(),

            self.conversation_loop(),

            self.tts_loop()

        )

    ###########################################################

    async def audio_loop(self):

        print("🎤 Audio Loop Started")

        while self.running:

            try:

                frame = self.audio.read_frame()

                #
                # If Jarvis is speaking,
                # AEC removes its own voice.
                #

                await self.stt.push_audio(frame)

                await asyncio.sleep(0)

            except Exception as e:

                print("Audio Loop:", e)

    ###########################################################

    async def conversation_loop(self):

        print("🧠 Conversation Loop Started")

        while self.running:

            transcript = await self.stt.get_transcript()

            transcript = transcript.strip()

            if transcript == "":
                continue

            print()

            print("🧑", transcript)

            ###################################################

            #
            # Shutdown
            #

            if transcript.lower() in [

                "shutdown",

                "goodbye",

                "exit",

                "quit"

            ]:

                print("👋 Shutting Down")

                self.running = False

                break

            ###################################################

            #
            # Barge In
            #

            if self.is_speaking:

                print("🛑 Interrupting Speech")

                self.is_speaking = False

            ###################################################

            self.memory.save_message(

                "user",

                transcript

            )

            context = self.memory.get_context()

            response = await self.llm.generate(

                transcript,

                context

            )

            self.memory.save_message(

                "assistant",

                response

            )

            print()

            print("🤖", response)

            await self.response_queue.put(

                response

            )

    ###########################################################

    async def tts_loop(self):

        print("🔊 TTS Loop Started")

        while self.running:

            response = await self.response_queue.get()

            self.is_speaking = True

            await self.tts.speak(

                response

            )

            while self.tts.has_audio():

                #
                # interrupted
                #

                if not self.is_speaking:

                    break

                frame = await self.tts.get_frame()

                self.audio.play_frame(

                    frame

                )

                await asyncio.sleep(0)

            self.is_speaking = False

    ###########################################################

    async def shutdown(self):

        self.running = False

        await self.stt.disconnect()

        self.audio.cleanup()


