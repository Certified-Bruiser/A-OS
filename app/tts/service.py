import asyncio
import wave
import tempfile
import os
import audioop
import time


class TTSService:


    def __init__(self):

        self.model = (
            "C:\\Users\\Anso Jacob\\AgentOS\\en_US-lessac-medium.onnx"
        )

        self.first_audio = False



    async def speak(

        self,

        text,

        on_audio_chunk,

        tts_start,
        should_stop=None

    ):


        self.first_audio = True


        text = text.strip()


        if not text:

            return



        with tempfile.NamedTemporaryFile(

            suffix=".wav",

            delete=False

        ) as f:

            wav_path = f.name



        try:


            process = await asyncio.create_subprocess_exec(

                "piper",

                "--model",

                self.model,

                "--output_file",

                wav_path,

                stdin=asyncio.subprocess.PIPE

            )



            await process.communicate(

                input=text.encode()

            )



            with wave.open(

                wav_path,

                "rb"

            ) as wav:


                rate = wav.getframerate()

                channels = wav.getnchannels()

                width = wav.getsampwidth()


                print(
                    f"Piper audio: "
                    f"{channels}ch "
                    f"{rate}Hz "
                    f"{width*8}bit"
                )



                pcm = wav.readframes(

                    wav.getnframes()

                )



                #
                # Piper 22050Hz -> 16000Hz
                #
                if rate != 16000:


                    pcm, _ = audioop.ratecv(

                        pcm,

                        width,

                        channels,

                        rate,

                        16000,

                        None

                    )



                #
                # WebRTC AEC frame size
                # 10ms @ 16kHz mono 16-bit
                # 320 bytes
                #
                FRAME_SIZE = 320



                for i in range(

                    0,

                    len(pcm),

                    FRAME_SIZE

                ):
                    if should_stop and should_stop():
                        print("TTS Interrupted")
                        break


                    chunk = pcm[

                        i:i + FRAME_SIZE

                    ]


                    if len(chunk) != FRAME_SIZE:

                        break



                    if not self.first_audio:

                        print(

                            f"🔊 TTS first audio latency: "

                            f"{time.perf_counter() - tts_start:.3f}s"

                        )

                        self.first_audio = True



                    await on_audio_chunk(

                        chunk

                    )



        finally:


            if os.path.exists(wav_path):

                os.remove(wav_path)
