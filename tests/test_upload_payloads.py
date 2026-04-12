from __future__ import annotations

import pytest

from instagram_runtime.upload_payloads import _dispatch_upload


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def photo_upload(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


def test_dispatch_upload_rejects_empty_media_paths() -> None:
    client = _StubClient()

    with pytest.raises(ValueError, match="media"):
        _dispatch_upload(
            client,
            "photo",
            [],
            "caption",
            None,
            None,
            [],
            None,
            {},
        )

    assert client.calls == []


def test_dispatch_upload_ignores_blank_media_paths() -> None:
    client = _StubClient()

    _dispatch_upload(
        client,
        "photo",
        ["", "   ", "/tmp/ready.jpg"],
        "caption",
        None,
        None,
        [],
        None,
        {},
    )

    assert len(client.calls) == 1
    uploaded_path = client.calls[0][0][0]
    assert str(uploaded_path) == "/tmp/ready.jpg"
