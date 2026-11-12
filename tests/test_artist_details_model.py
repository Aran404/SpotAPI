"""Regression tests for the artist model's public display-name interface."""

from spotapi.models.catalogue.artist import Artist, ArtistProfile
from spotapi.models.catalogue.artist_details import (
    ArtistDetails,
    ArtistProfileDetails,
)


def test_artist_search_hit_exposes_name_and_id() -> None:
    artist = Artist(
        profile=ArtistProfile(name="Daft Punk"),
        uri="spotify:artist:4tZwfgrHOc3mvqYlEYSvVi",
    )

    assert artist.name == "Daft Punk"
    assert artist.id == "4tZwfgrHOc3mvqYlEYSvVi"


def test_artist_details_exposes_name() -> None:
    artist = ArtistDetails(
        id="4tZwfgrHOc3mvqYlEYSvVi",
        uri="spotify:artist:4tZwfgrHOc3mvqYlEYSvVi",
        profile=ArtistProfileDetails(name="Daft Punk"),
    )

    assert artist.name == "Daft Punk"
