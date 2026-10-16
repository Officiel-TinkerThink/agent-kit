"""Route handlers for lab operator profiles."""

import logging

from auth import require_auth
from config import PAGE_SIZE_DEFAULT, page_size
from names import ProfileNameError, normalise_for_lookup

log = logging.getLogger("profiles.routes")

PROFILE_INDEX = {}


@require_auth
def get_profile(request):
    """Return the profile stored under the lookup key in the query string."""
    try:
        key = normalise_for_lookup(request.params.get("name", ""))
    except ProfileNameError as exc:
        log.info("lookup rejected: %s", exc)
        return {"status": 400, "body": {"error": str(exc)}}
    profile = PROFILE_INDEX.get(key)
    if profile is None:
        return {"status": 404, "body": {"error": "not found"}}
    return {"status": 200, "body": profile}


@require_auth
def list_profiles(request):
    """Return one page of stored profiles, ordered by lookup key."""
    limit = page_size(int(request.params.get("limit", PAGE_SIZE_DEFAULT)))
    keys = sorted(PROFILE_INDEX)[:limit]
    return {"status": 200, "body": [PROFILE_INDEX[k] for k in keys]}


@require_auth
def count_profiles(request):
    """Return the number of stored profiles."""
    return {"status": 200, "body": {"count": profile_count()}}


@require_auth
def delete_profile(request):
    """Remove the profile stored under the lookup key and confirm the removal."""
    try:
        key = normalise_for_lookup(request.params.get("name", ""))
    except ProfileNameError as exc:
        return {"status": 400, "body": {"error": str(exc)}}
    if PROFILE_INDEX.pop(key, None) is None:
        return {"status": 404, "body": {"error": "not found"}}
    log.info("profile removed: %s", key)
    return {"status": 200, "body": {"removed": key}}


def profile_count() -> int:
    """Return the number of stored profiles."""
    return len(PROFILE_INDEX)


ROUTES = {
    "get_profile": get_profile,
    "list_profiles": list_profiles,
    "count_profiles": count_profiles,
    "delete_profile": delete_profile,
}
