import asyncio
import math
import struct
import audioop

from app.audio.engine import AudioEngine


SAMPLE_RATE = 16000
DURATION = 3
FREQUENCY = 440
FRAME_BYTES = 320


def generate_tone():
    samples = []

    total_samples = SAMPLE_RATE * DURATION

    for i in range(total_samples):
        value = int(
            12000 *
            math.sin(
                2 * math.pi *
                FREQUENCY *
                i /
                SAMPLE_RATE
            )
        )

        samples.append(value)

    return struct.pack(
        "<" + ("h" * len(samples)),
        *samples
    )


async def monitor_microphone(engine):

    counter = 0

    while True:

        raw = await asyncio.to_thread(
            engine.microphone.read
        )

        processed = (
            engine.processor.process_microphone(
                raw
            )
        )

        counter += 1

        if counter % 10 == 0:

            raw_rms = audioop.rms(
                raw,
                2
            )

            processed_rms = audioop.rms(
                processed,
                2
            )

            print(
                f"🎤 AEC | "
                f"raw={raw_rms:5d} | "
                f"processed={processed_rms:5d}"
            )

        await asyncio.sleep(0)


async def main():

    print("\n======================================")
    print("        AEC ISOLATED TEST")
    print("======================================")
    print("Do NOT speak.")
    print("The speaker will play a test tone.")
    print("======================================\n")

    engine = AudioEngine()

    tone = generate_tone()

    monitor_task = asyncio.create_task(
        monitor_microphone(engine)
    )

    try:

        for i in range(
            0,
            len(tone),
            FRAME_BYTES
        ):

            frame = tone[
                i:i + FRAME_BYTES
            ]

            if len(frame) != FRAME_BYTES:
                break

            # Tell AEC what is being played
            engine.processor.process_speaker(
                frame
            )

            # Actually play it
            await asyncio.to_thread(
                engine.speaker.play,
                frame
            )

    finally:

        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        engine.cleanup()

    print("\n======================================")
    print("             TEST DONE")
    print("======================================")


if __name__ == "__main__":
    asyncio.run(main())
