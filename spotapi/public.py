from typing import Generic, TypeVar, Callable, Generator, Mapping, Any, TypeAlias
from spotapi.client import TLSClient
from typing import Deque
from collections import deque
from threading import Lock

from spotapi import Artist, PublicAlbum, PublicPlaylist, Song, Podcast

T = TypeVar("T")


class Pooler(Generic[T]):
    """
    Pooler is a generic object pool for caching and reusing objects.
    Inspired by golang's sync.Pool
    """

    def __init__(
        self, factory: Callable[..., T], *, max_cache: int | None = None
    ) -> None:
        self.obj_factory = factory
        self.queue: Deque[T] = deque(maxlen=max_cache)
        self.lock = Lock()

    def get(self) -> T:
        """
        Get an object from the pool.
        If the pool is empty, a new object will be created.
        """
        with self.lock:
            if self.queue:
                return self.queue.popleft()
            return self.obj_factory()

    def put(self, obj: T) -> None:
        """
        Put an object back into the pool.
        """
        with self.lock:
            self.queue.append(obj)

    def clear(self) -> None:
        with self.lock:
            self.queue.clear()


client_pool: Pooler[TLSClient] = Pooler(
    factory=lambda: TLSClient("chrome_120", "", auto_retries=3)
)
GeneratorType: TypeAlias = Generator[Mapping[str, Any], None, None]


class Public:
    """
    Public is a class for getting public information from Spotify.
    It does not directly implement any of the methods, but points to the original methods.
    """

    @staticmethod
    def artist_search(query: str, /) -> GeneratorType:
        client = client_pool.get()
        artist = Artist(client=client)
        try:
            yield from artist.paginate_artists(query)
        finally:
            client_pool.put(client)

    @staticmethod
    def album_info(album_id: str, /) -> GeneratorType:
        client = client_pool.get()
        album = PublicAlbum(album_id, client=client)
        try:
            yield from album.paginate_album()
        finally:
            client_pool.put(client)

    @staticmethod
    def playlist_info(playlist_id: str, /) -> GeneratorType:
        client = client_pool.get()
        playlist = PublicPlaylist(playlist_id, client=client)
        try:
            yield from playlist.paginate_playlist()
        finally:
            client_pool.put(client)

    @staticmethod
    def song_search(query: str, /) -> GeneratorType:
        client = client_pool.get()
        song = Song(client=client)
        try:
            yield from song.paginate_songs(query)
        finally:
            client_pool.put(client)

    @staticmethod
    def song_info(song_id: str, /) -> Mapping[str, Any]:
        client = client_pool.get()
        song = Song(client=client)
        try:
            info = song.get_track_info(song_id)
        finally:
            client_pool.put(client)
        return info

    @staticmethod
    def podcast_info(podcast_id: str, /) -> GeneratorType:
        client = client_pool.get()
        podcast = Podcast(podcast_id, client=client)
        try:
            yield from podcast.paginate_podcast()
        finally:
            client_pool.put(client)

    @staticmethod
    def podcast_episode_info(episode_id: str, /) -> Mapping[str, Any]:
        client = client_pool.get()
        podcast = Podcast(client=client)
        try:
            info = podcast.get_episode(episode_id)
        finally:
            client_pool.put(client)
        return info
