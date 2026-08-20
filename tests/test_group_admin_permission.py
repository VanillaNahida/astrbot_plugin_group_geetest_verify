import unittest
from types import SimpleNamespace

from core.permissions import (
    normalize_group_member_role,
    query_current_bot_group_role,
    role_allows_verification,
    should_check_bot_group_role,
)


class FakeAPI:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def call_action(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def raw_getter(raw, key, default=None):
    if isinstance(raw, dict):
        return raw.get(key, default)
    return getattr(raw, key, default)


def make_event(raw, api):
    return SimpleNamespace(
        message_obj=SimpleNamespace(raw_message=raw),
        bot=SimpleNamespace(api=api),
    )


class GroupAdminPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_role_uses_event_bound_api(self):
        api = FakeAPI({"role": " ADMIN "})
        event = make_event({"self_id": "10001"}, api)

        role = await query_current_bot_group_role(event, 123, raw_getter)

        self.assertEqual(role, "admin")
        self.assertEqual(
            api.calls,
            [("get_group_member_info", {"group_id": 123, "user_id": 10001})],
        )

    async def test_nested_owner_role_is_allowed(self):
        api = FakeAPI({"status": "ok", "data": {"role": "owner"}})
        event = make_event({"self_id": 10001}, api)

        role = await query_current_bot_group_role(event, 456, raw_getter)

        self.assertEqual(role, "owner")
        self.assertTrue(role_allows_verification(role))

    async def test_member_role_is_explicitly_skipped(self):
        self.assertEqual(normalize_group_member_role({"data": {"role": "member"}}), "member")
        self.assertFalse(role_allows_verification("member"))

    async def test_api_exception_is_fail_open(self):
        api = FakeAPI(error=RuntimeError("api unavailable"))
        event = make_event({"self_id": 10001}, api)

        role = await query_current_bot_group_role(event, 123, raw_getter)

        self.assertIsNone(role)
        self.assertIsNone(role_allows_verification(role))

    async def test_missing_self_id_or_role_is_unknown(self):
        missing_id_api = FakeAPI({"role": "admin"})
        missing_id_event = make_event({}, missing_id_api)
        self.assertIsNone(
            await query_current_bot_group_role(missing_id_event, 123, raw_getter)
        )
        self.assertEqual(missing_id_api.calls, [])

        missing_role_api = FakeAPI({"status": "ok", "data": {}})
        missing_role_event = make_event({"self_id": 10001}, missing_role_api)
        self.assertIsNone(
            await query_current_bot_group_role(missing_role_event, 123, raw_getter)
        )

    async def test_event_self_id_fallback_is_supported(self):
        api = FakeAPI({"role": "owner"})
        event = make_event({}, api)
        event.get_self_id = lambda: "10002"

        role = await query_current_bot_group_role(event, 123, raw_getter)

        self.assertEqual(role, "owner")
        self.assertEqual(api.calls[0][1]["user_id"], 10002)

    def test_role_check_is_limited_to_qq(self):
        self.assertTrue(should_check_bot_group_role("aiocqhttp"))
        self.assertFalse(should_check_bot_group_role("telegram"))
        self.assertFalse(should_check_bot_group_role("unsupported"))

    def test_role_allowlist(self):
        self.assertTrue(role_allows_verification("admin"))
        self.assertTrue(role_allows_verification("owner"))
        self.assertFalse(role_allows_verification("member"))
        self.assertIsNone(role_allows_verification(None))


if __name__ == "__main__":
    unittest.main()
