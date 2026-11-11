"""Unit tests for the public search-result model conveniences."""

from spotapi.specialized.data_wrappers import Album, Artist
from spotapi.specialized.data_wrappers.artist import ArtistProfile


def test_artist_search_result_exposes_identity_and_display_name() -> None:
    artist = Artist(
        profile=ArtistProfile(name="Daft Punk"),
        uri="spotify:artist:4tZwfgrHOc3mvqYlEYSvVi",
    )

    assert artist.id == "4tZwfgrHOc3mvqYlEYSvVi"
    assert artist.name == "Daft Punk"
    assert artist.uri == "spotify:artist:4tZwfgrHOc3mvqYlEYSvVi"


def test_album_search_result_exposes_id_from_uri() -> None:
    album = Album(
        name="Discovery",
        uri="spotify:album:2noRn2Aes5aoNVsU6iWThc",
    )

    assert album.id == "2noRn2Aes5aoNVsU6iWThc"
    assert album.name == "Discovery"
    assert album.uri == "spotify:album:2noRn2Aes5aoNVsU6iWThc"
