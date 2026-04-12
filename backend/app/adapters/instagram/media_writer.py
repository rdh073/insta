"""Instagram media writer adapter.

Maps like/unlike mutations through instagrapi into the
InstagramMediaWriter port.
"""

from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramMediaWriterAdapter:
    """Adapter for Instagram media like/unlike mutations."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def like_media(self, account_id: str, media_id: str) -> bool:
        """Like a post via instagrapi."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            return client.media_like(media_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="media_like",
                account_id=account_id,
            )
            raise ValueError(failure.user_message)

    def unlike_media(self, account_id: str, media_id: str) -> bool:
        """Remove a like from a post via instagrapi."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            return client.media_unlike(media_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="media_unlike",
                account_id=account_id,
            )
            raise ValueError(failure.user_message)
