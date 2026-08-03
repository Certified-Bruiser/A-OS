import time
from enum import Enum


class UtteranceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    WAITING = "waiting"


class UtteranceDetector:

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = UtteranceState.IDLE

        self.speech_started_at = None
        self.last_speech_at = None

        self.total_speech_time = 0

    def update(self, is_speech: bool):

        now = time.perf_counter()

        if is_speech:

            if self.state == UtteranceState.IDLE:
                self.speech_started_at = now

            self.last_speech_at = now
            self.state = UtteranceState.LISTENING

            self.total_speech_time = (
                now - self.speech_started_at
            )

            return "continue"

        if self.state == UtteranceState.IDLE:
            return "continue"

        self.state = UtteranceState.WAITING

        silence = now - self.last_speech_at

        #
        # Adaptive timeout
        #

        if self.total_speech_time < 1.5:
            timeout = 0.40

        elif self.total_speech_time < 5:
            timeout = 0.65

        else:
            timeout = 0.90

        print(f"Speech: {self.total_speech_time:.2f}s")
        print(f"Silence: {silence:.2f}s")
        print(f"Timeout: {timeout:.2f}s")


        if silence >= timeout:
            return "finished"

        return "continue"

