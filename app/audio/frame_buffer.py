from collections import deque


class FrameBuffer:
    """
    Accumulates fixed-size audio frames and exposes
    a larger analysis window.
    """

    def __init__(
        self,
        frame_size=160,
        window_frames=32
    ):
        self.frame_size = frame_size
        self.window_frames = window_frames

        self.buffer = deque(maxlen=window_frames)

    def add(self, frame: bytes):
        self.buffer.append(frame)

    def ready(self):
        return len(self.buffer) == self.window_frames

    def get(self):
        return b"".join(self.buffer)

    def clear(self):
        self.buffer.clear()

