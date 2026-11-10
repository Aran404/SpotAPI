"""Opt-in account reads; no profile changes, follows or notification acknowledgements."""

from __future__ import annotations

import os

import pytest

from spotapi import Private, Profiles
from spotapi.models import TimeRange

pytestmark = [pytest.mark.live, pytest.mark.authenticated]


async def test_live_account_and_content() -> None:
    async with Private.from_cookies(os.environ["SPOTIFY_COOKIE"]) as account:
        profile = await account.get_profile()
        assert profile.username
        assert (await account.get_plan()).name
        assert await account.verify_login()

        ranges: tuple[TimeRange, ...] = ("short_term", "medium_term", "long_term")
        for span in ranges:
            top = await account.stats.get(time_range=span, limit=2)
            assert all(track.id and track.name for track in top.tracks)

        saved = await account.liked_tracks.get(limit=2)
        assert all(entry.uri for entry in saved)
        library = await account.library.get(limit=2)
        assert all(entry.uri and entry.name for entry in library.items)
        await account.notifications.get(limit=2)
        assert type(await account.notifications.has_unread()) is bool

        json_profile = await account.profiles.get("spotify")
        proto_profile = await Profiles(account.session, protobuf=True).get("spotify")
        assert json_profile.uri == proto_profile.uri
        assert json_profile.name == proto_profile.name
