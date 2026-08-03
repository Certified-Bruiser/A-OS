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


  


    def process_microphone(
        self,
        chunk: bytes
    ):

        return self.processor.process_stream(
            chunk
        )

    def process_speaker(
        self,
        chunk: bytes
    ):

        self.processor.process_reverse_stream(
            chunk
        )


