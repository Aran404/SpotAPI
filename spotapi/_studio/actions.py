"""Explicit feature-lab commands and their small form schemas."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Action:
    """Describe one executable library operation, not an arbitrary Python call."""

    id: str
    title: str
    group: str
    fields: tuple[str, ...] = ()
    changes: bool = False
    authenticated: bool = True


ACTIONS = (
    Action("track", "Track details", "Catalogue", ("uri",), authenticated=False),
    Action("album", "Album & tracks", "Catalogue", ("uri",), authenticated=False),
    Action("artist", "Artist overview", "Catalogue", ("uri",), authenticated=False),
    Action("credits", "Song credits", "Catalogue", ("uri",), authenticated=False),
    Action("radio", "Find a radio playlist", "Catalogue", ("uri",), authenticated=False),
    Action(
        "recommendations", "Playlist recommendations", "Catalogue", ("uri",), authenticated=False
    ),
    Action("canvas", "Canvas metadata", "Catalogue", ("uri",), authenticated=False),
    Action("playlist", "Playlist & occurrences", "Catalogue", ("uri",), authenticated=False),
    Action("related", "Related artists", "Catalogue", ("uri",), authenticated=False),
    Action("artist_top", "Artist top tracks", "Catalogue", ("uri",), authenticated=False),
    Action("releases", "Artist releases", "Catalogue", ("uri",), authenticated=False),
    Action("podcast", "Podcast overview", "Catalogue", ("uri",), authenticated=False),
    Action("episodes", "Podcast episodes", "Catalogue", ("uri",), authenticated=False),
    Action("episode", "Episode details", "Catalogue", ("uri",), authenticated=False),
    Action("audiobook", "Audiobook overview", "Catalogue", ("uri",), authenticated=False),
    Action("profile", "Public profile", "People", ("user",), authenticated=False),
    Action("profile_playlists", "Public playlists", "People", ("user",)),
    Action("followers", "Followers preview", "People", ("user",)),
    Action("following", "Following preview", "People", ("user",)),
    Action("is_following", "Check followed users", "People", ("users",)),
    Action("follow", "Follow users", "People", ("users",), True),
    Action("unfollow", "Unfollow users", "People", ("users",), True),
    Action("account", "Account profile", "Account"),
    Action("plan", "Subscription card", "Account"),
    Action("verify", "Verify session", "Account"),
    Action("validate_profile", "Validate profile fields", "Account", ("email", "country")),
    Action(
        "edit_profile",
        "Edit profile",
        "Account",
        ("email", "country", "gender", "birthdate", "token", "password"),
        True,
    ),
    Action(
        "change_password", "Change password", "Account", ("current_password", "new_password"), True
    ),
    Action("set_password", "Set first password", "Account", ("new_password",), True),
    Action("logout_everywhere", "Sign out everywhere", "Account", (), True),
    Action(
        "edit_playlist",
        "Edit playlist metadata",
        "Playlists",
        ("playlist", "name", "description"),
        True,
    ),
    Action("publish_playlist", "Show playlist on profile", "Playlists", ("playlist",), True),
    Action("unpublish_playlist", "Hide playlist from profile", "Playlists", ("playlist",), True),
    Action("create_playlist", "Create a playlist", "Playlists", ("name",), True),
    Action("create_folder", "Create a library folder", "Playlists", ("name",), True),
    Action("move_folder", "Move items into a folder", "Playlists", ("folder", "uris"), True),
    Action("remove_library_items", "Remove library items", "Playlists", ("uris",), True),
    Action("add_tracks", "Add playlist tracks", "Playlists", ("playlist", "uris"), True),
    Action(
        "remove_tracks", "Remove first track occurrences", "Playlists", ("playlist", "uris"), True
    ),
    Action(
        "remove_occurrences",
        "Remove exact playlist occurrences",
        "Playlists",
        ("playlist", "uids"),
        True,
    ),
    Action("delete_playlist", "Remove playlist from library", "Playlists", ("playlist",), True),
    Action("saved_contains", "Check saved items", "Library", ("uris",)),
    Action("saved_add", "Save items", "Library", ("uris",), True),
    Action("saved_remove", "Unsave items", "Library", ("uris",), True),
    Action("pin", "Pin a library item", "Library", ("uri",), True),
    Action("unpin", "Unpin a library item", "Library", ("uri",), True),
    Action("blend_create", "Create a Blend invitation", "Social", (), True),
    Action("blend_join", "Join a Blend", "Social", ("invitation",), True),
    Action("notifications_seen", "Acknowledge notifications", "Social", ("cursor",), True),
    Action("notifications_unread", "Check unread badge", "Social"),
    Action("lyrics", "Lyrics", "Player", ("uri",), authenticated=False),
    Action("play", "Play a Spotify link", "Player", ("uri",), True),
    Action("seek", "Seek in milliseconds", "Player", ("position_ms",), True),
    Action("volume", "Set volume · 0–100", "Player", ("percent",), True),
    Action("transfer", "Transfer playback", "Player", ("device",), True),
    Action("queue_add", "Add a track or episode to queue", "Player", ("uri",), True),
    Action("queue_remove", "Remove a queued occurrence", "Player", ("uid",), True),
    Action("queue_clear", "Clear manually queued tracks", "Player", (), True),
    Action("queue_replace", "Replace upcoming queue", "Player", ("uris",), True),
    Action("sleep", "Sleep timer · seconds", "Player", ("seconds",), True),
    Action("video", "Switch to video", "Player", (), True),
    Action("audio", "Switch to audio", "Player", (), True),
)


def manifest() -> list[dict[str, object]]:
    """Return the public form schema without exposing service internals."""
    return [asdict(action) for action in ACTIONS]
