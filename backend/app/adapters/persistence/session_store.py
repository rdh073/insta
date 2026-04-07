"""Session file storage adapter."""

from __future__ import annotations

from pathlib import Path
import json

from .state_gateway import default_state_gateway


class SessionStore:
    """Manages Instagram session files."""

    def __init__(self, sessions_dir: Path = None, gateway=default_state_gateway):
        self.gateway = gateway
        self.sessions_dir = sessions_dir or self.gateway.sessions_dir

    def save_session(self, username: str, session_data: dict) -> None:
        """Save session file for a username."""
        session_file = self.sessions_dir / f"{username}.json"
        session_file.write_text(json.dumps(session_data))

    def load_session(self, username: str) -> dict:
        """Load session file for a username."""
        session_file = self.sessions_dir / f"{username}.json"
        if session_file.exists():
            return json.loads(session_file.read_text())
        return {}

    def delete_session(self, username: str) -> None:
        """Delete session file for a username if it exists."""
        session_file = self.sessions_dir / f"{username}.json"
        try:
            session_file.unlink(missing_ok=True)
        except OSError:
            pass

    def export_all_sessions(self) -> dict:
        """Export all session files as a dict."""
        sessions = {}
        for p in self.sessions_dir.glob("*.json"):
            try:
                sessions[p.stem] = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        return sessions

    def import_sessions(self, sessions: dict) -> None:
        """Import multiple session files."""
        for username, session_data in sessions.items():
            self.save_session(username, session_data)
