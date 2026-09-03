import pyaudio


class Speaker:

    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        output_device_index=None,
    ):

        self.sample_rate = sample_rate
        self.channels = channels
        self.output_device_index = output_device_index

        self.audio = pyaudio.PyAudio()

        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            output=True,
            frames_per_buffer=320,
            output_device_index=output_device_index,
        )

        self.stopped = False

    def play(self, audio_bytes):

        if self.stopped:
            return

        if self.stream is None:
            return

        try:

            self.stream.write(
                audio_bytes
            )

        except Exception as e:

            if not self.stopped:

                print(
                    f"⚠️ Speaker error: {e}"
                )

    def stop(self):

        self.stopped = True

        if self.stream is not None:

            try:
                self.stream.stop_stream()

            except Exception:
                pass

    def resume(self):

        self.stopped = False

        if self.stream is not None:

            try:

                if not self.stream.is_active():
                    self.stream.start_stream()

            except Exception:
                pass

    def cleanup(self):

        if self.stream:

            try:
                self.stream.stop_stream()
                self.stream.close()

            except Exception:
                pass

            finally:
                self.stream = None

        if self.audio:

            try:
                self.audio.terminate()

            except Exception:
                pass

            finally:
                self.audio = None


