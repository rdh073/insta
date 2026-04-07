from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load test env vars before any module-level code in the app reads os.environ.
# override=False so a real shell export always wins over the file.
_env_test = ROOT / ".env.test"
if _env_test.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_test, override=False)


if "instagrapi" not in sys.modules:
    instagrapi = types.ModuleType("instagrapi")
    instagrapi.__path__ = []  # make it look like a package
    exceptions = types.ModuleType("instagrapi.exceptions")
    ig_types = types.ModuleType("instagrapi.types")

    class Client:
        pass

    class LoginRequired(Exception):
        pass

    class BadPassword(Exception):
        pass

    class ReloginAttemptExceeded(Exception):
        pass

    class TwoFactorRequired(Exception):
        pass

    # Minimal type stubs used in instagram adapters
    class _StubType:
        def __init__(self, *args, **kwargs):
            pass

    for _name in (
        "StoryHashtag", "StoryLink", "StoryMedia", "StoryMention",
        "StoryPoll", "StorySticker", "StoryLocation",
        "UserShort", "Usertag", "Location", "Media", "User",
        "Story", "DirectThread", "Track", "Highlight", "Account",
    ):
        setattr(ig_types, _name, type(_name, (), {}))

    instagrapi.Client = Client
    exceptions.LoginRequired = LoginRequired
    exceptions.BadPassword = BadPassword
    exceptions.ReloginAttemptExceeded = ReloginAttemptExceeded
    exceptions.TwoFactorRequired = TwoFactorRequired

    sys.modules["instagrapi"] = instagrapi
    sys.modules["instagrapi.exceptions"] = exceptions
    sys.modules["instagrapi.types"] = ig_types

if "pyotp" not in sys.modules:
    pyotp = types.ModuleType("pyotp")

    class _TOTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def now(self):
            return "000000"

        def verify(self, *_args, **_kwargs):
            return True

        @property
        def secret(self):
            return "BASE32SECRET"

        def provisioning_uri(self, *_args, **_kwargs):
            return "otpauth://totp/stub"

    pyotp.TOTP = _TOTP
    pyotp.random_base32 = lambda: "BASE32SECRET"
    sys.modules["pyotp"] = pyotp


@pytest.fixture(autouse=True)
def isolated_backend_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import instagram
    import services
    import state

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    log_file = sessions_dir / "activity.log"

    monkeypatch.setattr(state, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(state, "LOG_FILE", log_file)
    monkeypatch.setattr(instagram, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(services, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(services, "LOG_FILE", log_file)

    state.clear_state()

    yield

    state.clear_state()
