import pyaudio


class Microphone:

    def __init__(

        self,

        sample_rate=16000,

        channels=1,

        chunk_size=160

    ):

        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.audio = pyaudio.PyAudio()

        self.stream = None

    def start(self):

        if self.stream:
            return

        self.stream = self.audio.open(

            format=pyaudio.paInt16,

            channels=self.channels,

            rate=self.sample_rate,

            input=True,

            frames_per_buffer=self.chunk_size

        )

    def read(self):

        return self.stream.read(

            self.chunk_size,

            exception_on_overflow=False

        )

    def stop(self):

        if self.stream:

            self.stream.stop_stream()

            self.stream.close()

            self.stream = None

    def cleanup(self):

        self.stop()

        self.audio.terminate()
