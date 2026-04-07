# Minimal idna stub to satisfy httpx import during pytest plugin loading
def encode(s, *a, **kw):
    return s.encode("ascii")

def decode(s, *a, **kw):
    return s if isinstance(s, str) else s.decode("ascii")

class core:
    @staticmethod
    def encode(s, *a, **kw):
        return s.encode("ascii")
