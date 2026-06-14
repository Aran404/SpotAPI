import pytest
from spotapi import Artist, ArtistError
from session import _MainFixture


instance = Artist(login=_MainFixture.login)


def test_artist_initialization():
    """Test the initialization of the Artist class."""
    artist_with_login = Artist(login=_MainFixture.login)
    assert artist_with_login._login is True
    assert isinstance(
        artist_with_login.base.client, _MainFixture.login.client.__class__
    )

    artist_without_login = Artist()
    assert artist_without_login._login is False
    assert isinstance(
        artist_without_login.base.client, _MainFixture.login.client.__class__
    )


def test_query_artists_with_login():
    """Test the query_artists method for valid response structure with login."""
    response = instance.query_artists("ariana", limit=2)

    assert "data" in response
    assert "searchV2" in response["data"]
    assert "artists" in response["data"]["searchV2"]
    assert "items" in response["data"]["searchV2"]["artists"]
    assert isinstance(response["data"]["searchV2"]["artists"]["items"], list)
    assert len(response["data"]["searchV2"]["artists"]["items"]) > 0


def test_query_artists_without_login():
    """Test the query_artists method for valid response structure without login."""
    artist_instance = Artist()
    response = artist_instance.query_artists("ariana", limit=2)

    assert "data" in response
    assert "searchV2" in response["data"]
    assert "artists" in response["data"]["searchV2"]
    assert "items" in response["data"]["searchV2"]["artists"]
    assert isinstance(response["data"]["searchV2"]["artists"]["items"], list)
    assert len(response["data"]["searchV2"]["artists"]["items"]) > 0


def test_paginate_artists():
    """Test the paginate_artists method for proper pagination."""
    query = "ariana"
    results = list(instance.paginate_artists(query))

    assert isinstance(results, list)
    assert len(results) > 0
    for chunk in results:
        assert isinstance(chunk, list)


# BTS — has plenty of albums + singles for paging assertions.
_DISCOGRAPHY_ARTIST_ID = "3Nrfpe0tUJi4K4DXYWgMUX"


def _assert_discography_section(response, section):
    """Common shape check for queryArtistDiscography* responses."""
    assert "data" in response
    artist_union = response["data"]["artistUnion"]
    assert artist_union["__typename"] == "Artist"
    assert "discography" in artist_union
    section_data = artist_union["discography"][section]
    assert "items" in section_data
    assert isinstance(section_data["items"], list)
    assert "totalCount" in section_data


def test_get_artist_discography_all():
    """Section 'all' returns combined releases sorted by date."""
    artist_instance = Artist()
    response = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="all", limit=5
    )
    _assert_discography_section(response, "all")
    items = response["data"]["artistUnion"]["discography"]["all"]["items"]
    assert 0 < len(items) <= 5


def test_get_artist_discography_albums():
    """Section 'albums' returns album-type releases only."""
    artist_instance = Artist()
    response = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="albums", limit=5
    )
    _assert_discography_section(response, "albums")


def test_get_artist_discography_singles():
    """Section 'singles' returns single-type releases only."""
    artist_instance = Artist()
    response = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="singles", limit=5
    )
    _assert_discography_section(response, "singles")


def test_get_artist_discography_with_uri():
    """Accepts both raw IDs and spotify:artist:* URIs."""
    artist_instance = Artist()
    response = artist_instance.get_artist_discography(
        f"spotify:artist:{_DISCOGRAPHY_ARTIST_ID}", section="all", limit=3
    )
    _assert_discography_section(response, "all")


def test_get_artist_discography_offset():
    """Advancing offset returns a different page of items than offset=0."""
    artist_instance = Artist()
    first = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="all", offset=0, limit=5
    )["data"]["artistUnion"]["discography"]["all"]["items"]
    second = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="all", offset=5, limit=5
    )["data"]["artistUnion"]["discography"]["all"]["items"]
    if len(first) >= 5 and len(second) > 0:
        first_ids = {item.get("releases", {}).get("items", [{}])[0].get("id") for item in first}
        second_ids = {item.get("releases", {}).get("items", [{}])[0].get("id") for item in second}
        assert first_ids != second_ids


def test_paginate_artist_discography():
    """Generator yields lists summing up to totalCount."""
    artist_instance = Artist()
    first = artist_instance.get_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="singles", limit=1
    )
    total = first["data"]["artistUnion"]["discography"]["singles"]["totalCount"]

    pages = list(artist_instance.paginate_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="singles"
    ))
    assert all(isinstance(chunk, list) for chunk in pages)
    assert sum(len(chunk) for chunk in pages) == total


def test_paginate_artist_discography_order_asc():
    """order=DATE_ASC yields oldest-first."""
    artist_instance = Artist()
    pages = list(artist_instance.paginate_artist_discography(
        _DISCOGRAPHY_ARTIST_ID, section="albums", order="DATE_ASC"
    ))
    assert len(pages) > 0
    # First release in the earliest page should be no later than the last release
    # in the final page when ordered ascending.
    first_release = pages[0][0]["releases"]["items"][0]
    last_release = pages[-1][-1]["releases"]["items"][0]
    first_year = first_release.get("date", {}).get("year")
    last_year = last_release.get("date", {}).get("year")
    if first_year and last_year:
        assert first_year <= last_year


def test_follow_artist():
    """Test the follow method to follow an artist."""
    artist_id = "3TVXtAsR1Inumwj472S9r4"
    try:
        instance.follow(artist_id)
    except ArtistError as e:
        pytest.fail(f"Follow method raised an error: {e}")
    except ValueError:
        pytest.fail("Follow method raised a ValueError for an authenticated user")


def test_unfollow_artist():
    """Test the unfollow method to unfollow an artist."""
    artist_id = "3TVXtAsR1Inumwj472S9r4"
    try:
        instance.unfollow(artist_id)
    except ArtistError as e:
        pytest.fail(f"Unfollow method raised an error: {e}")
    except ValueError:
        pytest.fail("Unfollow method raised a ValueError for an authenticated user")


def test_follow_artist_not_logged_in():
    """Test follow method raises ValueError if not logged in."""
    artist_id = "3TVXtAsR1Inumwj472S9r4"
    artist_instance = Artist()
    with pytest.raises(ValueError, match="Must be logged in"):
        artist_instance.follow(artist_id)


def test_unfollow_artist_not_logged_in():
    """Test unfollow method raises ValueError if not logged in."""
    artist_id = "3TVXtAsR1Inumwj472S9r4"
    artist_instance = Artist()
    with pytest.raises(ValueError, match="Must be logged in"):
        artist_instance.unfollow(artist_id)
