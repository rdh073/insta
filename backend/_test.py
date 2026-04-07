"""
Debug script: test real Instagram login using accounts.json credentials.
Calls IGClient directly with full instagrapi HTTP logging so we can see
exactly which endpoint hangs.

Run from backend/ with the virtualenv active:

    cd backend
    source .venv/bin/activate
    python _test.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

# ── Enable instagrapi's own HTTP-level logger ─────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
# Quiet noisy libs, keep only instagrapi's private API calls
for noisy in ("urllib3", "httpx", "httpcore", "PIL"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

ACCOUNTS_FILE = Path(__file__).parent / "sessions" / "accounts.json"
SESSIONS_DIR  = Path(__file__).parent / "sessions"


def load_accounts() -> dict:
    if not ACCOUNTS_FILE.exists():
        print(f"[ERROR] accounts.json not found at {ACCOUNTS_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(ACCOUNTS_FILE) as f:
        return json.load(f)


def test_login(account_id: str, meta: dict) -> None:
    from instagrapi import Client as IGClient
    from instagrapi.exceptions import TwoFactorRequired, BadPassword, ChallengeRequired
    from app.adapters.instagram.device_pool import random_device_profile

    username    = meta.get("username", "")
    password    = meta.get("password", "")
    proxy       = meta.get("proxy")
    totp_secret = meta.get("totp_secret")
    session_file = SESSIONS_DIR / f"{username}.json"

    print(f"\n{'='*60}")
    print(f"  Account : @{username}  (id={account_id})")
    print(f"  Proxy   : {proxy or '(none)'}")
    print(f"  TOTP    : {'yes' if totp_secret else 'no'}")
    print(f"  Session : {'exists' if session_file.exists() else 'none (fresh login)'}")
    print(f"{'='*60}\n")

    if totp_secret:
        import pyotp
        code = pyotp.TOTP(totp_secret).now()
        print(f"[totp] Generated code: {code}  (valid ~{30 - int(time.time()) % 30}s more)\n")
    else:
        code = ""

    # Build a fresh client exactly as _new_client() does
    cl = IGClient()
    cl.request_timeout = 60
    if proxy:
        cl.set_proxy(proxy)
    device, ua = random_device_profile()
    cl.set_device(device)
    cl.set_user_agent(ua)

    t0 = time.perf_counter()

    try:
        print(f"[step 1] cl.login({username!r}, '***', verification_code={code!r})")
        cl.login(username, password, verification_code=code)
        elapsed = time.perf_counter() - t0
        print(f"\n[OK] login() succeeded in {elapsed:.2f}s  user_id={cl.user_id}")

    except TwoFactorRequired as e:
        elapsed = time.perf_counter() - t0
        print(f"\n[2FA] TwoFactorRequired after {elapsed:.2f}s: {e}")
        print("      → totp_secret was passed but Instagram still requires manual 2FA")
        return

    except BadPassword as e:
        elapsed = time.perf_counter() - t0
        print(f"\n[ERR] BadPassword after {elapsed:.2f}s: {e}")
        return

    except ChallengeRequired as e:
        elapsed = time.perf_counter() - t0
        print(f"\n[ERR] ChallengeRequired after {elapsed:.2f}s: {e}")
        print(f"      last_json = {json.dumps(getattr(cl, 'last_json', {}), indent=2)}")
        return

    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"\n[ERR] {type(e).__name__} after {elapsed:.2f}s: {e}")
        return

    # Confirm session is alive
    try:
        print("\n[step 2] cl.get_timeline_feed()")
        t1 = time.perf_counter()
        feed = cl.get_timeline_feed()
        print(f"[OK] timeline_feed in {time.perf_counter()-t1:.2f}s  items={len(feed.get('feed_items', []))}")
    except Exception as e:
        print(f"[ERR] timeline_feed: {type(e).__name__}: {e}")

    # Persist session for future runs
    cl.dump_settings(session_file)
    print(f"\n[saved] session → {session_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test Instagram login")
    parser.add_argument("--username", "-u", help="Instagram username (overrides accounts.json)")
    parser.add_argument("--password", "-p", help="Instagram password")
    parser.add_argument("--totp",     "-t", help="TOTP secret (base32)")
    parser.add_argument("--proxy",          help="Proxy URL")
    args = parser.parse_args()

    # Manual credentials supplied via CLI — bypass accounts.json
    if args.username and args.password:
        import uuid
        meta = {
            "username":    args.username,
            "password":    args.password,
            "totp_secret": args.totp,
            "proxy":       args.proxy,
        }
        test_login(str(uuid.uuid4()), meta)
        return

    # Fall back to accounts.json
    accounts = load_accounts()
    if not accounts:
        print("[ERROR] accounts.json is empty — use --username / --password flags")
        sys.exit(1)

    print(f"Found {len(accounts)} account(s) in accounts.json")

    # Warn if credentials are missing
    missing = [v.get("username", aid) for aid, v in accounts.items() if not v.get("username") or not v.get("password")]
    if missing:
        print(f"[WARN] Missing credentials for: {missing}")
        print("       Use:  python3 _test.py -u <username> -p <password> [-t <totp_secret>]")

    for account_id, meta in accounts.items():
        if not meta.get("username") or not meta.get("password"):
            print(f"\n[SKIP] {account_id} — no username/password in accounts.json")
            continue
        test_login(account_id, meta)


if __name__ == "__main__":
    main()
