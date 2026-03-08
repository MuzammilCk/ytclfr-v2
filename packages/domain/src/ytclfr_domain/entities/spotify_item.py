"""Domain entity for Spotify enrichment output."""

from dataclasses import dataclass


@dataclass(slots=True)
class SpotifyItem:
    """Represents a Spotify track matched from parsed content."""

    track_id: str
    name: str
    artist: str
    url: str
