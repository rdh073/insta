"""
Android device pool for instagrapi client fingerprint diversification.

Each entry supplies the full dict that instagrapi's set_device() + set_user_agent()
accept. Covering a wide spread of manufacturers, chipsets, resolutions, and Android
versions reduces the chance that all managed accounts share an identical fingerprint.

Usage:
    from app.adapters.instagram.device_pool import random_device_profile
    device, user_agent = random_device_profile()
    cl.set_device(device)
    cl.set_user_agent(user_agent)
"""

from __future__ import annotations

import random

# App version used in user-agent strings.
# Matches instagrapi APP_SETTINGS entries.
_APP_VERSION = "364.0.0.35.86"
_VERSION_CODE = "374010953"

# Template matches instagrapi config.USER_AGENT_BASE
_UA_TEMPLATE = (
    "Instagram {app_version} "
    "Android ({android_version}/{android_release}; "
    "{dpi}; {resolution}; {manufacturer}; "
    "{model}; {device}; {cpu}; {locale}; {version_code})"
)

# device_settings keys mirror instagrapi DEVICE_SETTINGS
_DEVICES: list[dict] = [
    # ── Samsung ──────────────────────────────────────────────────────────────
    {
        "manufacturer": "Samsung",
        "model": "SM-G991B",
        "device": "o1s",
        "cpu": "exynos2100",
        "dpi": "480dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-G973F",
        "device": "beyond1",
        "cpu": "exynos9820",
        "dpi": "550dpi",
        "resolution": "1440x3040",
        "android_version": 31,
        "android_release": "12",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-A546B",
        "device": "a54x",
        "cpu": "exynos1380",
        "dpi": "400dpi",
        "resolution": "1080x2340",
        "android_version": 33,
        "android_release": "13",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-A325F",
        "device": "a32",
        "cpu": "mt6853",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 30,
        "android_release": "11",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-S908B",
        "device": "b0q",
        "cpu": "exynos2200",
        "dpi": "500dpi",
        "resolution": "1440x3088",
        "android_version": 33,
        "android_release": "13",
    },
    # ── Xiaomi ───────────────────────────────────────────────────────────────
    {
        "manufacturer": "Xiaomi",
        "model": "2201123G",
        "device": "zeus",
        "cpu": "qcom",
        "dpi": "440dpi",
        "resolution": "1080x2400",
        "android_version": 32,
        "android_release": "12L",
    },
    {
        "manufacturer": "Xiaomi",
        "model": "M2102J20SG",
        "device": "umi",
        "cpu": "qcom",
        "dpi": "395dpi",
        "resolution": "1080x2340",
        "android_version": 31,
        "android_release": "12",
    },
    {
        "manufacturer": "Xiaomi",
        "model": "220233L2G",
        "device": "psyche",
        "cpu": "mt6877",
        "dpi": "395dpi",
        "resolution": "1080x2400",
        "android_version": 32,
        "android_release": "12",
    },
    {
        "manufacturer": "Xiaomi",
        "model": "21091116AG",
        "device": "lisa",
        "cpu": "qcom",
        "dpi": "395dpi",
        "resolution": "1080x2400",
        "android_version": 31,
        "android_release": "12",
    },
    # ── Redmi ────────────────────────────────────────────────────────────────
    {
        "manufacturer": "Redmi",
        "model": "22111317G",
        "device": "tapas",
        "cpu": "mt6877",
        "dpi": "395dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    {
        "manufacturer": "Redmi",
        "model": "21121119SG",
        "device": "selene",
        "cpu": "mt6768",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 30,
        "android_release": "11",
    },
    # ── POCO ─────────────────────────────────────────────────────────────────
    {
        "manufacturer": "POCO",
        "model": "M2102J20SG",
        "device": "cas",
        "cpu": "qcom",
        "dpi": "395dpi",
        "resolution": "1080x2400",
        "android_version": 31,
        "android_release": "12",
    },
    # ── Google Pixel ─────────────────────────────────────────────────────────
    {
        "manufacturer": "Google",
        "model": "Pixel 7",
        "device": "panther",
        "cpu": "tensor",
        "dpi": "420dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 6a",
        "device": "bluejay",
        "cpu": "tensor",
        "dpi": "429dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 5",
        "device": "redfin",
        "cpu": "qcom",
        "dpi": "440dpi",
        "resolution": "1080x2340",
        "android_version": 32,
        "android_release": "12",
    },
    # ── Realme ───────────────────────────────────────────────────────────────
    {
        "manufacturer": "realme",
        "model": "RMX3085",
        "device": "RMX3085",
        "cpu": "mt6893",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 30,
        "android_release": "11",
    },
    {
        "manufacturer": "realme",
        "model": "RMX3761",
        "device": "RMX3761",
        "cpu": "mt6877",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    # ── OPPO ─────────────────────────────────────────────────────────────────
    {
        "manufacturer": "OPPO",
        "model": "CPH2387",
        "device": "OP5913L1",
        "cpu": "mt6877",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 33,
        "android_release": "13",
    },
    # ── Vivo ─────────────────────────────────────────────────────────────────
    {
        "manufacturer": "vivo",
        "model": "V2109",
        "device": "V2109",
        "cpu": "mt6891",
        "dpi": "400dpi",
        "resolution": "1080x2408",
        "android_version": 31,
        "android_release": "12",
    },
    # ── Sony ─────────────────────────────────────────────────────────────────
    {
        "manufacturer": "Sony",
        "model": "XQ-BC72",
        "device": "pdx203",
        "cpu": "qcom",
        "dpi": "441dpi",
        "resolution": "1080x2520",
        "android_version": 32,
        "android_release": "12",
    },
    # ── Motorola ─────────────────────────────────────────────────────────────
    {
        "manufacturer": "motorola",
        "model": "moto g82 5G",
        "device": "rhodep",
        "cpu": "qcom",
        "dpi": "400dpi",
        "resolution": "1080x2400",
        "android_version": 32,
        "android_release": "12",
    },
    # ── OnePlus (kept in pool, no longer the exclusive default) ──────────────
    {
        "manufacturer": "OnePlus",
        "model": "IN2023",
        "device": "OnePlus8Pro",
        "cpu": "qcom",
        "dpi": "513dpi",
        "resolution": "1440x3168",
        "android_version": 31,
        "android_release": "12",
    },
]


def random_device_profile(locale: str = "en_US") -> tuple[dict, str]:
    """Return a random (device_settings, user_agent) pair.

    Args:
        locale: IETF locale tag to embed in the user-agent string.
                Should match the proxy's country for anti-detection.

    Returns:
        Tuple of (device_settings dict, user_agent string) ready for
        ``cl.set_device()`` and ``cl.set_user_agent()``.
    """
    device = dict(random.choice(_DEVICES))  # shallow copy so callers can mutate
    user_agent = _UA_TEMPLATE.format(
        app_version=_APP_VERSION,
        version_code=_VERSION_CODE,
        locale=locale,
        **device,
    )
    return device, user_agent
