"""Named editorial playlists; Spotify may retire or replace their inventory."""

from .models.discovery import Chart

_CHARTS = (
    Chart("top-50-global", "Top 50 - Global", "37i9dQZEVXbMDoHDwVN2tF"),
    Chart("top-50-usa", "Top 50 - USA", "37i9dQZEVXbLRQDuF5jeBp"),
    Chart("top-songs-global", "Top Songs - Global", "37i9dQZEVXbNG2KDcFcKOF"),
    Chart("todays-top-hits", "Today's Top Hits", "37i9dQZF1DXcBWIGoYBM5M"),
)


def list_charts() -> tuple[Chart, ...]:
    """List built-in shortcuts without making requests; availability is not guaranteed."""
    return _CHARTS


def chart(key: str) -> Chart:
    for definition in _CHARTS:
        if definition.key == key:
            return definition
    raise ValueError(f"Unknown chart {key!r}; choose one of {', '.join(c.key for c in _CHARTS)}")
