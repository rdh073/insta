"""Instagram HTTP response mappers."""

from __future__ import annotations


def _to_public_profile(item) -> dict:
    return {
        "pk": item.pk,
        "username": item.username,
        "fullName": item.full_name,
        "biography": item.biography,
        "profilePicUrl": item.profile_pic_url,
        "followerCount": item.follower_count,
        "followingCount": item.following_count,
        "mediaCount": item.media_count,
        "isPrivate": item.is_private,
        "isVerified": item.is_verified,
        "isBusiness": item.is_business,
    }


def _to_media(m) -> dict:
    return {
        "pk": m.pk,
        "mediaId": m.media_id,
        "code": m.code,
        "owner": m.owner_username,
        "captionText": m.caption_text,
        "likeCount": m.like_count,
        "commentCount": m.comment_count,
        "mediaType": m.media_type,
        "productType": m.product_type,
        "takenAt": m.taken_at.isoformat() if m.taken_at else None,
        "resources": [_to_resource(r) for r in m.resources],
    }


def _to_resource(r) -> dict:
    return {
        "pk": r.pk,
        "mediaType": r.media_type,
        "thumbnailUrl": r.thumbnail_url,
        "videoUrl": r.video_url,
    }


def _to_oembed(o) -> dict:
    return {
        "mediaId": o.media_id,
        "authorName": o.author_name,
        "authorUrl": o.author_url,
        "authorId": o.author_id,
        "title": o.title,
        "providerName": o.provider_name,
        "html": o.html,
        "thumbnailUrl": o.thumbnail_url,
        "width": o.width,
        "height": o.height,
        "canView": o.can_view,
    }


def _to_story_summary(s) -> dict:
    return {
        "pk": s.pk,
        "storyId": s.story_id,
        "mediaType": s.media_type,
        "takenAt": s.taken_at.isoformat() if s.taken_at else None,
        "thumbnailUrl": s.thumbnail_url,
        "videoUrl": s.video_url,
        "viewerCount": s.viewer_count,
        "ownerUsername": s.owner_username,
    }


def _to_story_detail(s) -> dict:
    return {
        "summary": _to_story_summary(s.summary),
        "linkCount": s.link_count,
        "mentionCount": s.mention_count,
        "hashtagCount": s.hashtag_count,
        "locationCount": s.location_count,
        "stickerCount": s.sticker_count,
    }


def _to_story_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_comment(c) -> dict:
    return {
        "pk": c.pk,
        "text": c.text,
        "author": c.author.username,
        "likeCount": c.like_count,
        "hasLiked": c.has_liked,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


def _to_comment_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_direct_participant(p) -> dict:
    return {
        "userId": p.user_id,
        "username": p.username,
        "fullName": p.full_name,
        "profilePicUrl": p.profile_pic_url,
        "isPrivate": p.is_private,
    }


def _to_direct_search_user(u) -> dict:
    return {
        "userId": u.user_id,
        "username": u.username,
        "fullName": u.full_name,
        "profilePicUrl": u.profile_pic_url,
        "isPrivate": u.is_private,
        "isVerified": u.is_verified,
    }


def _to_direct_message(m) -> dict:
    return {
        "directMessageId": m.direct_message_id,
        "directThreadId": m.direct_thread_id,
        "senderUserId": m.sender_user_id,
        "sentAt": m.sent_at.isoformat() if m.sent_at else None,
        "itemType": m.item_type,
        "text": m.text,
        "isShhMode": m.is_shh_mode,
    }


def _to_direct_thread_summary(t) -> dict:
    return {
        "directThreadId": t.direct_thread_id,
        "pk": t.pk,
        "participants": [_to_direct_participant(p) for p in t.participants],
        "lastMessage": _to_direct_message(t.last_message) if t.last_message else None,
        "isPending": t.is_pending,
    }


def _to_direct_thread_detail(t) -> dict:
    return {
        "summary": _to_direct_thread_summary(t.summary),
        "messages": [_to_direct_message(m) for m in t.messages],
    }


def _to_direct_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_highlight_cover(c) -> dict | None:
    if c is None:
        return None
    return {
        "mediaId": c.media_id,
        "imageUrl": c.image_url,
        "cropRect": c.crop_rect,
    }


def _to_highlight_summary(h) -> dict:
    return {
        "pk": h.pk,
        "highlightId": h.highlight_id,
        "title": h.title,
        "createdAt": h.created_at.isoformat() if h.created_at else None,
        "isPinned": h.is_pinned,
        "mediaCount": h.media_count,
        "latestReelMedia": h.latest_reel_media,
        "ownerUsername": h.owner_username,
        "cover": _to_highlight_cover(h.cover),
    }


def _to_highlight_detail(h) -> dict:
    return {
        "summary": _to_highlight_summary(h.summary),
        "storyIds": h.story_ids,
        "items": [_to_story_summary(s) for s in h.items],
    }


def _to_highlight_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_insight(i) -> dict:
    return {
        "mediaPk": i.media_pk,
        "reachCount": i.reach_count,
        "impressionCount": i.impression_count,
        "likeCount": i.like_count,
        "commentCount": i.comment_count,
        "shareCount": i.share_count,
        "saveCount": i.save_count,
        "videoViewCount": i.video_view_count,
        "extraMetrics": i.extra_metrics,
    }
