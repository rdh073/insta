"""Direct use cases - application orchestration for Instagram DM operations.

Owns precondition enforcement, input validation, and application-level policy
for direct message thread/message operations.

Integrates with IdentityUseCases for username-to-user-id resolution, keeping the
resolution seam inside the application layer (not in router or adapter).

NAMING RULE: All methods use direct_thread_id and direct_message_id to avoid
collision with workflow thread_id used by AI graph execution.

Policy owned here (not in router or adapter):
  - direct_thread_id and direct_message_id must be non-empty strings (via domain value objects)
  - text for send must not be empty (stripped) (via domain value objects)
  - query for search must not be empty (stripped) (via domain value objects)
  - participant_user_ids and user_ids must not be empty, all positive integers (via UserIDList)
  - amount must be >= 1 (explicit guard; value object is not constructed redundantly)
  - thread_message_limit must be >= 1 (explicit guard; value object is not constructed redundantly)
  - username resolution goes through IdentityUseCases.get_public_user_by_username
"""

from __future__ import annotations

from app.application.dto.instagram_direct_dto import (
    DirectThreadSummary,
    DirectThreadDetail,
    DirectMessageSummary,
    DirectActionReceipt,
)
from app.application.ports.instagram_direct import (
    InstagramDirectReader,
    InstagramDirectWriter,
)
from app.application.ports.repositories import AccountRepository, ClientRepository
from app.application.use_cases.identity import IdentityUseCases
from app.domain.direct import (
    InvalidIdentifier,
    InvalidComposite,
    DirectThreadID,
    DirectMessageID,
    SearchQuery,
    UserIDList,
    CommentText,  # Reused for message text validation (CommentText and message text share same rules)
)


class DirectUseCases:
    """Application orchestration for Instagram direct message operations.

    Owns precondition enforcement (account exists, authenticated),
    thread/message ID validation, text and query normalization,
    and username-to-user-id resolution via IdentityUseCases.
    The underlying ports handle vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        direct_reader: InstagramDirectReader,
        direct_writer: InstagramDirectWriter,
        identity_use_cases: IdentityUseCases,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.direct_reader = direct_reader
        self.direct_writer = direct_writer
        self.identity_use_cases = identity_use_cases

    # -------------------------------------------------------------------------
    # Precondition helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def list_inbox_threads(
        self,
        account_id: str,
        amount: int = 20,
        filter_name: str = "",
        thread_message_limit: int = 10,
    ) -> list[DirectThreadSummary]:
        """List threads in the inbox.

        Args:
            account_id: Application account ID.
            amount: Maximum threads to retrieve (>= 1).
            filter_name: Optional filter string (e.g. "unread"). Empty = no filter.
            thread_message_limit: Messages per thread summary (>= 1).

        Returns:
            List of DirectThreadSummary.

        Raises:
            ValueError: If account not found, not authenticated, amount < 1,
                        or thread_message_limit < 1.
        """
        self._require_authenticated(account_id)
        if not isinstance(amount, int) or amount < 1:
            raise ValueError(f"amount must be a positive integer, got {amount!r}")
        if not isinstance(thread_message_limit, int) or thread_message_limit < 1:
            raise ValueError(
                "thread_message_limit must be a positive integer, "
                f"got {thread_message_limit!r}"
            )
        return self.direct_reader.list_inbox_threads(
            account_id, amount, filter_name, thread_message_limit
        )

    def list_pending_threads(
        self,
        account_id: str,
        amount: int = 20,
    ) -> list[DirectThreadSummary]:
        """List pending direct message requests.

        Args:
            account_id: Application account ID.
            amount: Maximum threads to retrieve (>= 1).

        Returns:
            List of DirectThreadSummary marked as pending.

        Raises:
            ValueError: If account not found, not authenticated, or amount < 1.
        """
        self._require_authenticated(account_id)
        if not isinstance(amount, int) or amount < 1:
            raise ValueError(f"amount must be a positive integer, got {amount!r}")
        return self.direct_reader.list_pending_threads(account_id, amount)

    def get_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        amount: int = 20,
    ) -> DirectThreadDetail:
        """Get a specific thread with messages.

        Args:
            account_id: Application account ID.
            direct_thread_id: Instagram direct thread ID (must not be empty).
            amount: Maximum messages to retrieve (>= 1).

        Returns:
            DirectThreadDetail with summary and messages.

        Raises:
            ValueError: If account not found, not authenticated, thread ID empty,
                        or amount < 1.
        """
        self._require_authenticated(account_id)
        if not isinstance(amount, int) or amount < 1:
            raise ValueError(f"amount must be a positive integer, got {amount!r}")
        try:
            tid = DirectThreadID(direct_thread_id)
            return self.direct_reader.get_thread(account_id, str(tid), amount)
        except InvalidIdentifier:
            raise ValueError(
                f"direct_thread_id must not be empty, got {direct_thread_id!r}"
            )

    def list_messages(
        self,
        account_id: str,
        direct_thread_id: str,
        amount: int = 20,
    ) -> list[DirectMessageSummary]:
        """List messages for a thread.

        Args:
            account_id: Application account ID.
            direct_thread_id: Instagram direct thread ID (must not be empty).
            amount: Maximum messages to retrieve (>= 1).

        Returns:
            List of DirectMessageSummary.

        Raises:
            ValueError: If account not found, not authenticated, thread ID empty,
                        or amount < 1.
        """
        self._require_authenticated(account_id)
        if not isinstance(amount, int) or amount < 1:
            raise ValueError(f"amount must be a positive integer, got {amount!r}")
        try:
            tid = DirectThreadID(direct_thread_id)
            return self.direct_reader.list_messages(account_id, str(tid), amount)
        except InvalidIdentifier:
            raise ValueError(
                f"direct_thread_id must not be empty, got {direct_thread_id!r}"
            )

    def search_threads(
        self,
        account_id: str,
        query: str,
    ) -> list[DirectThreadSummary]:
        """Search direct message threads by query.

        Args:
            account_id: Application account ID.
            query: Search query (must not be empty after stripping).

        Returns:
            List of matching DirectThreadSummary.

        Raises:
            ValueError: If account not found, not authenticated, or query is empty.
        """
        self._require_authenticated(account_id)
        try:
            sq = SearchQuery(query)
            return self.direct_reader.search_threads(account_id, str(sq))
        except InvalidComposite as e:
            raise ValueError(f"query must not be empty, got {query!r}") from e

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def find_or_create_thread(
        self,
        account_id: str,
        participant_user_ids: list[int],
    ) -> DirectThreadSummary:
        """Find existing thread or create a new one with participants.

        Args:
            account_id: Application account ID.
            participant_user_ids: User IDs for thread participants
                                  (must not be empty, all positive integers).

        Returns:
            DirectThreadSummary of found or created thread.

        Raises:
            ValueError: If account not found, not authenticated, or participant_user_ids invalid.
        """
        self._require_authenticated(account_id)
        try:
            uidlist = UserIDList(participant_user_ids)
            return self.direct_writer.find_or_create_thread(account_id, list(uidlist))
        except InvalidComposite as e:
            if not participant_user_ids:
                raise ValueError("participant_user_ids must not be empty") from e
            raise ValueError(
                f"all participant_user_ids must be positive integers, got {participant_user_ids!r}"
            ) from e

    def find_or_create_thread_with_usernames(
        self,
        account_id: str,
        usernames: list[str],
    ) -> DirectThreadSummary:
        """Find or create a thread, resolving usernames to user IDs first.

        Uses IdentityUseCases for resolution. Resolves each username and
        delegates to find_or_create_thread with resolved IDs.

        Args:
            account_id: Application account ID.
            usernames: Instagram usernames to resolve (must not be empty).
                       Leading '@' is stripped automatically.

        Returns:
            DirectThreadSummary of found or created thread.

        Raises:
            ValueError: If account not found, not authenticated, usernames empty,
                        or any username cannot be resolved.
        """
        self._require_authenticated(account_id)
        if not usernames:
            raise ValueError("usernames must not be empty")
        user_ids = [
            self.identity_use_cases.get_public_user_by_username(account_id, username).pk
            for username in usernames
        ]
        return self.direct_writer.find_or_create_thread(account_id, user_ids)

    def send_to_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        text: str,
    ) -> DirectMessageSummary:
        """Send a message to an existing thread.

        Args:
            account_id: Application account ID.
            direct_thread_id: Instagram direct thread ID (must not be empty).
            text: Message text (must not be empty after stripping).

        Returns:
            DirectMessageSummary of sent message.

        Raises:
            ValueError: If account not found, not authenticated, thread ID empty,
                        or text empty.
        """
        self._require_authenticated(account_id)
        try:
            tid = DirectThreadID(direct_thread_id)
            msg_text = CommentText(
                text
            )  # Reuse CommentText for message text (same rules)
            return self.direct_writer.send_to_thread(
                account_id, str(tid), str(msg_text)
            )
        except (InvalidIdentifier, InvalidComposite) as e:
            err_msg = str(e).lower()
            if "directthreadid" in err_msg:
                raise ValueError(
                    f"direct_thread_id must not be empty, got {direct_thread_id!r}"
                ) from e
            raise ValueError(f"text must not be empty, got {text!r}") from e

    def send_to_users(
        self,
        account_id: str,
        user_ids: list[int],
        text: str,
    ) -> DirectMessageSummary:
        """Send a message to one or more users (creates thread if needed).

        Args:
            account_id: Application account ID.
            user_ids: User IDs to message (must not be empty, all positive integers).
            text: Message text (must not be empty after stripping).

        Returns:
            DirectMessageSummary of sent message.

        Raises:
            ValueError: If account not found, not authenticated, user_ids invalid,
                        or text empty.
        """
        self._require_authenticated(account_id)
        try:
            uidlist = UserIDList(user_ids)
            msg_text = CommentText(text)  # Reuse CommentText for message text
            return self.direct_writer.send_to_users(
                account_id, list(uidlist), str(msg_text)
            )
        except (InvalidIdentifier, InvalidComposite) as e:
            err_msg = str(e).lower()
            if "useridlist" in err_msg:
                if not user_ids:
                    raise ValueError("user_ids must not be empty") from e
                raise ValueError(
                    f"all user_ids must be positive integers, got {user_ids!r}"
                ) from e
            raise ValueError(f"text must not be empty, got {text!r}") from e

    def send_to_username(
        self,
        account_id: str,
        username: str,
        text: str,
    ) -> DirectMessageSummary:
        """Send a message to a user by username (resolves username to user ID).

        Uses IdentityUseCases to resolve the username before sending.

        Args:
            account_id: Application account ID.
            username: Instagram username (leading '@' stripped automatically).
            text: Message text (must not be empty after stripping).

        Returns:
            DirectMessageSummary of sent message.

        Raises:
            ValueError: If account not found, not authenticated, username empty,
                        text empty, or username cannot be resolved.
        """
        self._require_authenticated(account_id)
        try:
            msg_text = CommentText(text)  # Reuse CommentText for message text
            profile = self.identity_use_cases.get_public_user_by_username(
                account_id, username
            )
            return self.direct_writer.send_to_users(
                account_id, [profile.pk], str(msg_text)
            )
        except InvalidComposite as e:
            raise ValueError(f"text must not be empty, got {text!r}") from e

    def delete_message(
        self,
        account_id: str,
        direct_thread_id: str,
        direct_message_id: str,
    ) -> DirectActionReceipt:
        """Delete a message from a thread.

        Args:
            account_id: Application account ID.
            direct_thread_id: Instagram direct thread ID (must not be empty).
            direct_message_id: Message ID to delete (must not be empty).

        Returns:
            DirectActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, or either ID empty.
        """
        self._require_authenticated(account_id)
        try:
            tid = DirectThreadID(direct_thread_id)
            mid = DirectMessageID(direct_message_id)
            return self.direct_writer.delete_message(account_id, str(tid), str(mid))
        except InvalidIdentifier as e:
            err_msg = str(e).lower()
            if "directmessageid" in err_msg:
                raise ValueError(
                    f"direct_message_id must not be empty, got {direct_message_id!r}"
                ) from e
            raise ValueError(
                f"direct_thread_id must not be empty, got {direct_thread_id!r}"
            ) from e

    def approve_pending_thread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Approve a pending DM request, moving it to the main inbox.

        Args:
            account_id: Application account ID.
            direct_thread_id: Pending thread ID (must not be empty).

        Returns:
            DirectActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, or thread ID empty.
        """
        self._require_authenticated(account_id)
        try:
            tid = DirectThreadID(direct_thread_id)
            return self.direct_writer.approve_pending_thread(account_id, str(tid))
        except InvalidIdentifier:
            raise ValueError(
                f"direct_thread_id must not be empty, got {direct_thread_id!r}"
            )

    def mark_thread_seen(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Mark the most recent message in a thread as seen.

        Args:
            account_id: Application account ID.
            direct_thread_id: Thread ID (must not be empty).

        Returns:
            DirectActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, or thread ID empty.
        """
        self._require_authenticated(account_id)
        try:
            tid = DirectThreadID(direct_thread_id)
            return self.direct_writer.mark_thread_seen(account_id, str(tid))
        except InvalidIdentifier:
            raise ValueError(
                f"direct_thread_id must not be empty, got {direct_thread_id!r}"
            )
