"""Unit tests for final action generation by content type."""

import asyncio

from ytclfr_core.config import Settings
from ytclfr_infra.ai.action_engine import ActionEngine
from ytclfr_infra.spotify.spotify_service import (
    PlaylistCreationResult,
    SpotifyTrack,
    TrackMatchResult,
)


def _build_settings(
    *,
    spotify_user_id: str | None = None,
    spotify_user_access_token: str | None = None,
) -> Settings:
    """Create deterministic settings object for action engine tests."""
    payload = {
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
        "TMDB_WEB_BASE_URL": "https://www.themoviedb.org",
        "GOODREADS_WEB_BASE_URL": "https://www.goodreads.com",
    }
    if spotify_user_id is not None:
        payload["SPOTIFY_USER_ID"] = spotify_user_id
    if spotify_user_access_token is not None:
        payload["SPOTIFY_USER_ACCESS_TOKEN"] = spotify_user_access_token
    return Settings.model_validate(payload)


class _FakeSpotifyService:
    """Minimal fake Spotify service for music action tests."""

    async def create_playlist_from_queries(
        self,
        *,
        user_id: str,
        user_access_token: str,
        playlist_name: str,
        track_queries: list[str],
        playlist_description: str | None,
        public: bool,
        include_ambiguous: bool,
    ) -> PlaylistCreationResult:
        _ = (
            user_id,
            user_access_token,
            playlist_name,
            track_queries,
            playlist_description,
            public,
            include_ambiguous,
        )
        return PlaylistCreationResult(
            playlist_id="playlist_123",
            playlist_url="https://open.spotify.com/playlist/playlist_123",
            added_tracks=[
                SpotifyTrack(
                    track_id="track_1",
                    uri="spotify:track:track_1",
                    name="Song A",
                    artists=["Artist A"],
                    popularity=60,
                    external_url="https://open.spotify.com/track/track_1",
                )
            ],
            not_found_queries=["unknown song"],
            ambiguous_matches=[
                TrackMatchResult(
                    query="ambiguous",
                    status="ambiguous",
                    selected_track=None,
                    candidates=[],
                    message="Multiple close track matches found.",
                )
            ],
        )


def test_recipe_action_output() -> None:
    """Recipe type should generate structured recipe JSON payload."""
    engine = ActionEngine(settings=_build_settings())
    parsed_payload = {
        "video_type": "recipe",
        "structured_data": {
            "recipe": {
                "dish_name": "Pasta",
                "ingredients": ["Tomato", "Salt"],
                "steps": ["Boil water", "Cook pasta"],
            }
        },
    }

    result = asyncio.run(engine.generate(parsed_payload))

    assert result["action_type"] == "recipe_json"
    assert result["status"] == "completed"
    assert result["payload"]["recipe"]["dish_name"] == "Pasta"


def test_movie_action_links() -> None:
    """Movie type should generate TMDB links."""
    engine = ActionEngine(settings=_build_settings())
    parsed_payload = {
        "video_type": "movie",
        "structured_data": {"movie": {"title": "Inception", "characters": ["Cobb"]}},
    }

    result = asyncio.run(engine.generate(parsed_payload))

    assert result["action_type"] == "tmdb_links"
    assert result["status"] == "completed"
    assert len(result["payload"]["links"]) >= 1
    assert result["payload"]["links"][0]["url"].startswith("https://www.themoviedb.org")


def test_books_action_links() -> None:
    """Books type should generate Goodreads links."""
    engine = ActionEngine(settings=_build_settings())
    parsed_payload = {
        "video_type": "books",
        "structured_data": {"books": {"title": "Atomic Habits", "author": "James Clear"}},
    }

    result = asyncio.run(engine.generate(parsed_payload))

    assert result["action_type"] == "goodreads_links"
    assert result["status"] == "completed"
    assert len(result["payload"]["links"]) >= 1
    assert result["payload"]["links"][0]["url"].startswith("https://www.goodreads.com")


def test_music_action_skips_without_user_token() -> None:
    """Music type should skip playlist creation when user token is missing."""
    engine = ActionEngine(settings=_build_settings())
    parsed_payload = {
        "video_type": "music",
        "entities": ["Song A Artist A"],
        "structured_data": {"music": {"title": "Song A", "artist": "Artist A"}},
    }

    result = asyncio.run(engine.generate(parsed_payload))

    assert result["action_type"] == "spotify_playlist"
    assert result["status"] == "skipped"
    assert "Spotify user credentials" in (result["message"] or "")


def test_music_action_completed_with_spotify_service() -> None:
    """Music type should return completed action when playlist is created."""
    engine = ActionEngine(
        settings=_build_settings(
            spotify_user_id="user_1",
            spotify_user_access_token="token_1",
        ),
        spotify_service=_FakeSpotifyService(),
    )
    parsed_payload = {
        "video_type": "music",
        "entities": ["Song A Artist A", "unknown song", "ambiguous"],
        "structured_data": {"music": {"title": "Song A", "artist": "Artist A"}},
    }

    result = asyncio.run(engine.generate(parsed_payload, video_title="Music Video"))

    assert result["action_type"] == "spotify_playlist"
    assert result["status"] == "completed"
    assert result["payload"]["playlist_id"] == "playlist_123"
    assert result["payload"]["added_tracks"][0]["track_id"] == "track_1"

