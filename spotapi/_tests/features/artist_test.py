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
