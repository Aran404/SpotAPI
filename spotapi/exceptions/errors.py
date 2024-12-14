__all__ = [
    "ParentException",
    "CaptchaException",
    "SolverError",
    "LoginError",
    "UserError",
    "PlaylistError",
    "SaverError",
    "SongError",
    "ArtistError",
    "BaseClientError",
    "RequestError",
    "GeneratorError",
    "PasswordError",
    "FamilyError",
    "WebSocketError",
    "PlayerError",
    "AlbumError",
    "PodcastError",
]


class ParentException(Exception):
    def __init__(self, message: str, error: str | None = None) -> None:
        super().__init__(message)
        self.error = error


# Runtime exceptions (API errors)
class CaptchaException(ParentException):
    pass


# Final exceptions
class SolverError(ParentException):
    pass


# Login.py exceptions
class LoginError(ParentException):
    pass


# User.py exceptions
class UserError(ParentException):
    pass


# Playlist.py exceptions
class PlaylistError(ParentException):
    pass


# Saver.py exceptions
class SaverError(ParentException):
    pass


# Song.py exceptions
class SongError(ParentException):
    pass


# Artist.py exceptions
class ArtistError(ParentException):
    pass


# client.py exceptions
class BaseClientError(ParentException):
    pass


# request.py exceptions
class RequestError(ParentException):
    pass


# generator.py exceptions
class GeneratorError(ParentException):
    pass


# password.py exceptions
class PasswordError(ParentException):
    pass


# family.py exceptions
class FamilyError(ParentException):
    pass


# websocket.py exceptions
class WebSocketError(ParentException):
    pass


# player.py exceptions
class PlayerError(ParentException):
    pass


# album.py exceptions
class AlbumError(ParentException):
    pass


# podcast.py exceptions
class PodcastError(ParentException):
    pass
