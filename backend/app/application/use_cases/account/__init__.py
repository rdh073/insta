"""Account use cases package.

This package splits the original monolithic account.py into focused modules:
- auth.py: Login, 2FA, logout
- relogin.py: Single and bulk relogin with concurrency control
- profile.py: Account listing, info, proxy management
- totp.py: TOTP setup and management
- imports.py: Text and session archive imports
- facade.py: Compatibility facade preserving the original AccountUseCases API

The facade is the public interface - import AccountUseCases from here.
"""

from .facade import AccountUseCases

__all__ = ["AccountUseCases"]
