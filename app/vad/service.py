from collections import deque
import numpy as np
import torch

from silero_vad import load_silero_vad, get_speech_timestamps


class VADService:

    def __init__(self):
        self.model = load_silero_vad()
        self.sample_rate = 16000

    def is_speech(self, pcm: bytes):

        audio = np.frombuffer(
            pcm,
            dtype=np.int16
        ).astype(np.float32)

        audio /= 32768.0

        tensor = torch.from_numpy(audio)

        speech = get_speech_timestamps(
            tensor,
            self.model,
            sampling_rate=self.sample_rate
        )

        return len(speech) > 0

