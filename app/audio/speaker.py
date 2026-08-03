import pyaudio


class Speaker:

    def __init__(

        self,

        sample_rate=16000,

        channels=1

    ):

        self.audio = pyaudio.PyAudio()

        self.stream = self.audio.open(

            format=pyaudio.paInt16,

            channels=channels,

            rate=sample_rate,

            output=True

        )

        self.stopped = False

    def play(

        self,

        audio_bytes

    ):

        if self.stopped:
            return

        self.stream.write(
            audio_bytes
        )

    def stop(self):

        #
        # Interrupt current playback
        #
        self.stopped = True

    def resume(self):

        self.stopped = False

    def cleanup(self):

        if self.stream:

            self.stream.stop_stream()

            self.stream.close()

            self.stream = None

        self.audio.terminate()

