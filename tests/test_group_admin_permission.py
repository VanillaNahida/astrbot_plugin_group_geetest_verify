import unittest
from types import SimpleNamespace

from core.permissions import (
    normalize_group_member_role,
    query_current_bot_group_role,
    role_allows_verification,
    should_check_bot_group_role,
)


_UNSET = object()


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


def make_event(
    raw,
    api=None,
    *,
    event_self_id=_UNSET,
    use_api_property=False,
):
    bot = SimpleNamespace(api=api) if use_api_property else api
    event = SimpleNamespace(
        message_obj=SimpleNamespace(raw_message=raw),
        bot=bot,
    )
    if event_self_id is not _UNSET:
        event.get_self_id = lambda: event_self_id
    return event


class GroupAdminPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_role_prefers_event_self_id_and_routes_bound_bot(self):
        api = FakeAPI({"role": " ADMIN "})
        event = make_event(
            {"self_id": "99999"},
            api,
            event_self_id="10001",
        )

        role = await query_current_bot_group_role(event, 123, raw_getter)

        self.assertEqual(role, "admin")
        self.assertEqual(
            api.calls,
            [
                (
                    "get_group_member_info",
                    {
                        "self_id": 10001,
                        "group_id": 123,
                        "user_id": 10001,
                    },
                )
            ],
        )

    async def test_api_property_fallback_supports_nested_owner_role(self):
        api = FakeAPI({"status": "ok", "data": {"role": "owner"}})
        event = make_event(
            {},
            api,
            event_self_id=10002,
            use_api_property=True,
        )

        role = await query_current_bot_group_role(event, 456, raw_getter)

        self.assertEqual(role, "owner")
        self.assertTrue(role_allows_verification(role))
        self.assertEqual(api.calls[0][1]["self_id"], 10002)

    async def test_raw_self_id_fallback_is_supported(self):
        api = FakeAPI({"role": "admin"})
        event = make_event({"self_id": "10003"}, api)

        role = await query_current_bot_group_role(event, 123, raw_getter)

        self.assertEqual(role, "admin")
        self.assertEqual(api.calls[0][1]["user_id"], 10003)

    async def test_api_exception_propagates_to_platform_layer(self):
        api = FakeAPI(error=RuntimeError("api unavailable"))
        event = make_event({}, api, event_self_id=10001)

        with self.assertRaisesRegex(RuntimeError, "api unavailable"):
            await query_current_bot_group_role(event, 123, raw_getter)

    async def test_missing_self_id_or_role_is_unknown(self):
        missing_id_api = FakeAPI({"role": "admin"})
        missing_id_event = make_event({}, missing_id_api, event_self_id="")
        self.assertIsNone(
            await query_current_bot_group_role(missing_id_event, 123, raw_getter)
        )
        self.assertEqual(missing_id_api.calls, [])

        missing_role_api = FakeAPI({"status": "ok", "data": {}})
        missing_role_event = make_event(
            {},
            missing_role_api,
            event_self_id=10001,
        )
        self.assertIsNone(
            await query_current_bot_group_role(missing_role_event, 123, raw_getter)
        )

    async def test_missing_event_bound_client_raises(self):
        event = make_event({}, None, event_self_id=10001)

        with self.assertRaisesRegex(
            RuntimeError,
            "event-bound OneBot API client is unavailable",
        ):
            await query_current_bot_group_role(event, 123, raw_getter)

    def test_member_role_is_explicitly_skipped(self):
        self.assertEqual(
            normalize_group_member_role({"data": {"role": "member"}}),
            "member",
        )
        self.assertFalse(role_allows_verification("member"))

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
