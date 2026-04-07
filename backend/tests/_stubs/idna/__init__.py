"""Minimal idna stub so httpx imports don't crash during test collection."""

def encode(s, *a, **kw):
    return s.encode("ascii")

def decode(s, *a, **kw):
    return s if isinstance(s, str) else s.decode("ascii")

class core:
    @staticmethod
    def encode(s, *a, **kw):
        return s.encode("ascii")
    @staticmethod
    def decode(s, *a, **kw):
        return s if isinstance(s, str) else s.decode("ascii")
