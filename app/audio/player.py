import pygame


class AudioPlayer:

    def __init__(self):

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.current_file = None

    def play(self, audio_file):

        self.current_file = audio_file

        pygame.mixer.music.load(
            audio_file
        )

        pygame.mixer.music.play()

    def stop(self):

        pygame.mixer.music.stop()

    def pause(self):

        pygame.mixer.music.pause()

    def resume(self):

        pygame.mixer.music.unpause()

    def is_playing(self):

        return pygame.mixer.music.get_busy()

