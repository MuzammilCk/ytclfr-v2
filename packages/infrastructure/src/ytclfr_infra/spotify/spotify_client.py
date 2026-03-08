"""Backward-compatible Spotify client exports."""

from ytclfr_infra.spotify.spotify_service import (
    PlaylistCreationResult,
    SpotifyClient,
    SpotifyService,
    SpotifyTrack,
    TrackMatchResult,
)

__all__ = [
    "PlaylistCreationResult",
    "SpotifyClient",
    "SpotifyService",
    "SpotifyTrack",
    "TrackMatchResult",
]
