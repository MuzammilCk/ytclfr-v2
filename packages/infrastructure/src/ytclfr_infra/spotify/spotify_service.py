"""Spotify Web API service for search and playlist creation."""

import asyncio
import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import SpotifyIntegrationError


@dataclass(slots=True)
class SpotifyTrack:
    """Normalized Spotify track candidate."""

    track_id: str
    uri: str
    name: str
    artists: list[str]
    popularity: int
    external_url: str | None


@dataclass(slots=True)
class TrackMatchResult:
    """Track resolution result for one query."""

    query: str
    status: str
    selected_track: SpotifyTrack | None
    candidates: list[SpotifyTrack]
    message: str


@dataclass(slots=True)
class PlaylistCreationResult:
    """Result payload for playlist creation workflow."""

    playlist_id: str
    playlist_url: str | None
    added_tracks: list[SpotifyTrack]
    not_found_queries: list[str]
    ambiguous_matches: list[TrackMatchResult]


class SpotifyService:
    """Service for Spotify authentication, search, and playlist operations."""

    def __init__(
        self,
        settings: Settings,
        *,
        max_retries: int = 3,
        default_search_limit: int = 5,
        ambiguity_margin: float = 3.0,
    ) -> None:
        if max_retries < 1:
            raise SpotifyIntegrationError("max_retries must be at least 1.")
        if default_search_limit < 1 or default_search_limit > 50:
            raise SpotifyIntegrationError("default_search_limit must be between 1 and 50.")
        self._settings = settings
        self._max_retries = int(max_retries)
        self._default_search_limit = int(default_search_limit)
        self._ambiguity_margin = float(ambiguity_margin)
        self._app_access_token: str | None = None
        self._app_token_expires_at: datetime | None = None

    async def authenticate(self) -> str:
        """Authenticate with client credentials flow and return app token."""
        if self._app_access_token and self._app_token_expires_at:
            if datetime.now(UTC) < self._app_token_expires_at:
                return self._app_access_token

        auth_raw = f"{self._settings.spotify_client_id}:{self._settings.spotify_client_secret}"
        auth_encoded = base64.b64encode(auth_raw.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = {"grant_type": "client_credentials"}
        response = await self._request(
            method="POST",
            url=self._settings.spotify_auth_url,
            headers=headers,
            data=body,
            requires_bearer=False,
        )
        payload = self._parse_json(response, context="spotify token")
        token = str(payload.get("access_token", "")).strip()
        if not token:
            raise SpotifyIntegrationError("Spotify token response missing access_token.")
        expires_in = int(payload.get("expires_in", 3600))
        self._app_access_token = token
        self._app_token_expires_at = datetime.now(UTC) + timedelta(
            seconds=max(60, expires_in - 30)
        )
        return token

    async def search_tracks(
        self,
        query: str,
        *,
        limit: int | None = None,
        access_token: str | None = None,
    ) -> list[SpotifyTrack]:
        """Search tracks by free-text query and return normalized candidates."""
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            raise SpotifyIntegrationError("Track search query cannot be empty.")
        search_limit = int(limit or self._default_search_limit)
        if search_limit < 1 or search_limit > 50:
            raise SpotifyIntegrationError("Track search limit must be between 1 and 50.")
        token = access_token or await self.authenticate()
        response = await self._request(
            method="GET",
            url=f"{self._settings.spotify_api_base_url.rstrip('/')}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": cleaned_query, "type": "track", "limit": search_limit},
            requires_bearer=True,
        )
        data = self._parse_json(response, context="spotify track search")
        items = data.get("tracks", {}).get("items", [])
        if not isinstance(items, list):
            return []
        return [self._to_spotify_track(item) for item in items if isinstance(item, dict)]

    async def resolve_track(
        self,
        query: str,
        *,
        access_token: str | None = None,
        limit: int | None = None,
    ) -> TrackMatchResult:
        """Resolve one query to a best candidate, handling not-found/ambiguous cases."""
        candidates = await self.search_tracks(query, limit=limit, access_token=access_token)
        if not candidates:
            return TrackMatchResult(
                query=query,
                status="not_found",
                selected_track=None,
                candidates=[],
                message="No tracks found for query.",
            )

        scored = sorted(
            ((self._score_candidate(query, candidate), candidate) for candidate in candidates),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best_track = scored[0]
        if best_score < 55.0:
            return TrackMatchResult(
                query=query,
                status="not_found",
                selected_track=None,
                candidates=candidates,
                message="No sufficiently relevant track match found.",
            )

        if len(scored) > 1:
            second_score, _ = scored[1]
            if (best_score - second_score) <= self._ambiguity_margin:
                return TrackMatchResult(
                    query=query,
                    status="ambiguous",
                    selected_track=best_track,
                    candidates=candidates,
                    message="Multiple close track matches found.",
                )

        return TrackMatchResult(
            query=query,
            status="matched",
            selected_track=best_track,
            candidates=candidates,
            message="Track resolved successfully.",
        )

    async def create_playlist(
        self,
        *,
        user_id: str,
        name: str,
        user_access_token: str,
        description: str | None = None,
        public: bool = False,
    ) -> tuple[str, str | None]:
        """Create a Spotify playlist and return playlist id/url."""
        cleaned_user_id = str(user_id or "").strip()
        cleaned_name = str(name or "").strip()
        token = str(user_access_token or "").strip()
        if not cleaned_user_id:
            raise SpotifyIntegrationError("user_id is required for playlist creation.")
        if not cleaned_name:
            raise SpotifyIntegrationError("Playlist name cannot be empty.")
        if not token:
            raise SpotifyIntegrationError(
                "User access token is required for playlist creation."
            )

        response = await self._request(
            method="POST",
            url=f"{self._settings.spotify_api_base_url.rstrip('/')}/users/{cleaned_user_id}/playlists",
            headers={"Authorization": f"Bearer {token}"},
            json_payload={
                "name": cleaned_name,
                "description": str(description or ""),
                "public": bool(public),
            },
            requires_bearer=True,
        )
        payload = self._parse_json(response, context="spotify create playlist")
        playlist_id = str(payload.get("id", "")).strip()
        if not playlist_id:
            raise SpotifyIntegrationError("Spotify playlist creation response missing id.")
        playlist_url = payload.get("external_urls", {}).get("spotify")
        return playlist_id, (str(playlist_url) if playlist_url else None)

    async def add_tracks_to_playlist(
        self,
        *,
        playlist_id: str,
        track_ids: list[str],
        user_access_token: str,
    ) -> None:
        """Add tracks to playlist in batches and validate response."""
        token = str(user_access_token or "").strip()
        cleaned_playlist_id = str(playlist_id or "").strip()
        if not cleaned_playlist_id:
            raise SpotifyIntegrationError("playlist_id is required to add tracks.")
        if not token:
            raise SpotifyIntegrationError("User access token is required to add tracks.")
        if not track_ids:
            return

        uris = [f"spotify:track:{tid.strip()}" for tid in track_ids if str(tid).strip()]
        if not uris:
            return

        endpoint = (
            f"{self._settings.spotify_api_base_url.rstrip('/')}/playlists/{cleaned_playlist_id}/tracks"
        )
        for start in range(0, len(uris), 100):
            batch = uris[start : start + 100]
            response = await self._request(
                method="POST",
                url=endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json_payload={"uris": batch},
                requires_bearer=True,
            )
            payload = self._parse_json(response, context="spotify add tracks")
            if "snapshot_id" not in payload:
                raise SpotifyIntegrationError(
                    "Spotify add-tracks response missing snapshot_id."
                )

    async def create_playlist_from_queries(
        self,
        *,
        user_id: str,
        user_access_token: str,
        playlist_name: str,
        track_queries: list[str],
        playlist_description: str | None = None,
        public: bool = False,
        search_limit: int | None = None,
        include_ambiguous: bool = False,
    ) -> PlaylistCreationResult:
        """Run full workflow: authenticate, search, create playlist, and add tracks."""
        token = str(user_access_token or "").strip()
        if not token:
            raise SpotifyIntegrationError(
                "User access token is required for playlist creation flow."
            )
        if not track_queries:
            raise SpotifyIntegrationError("At least one track query is required.")

        matched_tracks: list[SpotifyTrack] = []
        ambiguous_matches: list[TrackMatchResult] = []
        not_found_queries: list[str] = []

        for query in track_queries:
            resolved = await self.resolve_track(
                query=query,
                access_token=token,
                limit=search_limit,
            )
            if resolved.status == "matched" and resolved.selected_track is not None:
                matched_tracks.append(resolved.selected_track)
                continue
            if resolved.status == "ambiguous":
                ambiguous_matches.append(resolved)
                if include_ambiguous and resolved.selected_track is not None:
                    matched_tracks.append(resolved.selected_track)
                continue
            not_found_queries.append(query)

        playlist_id, playlist_url = await self.create_playlist(
            user_id=user_id,
            name=playlist_name,
            user_access_token=token,
            description=playlist_description,
            public=public,
        )
        await self.add_tracks_to_playlist(
            playlist_id=playlist_id,
            track_ids=[track.track_id for track in matched_tracks],
            user_access_token=token,
        )
        return PlaylistCreationResult(
            playlist_id=playlist_id,
            playlist_url=playlist_url,
            added_tracks=matched_tracks,
            not_found_queries=not_found_queries,
            ambiguous_matches=ambiguous_matches,
        )

    async def _request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        requires_bearer: bool,
    ) -> httpx.Response:
        """Execute HTTP request with retry handling for rate limits and transient failures."""
        timeout = self._settings.spotify_timeout_seconds
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        data=data,
                        json=json_payload,
                    )
                if response.status_code == 429:
                    await self._handle_rate_limit(response=response, attempt=attempt)
                    continue
                if response.status_code >= 500:
                    if attempt >= self._max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(min(5, attempt))
                    continue
                if response.status_code in {401, 403} and requires_bearer:
                    raise SpotifyIntegrationError(
                        "Spotify authorization failed; token may be invalid or missing scopes."
                    )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if attempt >= self._max_retries:
                    raise SpotifyIntegrationError(
                        f"Spotify API request failed: {exc.response.status_code}"
                    ) from exc
                await asyncio.sleep(min(5, attempt))
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise SpotifyIntegrationError("Spotify network request failed.") from exc
                await asyncio.sleep(min(5, attempt))
        raise SpotifyIntegrationError("Spotify request failed after retries.")

    async def _handle_rate_limit(self, response: httpx.Response, attempt: int) -> None:
        """Sleep according to retry-after header for 429 handling."""
        if attempt >= self._max_retries:
            raise SpotifyIntegrationError("Spotify rate limit exceeded after retries.")
        retry_after_header = response.headers.get("Retry-After", "1").strip()
        try:
            retry_after_seconds = max(1, int(retry_after_header))
        except ValueError:
            retry_after_seconds = 1
        await asyncio.sleep(retry_after_seconds)

    def _parse_json(self, response: httpx.Response, *, context: str) -> dict[str, Any]:
        """Safely parse JSON response into dict."""
        try:
            data = response.json()
        except ValueError as exc:
            raise SpotifyIntegrationError(f"Invalid JSON response from {context}.") from exc
        if not isinstance(data, dict):
            raise SpotifyIntegrationError(f"Unexpected response type from {context}.")
        return data

    def _to_spotify_track(self, item: dict[str, Any]) -> SpotifyTrack:
        """Convert Spotify API track object into normalized dataclass."""
        artists = []
        raw_artists = item.get("artists", [])
        if isinstance(raw_artists, list):
            artists = [
                str(artist.get("name", "")).strip()
                for artist in raw_artists
                if isinstance(artist, dict) and str(artist.get("name", "")).strip()
            ]
        return SpotifyTrack(
            track_id=str(item.get("id", "")).strip(),
            uri=str(item.get("uri", "")).strip(),
            name=str(item.get("name", "")).strip(),
            artists=artists,
            popularity=int(item.get("popularity", 0) or 0),
            external_url=(
                str(item.get("external_urls", {}).get("spotify", "")).strip() or None
            ),
        )

    def _score_candidate(self, query: str, track: SpotifyTrack) -> float:
        """Score candidate match using query similarity and popularity."""
        cleaned_query = query.strip().lower()
        name_text = track.name.lower()
        artist_text = " ".join(track.artists).lower()
        joined = f"{name_text} {artist_text}".strip()

        title_score = SequenceMatcher(None, cleaned_query, name_text).ratio() * 100.0
        combined_score = SequenceMatcher(None, cleaned_query, joined).ratio() * 100.0
        popularity_bonus = min(5.0, track.popularity / 20.0)
        return max(title_score, combined_score) + popularity_bonus


class SpotifyClient(SpotifyService):
    """Backward-compatible alias for existing imports."""

    async def search_track(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Legacy return shape for search endpoint results."""
        tracks = await self.search_tracks(query=query, limit=limit)
        return [
            {
                "id": track.track_id,
                "name": track.name,
                "artists": [{"name": artist} for artist in track.artists],
                "uri": track.uri,
                "external_urls": {"spotify": track.external_url},
                "popularity": track.popularity,
            }
            for track in tracks
        ]

