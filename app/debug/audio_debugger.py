import os
import wave


class AudioDebugger:
    def __init__(self):
        self.debug_dir = "app/debug"

        os.makedirs(self.debug_dir, exist_ok=True)

    def save_wav(
        self,
        filename: str,
        pcm: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ):
        """
        Save raw PCM bytes as a WAV file.
        """

        path = os.path.join(
            self.debug_dir,
            filename
        )

        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)

        print(f"💾 Saved {path}")

