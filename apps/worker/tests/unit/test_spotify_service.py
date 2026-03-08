"""Unit tests for Spotify playlist workflow logic."""

import asyncio
import json

import pytest

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import SpotifyIntegrationError
from ytclfr_infra.spotify.spotify_service import SpotifyService, SpotifyTrack


def _build_settings() -> Settings:
    """Create deterministic settings object for Spotify tests."""
    return Settings.model_validate(
        {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "INFO",
            "API_PORT": 8000,
            "DATABASE_URL": "postgresql+psycopg://ytclfr:ytclfr@127.0.0.1:5432/ytclfr",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "OPENROUTER_API_KEY": "test_api_key_123",
            "SPOTIFY_CLIENT_ID": "client_id",
            "SPOTIFY_CLIENT_SECRET": "client_secret_123",
            "STORAGE_PATH": "./storage",
            "MAX_VIDEO_DURATION": 3600,
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_MODEL": "openai/gpt-4o-mini",
            "OPENROUTER_TIMEOUT_SECONDS": 30,
            "SPOTIFY_AUTH_URL": "https://accounts.spotify.com/api/token",
            "SPOTIFY_API_BASE_URL": "https://api.spotify.com/v1",
            "SPOTIFY_TIMEOUT_SECONDS": 30,
        }
    )


def test_resolve_track_not_found(monkeypatch) -> None:
    """resolve_track should return not_found when no candidates exist."""
    service = SpotifyService(_build_settings())

    async def fake_search_tracks(query: str, *, limit: int | None, access_token: str | None):
        _ = (query, limit, access_token)
        return []

    monkeypatch.setattr(service, "search_tracks", fake_search_tracks)
    result = asyncio.run(service.resolve_track("missing song"))

    assert result.status == "not_found"
    assert result.selected_track is None


def test_resolve_track_ambiguous(monkeypatch) -> None:
    """resolve_track should report ambiguity for close top candidates."""
    service = SpotifyService(_build_settings(), ambiguity_margin=5.0)
    tracks = [
        SpotifyTrack(
            track_id="id1",
            uri="spotify:track:id1",
            name="Hello World",
            artists=["Artist A"],
            popularity=90,
            external_url=None,
        ),
        SpotifyTrack(
            track_id="id2",
            uri="spotify:track:id2",
            name="Hello Worlds",
            artists=["Artist A"],
            popularity=89,
            external_url=None,
        ),
    ]

    async def fake_search_tracks(query: str, *, limit: int | None, access_token: str | None):
        _ = (query, limit, access_token)
        return tracks

    monkeypatch.setattr(service, "search_tracks", fake_search_tracks)
    result = asyncio.run(service.resolve_track("hello world"))

    assert result.status == "ambiguous"
    assert result.selected_track is not None
    assert len(result.candidates) == 2


def test_create_playlist_requires_user_token() -> None:
    """Playlist creation should reject missing user token."""
    service = SpotifyService(_build_settings())

    with pytest.raises(SpotifyIntegrationError):
        asyncio.run(
            service.create_playlist(
                user_id="user123",
                name="My Playlist",
                user_access_token="",
            )
        )

