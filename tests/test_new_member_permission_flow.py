import importlib
import logging
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = REPO_ROOT.name


def _install_runtime_stubs():
    try:
        importlib.import_module("aiohttp")
    except ModuleNotFoundError:
        aiohttp = ModuleType("aiohttp")
        aiohttp.ClientSession = object
        aiohttp.ClientError = Exception
        sys.modules.setdefault("aiohttp", aiohttp)

    try:
        importlib.import_module("aiosqlite")
    except ModuleNotFoundError:
        aiosqlite = ModuleType("aiosqlite")
        aiosqlite.Connection = object
        aiosqlite.Row = object
        sys.modules.setdefault("aiosqlite", aiosqlite)

    try:
        importlib.import_module("astrbot.api.event")
        importlib.import_module("astrbot.api.star")
        importlib.import_module("astrbot.core.config.default")
        return
    except ModuleNotFoundError:
        pass

    astrbot = ModuleType("astrbot")
    astrbot.__path__ = []
    astrbot_api = ModuleType("astrbot.api")
    astrbot_api.__path__ = []
    astrbot_event = ModuleType("astrbot.api.event")
    astrbot_star = ModuleType("astrbot.api.star")
    astrbot_core = ModuleType("astrbot.core")
    astrbot_core.__path__ = []
    astrbot_config = ModuleType("astrbot.core.config")
    astrbot_config.__path__ = []
    astrbot_default = ModuleType("astrbot.core.config.default")

    class EventMessageType:
        GROUP_MESSAGE = "GROUP_MESSAGE"

    class Filter:
        @staticmethod
        def event_message_type(*args, **kwargs):
            return lambda func: func

        @staticmethod
        def command(*args, **kwargs):
            return lambda func: func

    Filter.EventMessageType = EventMessageType

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context=None):
            self.context = context

    class StarTools:
        @staticmethod
        def get_data_dir(_name):
            return REPO_ROOT / ".test-data"

    def register(*args, **kwargs):
        return lambda cls: cls

    logger = logging.getLogger("astrbot-test")
    astrbot_api.logger = logger
    astrbot_api.AstrBotConfig = dict
    astrbot_event.filter = Filter()
    astrbot_event.AstrMessageEvent = AstrMessageEvent
    astrbot_star.Context = Context
    astrbot_star.Star = Star
    astrbot_star.StarTools = StarTools
    astrbot_star.register = register
    astrbot_default.VERSION = "test"

    astrbot.api = astrbot_api
    astrbot.core = astrbot_core
    astrbot_api.event = astrbot_event
    astrbot_api.star = astrbot_star
    astrbot_core.config = astrbot_config
    astrbot_config.default = astrbot_default

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api
    sys.modules["astrbot.api.event"] = astrbot_event
    sys.modules["astrbot.api.star"] = astrbot_star
    sys.modules["astrbot.core"] = astrbot_core
    sys.modules["astrbot.core.config"] = astrbot_config
    sys.modules["astrbot.core.config.default"] = astrbot_default


_install_runtime_stubs()
sys.path.insert(0, str(REPO_ROOT.parent))

plugin_main = importlib.import_module(f"{PACKAGE_NAME}.main")
platform_module = importlib.import_module(f"{PACKAGE_NAME}.platform.platform")
Plugin = plugin_main.GroupGeetestVerifyPlugin


def make_event(raw):
    return SimpleNamespace(
        message_obj=SimpleNamespace(raw_message=raw),
        bot=SimpleNamespace(),
    )


def build_plugin(platform="aiocqhttp", role_result=True, enabled=True):
    plugin = object.__new__(Plugin)
    group_config = {
        "enabled": enabled,
        "enable_level_verify": False,
        "min_qq_level": 20,
        "verify_delay": 0,
        "verification_timeout": 300,
    }

    plugin._tasks = {}
    plugin._get_platform = Mock(return_value=platform)
    plugin._get_group_id = Mock(return_value=123)
    plugin._get_group_config = Mock(return_value=group_config)
    plugin._is_current_bot_group_admin = AsyncMock(return_value=role_result)
    plugin._generate_math_problem = Mock(return_value=("1 + 1 = ?", 2))
    plugin._format_user_mention = Mock(return_value="[CQ:at,qq=20001]")
    plugin._get_user_level = AsyncMock(return_value=0)
    plugin._send_group_message = AsyncMock()
    plugin._start_verification_process = AsyncMock()
    plugin.db = SimpleNamespace(
        get_cached=Mock(return_value=None),
        set=AsyncMock(),
    )
    return plugin


class NewMemberPermissionFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_group_does_not_query_bot_role(self):
        plugin = build_plugin(enabled=False)
        event = make_event({"group_id": 123, "user_id": 20001})

        await plugin._process_new_member(event)

        plugin._is_current_bot_group_admin.assert_not_awaited()
        plugin.db.get_cached.assert_not_called()
        plugin._start_verification_process.assert_not_awaited()

    async def test_member_bot_returns_before_any_verification_side_effect(self):
        plugin = build_plugin(role_result=False)
        event = make_event({"group_id": 123, "user_id": 20001})

        await plugin._process_new_member(event)

        plugin._is_current_bot_group_admin.assert_awaited_once_with(event, 123)
        plugin.db.get_cached.assert_not_called()
        plugin._get_user_level.assert_not_awaited()
        plugin._send_group_message.assert_not_awaited()
        plugin._start_verification_process.assert_not_awaited()
        self.assertEqual(plugin._tasks, {})

    async def test_admin_bot_reaches_existing_verification_flow(self):
        plugin = build_plugin(role_result=True)
        event = make_event({"group_id": 123, "user_id": 20001})

        with patch.object(plugin_main.asyncio, "sleep", new=AsyncMock()):
            await plugin._process_new_member(event)

        plugin.db.get_cached.assert_called_once_with("123:20001")
        plugin._start_verification_process.assert_awaited_once()
        self.assertEqual(
            plugin._start_verification_process.await_args.args[:3],
            (event, "20001", 123),
        )

    async def test_unknown_role_is_fail_open(self):
        plugin = build_plugin(role_result=None)
        event = make_event({"group_id": 123, "user_id": 20001})

        with patch.object(plugin_main.asyncio, "sleep", new=AsyncMock()):
            await plugin._process_new_member(event)

        plugin._start_verification_process.assert_awaited_once()

    async def test_telegram_does_not_query_qq_role(self):
        plugin = build_plugin(platform="telegram", role_result=False)
        event = make_event({"new_chat_members": [{"id": 20001}]})

        with patch.object(plugin_main.asyncio, "sleep", new=AsyncMock()):
            await plugin._process_new_member(event)

        plugin._is_current_bot_group_admin.assert_not_awaited()
        plugin._start_verification_process.assert_awaited_once()

    async def test_member_and_admin_pair_only_admin_starts(self):
        plugin = build_plugin()
        plugin._is_current_bot_group_admin.side_effect = [False, True]
        event_a = make_event({"group_id": 123, "user_id": 20001})
        event_b = make_event({"group_id": 123, "user_id": 20001})

        with patch.object(plugin_main.asyncio, "sleep", new=AsyncMock()):
            await plugin._process_new_member(event_a)
            await plugin._process_new_member(event_b)

        self.assertEqual(plugin._start_verification_process.await_count, 1)

    async def test_two_admin_bots_are_not_deduplicated_by_this_change(self):
        plugin = build_plugin()
        plugin._is_current_bot_group_admin.side_effect = [True, True]
        event_a = make_event({"group_id": 123, "user_id": 20001})
        event_b = make_event({"group_id": 123, "user_id": 20001})

        with patch.object(plugin_main.asyncio, "sleep", new=AsyncMock()):
            await plugin._process_new_member(event_a)
            await plugin._process_new_member(event_b)

        self.assertEqual(plugin._start_verification_process.await_count, 2)

    async def test_platform_layer_logs_api_failure_and_fails_open(self):
        plugin = build_plugin()
        del plugin._is_current_bot_group_admin
        event = make_event({"group_id": 123, "self_id": 10001})

        with patch.object(
            platform_module,
            "query_current_bot_group_role",
            new=AsyncMock(side_effect=RuntimeError("api unavailable")),
        ):
            with self.assertLogs(platform_module.logger, level="WARNING") as logs:
                result = await plugin._is_current_bot_group_admin(event, 123)

        self.assertIsNone(result)
        self.assertTrue(any("RuntimeError" in message for message in logs.output))


if __name__ == "__main__":
    unittest.main()
