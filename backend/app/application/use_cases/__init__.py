"""Use cases - application-level orchestration of workflows."""

__all__ = [
    "AccountUseCases",
    "PostJobUseCases",
    "IdentityUseCases",
    "RelationshipUseCases",
    "MediaUseCases",
    "HashtagUseCases",
    "CollectionUseCases",
    "InsightUseCases",
    "StoryUseCases",
    "HighlightUseCases",
    "CommentUseCases",
    "DirectUseCases",
]


def __getattr__(name: str):
    """Lazy-load use case classes to avoid heavy import side effects."""
    if name == "AccountUseCases":
        from .account import AccountUseCases

        return AccountUseCases
    if name == "PostJobUseCases":
        from .post_job import PostJobUseCases

        return PostJobUseCases
    if name == "IdentityUseCases":
        from .identity import IdentityUseCases

        return IdentityUseCases
    if name == "RelationshipUseCases":
        from .relationships import RelationshipUseCases

        return RelationshipUseCases
    if name == "MediaUseCases":
        from .media import MediaUseCases

        return MediaUseCases
    if name == "HashtagUseCases":
        from .hashtag import HashtagUseCases

        return HashtagUseCases
    if name == "CollectionUseCases":
        from .collection import CollectionUseCases

        return CollectionUseCases
    if name == "InsightUseCases":
        from .insight import InsightUseCases

        return InsightUseCases
    if name == "StoryUseCases":
        from .story import StoryUseCases

        return StoryUseCases
    if name == "HighlightUseCases":
        from .highlight import HighlightUseCases

        return HighlightUseCases
    if name == "CommentUseCases":
        from .comment import CommentUseCases

        return CommentUseCases
    if name == "DirectUseCases":
        from .direct import DirectUseCases

        return DirectUseCases
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
