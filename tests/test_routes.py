"""Endpoint construction preserves resource identity and regional hosts."""

from spotapi._protocol.routes import CONNECT_ROUTES, LYRICS_IMAGE, PROFILE, RADIO, ROOTLIST


def test_profile_names_are_encoded_as_one_path_segment() -> None:
    assert PROFILE.url(user="a/b ?#%") == (
        "https://spclient.wg.spotify.com/user-profile-view/v3/profile/a%2Fb%20%3F%23%25"
    )


def test_embedded_image_url_is_encoded_once() -> None:
    assert LYRICS_IMAGE.url(track="track", image="https://image.test/a%20b?size=2") == (
        "https://spclient.wg.spotify.com/color-lyrics/v2/track/track/image/"
        "https%3A%2F%2Fimage.test%2Fa%2520b%3Fsize%3D2"
    )


def test_connect_operation_segments_and_regional_hosts_are_preserved() -> None:
    assert (
        CONNECT_ROUTES["player/command"].url(
            base="https://regional.spotify.com/", source="source", target="target"
        )
        == "https://regional.spotify.com/connect-state/v1/player/command/from/source/to/target"
    )


def test_rootlist_username_uses_the_same_segment_encoding() -> None:
    assert ROOTLIST.url(user="listener@example.com").endswith(
        "/playlist/v2/user/listener%40example.com/rootlist/changes"
    )


def test_radio_seed_is_encoded_as_one_path_segment() -> None:
    assert RADIO.url(seed="spotify:track:abc") == (
        "https://spclient.wg.spotify.com/inspiredby-mix/v2/seed_to_playlist/spotify:track:abc"
    )
    assert RADIO.url(seed="spotify:track:a/b").endswith("spotify:track:a%2Fb")
