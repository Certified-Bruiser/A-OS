import asyncio
import time

from app.audio.engine import AudioEngine
from app.stt.service import STTService
from app.tts.service import TTSService
from app.llm.service import LLMService
from app.memory.service import MemoryService



class RuntimeState:


    def __init__(self):

        self.transcript = None
        self.speaking = False
        self.shutdown = False





async def main():


    state = RuntimeState()


    audio_engine = AudioEngine()

    stt = STTService()

    tts = TTSService()

    llm = LLMService()

    memory = MemoryService()



    tts_queue = asyncio.Queue()



    print("\n🎤 AgentOS Ready")



    await stt.connect()





    ######################################################
    # AUDIO CALLBACK
    ######################################################


    async def on_audio_chunk(chunk):

        await audio_engine.play_queue.put(
            chunk
        )






    ######################################################
    # TTS WORKER
    ######################################################


    async def tts_worker():


        while not state.shutdown:


            text = await tts_queue.get()


            print(
                "\n🔊 TTS RECEIVED:",
                text
            )


            if text:


                state.speaking = True


                try:


                    tts_start = time.perf_counter()


                    await tts.speak(

                        text,

                        on_audio_chunk,

                        tts_start

                    )


                    print(
                        "✅ TTS DONE"
                    )


                finally:


                    state.speaking = False



            tts_queue.task_done()







    ######################################################
    # LISTENER
    ######################################################


    async def listener():


        while not state.shutdown:


            audio_packet = await audio_engine.listen()


            audio = audio_packet["audio"]

            audio_finished = audio_packet["captured_at"]



            transcript = await stt.transcribe(

                audio

            )


            stt_finished = time.perf_counter()



            print(

                f"STT Latency: "
                f"{stt_finished-audio_finished:.3f}s"

            )



            if not transcript:

                continue



            print(
                f"\n📝 You:\n{transcript}"
            )



            if state.speaking:


                print(
                    "\n🛑 Barge-in detected"
                )


                audio_engine.stop()



            state.transcript = transcript







    ######################################################
    # ASSISTANT
    ######################################################


    async def assistant():


        while not state.shutdown:


            if state.transcript is None:


                await asyncio.sleep(0.01)

                continue



            transcript = state.transcript


            state.transcript = None




            if transcript.lower() in [

                "exit",
                "quit",
                "shutdown",
                "goodbye",
                "jarvis shutdown"

            ]:

                state.shutdown = True

                break






            memory.save_message(

                "user",

                transcript

            )





            if not await llm.is_running():


                print(
                    "\n❌ LLM not running"
                )


                state.shutdown = True

                break





            print(
                "\n🧠 Thinking..."
            )




            full_response = ""



            llm_start = time.perf_counter()

            first_token = True




            async for token in llm.stream(


                transcript,


                memory.get_context()


            ):


                if first_token:


                    print(

                        f"LLM first token latency: "
                        f"{time.perf_counter()-llm_start:.3f}s"

                    )

                    first_token = False



                print(

                    token,

                    end="",

                    flush=True

                )



                full_response += token





            print(

                "\n\n🤖 Jarvis:",

                full_response

            )





            #
            # One complete TTS call
            #

            await tts_queue.put(

                full_response.strip()

            )



            await tts_queue.join()





            memory.save_message(

                "assistant",

                full_response

            )








    ######################################################
    # RUN
    ######################################################


    try:


        await asyncio.gather(

            listener(),

            assistant(),

            tts_worker(),

            audio_engine.playback_worker()

        )


    finally:


        await stt.disconnect()


        await llm.close()


        audio_engine.cleanup()






if __name__ == "__main__":


    asyncio.run(main())
