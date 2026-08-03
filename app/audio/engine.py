import io
import wave
import audioop
import asyncio
import time

from app.audio.microphone import Microphone
from app.audio.speaker import Speaker
from app.audio.processor import AudioProcessorService
from app.vad.service import VADService
from app.debug.audio_debugger import AudioDebugger
from app.audio.frame_buffer import FrameBuffer
from app.conversation.utterance_detector import UtteranceDetector

class AudioEngine:

    def __init__(self):

        self.processor = AudioProcessorService()
        self.microphone = Microphone()
        self.speaker = Speaker()
        self.vad = VADService()
        self.debugger = AudioDebugger()
        self.microphone.start()
        self.frame_buffer = FrameBuffer()
        self.utterance_detector = UtteranceDetector()
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2

        # Playback state
        self.is_playing = False

        # Async playback queue
        self.play_queue = asyncio.Queue()

        # Streaming PCM buffer
        self.playback_buffer = bytearray()

        # Playback worker task
        self.playback_task = None

    # --------------------------------------------------
    # Start playback worker
    # --------------------------------------------------
    async def start(self):
        if self.playback_task is None:
            self.playback_task = asyncio.create_task(
                self.playback_worker()
            )

    # --------------------------------------------------
    # Listen until VAD returns a complete utterance
    # --------------------------------------------------
    async def listen(self):
        frames = []

        speech_detected = False

        print("\n🎤 Waiting for speech...")

    # Reset detector
        self.utterance_detector.reset()

    # Reset analysis buffer
        self.frame_buffer.clear()

        while True:
            frame = await asyncio.to_thread(self.microphone.read)

            clean_frame = self.processor.process_microphone(frame)

        # Always keep every frame
            frames.append(clean_frame)

        # Build larger analysis window
            self.frame_buffer.add(clean_frame)

            if not self.frame_buffer.ready():
                continue

            analysis_pcm = self.frame_buffer.get()

            is_speech = self.vad.is_speech(analysis_pcm)

            result = self.utterance_detector.update(is_speech)

            if is_speech and not speech_detected:
                print("\n🟢 Speech detected")
                speech_detected = True

            if result == "finished":
                print("\n⏹️ End of speech")
                break

        return {
        "audio": self._pcm_to_wav(
            b"".join(frames)
        ),
        "captured_at": time.perf_counter(),
    }







    # --------------------------------------------------
    # Playback worker
    # --------------------------------------------------
    async def playback_worker(self):

        print("🎵 Playback worker running")

        while True:

            frame = await self.play_queue.get()

            if frame is None:
                print("🛑 Playback worker stopping")
                self.play_queue.task_done()
                break

            self.is_playing = True

            self.processor.process_speaker(frame)

            await asyncio.to_thread(
                self.speaker.play,
                frame
            )

            self.play_queue.task_done()

            if self.play_queue.empty():
                self.is_playing = False

    # --------------------------------------------------
    # Legacy WAV playback
    # --------------------------------------------------
    def play(self, wav_bytes):

        self.is_playing = True

        self.speaker.resume()

        wav = wave.open(
            io.BytesIO(wav_bytes),
            "rb"
        )

        channels = wav.getnchannels()
        rate = wav.getframerate()
        width = wav.getsampwidth()

        pcm = wav.readframes(
            wav.getnframes()
        )

        wav.close()

        if rate != 16000:

            pcm, _ = audioop.ratecv(
                pcm,
                width,
                channels,
                rate,
                16000,
                None,
            )

        FRAME_BYTES = 320

        for i in range(0, len(pcm), FRAME_BYTES):

            if self.speaker.stopped:
                print("\n🛑 Playback interrupted")
                break

            frame = pcm[i:i + FRAME_BYTES]

            if len(frame) != FRAME_BYTES:
                break

            self.processor.process_speaker(frame)

            self.speaker.play(frame)

        self.is_playing = False

    # --------------------------------------------------
    # Streaming playback
    # --------------------------------------------------
    async def play_frame(self, chunk):

        if self.speaker.stopped:
            return

        self.is_playing = True

        self.speaker.resume()

        self.playback_buffer.extend(chunk)

        FRAME_BYTES = 320

        while len(self.playback_buffer) >= FRAME_BYTES:

            frame = bytes(
                self.playback_buffer[:FRAME_BYTES]
            )

            del self.playback_buffer[:FRAME_BYTES]

            await self.play_queue.put(frame)

    # --------------------------------------------------
    # Stop playback immediately
    # --------------------------------------------------
    def stop(self):

        self.is_playing = False

        self.playback_buffer.clear()

        self.speaker.stop()

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------
    async def shutdown(self):

        if self.playback_task is not None:

            await self.play_queue.put(None)

            await self.playback_task

            self.playback_task = None

        self.microphone.cleanup()

        self.speaker.cleanup()

    # --------------------------------------------------
    def cleanup(self):

        self.microphone.cleanup()

        self.speaker.cleanup()

    # --------------------------------------------------
    # Convert PCM -> WAV
    # --------------------------------------------------
    def _pcm_to_wav(self, pcm):

        buffer = io.BytesIO()

        wf = wave.open(
            buffer,
            "wb"
        )

        wf.setnchannels(self.channels)
        wf.setsampwidth(self.sample_width)
        wf.setframerate(self.sample_rate)

        wf.writeframes(pcm)

        wf.close()

        return buffer.getvalue()

