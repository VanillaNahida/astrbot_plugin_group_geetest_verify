"""Small, dependency-free helpers for bot group-role checks."""

from typing import Any, Callable, Optional


BOT_ADMIN_ROLES = frozenset({"admin", "owner"})


def should_check_bot_group_role(platform: str) -> bool:
    """Return whether automatic bot-role checking applies to this platform."""
    return platform == "aiocqhttp"


def normalize_group_member_role(result: Any) -> Optional[str]:
    """Extract and normalize a role from direct or nested OneBot responses."""
    if not isinstance(result, dict):
        return None

    payload = result
    data = result.get("data")
    if isinstance(data, dict):
        payload = data

    role = payload.get("role")
    if role is None:
        return None

    normalized = str(role).strip().lower()
    return normalized or None


def role_allows_verification(role: Optional[str]) -> Optional[bool]:
    """Map a known role to allow/skip; None means the role is unknown."""
    if role is None:
        return None
    return role in BOT_ADMIN_ROLES


async def query_current_bot_group_role(
    event: Any,
    group_id: int,
    raw_getter: Callable[[Any, str, Any], Any],
) -> Optional[str]:
    """Query the role of the bot bound to an event's OneBot API client.

    Missing identifiers or role fields return None. OneBot action failures
    propagate so the platform layer can log them before preserving the existing
    verification flow (fail-open).
    """
    get_self_id = getattr(event, "get_self_id", None)
    self_id = get_self_id() if callable(get_self_id) else None

    if self_id in (None, ""):
        raw = getattr(getattr(event, "message_obj", None), "raw_message", None)
        self_id = raw_getter(raw, "self_id", None)

    if self_id in (None, ""):
        return None

    bot_id = int(self_id)
    bot = getattr(event, "bot", None)
    call_action = getattr(bot, "call_action", None)
    if not callable(call_action):
        api = getattr(bot, "api", None)
        call_action = getattr(api, "call_action", None)
    if not callable(call_action):
        raise RuntimeError("event-bound OneBot API client is unavailable")

    result = await call_action(
        "get_group_member_info",
        self_id=bot_id,
        group_id=int(group_id),
        user_id=bot_id,
    )
    return normalize_group_member_role(result)
