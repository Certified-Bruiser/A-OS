import pyaudio
import wave
import audioop


class AudioService:

    def __init__(

        self,
        processor,
        sample_rate=16000,
        channels=1,
        chunk_size=160

    ):

        self.processor = processor

        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.audio = pyaudio.PyAudio()

    async def listen(self):

        stream = self.audio.open(

            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size

        )

        print("\n🎤 Waiting for speech...")

        frames = []

        speech_detected = False
        silence_count = 0

        SILENCE_THRESHOLD = 500
        MAX_SILENCE_CHUNKS = 20

        while True:

            chunk = stream.read(

                self.chunk_size,
                exception_on_overflow=False

            )

            clean_chunk = self.processor.process_microphone(
                chunk
            )

            volume = audioop.rms(
                clean_chunk,
                2
            )

            if volume > SILENCE_THRESHOLD:

                if not speech_detected:

                    print(
                        "\n🟢 Speech detected"
                    )

                    speech_detected = True

                silence_count = 0

                frames.append(
                    clean_chunk
                )

            elif speech_detected:

                frames.append(
                    clean_chunk
                )

                silence_count += 1

                if silence_count >= MAX_SILENCE_CHUNKS:

                    print(
                        "\n⏹️ End of speech detected"
                    )

                    break

        stream.stop_stream()
        stream.close()

        return b"".join(
            frames
        )

    def save_wav(

        self,
        filename,
        audio_data

    ):

        wf = wave.open(
            filename,
            "wb"
        )

        wf.setnchannels(
            self.channels
        )

        wf.setsampwidth(

            self.audio.get_sample_size(
                pyaudio.paInt16
            )

        )

        wf.setframerate(
            self.sample_rate
        )

        wf.writeframes(
            audio_data
        )

        wf.close()

    def cleanup(self):

        self.audio.terminate()
