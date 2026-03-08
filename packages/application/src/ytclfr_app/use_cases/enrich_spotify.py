"""Use case boundary for Spotify enrichment."""

from ytclfr_core.errors.exceptions import SpotifyIntegrationError
from ytclfr_domain.entities.spotify_item import SpotifyItem


class EnrichSpotifyUseCase:
    """Match knowledge items to Spotify metadata where possible."""

    def execute(self, query: str) -> list[SpotifyItem]:
        """Placeholder implementation for Spotify enrichment."""
        try:
            _ = query
            return []
        except Exception as exc:
            raise SpotifyIntegrationError("Spotify enrichment failed.") from exc
