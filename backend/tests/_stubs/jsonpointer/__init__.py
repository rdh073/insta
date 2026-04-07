"""Minimal jsonpointer stub for langsmith pytest plugin."""

class JsonPointerException(Exception):
    pass

class JsonPointer:
    def __init__(self, pointer):
        self.pointer = pointer
    def resolve(self, doc):
        return doc
