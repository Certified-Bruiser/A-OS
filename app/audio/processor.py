import audioop

from aec_audio_processing import AudioProcessor


class AudioProcessorService:

    def __init__(self):

        self.processor = AudioProcessor(
            enable_aec=True,
            enable_ns=True,
            enable_agc=True,
            enable_vad=True
        )

        self.processor.set_stream_format(
            sample_rate_in=16000,
            channel_count_in=1,
            sample_rate_out=16000,
            channel_count_out=1
        )

        self.processor.set_reverse_stream_format(
            16000,
            1
        )

        self.processor.set_stream_delay(50)

        self.reverse_frames = 0
        self.mic_frames = 0

    def process_microphone(self, chunk: bytes):

        processed = self.processor.process_stream(chunk)

        self.mic_frames += 1

        if self.mic_frames % 100 == 0:

            raw_rms = audioop.rms(chunk, 2)
            processed_rms = audioop.rms(processed, 2)

            print(
                f"\n🎤 AEC DEBUG"
                f"\n   raw RMS:       {raw_rms}"
                f"\n   processed RMS: {processed_rms}"
                f"\n   reverse frames:{self.reverse_frames}"
            )

        return processed

    def process_speaker(self, chunk: bytes):

        self.reverse_frames += 1

        self.processor.process_reverse_stream(chunk)

